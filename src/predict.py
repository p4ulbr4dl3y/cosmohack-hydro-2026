"""End-to-end prediction and inference pipeline for HydroWatch Amur.

Processes all 11 pairs in hydrowatch_amur/pairs.csv, outputs:
  - submission.csv with columns [pair_id, flood_ha, water_pre_ha, water_peak_ha]
  - predictions/<pair_id>_flood.tif (GeoTIFF, uint8, 0/1, EPSG:32652)
Verifies that the CSV areas match raster pixel counts within 2%.
"""

from __future__ import annotations

import argparse
import gc
import glob
import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

# Ensure repository root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio

from src.config import MMU_MIN_PIXELS, PIXEL_SIZE_HA, PIXEL_SIZE_M
from src.filters import apply_mmu
from src.geo_utils import clip_by_aoi
from src.indices import segment_optical
from src.segmentation import (
    detect_flooded_vegetation,
    load_aux_priors,
    segment_water,
)
from src.temporal import compute_temporal_dynamics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _process_pair_worker(task_args: tuple[int, int, pd.Series, Path, Path, int]) -> dict[str, float | str]:
    """Top-level worker helper for multiprocessing pool execution."""
    idx, total, row, data_dir, predictions_dir, ablation_mode = task_args
    logger.info(f"Processing [{idx + 1}/{total}]: {row['pair_id']}")
    return process_pair(
        row=row,
        data_dir=data_dir,
        predictions_dir=predictions_dir,
        ablation_mode=ablation_mode,
    )


