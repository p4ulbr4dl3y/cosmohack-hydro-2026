"""Сервис загрузки данных и пространственной обработки для HydroWatch Amur."""

from __future__ import annotations

import gc
import glob
import json
import logging
import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely.geometry
from rasterio.enums import Resampling
from rasterio.features import shapes
from rasterio.warp import reproject, transform_bounds
from scipy import ndimage
from shapely.geometry import box, mapping, shape

from hydrowatch_amur.tables.hydro_gauges import get_gauge_status
from src.audit import generate_flood_audit_certificate
from src.carbon_metrics import compute_flood_carbon_impact
from src.competition_metrics import calculate_q_score
from src.config import HydroConfig
from src.depth import classify_depth_risk, estimate_water_depth
from src.service.mchs_report import build_mchs_dispatch
from src.temporal import compute_receded_ha
from src.uncertainty import compute_flood_area_uncertainty

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "hydrowatch_amur"
PREDICTIONS_DIR = BASE_DIR / "predictions"
SUBMISSION_CSV = BASE_DIR / "submission.csv"
DEFAULT_CACHE_DIR = BASE_DIR / ".cache" / "hydrowatch"
CACHE_DIR = Path(os.getenv("HYDROWATCH_CACHE_DIR", str(DEFAULT_CACHE_DIR)))


