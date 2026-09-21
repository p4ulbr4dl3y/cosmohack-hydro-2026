"""End-to-end prediction and inference pipeline for HydroWatch Amur.

Processes all 11 pairs in hydrowatch_amur/pairs.csv, outputs:
  - submission.csv with columns [pair_id, flood_ha, water_pre_ha, water_peak_ha]
  - predictions/<pair_id>_flood.tif (GeoTIFF, uint8, 0/1, EPSG:32652)
Verifies that the CSV areas match raster pixel counts within 2%.
"""

from __future__ import annotations

import argparse
import glob
import logging
import sys
from pathlib import Path

# Ensure repository root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any

import numpy as np
import pandas as pd
import rasterio

from src.segmentation import (
    load_aux_priors,
    segment_optical,
    segment_water,
)
from src.temporal import compute_temporal_dynamics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


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
    ref_tif_path = data_dir / str(row["reference_mask"])

    # Target geometry is defined by the reference raster grid (EPSG:32652, 10m)
    with rasterio.open(ref_tif_path) as ref_src:
        target_shape = ref_src.shape
        target_transform = ref_src.transform
        target_crs = ref_src.crs

    height, width = target_shape

    # 1. Load Sentinel-1 rasters
    s1_pre_files = sorted(glob.glob(str(rasters_dir / "S1_pre_*.tif")))
    s1_peak_files = sorted(glob.glob(str(rasters_dir / "S1_peak_*.tif")))

    if not s1_pre_files or not s1_peak_files:
        raise FileNotFoundError(f"Missing S1 pre/peak rasters in {rasters_dir}")

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
        pixel_size_m=10.0,
    )

    flood_mask = temporal["flood"]
    flood_ha = temporal["flood_ha"]
    water_pre_ha = temporal["water_pre_ha"]
    water_peak_ha = temporal["water_peak_ha"]

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

    # 8. Strict Area Verification (< 2% difference between CSV and raster mask)
    raster_flood_px = int(np.sum(flood_mask == 1))
    raster_flood_ha = round(raster_flood_px * 0.01, 2)
    diff = abs(flood_ha - raster_flood_ha)
    denom = max(raster_flood_ha, 1.0)
    diff_pct = (diff / denom) * 100.0
    if diff_pct >= 2.0:
        logger.warning(f"[{pair_id}] Area mismatch: CSV={flood_ha} ha, Raster={raster_flood_ha} ha ({diff_pct:.2f}%)")
    assert diff_pct < 2.0, f"Area verification failed for {pair_id}: {diff_pct:.2f}% >= 2.0%"

    logger.info(
        f"[{pair_id}] Done -> flood: {flood_ha} ha, pre: {water_pre_ha} ha, peak: {water_peak_ha} ha (diff={diff_pct:.4f}%)"
    )

    return {
        "pair_id": pair_id,
        "flood_ha": flood_ha,
        "water_pre_ha": water_pre_ha,
        "water_peak_ha": water_peak_ha,
    }


def run_prediction(
    pairs_csv_path: Path = Path("hydrowatch_amur/pairs.csv"),
    data_dir: Path = Path("hydrowatch_amur"),
    output_csv_path: Path = Path("submission.csv"),
    predictions_dir: Path = Path("predictions"),
    ablation_mode: int = 4,
) -> pd.DataFrame:
    """Run inference over all pairs in pairs.csv and generate submission.csv."""
    pairs_df = pd.read_csv(pairs_csv_path)
    logger.info(f"Loaded {len(pairs_df)} pairs from {pairs_csv_path}")

    records: list[dict[str, Any]] = []
    for idx, row in pairs_df.iterrows():
        logger.info(f"Processing [{idx + 1}/{len(pairs_df)}]: {row['pair_id']}")
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
    args = parser.parse_args()

    run_prediction(
        pairs_csv_path=args.pairs,
        data_dir=args.data_dir,
        output_csv_path=args.output_csv,
        predictions_dir=args.predictions_dir,
        ablation_mode=args.ablation_mode,
    )


if __name__ == "__main__":
    main()