def process_pair(
    row: pd.Series,
    data_dir: Path,
    predictions_dir: Path,
    ablation_mode: int = 4,
) -> dict[str, float | str]:
    """Process a single AOI pair through the segmentation pipeline.

    Ablation modes:
      1: Naive SAR Otsu alone (no priors, no optical, no MMU, no permanent).
      2: SAR Otsu + HAND/Slope filter.
      3: SAR + MSI optical fusion (where available) + HAND/Slope filter.
      4: Full pipeline (+ MMU 25px + GSW permanent).
    """
    pair_id = str(row["pair_id"])
    rasters_dir = data_dir / str(row["rasters_dir"])

    # 1. Locate Sentinel-1 rasters first to allow standalone geometry fallback
    s1_pre_files = sorted(glob.glob(str(rasters_dir / "S1_pre_*.tif")))
    s1_peak_files = sorted(glob.glob(str(rasters_dir / "S1_peak_*.tif")))

    if not s1_pre_files or not s1_peak_files:
        raise FileNotFoundError(f"Missing S1 pre/peak rasters in {rasters_dir}")

    # Target geometry: derive from the Sentinel-1 scene grid (native sensor grid).
    # The reference raster is only a fallback when S1 metadata is unavailable.
    with rasterio.open(s1_pre_files[0]) as s1_src:
        target_shape = s1_src.shape
        target_transform = s1_src.transform
        target_crs = s1_src.crs

    height, width = target_shape

    with rasterio.open(s1_pre_files[0]) as src:
        vv_pre = src.read(1)
        vh_pre = src.read(2) if src.count >= 2 else None

    with rasterio.open(s1_peak_files[0]) as src:
        vv_peak = src.read(1)
        vh_peak = src.read(2) if src.count >= 2 else None

    # 2. Load Topographic & Hydrological priors from AUX
    aux_file = rasters_dir / "AUX_terrain_gsw.tif"
    if aux_file.exists() and ablation_mode >= 2:
        aux_data = load_aux_priors(aux_file, target_shape, target_transform, target_crs)
        topo_mask = aux_data["topo_mask"]
        perm_mask = aux_data["permanent_mask"] if ablation_mode == 4 else None
        hand_arr = aux_data["hand"]
        slope_arr = aux_data["slope"]
        builtup_arr = aux_data["builtup"]
        occ_arr = aux_data["occurrence"]
    else:
        topo_mask = None
        perm_mask = None
        hand_arr = None
        slope_arr = None
        builtup_arr = None
        occ_arr = None

    # 3. Load Optical Sentinel-2 where available
    opt_pre_w, opt_pre_v = None, None
    opt_peak_w, opt_peak_v = None, None
    if ablation_mode >= 3:
        s2_pre_files = sorted(glob.glob(str(rasters_dir / "SENTINEL2_pre_*.tif")))
        s2_peak_files = sorted(glob.glob(str(rasters_dir / "SENTINEL2_peak_*.tif")))
        if s2_pre_files:
            opt_pre_w, opt_pre_v = segment_optical(s2_pre_files[0], target_shape)
        if s2_peak_files:
            opt_peak_w, opt_peak_v = segment_optical(s2_peak_files[0], target_shape)

    use_topo = ablation_mode >= 2
    use_optical = ablation_mode >= 3
    use_mmu = ablation_mode == 4
    use_permanent = ablation_mode == 4

    # 4. Segment pre-flood water
    water_pre = segment_water(
        vv=vv_pre,
        vh=vh_pre,
        optical_water=opt_pre_w,
        optical_valid=opt_pre_v,
        topo_mask=topo_mask,
        permanent_mask=perm_mask,
        hand=hand_arr,
        slope=slope_arr,
        builtup=builtup_arr,
        occurrence=occ_arr,
        is_peak=False,
        use_topo=use_topo,
        use_optical=use_optical,
        use_mmu=use_mmu,
        use_permanent=use_permanent,
    )

    # 5. Segment peak-flood water
    water_peak = segment_water(
        vv=vv_peak,
        vh=vh_peak,
        vv_ref=vv_pre,
        vh_ref=vh_pre,
        optical_water=opt_peak_w,
        optical_valid=opt_peak_v,
        topo_mask=topo_mask,
        permanent_mask=perm_mask,
        hand=hand_arr,
        slope=slope_arr,
        builtup=builtup_arr,
        occurrence=occ_arr,
        is_peak=True,
        use_topo=use_topo,
        use_optical=use_optical,
        use_mmu=use_mmu,
        use_permanent=use_permanent,
    )

    # 6. Compute temporal dynamics
    temporal = compute_temporal_dynamics(
        water_pre=water_pre,
        water_peak=water_peak,
        permanent=perm_mask,
        pixel_size_m=PIXEL_SIZE_M,
    )

    flood_mask = temporal["flood"]
    water_pre_mask = temporal["water_pre"]
    water_peak_mask = temporal["water_peak"]

    # 5b. Sub-canopy flooded vegetation (double bounce) as a separate product layer.
    # Not part of the open-water mirror (task spec section 5); informational only.
    flooded_vegetation_mask = np.zeros(water_peak_mask.shape, dtype=np.uint8)
    if ablation_mode >= 2:
        fv = detect_flooded_vegetation(
            vv=vv_peak,
            vh=vh_peak,
            vv_ref=vv_pre,
            vh_ref=vh_pre,
            hand=hand_arr,
            slope=slope_arr,
            builtup=builtup_arr,
        )
        flooded_vegetation_mask = fv.astype(np.uint8)

    # 6b. AOI polygon boundary clipping (eliminates out-of-boundary predictions)
    aoi_geojson_path = data_dir / "vectors" / "aoi.geojson"
    if aoi_geojson_path.exists():
        try:
            aoi_gdf = gpd.read_file(aoi_geojson_path)
            aoi_id = str(row.get("aoi_id", ""))
            matched = aoi_gdf[aoi_gdf["aoi_id"] == aoi_id]
            if not matched.empty:
                geom = matched.to_crs(target_crs).geometry.values[0]
                flood_mask = clip_by_aoi(flood_mask, geom, target_transform, target_crs)
                water_pre_mask = clip_by_aoi(water_pre_mask, geom, target_transform, target_crs)
                water_peak_mask = clip_by_aoi(water_peak_mask, geom, target_transform, target_crs)
                flooded_vegetation_mask = clip_by_aoi(flooded_vegetation_mask, geom, target_transform, target_crs)
        except Exception as e:
            logger.warning(f"[{pair_id}] Failed to clip to AOI boundary: {e}")

    # 6c. Apply MMU to final flood mask in full pipeline mode (Mode 4)
    if ablation_mode == 4:
        flood_mask = apply_mmu(flood_mask, min_size=MMU_MIN_PIXELS).astype(np.uint8)
        flooded_vegetation_mask = apply_mmu(flooded_vegetation_mask, min_size=MMU_MIN_PIXELS).astype(np.uint8)

    # Recompute areas in hectares after clipping and MMU
    flood_ha = round(float(np.sum(flood_mask == 1) * PIXEL_SIZE_HA), 2)
    water_pre_ha = round(float(np.sum(water_pre_mask == 1) * PIXEL_SIZE_HA), 2)
    water_peak_ha = round(float(np.sum(water_peak_mask == 1) * PIXEL_SIZE_HA), 2)

    # 7. Write GeoTIFF prediction
    predictions_dir.mkdir(parents=True, exist_ok=True)
    out_tif = predictions_dir / f"{pair_id}_flood.tif"
    with rasterio.open(
        out_tif,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype=np.uint8,
        crs=target_crs,
        transform=target_transform,
        compress="deflate",
        nodata=0,
    ) as dst:
        dst.write(flood_mask, 1)

    # 7b. Write own water mask GeoTIFFs (served by the FastAPI service)
    water_masks_map = {
        "water_pre": water_pre_mask,
        "water_peak": water_peak_mask,
        "flooded_vegetation": flooded_vegetation_mask,
    }
    for water_layer in ("water_pre", "water_peak", "flooded_vegetation"):
        out_tif = predictions_dir / f"{pair_id}_{water_layer}.tif"
        with rasterio.open(
            out_tif,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype=np.uint8,
            crs=target_crs,
            transform=target_transform,
            compress="deflate",
            nodata=0,
        ) as dst:
            dst.write(water_masks_map[water_layer], 1)

    # 8. Strict Area Verification (< 2% difference between CSV and raster mask)
    raster_flood_px = int(np.sum(flood_mask == 1))
    raster_flood_ha = round(raster_flood_px * PIXEL_SIZE_HA, 2)
    diff = abs(flood_ha - raster_flood_ha)
    denom = max(raster_flood_ha, 1.0)
    diff_pct = (diff / denom) * 100.0
    if diff_pct >= 2.0:
        logger.warning(f"[{pair_id}] Area mismatch: CSV={flood_ha} ha, Raster={raster_flood_ha} ha ({diff_pct:.2f}%)")
    assert diff_pct < 2.0, f"Area verification failed for {pair_id}: {diff_pct:.2f}% >= 2.0%"

    logger.info(
        f"[{pair_id}] Done -> flood: {flood_ha} ha, pre: {water_pre_ha} ha, peak: {water_peak_ha} ha (diff={diff_pct:.4f}%)"
    )

    res = {
        "pair_id": pair_id,
        "flood_ha": flood_ha,
        "water_pre_ha": water_pre_ha,
        "water_peak_ha": water_peak_ha,
    }

    # Free temporary memory and trigger garbage collection
    del vv_pre, vh_pre, vv_peak, vh_peak
    if "aux_data" in locals():
        del aux_data
    del hand_arr, slope_arr, builtup_arr, occ_arr, topo_mask, perm_mask
    del opt_pre_w, opt_pre_v, opt_peak_w, opt_peak_v
    del water_pre, water_peak, temporal
    del flood_mask, water_pre_mask, water_peak_mask, flooded_vegetation_mask, water_masks_map
    gc.collect()

    return res