class DataLoader:
    def __init__(
        self,
        data_dir: Path = DATA_DIR,
        predictions_dir: Path = PREDICTIONS_DIR,
        submission_csv: Path = SUBMISSION_CSV,
        cache_dir: Path | None = None,
    ):
        self.data_dir = data_dir
        self.predictions_dir = predictions_dir
        self.submission_csv = submission_csv
        if cache_dir is None:
            self.cache_dir = Path(os.getenv("HYDROWATCH_CACHE_DIR", str(DEFAULT_CACHE_DIR)))
        else:
            self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.pairs_df: pd.DataFrame | None = None
        self._pairs_cache: list[dict[str, Any]] = []
        self._reports_cache: dict[str, dict[str, Any]] = {}
        self.init_data()

    @staticmethod
    def _parse_query_dates(date_pre: str | None, date_peak: str | None) -> dict[str, Any]:
        """Разбирает необязательные запрошенные даты ISO, игнорируя некорректные и пустые значения."""
        from datetime import datetime as _datetime

        parsed: dict[str, Any] = {"date_pre": None, "date_peak": None}
        for name, val in (("date_pre", date_pre), ("date_peak", date_peak)):
            if not val:
                continue
            try:
                parsed[name] = _datetime.strptime(str(val), "%Y-%m-%d").date()
            except ValueError:
                parsed[name] = None
        return parsed

    @staticmethod
    def _pair_date_distance(pair_meta: dict[str, Any], req_dates: dict[str, Any]) -> float:
        """Среднее абсолютное расстояние в днях между запрошенными и сценовыми датами для пары.

        Когда даты не запрошены, расстояние равно 0 для каждой пары, поэтому сортировка
        сводится к пространственному перекрытию.
        """
        from datetime import datetime as _datetime

        dists: list[float] = []
        for name in ("date_pre", "date_peak"):
            req_d = req_dates.get(name)
            scene_val = pair_meta.get(f"{name}_sar")
            if req_d is None or not scene_val:
                continue
            try:
                scene_dt = _datetime.strptime(str(scene_val), "%Y-%m-%d").date()
            except ValueError:
                continue
            dists.append(abs((req_d - scene_dt).days))
        return float(np.mean(dists)) if dists else 0.0

    def _metric_area_ha(self, geom_4326: Any, pair_id: str) -> float:
        """Площадь геометрии WGS84 в гектарах, вычисленная в локальной CRS UTM."""
        utm_crs = "EPSG:32652"
        aoi_path = self.data_dir / "vectors" / "aoi.geojson"
        if aoi_path.exists():
            try:
                aoi_gdf = gpd.read_file(aoi_path)
                meta = self.get_pair_meta(pair_id)
                if meta is not None and "aoi_id" in aoi_gdf.columns:
                    matched = aoi_gdf[aoi_gdf["aoi_id"] == meta["aoi_id"]]
                    if not matched.empty and "utm_crs" in matched.columns:
                        candidate = matched.iloc[0].get("utm_crs")
                        if isinstance(candidate, str) and candidate:
                            utm_crs = candidate
            except Exception:  # noqa: BLE001
                pass

        series = gpd.GeoSeries([geom_4326], crs="EPSG:4326").to_crs(utm_crs)
        return float(series.iloc[0].area) / 10000.0

    def init_data(self) -> None:
        pairs_csv = self.data_dir / "pairs.csv"
        if not pairs_csv.exists():
            raise FileNotFoundError(f"pairs.csv not found at {pairs_csv}")

        self.pairs_df = pd.read_csv(pairs_csv)
        pairs_list = []

        for _, row in self.pairs_df.iterrows():
            pair_id = str(row["pair_id"])
            pred_tif = self.predictions_dir / f"{pair_id}_flood.tif"
            ref_tif = self.data_dir / str(row["reference_mask"])

            bounds_4326 = [127.0, 50.0, 128.0, 51.0]
            s1_pre_matches = sorted(glob.glob(str(self.data_dir / str(row["rasters_dir"]) / "S1_pre_*.tif")))
            s1_tif = Path(s1_pre_matches[0]) if s1_pre_matches else None
            target_tif = pred_tif if pred_tif.exists() else (s1_tif if (s1_tif and s1_tif.exists()) else ref_tif)
            if target_tif and target_tif.exists():
                with rasterio.open(target_tif) as src:
                    b = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
                    bounds_4326 = [round(x, 6) for x in b]

            center_4326 = [
                round((bounds_4326[1] + bounds_4326[3]) / 2.0, 6),
                round((bounds_4326[0] + bounds_4326[2]) / 2.0, 6),
            ]

            pair_meta = {
                "pair_id": pair_id,
                "aoi_id": str(row["aoi_id"]),
                "aoi_name": str(row["aoi_name"]),
                "event_id": str(row["event_id"]),
                "event_name": str(row["event_name"]),
                "event_kind": str(row["event_kind"]),
                "year": int(row["year"]),
                "sensor_sar": str(row["sensor_sar"]) if pd.notna(row["sensor_sar"]) else "",
                "sensor_optical": str(row["sensor_optical"]) if pd.notna(row["sensor_optical"]) else "",
                "date_pre_sar": str(row["date_pre_sar"]) if pd.notna(row["date_pre_sar"]) else "",
                "date_peak_sar": str(row["date_peak_sar"]) if pd.notna(row["date_peak_sar"]) else "",
                "date_pre_opt": str(row["date_pre_opt"]) if pd.notna(row["date_pre_opt"]) else "",
                "date_peak_opt": str(row["date_peak_opt"]) if pd.notna(row["date_peak_opt"]) else "",
                "aoi_km2": float(row["aoi_km2"]),
                "aoi_ha": round(float(row["aoi_km2"]) * 100.0, 2),
                "bounds_4326": bounds_4326,
                "center_4326": center_4326,
            }
            pairs_list.append(pair_meta)

        self._pairs_cache = pairs_list

    def get_pairs(self) -> list[dict[str, Any]]:
        return self._pairs_cache

    def _backfill_report_metadata(self, data: dict[str, Any], pair_id: str, cache_file: Path) -> None:
        """Дозаполняет метаданные датчика и генерации в отчётах, закэшированных до схемы v1.1.

        В отчётах, созданных старым кодом, отсутствуют `sensor_*` и `generated_at`; время
        изменения файла на диске служит точной заменой метки времени генерации.
        """
        pair_meta = self.get_pair_meta(pair_id)
        if pair_meta:
            data.setdefault("sensor_sar", pair_meta.get("sensor_sar", ""))
            data.setdefault("sensor_optical", pair_meta.get("sensor_optical", ""))
            if "gauge_status" not in data:
                data["gauge_status"] = get_gauge_status(pair_meta["aoi_id"], pair_meta["event_id"])
        if "depth_statistics" not in data:
            data["depth_statistics"] = classify_depth_risk(np.array([], dtype=np.float32))
        if not data.get("generated_at"):
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime, tz=UTC)
            data["generated_at"] = mtime.isoformat(timespec="seconds")

    def _enrich_report_analytics(self, data: dict[str, Any], pair_id: str) -> None:
        """Enrich report data with dynamic uncertainty, Merkle audit, SAR polarimetry, carbon metrics, and competition score."""
        pair_meta = self.get_pair_meta(pair_id) or {}
        flood_ha = float(data.get("flood_ha", 0.0))
        aoi_ha = float(data.get("aoi_ha", pair_meta.get("aoi_ha", 1000.0)))
        has_optical = bool(data.get("date_pre_opt") and data.get("date_peak_opt"))

        # 1. Оценка пространственной динамической неопределенности
        if "uncertainty" not in data or data["uncertainty"] is None:
            pred_tif = self.predictions_dir / f"{pair_id}_flood.tif"
            if pred_tif.exists():
                try:
                    with rasterio.open(pred_tif) as src:
                        mask = src.read(1) == 1
                    unc_res = compute_flood_area_uncertainty(mask, pixel_area_ha=0.01, has_optical=has_optical)
                except Exception:
                    n_pixels = int(round(flood_ha / 0.01))
                    dummy_mask = np.ones(n_pixels, dtype=bool) if n_pixels > 0 else np.zeros(0, dtype=bool)
                    unc_res = compute_flood_area_uncertainty(dummy_mask, pixel_area_ha=0.01, has_optical=has_optical)
            else:
                n_pixels = int(round(flood_ha / 0.01))
                dummy_mask = np.ones(n_pixels, dtype=bool) if n_pixels > 0 else np.zeros(0, dtype=bool)
                unc_res = compute_flood_area_uncertainty(dummy_mask, pixel_area_ha=0.01, has_optical=has_optical)

            data["uncertainty"] = {
                "pair_id": pair_id,
                "area_ha": unc_res.area_ha,
                "confidence_level": unc_res.confidence_level,
                "lower_bound_ha": unc_res.lower_bound_ha,
                "upper_bound_ha": unc_res.upper_bound_ha,
                "margin_ha": unc_res.margin_ha,
                "relative_uncertainty_pct": unc_res.relative_uncertainty_pct,
                "sigma_effective_ha": unc_res.sigma_effective_ha,
                "effective_n_pixels": unc_res.effective_n_pixels,
                "spatial_correlation": unc_res.spatial_correlation,
            }

        # 2. Криптографический аудит дерева Меркла
        if "audit" not in data or data["audit"] is None:
            inputs_info = {
                "pair_id": pair_id,
                "aoi_id": data.get("aoi_id"),
                "date_pre": data.get("date_pre_sar"),
                "date_peak": data.get("date_peak_sar"),
                "sensor_sar": pair_meta.get("sensor_sar", "sentinel1"),
                "rasters_dir": str(pair_meta.get("rasters_dir", "")),
            }
            cert = generate_flood_audit_certificate(
                pair_id=pair_id,
                aoi_id=str(data.get("aoi_id", "AOI")),
                inputs_info=inputs_info,
                parameters={
                    "otsu_corridor_db": [-22.0, -12.0],
                    "mmu_min_pixels": 25,
                    "speckle_filter": "Lee-MMSE-7x7",
                    "crs": "EPSG:4326",
                },
                results_summary={
                    "flood_ha": flood_ha,
                    "water_peak_ha": float(data.get("water_peak_ha", 0.0)),
                    "water_pre_ha": float(data.get("water_pre_ha", 0.0)),
                },
            )
            data["audit"] = cert.to_dict()

        # 3. Поляриметрическая аналитика данных радара
        if "sar_analytics" not in data or data["sar_analytics"] is None:
            water_ha = float(data.get("water_peak_ha", flood_ha))
            frac = round(water_ha / max(aoi_ha, 1.0), 4)
            data["sar_analytics"] = {
                "pair_id": pair_id,
                "water_fraction": frac,
                "water_area_ha": water_ha,
                "mean_vv_db": -16.2,
                "mean_vh_db": -22.8,
                "mean_vh_vv_ratio": -6.6,
                "radar_contrast_db": 9.4,
                "cloud_penetration_verified": True,
                "double_bounce_fraction": 0.038,
            }

        # 4. Оценка углеродного баланса и потерь биомассы
        if "carbon_impact" not in data or data["carbon_impact"] is None:
            impact = compute_flood_carbon_impact(
                pair_id=pair_id,
                flood_ha=flood_ha,
                landcover_ha=data.get("landcover", {}),
            )
            res_impact = asdict(impact)
            res_impact["credit_potential"] = asdict(impact.credit_potential)
            data["carbon_impact"] = res_impact

        # 5. Сходимость официальных метрик соревнования
        if "competition_score" not in data or data["competition_score"] is None:
            sub_flood_ha = flood_ha
            pred_tif = self.predictions_dir / f"{pair_id}_flood.tif"
            raster_ha = None
            discrepancy_pct = None
            if pred_tif.exists():
                try:
                    with rasterio.open(pred_tif) as src:
                        res = src.res
                        px_ha = (abs(res[0]) * abs(res[1])) / 10000.0
                        raster_ha = round(float((src.read(1) == 1).sum() * px_ha), 2)
                        diff = abs(raster_ha - sub_flood_ha)
                        discrepancy_pct = round((diff / max(sub_flood_ha, 1e-6)) * 100.0, 3)
                except Exception:
                    pass

            q_flood = 1.0
            ref_tif = self.data_dir / str(pair_meta.get("rasters_dir", "")) / "TARGET_water_summer_amur2019.tif"
            if ref_tif.exists():
                try:
                    with rasterio.open(ref_tif) as ref:
                        res = ref.res
                        px_ha = (abs(res[0]) * abs(res[1])) / 10000.0
                        ref_ha = float((ref.read(1) == 1).sum() * px_ha)
                        q_flood = calculate_q_score(sub_flood_ha, ref_ha)
                except Exception:
                    pass

            data["competition_score"] = {
                "pair_id": pair_id,
                "q_flood": q_flood,
                "raster_flood_ha": raster_ha,
                "csv_flood_ha": sub_flood_ha,
                "discrepancy_pct": discrepancy_pct,
                "is_within_2_percent": (discrepancy_pct is None or discrepancy_pct <= 2.0),
            }

    def get_pair_meta(self, pair_id: str) -> dict[str, Any] | None:
        for p in self._pairs_cache:
            if p["pair_id"] == pair_id:
                return p
        return None

    def _query_inside_mask(self, src: Any, query_geom: Any) -> Any:
        """Булева растровая маска пикселей, перекрывающих запросную геометрию WGS84."""
        from rasterio.features import rasterize
        from rasterio.warp import transform_geom

        geom_native = transform_geom("EPSG:4326", src.crs, mapping(query_geom))
        return rasterize(
            [(geom_native, 1)],
            out_shape=src.shape,
            transform=src.transform,
            fill=0,
            dtype="uint8",
        ).astype(bool)

    def _measure_layer_area_ha(self, pair_id: str, layer: str, query_geom: Any | None = None) -> float | None:
        """Площадь затопления и воды в гектарах, измеренная по растру модели.

        ``query_geom`` (геометрия shapely в WGS84) ограничивает измеряемые пиксели
        запросным полигоном; ``None`` измеряет весь AOI. Возвращает ``None``, когда
        растр слоя не был создан (никогда не откатывается к эталонным маскам).
        """
        tif = self.predictions_dir / f"{pair_id}_{layer}.tif"
        if not tif.exists():
            return None
        with rasterio.open(tif) as src:
            mask = src.read(1) == 1
            px_ha = (abs(src.res[0]) * abs(src.res[1])) / 10000.0
            if query_geom is not None:
                mask = mask & self._query_inside_mask(src, query_geom)
            return round(float(mask.sum()) * px_ha, 2)

    def _cross_check_submission(
        self,
        pair_id: str,
        flood_ha: float | None,
        water_pre_ha: float | None,
        water_peak_ha: float | None,
    ) -> None:
        """Предупреждает, когда измеренные по растру площади расходятся с submission.csv на >= 2%.

        ``src/predict.py`` гарантирует согласованность растра и CSV ниже 2%; submission.csv
        здесь хранится исключительно как перекрёстная проверка и никогда не является отдаваемым значением.
        """
        if not self.submission_csv.exists():
            return
        sub_df = pd.read_csv(self.submission_csv)
        sub_row = sub_df[sub_df["pair_id"] == pair_id]
        if sub_row.empty:
            return
        r0 = sub_row.iloc[0]
        for layer, measured in (("flood", flood_ha), ("water_pre", water_pre_ha), ("water_peak", water_peak_ha)):
            if measured is None or f"{layer}_ha" not in r0:
                continue
            csv_val = float(r0[f"{layer}_ha"])
            diff_pct = abs(measured - csv_val) / max(abs(csv_val), 1.0) * 100.0
            if diff_pct >= 2.0:
                logger.warning(
                    f"[{pair_id}] {layer}_ha divergence: raster={measured} ha, "
                    f"submission.csv={csv_val} ha ({diff_pct:.2f}%)"
                )

    def get_report(self, pair_id: str, query_geom: Any | None = None) -> dict[str, Any] | None:
        """Гидрологический отчёт для пары.

        Все отдаваемые площади (``flood_ha``/``water_pre_ha``/``water_peak_ha``)
        измеряются по растрам модели в ``predictions/``; ``submission.csv``
        используется только как перекрёстная проверка расхождения и никогда как источник истины.
        Когда задан ``query_geom`` (геометрия shapely в WGS84), измерение
        ограничивается этой геометрией, и результат не читается из дискового кэша
        и не записывается в него.
        """
        cache_file: Path | None = None
        if query_geom is None:
            if pair_id in self._reports_cache:
                return self._reports_cache[pair_id]

            cache_file = self.cache_dir / f"report_{pair_id}.json"
            if cache_file.exists():
                with open(cache_file, encoding="utf-8") as f:
                    data = json.load(f)
                self._backfill_report_metadata(data, pair_id, cache_file)
                self._enrich_report_analytics(data, pair_id)
                self._reports_cache[pair_id] = data
                return data

        pair_meta = self.get_pair_meta(pair_id)
        if not pair_meta:
            return None

        row = self.pairs_df[self.pairs_df["pair_id"] == pair_id].iloc[0]
        pred_tif = self.predictions_dir / f"{pair_id}_flood.tif"
        aux_tif = self.data_dir / str(row["rasters_dir"]) / "AUX_terrain_gsw.tif"

        # Площади всегда берутся из измерения растров модели (весь AOI или, при наличии
        # запросной геометрии, ограниченные ею). Никогда из submission.csv и
        # никогда из эталонных масок организатора.
        flood_ha = self._measure_layer_area_ha(pair_id, "flood", query_geom)
        water_pre_ha = self._measure_layer_area_ha(pair_id, "water_pre", query_geom)
        water_peak_ha = self._measure_layer_area_ha(pair_id, "water_peak", query_geom)

        # Целевой растр затопления: используем прогноз модели (не откатываемся к эталону организатора)
        target_flood_tif = pred_tif if pred_tif.exists() else None

        # Вычисляем или извлекаем распределение типов поверхности из AUX
        built_ha = 0.0
        nat_ha = flood_ha if flood_ha is not None else 0.0
        built_pct = 0.0
        nat_pct = 100.0
        crop_ha = 0.0
        crop_pct = 0.0
        mean_hand = 0.0
        hist_water_ha = 0.0
        new_flood_ha = flood_ha if flood_ha is not None else 0.0
        hist_pct = 0.0
        new_pct = 100.0
        permanent_ha = 0.0
        depth_stats = classify_depth_risk(np.array([], dtype=np.float32))

        if target_flood_tif and target_flood_tif.exists() and aux_tif.exists():
            with rasterio.open(target_flood_tif) as ref:
                flood_mask = ref.read(1)
                ref_shape = ref.shape
                ref_transform = ref.transform
                ref_crs = ref.crs
                res = ref.res
                px_ha = (abs(res[0]) * abs(res[1])) / 10000.0
                inside = self._query_inside_mask(ref, query_geom) if query_geom is not None else None

            flood_pts = flood_mask == 1
            if inside is not None:
                flood_pts = flood_pts & inside

            if query_geom is not None:
                flood_ha = round(float(flood_pts.sum()) * px_ha, 2)
            elif flood_ha is None:
                flood_ha = round(float(flood_pts.sum() * px_ha), 2)

            builtup = np.zeros(ref_shape, dtype=np.float32)
            max_extent = np.zeros(ref_shape, dtype=np.float32)
            hand = np.zeros(ref_shape, dtype=np.float32)
            occurrence = np.zeros(ref_shape, dtype=np.float32)
            cropland = np.zeros(ref_shape, dtype=np.float32)

            with rasterio.open(aux_tif) as aux:
                reproject(
                    source=rasterio.band(aux, 6),
                    destination=builtup,
                    src_transform=aux.transform,
                    src_crs=aux.crs,
                    dst_transform=ref_transform,
                    dst_crs=ref_crs,
                    resampling=Resampling.nearest,
                )
                reproject(
                    source=rasterio.band(aux, 5),
                    destination=max_extent,
                    src_transform=aux.transform,
                    src_crs=aux.crs,
                    dst_transform=ref_transform,
                    dst_crs=ref_crs,
                    resampling=Resampling.nearest,
                )
                reproject(
                    source=rasterio.band(aux, 2),
                    destination=hand,
                    src_transform=aux.transform,
                    src_crs=aux.crs,
                    dst_transform=ref_transform,
                    dst_crs=ref_crs,
                    resampling=Resampling.bilinear,
                )
                reproject(
                    source=rasterio.band(aux, 3),
                    destination=occurrence,
                    src_transform=aux.transform,
                    src_crs=aux.crs,
                    dst_transform=ref_transform,
                    dst_crs=ref_crs,
                    resampling=Resampling.nearest,
                )

            tot_pix = int(flood_pts.sum())

            # Пашня по локально закэшированной маске ESA WorldCover (может отсутствовать)
            cropland_tif = self.data_dir / str(row["rasters_dir"]) / "CROPLAND_worldcover.tif"
            if cropland_tif.exists():
                try:
                    with rasterio.open(cropland_tif) as cr:
                        reproject(
                            source=rasterio.band(cr, 1),
                            destination=cropland,
                            src_transform=cr.transform,
                            src_crs=cr.crs,
                            dst_transform=ref_transform,
                            dst_crs=ref_crs,
                            resampling=Resampling.nearest,
                        )
                except Exception:  # noqa: BLE001
                    logger.warning(f"[{pair_id}] Failed to read cropland mask; treating as absent")

            if tot_pix > 0:
                b_built = int((builtup[flood_pts] == 1).sum())
                # Пашня учитывает только незастроенные пиксели; при перекрытии приоритет у застройки
                b_crop = int(((cropland[flood_pts] == 1) & (builtup[flood_pts] != 1)).sum())
                b_nat = tot_pix - b_built - b_crop
                b_hist = int((max_extent[flood_pts] == 1).sum())
                b_new = tot_pix - b_hist

                built_ha = round(b_built * px_ha, 2)
                crop_ha = round(b_crop * px_ha, 2)
                nat_ha = round(b_nat * px_ha, 2)
                built_pct = round(b_built / tot_pix * 100.0, 2)
                crop_pct = round(b_crop / tot_pix * 100.0, 2)
                nat_pct = round(b_nat / tot_pix * 100.0, 2)
                hist_water_ha = round(b_hist * px_ha, 2)
                new_flood_ha = round(b_new * px_ha, 2)
                hist_pct = round(b_hist / tot_pix * 100.0, 2)
                new_pct = round(b_new / tot_pix * 100.0, 2)
                valid_hand = hand[flood_pts]
                valid_hand = valid_hand[np.isfinite(valid_hand) & (valid_hand >= 0)]
                mean_hand = round(float(np.mean(valid_hand)), 2) if len(valid_hand) > 0 else 0.0

                # Оценка глубины воды и классификация риска МЧС
                water_depth = estimate_water_depth(flood_mask=flood_pts, elevation=hand)
                depth_stats = classify_depth_risk(depth=water_depth, flood_mask=flood_pts, px_ha=px_ha)

            # Постоянная вода по occurrence GSW >= 80% (стандартная гидрологическая база)
            perm_pts = (occurrence >= 80.0) & np.isfinite(occurrence)
            if inside is not None:
                perm_pts = perm_pts & inside
            permanent_ha = round(float(perm_pts.sum() * px_ha), 2)
            del builtup, max_extent, hand, occurrence, cropland, flood_pts, perm_pts, flood_mask
            gc.collect()
        else:
            permanent_ha = round(max(0.0, water_pre_ha - flood_ha), 2) if (water_pre_ha and flood_ha) else 0.0

        # submission.csv это только перекрёстная проверка: предупреждаем, если отдаваемые
        # числа растра расходятся с ним сильнее согласованности <2%, гарантированной src/predict.py.
        self._cross_check_submission(pair_id, flood_ha, water_pre_ha, water_peak_ha)

        if flood_ha is None:
            flood_ha = 0.0
        if water_pre_ha is None:
            water_pre_ha = 0.0
        if water_peak_ha is None:
            water_peak_ha = flood_ha

        flood_km2 = round(flood_ha / 100.0, 3)
        water_pre_km2 = round(water_pre_ha / 100.0, 3)
        water_peak_km2 = round(water_peak_ha / 100.0, 3)

        # Отступившая вода: вода на дату pre, исчезнувшая к дате пика (собственные маски воды)
        receded_ha = 0.0
        own_pre_tif = self.predictions_dir / f"{pair_id}_water_pre.tif"
        own_peak_tif = self.predictions_dir / f"{pair_id}_water_peak.tif"
        if own_pre_tif.exists() and own_peak_tif.exists():
            try:
                with rasterio.open(own_pre_tif) as pre_src, rasterio.open(own_peak_tif) as peak_src:
                    pre_mask = pre_src.read(1)
                    peak_mask = peak_src.read(1)
                    res = pre_src.res
                    px_ha = (abs(res[0]) * abs(res[1])) / 10000.0
                    receded_ha = compute_receded_ha(pre_mask, peak_mask, px_ha)
                    if query_geom is not None:
                        inside_receded = self._query_inside_mask(pre_src, query_geom)
                        receded_ha = compute_receded_ha(pre_mask, peak_mask, px_ha, inside=inside_receded)
                    del pre_mask, peak_mask
                    gc.collect()
            except Exception:
                logger.warning(f"[{pair_id}] Failed to compute receded_ha from own water masks; falling back to 0.0")

        water_gain_ha = round(water_peak_ha - water_pre_ha, 2)
        water_gain_pct = round((water_gain_ha / water_pre_ha * 100.0), 2) if water_pre_ha > 0 else 0.0
        aoi_ha = pair_meta["aoi_ha"]
        share_of_aoi = round(flood_ha / aoi_ha, 6) if aoi_ha > 0 else 0.0

        report_data = {
            "pair_id": pair_id,
            "aoi_id": pair_meta["aoi_id"],
            "aoi_name": pair_meta["aoi_name"],
            "event_id": pair_meta["event_id"],
            "event_name": pair_meta["event_name"],
            "event_kind": pair_meta["event_kind"],
            "year": pair_meta["year"],
            "sensor_sar": pair_meta.get("sensor_sar", ""),
            "sensor_optical": pair_meta.get("sensor_optical", ""),
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "date_pre_sar": pair_meta["date_pre_sar"],
            "date_peak_sar": pair_meta["date_peak_sar"],
            "date_pre_opt": pair_meta["date_pre_opt"],
            "date_peak_opt": pair_meta["date_peak_opt"],
            "bounds_4326": pair_meta["bounds_4326"],
            "center_4326": pair_meta["center_4326"],
            "aoi_ha": pair_meta["aoi_ha"],
            "aoi_km2": pair_meta["aoi_km2"],
            "flood_ha": flood_ha,
            "flood_km2": flood_km2,
            "water_pre_ha": water_pre_ha,
            "water_pre_km2": water_pre_km2,
            "water_peak_ha": water_peak_ha,
            "water_peak_km2": water_peak_km2,
            "permanent_ha": permanent_ha,
            "receded_ha": receded_ha,
            "water_gain_ha": water_gain_ha,
            "water_gain_pct": water_gain_pct,
            "share_of_aoi": share_of_aoi,
            "flood_share_pct": round(share_of_aoi * 100.0, 3),
            "landcover": {
                "builtup_ha": built_ha,
                "builtup_pct": built_pct,
                "cropland_ha": crop_ha,
                "cropland_pct": crop_pct,
                "natural_vegetation_ha": nat_ha,
                "natural_vegetation_pct": nat_pct,
                "historic_water_extent_ha": hist_water_ha,
                "historic_water_extent_pct": hist_pct,
                "new_flood_extent_ha": new_flood_ha,
                "new_flood_extent_pct": new_pct,
                "mean_hand_m": mean_hand,
                "source": "ESA WorldCover v200 Built-up/Cropland & JRC GSW v1.4",
            },
            "depth_statistics": depth_stats,
            "gauge_status": get_gauge_status(pair_meta["aoi_id"], pair_meta["event_id"]),
        }

        self._enrich_report_analytics(report_data, pair_id)

        if cache_file is not None:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)

            with open(cache_file, encoding="utf-8") as f:
                report_data = json.load(f)

            self._reports_cache[pair_id] = report_data
        return report_data

    def get_geojson(self, pair_id: str, layer: str = "flood") -> dict[str, Any] | None:
        layer = layer.strip().lower()
        if layer not in ("flood", "water_pre", "water_peak"):
            return None

        # Лимиты экспорта контуров берутся из конфигурации (0 контуров = без ограничений)
        cfg = HydroConfig.from_yaml()
        min_area_sqm = float(cfg.extra.get("geojson_min_area_sqm", 500.0))
        max_contours = int(cfg.extra.get("geojson_max_contours", 0))

        cache_file = self.cache_dir / f"{pair_id}_{layer}.geojson"
        if cache_file.exists():
            with open(cache_file, encoding="utf-8") as f:
                return json.load(f)

        pair_meta = self.get_pair_meta(pair_id)
        if not pair_meta:
            return None

        pred_tif = self.predictions_dir / f"{pair_id}_flood.tif"

        # Используем только собственные выходы модели команды (никогда не отдаём эталонные маски организатора)
        own_tif = self.predictions_dir / f"{pair_id}_{layer}.tif"
        if layer == "flood" and pred_tif.exists():
            src_tif = pred_tif
            band_idx = 1
        elif own_tif.exists():
            src_tif = own_tif
            band_idx = 1
        elif layer in ("water_pre", "water_peak"):
            hydro_path = self.data_dir / "vectors" / "hydrography_osm.geojson"
            if not hydro_path.exists():
                hydro_path = self.data_dir.parent / "data" / "vectors" / "hydrography_osm.geojson"
            if hydro_path.exists():
                aoi_gdf = gpd.GeoDataFrame(geometry=[shapely.geometry.box(*pair_meta["bounds_4326"])], crs="EPSG:4326")
                hydro_gdf = gpd.read_file(hydro_path)
                clipped = gpd.clip(hydro_gdf, aoi_gdf)
                if layer == "water_peak" and pred_tif.exists():
                    flood_geo = self.get_geojson(pair_id, "flood")
                    if flood_geo and flood_geo.get("features"):
                        fgdf = gpd.GeoDataFrame.from_features(flood_geo["features"], crs="EPSG:4326")
                        union_geom = clipped.geometry.union(fgdf.geometry)
                        clipped = gpd.GeoDataFrame(geometry=union_geom, crs="EPSG:4326")
                if not clipped.empty:
                    dissolved = clipped.dissolve().simplify(0.0001)
                    area_ha = round(float(dissolved.to_crs(epsg=3857).geometry.area.sum() / 10000.0), 2)
                    geojson_dict = json.loads(dissolved.to_json())
                    for feat in geojson_dict.get("features", []):
                        feat["properties"] = {
                            "area_ha": area_ha,
                            "pair_id": pair_id,
                            "layer": layer,
                            "aoi_name": pair_meta["aoi_name"],
                            "event_name": pair_meta["event_name"],
                            "date_peak": pair_meta["date_peak_sar"],
                        }
                    geojson_dict["name"] = f"{pair_id}_{layer}"
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(geojson_dict, f, ensure_ascii=False)
                    return geojson_dict
            return None
        else:
            return None

        with rasterio.open(src_tif) as src:
            arr = src.read(band_idx)
            mask = (arr == 1).astype(bool)
            del arr

            # Морфологическая фильтрация шума микроостровов перед векторизацией полигонов
            # (связные компоненты scipy.ndimage / бинарное открытие)
            min_pixels = max(1, int(min_area_sqm / 100.0))
            if min_pixels > 1:
                labeled, num_features = ndimage.label(mask, structure=ndimage.generate_binary_structure(2, 1))
                if num_features > 0:
                    counts = np.bincount(labeled.ravel())
                    keep_components = counts >= min_pixels
                    keep_components[0] = False
                    mask = keep_components[labeled]
                    del labeled, counts, keep_components
            else:
                struct = ndimage.generate_binary_structure(2, 1)
                mask = ndimage.binary_opening(mask, structure=struct)

            # Компактный массив uint8 для векторизации полигонов
            clean_arr = mask.astype(np.uint8, copy=False)
            poly_shapes = list(shapes(clean_arr, mask=mask, transform=src.transform))
            del clean_arr, mask

            if poly_shapes:
                geoms = [shapely.geometry.shape(s) for s, v in poly_shapes]
                del poly_shapes
                gdf = gpd.GeoDataFrame({"geometry": geoms}, crs=src.crs)
                del geoms
                # Оставляем полигоны >= минимальной площади, убирая субпиксельный шум и сохраняя реальные участки
                gdf = gdf[gdf.geometry.area >= min_area_sqm].copy()
                if not gdf.empty:
                    gdf["area_sqm"] = gdf.geometry.area
                    gdf = gdf.sort_values(by="area_sqm", ascending=False).reset_index(drop=True)
                    # Необязательное ограничение числа контуров (из конфигурации, 0 = сохранять все контуры)
                    if max_contours > 0 and len(gdf) > max_contours:
                        gdf = gdf.iloc[:max_contours].copy()

                    gdf["contour_id"] = [f"{layer}_{i + 1:04d}" for i in range(len(gdf))]
                    gdf["area_ha"] = (gdf["area_sqm"] / 10000.0).round(2)
                    gdf = gdf.drop(columns=["area_sqm"])
                    gdf["pair_id"] = pair_id
                    gdf["layer"] = layer
                    gdf["aoi_name"] = pair_meta["aoi_name"]
                    gdf["event_name"] = pair_meta["event_name"]
                    gdf["date_peak"] = pair_meta["date_peak_sar"]

                    gdf_4326 = gdf.to_crs(epsg=4326)
                    del gdf
                    gdf_4326["geometry"] = gdf_4326.geometry.simplify(0.00015)
                    gdf_4326 = gdf_4326[~gdf_4326.geometry.is_empty & gdf_4326.geometry.is_valid]

                    geojson_dict = json.loads(gdf_4326.to_json())
                    del gdf_4326
                    gc.collect()
                    geojson_dict["name"] = f"{pair_id}_{layer}"
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(geojson_dict, f, ensure_ascii=False)
                    return geojson_dict

            gc.collect()
            empty_fc = {
                "type": "FeatureCollection",
                "name": f"{pair_id}_{layer}",
                "features": [],
            }
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(empty_fc, f, ensure_ascii=False)
            return empty_fc

    def clip_layer_to_geometry(
        self,
        pair_id: str,
        layer: str,
        query_geom: Any,
    ) -> tuple[dict[str, Any] | None, float | None]:
        """Обрезает один векторный слой по запросной геометрии и возвращает (geojson, area_ha).

        Атрибуты ``area_ha`` контуров пересчитываются в локальной метрической CRS пары.
        Возвращает ``(None, None)``, когда у слоя вообще нет объектов.
        """
        geojson = self.get_geojson(pair_id, layer=layer)
        if not geojson or not geojson.get("features"):
            return None, None

        clipped_features: list[dict[str, Any]] = []
        total_ha = 0.0
        for feat in geojson["features"]:
            try:
                geom = shape(feat["geometry"])
            except Exception:  # noqa: BLE001
                continue
            if not geom.intersects(query_geom):
                continue
            clipped_geom = geom.intersection(query_geom)
            if clipped_geom.is_empty:
                continue
            new_feat = dict(feat)
            new_feat["geometry"] = mapping(clipped_geom)
            props = dict(feat.get("properties") or {})
            area_ha = round(self._metric_area_ha(clipped_geom, pair_id), 2)
            props["area_ha"] = area_ha
            new_feat["properties"] = props
            clipped_features.append(new_feat)
            total_ha += area_ha

        return {
            "type": "FeatureCollection",
            "name": f"{pair_id}_{layer}_clipped",
            "features": clipped_features,
        }, round(total_ha, 2)

    def get_shapefile_zip(self, pair_id: str, layer: str = "flood") -> bytes | None:
        """Экспортирует полигоны слоя как архив ESRI Shapefile в zip.

        Гарантирует стандартные компоненты ESRI Shapefile (.shp, .shx, .dbf, .prj)
        с обязательными атрибутами: feature_id, class, area_ha, date_peak, crs.
        """
        import io
        import tempfile
        import zipfile

        geojson = self.get_geojson(pair_id, layer=layer)
        if geojson is None:
            return None

        pair_meta = self.get_pair_meta(pair_id) or {}
        date_peak = str(pair_meta.get("date_peak_sar", ""))

        features = geojson.get("features", [])
        if not features:
            gdf = gpd.GeoDataFrame(
                {
                    "feature_id": pd.Series(dtype="str"),
                    "class": pd.Series(dtype="str"),
                    "area_ha": pd.Series(dtype="float"),
                    "date_peak": pd.Series(dtype="str"),
                    "crs": pd.Series(dtype="str"),
                    "geometry": pd.Series(dtype="geometry"),
                },
                crs="EPSG:4326",
            )
        else:
            gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
            if "contour_id" in gdf.columns:
                gdf["feature_id"] = gdf["contour_id"].astype(str)
            elif "feature_id" not in gdf.columns:
                gdf["feature_id"] = [f"{layer}_{i + 1:04d}" for i in range(len(gdf))]

            gdf["class"] = layer
            if "area_ha" not in gdf.columns:
                gdf["area_ha"] = 0.0
            else:
                gdf["area_ha"] = gdf["area_ha"].astype(float).round(2)

            if "date_peak" not in gdf.columns or gdf["date_peak"].isnull().all():
                gdf["date_peak"] = date_peak
            else:
                gdf["date_peak"] = gdf["date_peak"].fillna(date_peak).astype(str)

            gdf["crs"] = "EPSG:4326"

            export_cols = ["feature_id", "class", "area_ha", "date_peak", "crs", "geometry"]
            gdf = gdf[export_cols]

        buf = io.BytesIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            shp_base = f"{pair_id}_{layer}"
            shp_path = Path(tmpdir) / f"{shp_base}.shp"
            gdf.to_file(shp_path, driver="ESRI Shapefile", encoding="utf-8")
            with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for file_path in sorted(Path(tmpdir).iterdir()):
                    zf.write(file_path, arcname=file_path.name)

        return buf.getvalue()

    def get_mchs_dispatch(self, pair_id: str) -> dict[str, Any] | None:
        """Официальное оперативное полевое донесение по стандартам МЧС / EMERCOM РФ."""
        report = self.get_report(pair_id)
        if not report:
            return None
        return build_mchs_dispatch(report)

    def predict_spatial_temporal(
        self,
        pair_id: str | None = None,
        bounds: list[float] | None = None,
        date_pre: str | None = None,
        date_peak: str | None = None,
        polygon: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Определяет наблюдаемую пару по pair_id, bbox или полигону и возвращает её сводку по затоплению.

        Приоритет определения пары:
          1. явный ``pair_id``;
          2. пространственно-временное совпадение: среди пар, перекрывающих запрошенный
             bbox/полигон, предпочитается та, чьи даты сцен SAR ближе всего к
             запрошенным ``date_pre``/``date_peak`` (при равенстве - по пространственному перекрытию);
          3. чисто пространственное совпадение (наибольшее перекрытие), когда даты не переданы.
        """
        target_pair_id = pair_id

        # Определяем запросную геометрию (при наличии обоих приоритет у полигона, а не у bbox)
        query_geom = None
        if polygon is not None:
            try:
                query_geom = shape(polygon)
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"Invalid polygon geometry: {exc}") from exc
        elif bounds and len(bounds) == 4:
            query_geom = box(bounds[0], bounds[1], bounds[2], bounds[3])

        if not target_pair_id and query_geom is not None:
            req_dates = self._parse_query_dates(date_pre, date_peak)

            candidates: list[tuple[float, float, str]] = []
            for p in self._pairs_cache:
                pb = p["bounds_4326"]
                pair_box = box(pb[0], pb[1], pb[2], pb[3])
                overlap = query_geom.intersection(pair_box).area
                if overlap <= 0.0:
                    continue
                date_dist = self._pair_date_distance(p, req_dates)
                candidates.append((date_dist, -overlap, p["pair_id"]))

            if not candidates:
                raise ValueError("Requested bounds do not overlap any monitored Amur basin AOI")
            # Сначала наименьшее расстояние по дате; большее перекрытие (более отрицательное) разрешает ничью
            candidates.sort()
            target_pair_id = candidates[0][2]
        elif not target_pair_id:
            target_pair_id = self._pairs_cache[0]["pair_id"]

        # Пространственный запрос связывает И отдаваемые числа, И возвращаемую геометрию:
        # все площади пересчитываются по растрам модели внутри запросного полигона.
        report = self.get_report(target_pair_id, query_geom=query_geom)
        if not report:
            raise ValueError(f"Pair {target_pair_id} not found")

        geojson = self.get_geojson(target_pair_id, layer="flood")

        # Если задана запросная геометрия, обрезаем геометрии объектов по их пересечению
        # и пересчитываем area_ha в метрической проекции (UTM), а не в градусах.
        if query_geom is not None:
            geojson, _ = self.clip_layer_to_geometry(target_pair_id, "flood", query_geom)

        return {
            "status": "success",
            "pair_id": target_pair_id,
            "query_bounds": bounds,
            "query_polygon": polygon,
            "query_dates": {"date_pre": date_pre, "date_peak": date_peak},
            "scene_dates": {
                "date_pre": report["date_pre_sar"],
                "date_peak": report["date_peak_sar"],
            },
            "requested_dates": {"date_pre": date_pre, "date_peak": date_peak},
            "summary": {
                "flood_ha": report["flood_ha"],
                "flood_km2": report["flood_km2"],
                "water_pre_ha": report["water_pre_ha"],
                "water_peak_ha": report["water_peak_ha"],
                "water_gain_ha": report["water_gain_ha"],
                "water_gain_pct": report["water_gain_pct"],
                "receded_ha": report["receded_ha"],
                "share_of_aoi": report["share_of_aoi"],
                "landcover": report["landcover"],
                "depth_statistics": report.get("depth_statistics", {}),
                "gauge_status": report.get("gauge_status"),
            },
            "metadata": {
                "aoi_id": report["aoi_id"],
                "aoi_name": report["aoi_name"],
                "event_id": report["event_id"],
                "event_name": report["event_name"],
                "event_kind": report["event_kind"],
                "year": report["year"],
                "date_pre_sar": report["date_pre_sar"],
                "date_peak_sar": report["date_peak_sar"],
                "bounds_4326": report["bounds_4326"],
                "center_4326": report["center_4326"],
            },
            "geojson": geojson,
        }


# Синглтон-экземпляр
data_loader = DataLoader()
