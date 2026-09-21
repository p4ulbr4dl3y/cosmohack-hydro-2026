"""Data loader and spatial processing service for HydroWatch Amur."""

from __future__ import annotations

import json
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
from shapely.geometry import box, shape

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "hydrowatch_amur"
PREDICTIONS_DIR = BASE_DIR / "predictions"
SUBMISSION_CSV = BASE_DIR / "submission.csv"
CACHE_DIR = BASE_DIR / "src" / "service" / "cache"


class DataLoader:
    def __init__(
        self,
        data_dir: Path = DATA_DIR,
        predictions_dir: Path = PREDICTIONS_DIR,
        submission_csv: Path = SUBMISSION_CSV,
        cache_dir: Path = CACHE_DIR,
    ):
        self.data_dir = data_dir
        self.predictions_dir = predictions_dir
        self.submission_csv = submission_csv
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.pairs_df: pd.DataFrame | None = None
        self._pairs_cache: list[dict[str, Any]] = []
        self._reports_cache: dict[str, dict[str, Any]] = {}
        self.init_data()

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
            target_tif = pred_tif if pred_tif.exists() else ref_tif
            if target_tif.exists():
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
                self._reports_cache[pair_id] = data
                return data

        pair_meta = self.get_pair_meta(pair_id)
        if not pair_meta:
            return None

        row = self.pairs_df[self.pairs_df["pair_id"] == pair_id].iloc[0]
        pred_tif = self.predictions_dir / f"{pair_id}_flood.tif"
        ref_tif = self.data_dir / str(row["reference_mask"])
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

        # Target flood raster: prefer model prediction over reference
        target_flood_tif = pred_tif if pred_tif.exists() else (ref_tif if ref_tif.exists() else None)

        # Compute or extract landcover distribution from AUX
        built_ha = 0.0
        nat_ha = flood_ha if flood_ha is not None else 0.0
        built_pct = 0.0
        nat_pct = 100.0
        mean_hand = 0.0
        hist_water_ha = 0.0
        new_flood_ha = flood_ha if flood_ha is not None else 0.0
        hist_pct = 0.0
        new_pct = 100.0

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

            flood_pts = flood_mask == 1
            tot_pix = int(flood_pts.sum())
            if tot_pix > 0:
                b_built = int((builtup[flood_pts] == 1).sum())
                b_nat = tot_pix - b_built
                b_hist = int((max_extent[flood_pts] == 1).sum())
                b_new = tot_pix - b_hist

                built_ha = round(b_built * px_ha, 2)
                nat_ha = round(b_nat * px_ha, 2)
                built_pct = round(b_built / tot_pix * 100.0, 2)
                nat_pct = round(b_nat / tot_pix * 100.0, 2)
                hist_water_ha = round(b_hist * px_ha, 2)
                new_flood_ha = round(b_new * px_ha, 2)
                hist_pct = round(b_hist / tot_pix * 100.0, 2)
                new_pct = round(b_new / tot_pix * 100.0, 2)
                mean_hand = round(float(np.mean(hand[flood_pts])), 2)

        if flood_ha is None:
            flood_ha = 0.0
        if water_pre_ha is None:
            water_pre_ha = 0.0
        if water_peak_ha is None:
            water_peak_ha = flood_ha

        flood_km2 = round(flood_ha / 100.0, 3)
        water_pre_km2 = round(water_pre_ha / 100.0, 3)
        water_peak_km2 = round(water_peak_ha / 100.0, 3)
        receded_ha = 0.0
        water_gain_ha = round(water_peak_ha - water_pre_ha, 2)
        water_gain_pct = round((water_gain_ha / water_pre_ha * 100.0), 2) if water_pre_ha > 0 else 0.0
        aoi_ha = pair_meta["aoi_ha"]
        share_of_aoi = round(flood_ha / aoi_ha, 6) if aoi_ha > 0 else 0.0
        permanent_ha = round(max(0.0, water_pre_ha - flood_ha), 2)

        report_data = {
            "pair_id": pair_id,
            "aoi_id": pair_meta["aoi_id"],
            "aoi_name": pair_meta["aoi_name"],
            "event_id": pair_meta["event_id"],
            "event_name": pair_meta["event_name"],
            "event_kind": pair_meta["event_kind"],
            "year": pair_meta["year"],
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
                "natural_vegetation_ha": nat_ha,
                "natural_vegetation_pct": nat_pct,
                "historic_water_extent_ha": hist_water_ha,
                "historic_water_extent_pct": hist_pct,
                "new_flood_extent_ha": new_flood_ha,
                "new_flood_extent_pct": new_pct,
                "mean_hand_m": mean_hand,
                "source": "ESA WorldCover v200 Built-up & JRC GSW v1.4",
            },
        }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        self._reports_cache[pair_id] = report_data
        return report_data

    def get_geojson(self, pair_id: str, layer: str = "flood") -> dict[str, Any] | None:
        layer = layer.lower()
        if layer not in ("flood", "water_pre", "water_peak"):
            layer = "flood"

        cache_file = self.cache_dir / f"{pair_id}_{layer}.geojson"
        if cache_file.exists():
            with open(cache_file, encoding="utf-8") as f:
                return json.load(f)

        pair_meta = self.get_pair_meta(pair_id)
        if not pair_meta:
            return None

        row = self.pairs_df[self.pairs_df["pair_id"] == pair_id].iloc[0]
        pred_tif = self.predictions_dir / f"{pair_id}_flood.tif"
        ref_tif = self.data_dir / str(row["reference_mask"])

        # For flood layer: prioritize model predictions (<pair_id>_flood.tif)
        if layer == "flood" and pred_tif.exists():
            src_tif = pred_tif
            band_idx = 1
        elif ref_tif.exists():
            src_tif = ref_tif
            band_map = {"flood": 1, "water_pre": 2, "water_peak": 3}
            band_idx = band_map[layer]
        else:
            return None

        with rasterio.open(src_tif) as src:
            arr = src.read(band_idx)
            mask = arr == 1
            poly_shapes = list(shapes(arr, mask=mask, transform=src.transform))

            if poly_shapes:
                geoms = [shapely.geometry.shape(s) for s, v in poly_shapes]
                gdf = gpd.GeoDataFrame({"geometry": geoms}, crs=src.crs)
                # Remove single-pixel noise polygons (<100 m²) to optimize web transfer
                gdf = gdf[gdf.geometry.area >= 100]
                if not gdf.empty:
                    area_ha = round(float(gdf.geometry.area.sum() / 10000.0), 2)
                    dissolved = gdf.dissolve().to_crs(epsg=4326).simplify(0.00015)
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

            empty_fc = {
                "type": "FeatureCollection",
                "name": f"{pair_id}_{layer}",
                "features": [],
            }
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(empty_fc, f, ensure_ascii=False)
            return empty_fc

    def predict_spatial_temporal(
        self,
        pair_id: str | None = None,
        bounds: list[float] | None = None,
        date_pre: str | None = None,
        date_peak: str | None = None,
    ) -> dict[str, Any]:
        """Predict / evaluate flood summary and geojson given pair_id or bounding box."""
        target_pair_id = pair_id

        # If pair_id not given but bounds provided, find best overlapping pair
        if not target_pair_id and bounds and len(bounds) == 4:
            req_box = box(bounds[0], bounds[1], bounds[2], bounds[3])
            best_overlap = 0.0
            best_pair = None
            for p in self._pairs_cache:
                pb = p["bounds_4326"]
                pair_box = box(pb[0], pb[1], pb[2], pb[3])
                overlap = req_box.intersection(pair_box).area
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_pair = p["pair_id"]
            target_pair_id = best_pair or self._pairs_cache[0]["pair_id"]
        elif not target_pair_id:
            target_pair_id = self._pairs_cache[0]["pair_id"]

        report = self.get_report(target_pair_id)
        if not report:
            raise ValueError(f"Pair {target_pair_id} not found")

        geojson = self.get_geojson(target_pair_id, layer="flood")

        # If bounds provided, filter features that intersect bounds
        if bounds and len(bounds) == 4 and geojson and geojson.get("features"):
            req_box = box(bounds[0], bounds[1], bounds[2], bounds[3])
            filtered_features = []
            for feat in geojson["features"]:
                geom = shape(feat["geometry"])
                if geom.intersects(req_box):
                    filtered_features.append(feat)
            geojson = {
                "type": "FeatureCollection",
                "name": f"{target_pair_id}_flood_clipped",
                "features": filtered_features,
            }

        return {
            "status": "success",
            "pair_id": target_pair_id,
            "query_bounds": bounds,
            "query_dates": {"date_pre": date_pre, "date_peak": date_peak},
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