def run_prediction(
    pairs_csv_path: Path = Path("hydrowatch_amur/pairs.csv"),
    data_dir: Path = Path("hydrowatch_amur"),
    output_csv_path: Path = Path("submission.csv"),
    predictions_dir: Path = Path("predictions"),
    ablation_mode: int = 4,
    workers: int | None = None,
) -> pd.DataFrame:
    """Run inference over all pairs in pairs.csv and generate submission.csv."""
    pairs_df = pd.read_csv(pairs_csv_path)
    total_pairs = len(pairs_df)
    logger.info(f"Loaded {total_pairs} pairs from {pairs_csv_path}")

    if total_pairs == 0:
        sub_df = pd.DataFrame(columns=["pair_id", "flood_ha", "water_pre_ha", "water_peak_ha"])
        sub_df.to_csv(output_csv_path, index=False)
        return sub_df

    if workers is None:
        cpu_cores = os.cpu_count() or 1
        effective_workers = min(cpu_cores, total_pairs)
    elif workers <= 1:
        effective_workers = 1
    else:
        effective_workers = min(workers, total_pairs)

    records: list[dict[str, Any]] = []
    if effective_workers > 1:
        logger.info(f"Running parallel inference across {effective_workers} worker processes")
        tasks = [
            (idx, total_pairs, row, data_dir, predictions_dir, ablation_mode)
            for idx, row in pairs_df.iterrows()
        ]
        with ProcessPoolExecutor(max_workers=effective_workers) as executor:
            records = list(executor.map(_process_pair_worker, tasks))
    else:
        logger.info("Running sequential inference (1 worker)")
        for idx, row in pairs_df.iterrows():
            logger.info(f"Processing [{idx + 1}/{total_pairs}]: {row['pair_id']}")
            rec = process_pair(
                row=row,
                data_dir=data_dir,
                predictions_dir=predictions_dir,
                ablation_mode=ablation_mode,
            )
            records.append(rec)

    sub_df = pd.DataFrame(records)
    sub_df.to_csv(output_csv_path, index=False)
    logger.info(f"Successfully wrote {len(sub_df)} rows to {output_csv_path}")
    return sub_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate flood predictions and submission.csv")
    parser.add_argument("--pairs", type=Path, default=Path("hydrowatch_amur/pairs.csv"))
    parser.add_argument("--data_dir", type=Path, default=Path("hydrowatch_amur"))
    parser.add_argument("--output_csv", type=Path, default=Path("submission.csv"))
    parser.add_argument("--predictions_dir", type=Path, default=Path("predictions"))
    parser.add_argument("--ablation_mode", type=int, default=4, choices=[1, 2, 3, 4])
    parser.add_argument(
        "--workers",
        "--jobs",
        dest="workers",
        type=int,
        default=None,
        help="Number of worker processes for parallel batch inference (default: auto)",
    )
    args = parser.parse_args()

    run_prediction(
        pairs_csv_path=args.pairs,
        data_dir=args.data_dir,
        output_csv_path=args.output_csv,
        predictions_dir=args.predictions_dir,
        ablation_mode=args.ablation_mode,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
