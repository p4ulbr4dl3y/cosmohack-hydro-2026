"""Data loader and spatial processing service for HydroWatch Amur."""

from __future__ import annotations

import glob
import json
import logging
import os
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
from shapely.geometry import box, mapping, shape

from src.config import HydroConfig
from src.temporal import compute_receded_ha

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "hydrowatch_amur"
PREDICTIONS_DIR = BASE_DIR / "predictions"
SUBMISSION_CSV = BASE_DIR / "submission.csv"
DEFAULT_CACHE_DIR = BASE_DIR / ".cache" / "hydrowatch"
LEGACY_CACHE_DIR = BASE_DIR / "src" / "service" / "cache"
CACHE_DIR = Path(os.getenv("HYDROWATCH_CACHE_DIR", str(DEFAULT_CACHE_DIR)))


class DataLoader:
    def __init__(
        self,
        data_dir: Path = DATA_DIR,
        predictions_dir: Path = PREDICTIONS_DIR,
        submission_csv: Path = SUBMISSION_CSV,
        cache_dir: Path | None = None,
        legacy_cache_dir: Path | None = None,
    ):
        self.data_dir = data_dir
        self.predictions_dir = predictions_dir
        self.submission_csv = submission_csv
        if cache_dir is None:
            self.cache_dir = Path(os.getenv("HYDROWATCH_CACHE_DIR", str(DEFAULT_CACHE_DIR)))
            self.legacy_cache_dir = legacy_cache_dir or LEGACY_CACHE_DIR
        else:
            self.cache_dir = Path(cache_dir)
            self.legacy_cache_dir = legacy_cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.pairs_df: pd.DataFrame | None = None
        self._pairs_cache: list[dict[str, Any]] = []
        self._reports_cache: dict[str, dict[str, Any]] = {}
        self.init_data()

    def _resolve_cache_path(self, filename: str) -> Path:
        """Resolve path to cached file with fallback to legacy cache dir."""
        primary = self.cache_dir / filename
        if primary.exists():
            return primary
        if self.legacy_cache_dir is not None:
            legacy = self.legacy_cache_dir / filename
            if legacy.exists():
                return legacy
        return primary

    @staticmethod
    def _parse_query_dates(date_pre: str | None, date_peak: str | None) -> dict[str, Any]:
        """Parse optional requested ISO dates, ignoring malformed/empty values."""
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
        """Mean absolute day distance between requested and scene dates for a pair.

        When no dates are requested the distance is 0 for every pair, so ordering
        falls back to spatial overlap.
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
        """Area of a WGS84 geometry in hectares, computed in local UTM CRS."""
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
        """Backfill sensor/generation metadata into reports cached before schema v1.1.

        Reports written by older code lack `sensor_*` and `generated_at`; the disk
        mtime is a faithful stand-in for the generation timestamp.
        """
        pair_meta = self.get_pair_meta(pair_id)
        if pair_meta:
            data.setdefault("sensor_sar", pair_meta.get("sensor_sar", ""))
            data.setdefault("sensor_optical", pair_meta.get("sensor_optical", ""))
        if not data.get("generated_at"):
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime, tz=UTC)
            data["generated_at"] = mtime.isoformat(timespec="seconds")

    def get_pair_meta(self, pair_id: str) -> dict[str, Any] | None:
        for p in self._pairs_cache:
            if p["pair_id"] == pair_id:
                return p
        return None

    def get_report(self, pair_id: str) -> dict[str, Any] | None:
        if pair_id in self._reports_cache:
            return self._reports_cache[pair_id]

        cache_file = self.cache_dir / f"report_{pair_id}.json"
        if cache_file.exists():
            with open(cache_file, encoding="utf-8") as f:
                data = json.load(f)
            self._backfill_report_metadata(data, pair_id, cache_file)
            self._reports_cache[pair_id] = data
            return data

        pair_meta = self.get_pair_meta(pair_id)
        if not pair_meta:
            return None

        row = self.pairs_df[self.pairs_df["pair_id"] == pair_id].iloc[0]
        pred_tif = self.predictions_dir / f"{pair_id}_flood.tif"
        aux_tif = self.data_dir / str(row["rasters_dir"]) / "AUX_terrain_gsw.tif"

        # Load areas from submission.csv if available
        flood_ha = None
        water_pre_ha = None
        water_peak_ha = None

        if self.submission_csv.exists():
            sub_df = pd.read_csv(self.submission_csv)
            sub_row = sub_df[sub_df["pair_id"] == pair_id]
            if not sub_row.empty:
                r0 = sub_row.iloc[0]
                flood_ha = float(r0["flood_ha"])
                water_pre_ha = float(r0["water_pre_ha"])
                water_peak_ha = float(r0["water_peak_ha"])

        # Target flood raster: use model prediction (do not fall back to organizer reference)
        target_flood_tif = pred_tif if pred_tif.exists() else None

        # Compute or extract landcover distribution from AUX
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

        if target_flood_tif and target_flood_tif.exists() and aux_tif.exists():
            with rasterio.open(target_flood_tif) as ref:
                flood_mask = ref.read(1)
                ref_shape = ref.shape
                ref_transform = ref.transform
                ref_crs = ref.crs
                res = ref.res
                px_ha = (abs(res[0]) * abs(res[1])) / 10000.0

            if flood_ha is None:
                flood_ha = round(float((flood_mask == 1).sum() * px_ha), 2)

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

            flood_pts = flood_mask == 1
            tot_pix = int(flood_pts.sum())

            # Cropland from a locally cached ESA WorldCover mask (may be absent)
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
                # Cropland only counts non-built-up pixels; built-up wins on overlap
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

            # Permanent water from GSW occurrence >= 80% (standard hydrological baseline)
            perm_pts = (occurrence >= 80.0) & np.isfinite(occurrence)
            permanent_ha = round(float(perm_pts.sum() * px_ha), 2)
        else:
            permanent_ha = round(max(0.0, water_pre_ha - flood_ha), 2) if (water_pre_ha and flood_ha) else 0.0

        if flood_ha is None:
            flood_ha = 0.0
        if water_pre_ha is None:
            water_pre_ha = 0.0
        if water_peak_ha is None:
            water_peak_ha = flood_ha

        flood_km2 = round(flood_ha / 100.0, 3)
        water_pre_km2 = round(water_pre_ha / 100.0, 3)
        water_peak_km2 = round(water_peak_ha / 100.0, 3)

        # Receded water: water on pre date, gone by peak date (own water masks)
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
        }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        self._reports_cache[pair_id] = report_data
        return report_data

    def get_geojson(self, pair_id: str, layer: str = "flood") -> dict[str, Any] | None:
        layer = layer.strip().lower()
        if layer not in ("flood", "water_pre", "water_peak"):
            return None

        # Contour export limits come from config (0 contours = unlimited)
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

        # Use the team's own model outputs only (never serve organizer reference masks)
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
            mask = arr == 1
            poly_shapes = list(shapes(arr, mask=mask, transform=src.transform))

            if poly_shapes:
                geoms = [shapely.geometry.shape(s) for s, v in poly_shapes]
                gdf = gpd.GeoDataFrame({"geometry": geoms}, crs=src.crs)
                # Keep polygons >= min area to avoid sub-pixel noise while preserving real flood patches
                gdf = gdf[gdf.geometry.area >= min_area_sqm].copy()
                if not gdf.empty:
                    gdf["area_sqm"] = gdf.geometry.area
                    gdf = gdf.sort_values(by="area_sqm", ascending=False).reset_index(drop=True)
                    # Optional cap on contour count (config-driven, 0 = keep all contours)
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
                    gdf_4326["geometry"] = gdf_4326.geometry.simplify(0.00015)
                    gdf_4326 = gdf_4326[~gdf_4326.geometry.is_empty & gdf_4326.geometry.is_valid]

                    geojson_dict = json.loads(gdf_4326.to_json())
                    geojson_dict["name"] = f"{pair_id}_{layer}"
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(geojson_dict, f, ensure_ascii=False)
                    return geojson_dict

            empty_fc = {
                "type": "FeatureCollection",
                "name": f"{pair_id}_{layer}",
                "features": [],
            }
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(empty_fc, f, ensure_ascii=False)
            return empty_fc

    def get_shapefile_zip(self, pair_id: str, layer: str = "flood") -> bytes | None:
        """Export layer polygons as a zipped ESRI Shapefile archive."""
        import io
        import tempfile
        import zipfile

        geojson = self.get_geojson(pair_id, layer=layer)
        if geojson is None:
            return None

        features = geojson.get("features", [])
        if not features:
            gdf = gpd.GeoDataFrame(columns=["area_ha", "pair_id", "layer", "geometry"], crs="EPSG:4326")
        else:
            gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")

        buf = io.BytesIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            shp_base = f"{pair_id}_{layer}"
            shp_path = Path(tmpdir) / f"{shp_base}.shp"
            gdf.to_file(shp_path, driver="ESRI Shapefile", encoding="utf-8")
            with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for file_path in Path(tmpdir).iterdir():
                    zf.write(file_path, arcname=file_path.name)

        return buf.getvalue()

    def predict_spatial_temporal(
        self,
        pair_id: str | None = None,
        bounds: list[float] | None = None,
        date_pre: str | None = None,
        date_peak: str | None = None,
        polygon: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resolve a monitored pair from pair_id, bbox or polygon and return its flood summary.

        Pair resolution precedence:
          1. explicit ``pair_id``;
          2. spatial+temporal match: among pairs overlapping the requested
             bbox/polygon, prefer the one whose SAR scene dates are closest to the
             requested ``date_pre``/``date_peak`` (ties broken by spatial overlap);
          3. purely spatial match (largest overlap) when no dates are supplied.
        """
        target_pair_id = pair_id

        # Resolve the requested query geometry (polygon wins over bbox when both given)
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
            # Smallest date distance first; larger overlap (more negative) as tie-break
            candidates.sort()
            target_pair_id = candidates[0][2]
        elif not target_pair_id:
            target_pair_id = self._pairs_cache[0]["pair_id"]

        report = self.get_report(target_pair_id)
        if not report:
            raise ValueError(f"Pair {target_pair_id} not found")

        geojson = self.get_geojson(target_pair_id, layer="flood")

        # If a query geometry was given, clip feature geometries to its intersection
        # and recompute area_ha in a metric (UTM) projection rather than degrees.
        if query_geom is not None and geojson and geojson.get("features"):
            clipped_features = []
            for feat in geojson["features"]:
                geom = shape(feat["geometry"])
                if geom.intersects(query_geom):
                    clipped_geom = geom.intersection(query_geom)
                    if not clipped_geom.is_empty:
                        new_feat = dict(feat)
                        new_feat["geometry"] = mapping(clipped_geom)
                        props = dict(feat.get("properties") or {})
                        props["area_ha"] = round(self._metric_area_ha(clipped_geom, target_pair_id), 2)
                        new_feat["properties"] = props
                        clipped_features.append(new_feat)
            geojson = {
                "type": "FeatureCollection",
                "name": f"{target_pair_id}_flood_clipped",
                "features": clipped_features,
            }

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


# Singleton instance
data_loader = DataLoader()
