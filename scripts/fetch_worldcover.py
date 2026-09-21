"""Fetch ESA WorldCover v200 cropland masks for every AOI.

Downloads the WorldCover COG tiles (10 m) via the Microsoft Planetary Computer
STAC API and clips/reprojects the cropland class (v200 class code 40) onto each
pair's native Sentinel-1 grid, writing

    hydrowatch_amur/rasters/<event>/<aoi>/CROPLAND_worldcover.tif

as a uint8 0/1 mask. The resulting masks are consumed by
``src.service.data_loader`` to stratify the flooded area into built-up,
cropland and other natural land.

Usage:
    uv run python -m scripts.fetch_worldcover            # all pairs
    uv run python -m scripts.fetch_worldcover --force    # overwrite existing
"""

from __future__ import annotations

import argparse
import glob
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import planetary_computer as pc
import pystac_client
import rasterio
from rasterio.warp import Resampling
from rasterio.windows import from_bounds

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CROPLAND_CLASS = 40
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"


def _worldcover_cropland_on_grid(bounds: tuple[float, float, float, float], shape, transform, crs) -> np.ndarray:
    """Return a 0/1 cropland mask reprojected onto the requested target grid."""
    height, width = shape
    left, bottom, right, top = bounds

    catalog = pystac_client.Client.open(STAC_URL, modifier=pc.sign_inplace)
    items = list(catalog.search(collections=["esa-worldcover"], bbox=[left, bottom, right, top]).items())
    if not items:
        raise RuntimeError(f"No ESA WorldCover tiles cover bbox {bounds}")

    result = np.zeros((height, width), dtype=np.uint8)
    for item in items:
        href = item.assets["map"].href
        with rasterio.open(href) as src:
            src_b = src.bounds
            if src_b.left >= right or src_b.right <= left or src_b.bottom >= top or src_b.top <= bottom:
                continue
            window = from_bounds(left, bottom, right, top, src.transform)
            data = src.read(1, window=window, out_shape=(height, width), resampling=Resampling.nearest)
            result = np.where(data == CROPLAND_CLASS, np.uint8(1), result)

    return result


def fetch_pair(row: pd.Series, data_dir: Path, force: bool = False) -> Path | None:
    """Fetch the cropland mask for a single pair; return its path (or None)."""
    pair_id = str(row["pair_id"])
    rasters_dir = data_dir / str(row["rasters_dir"])
    out_path = rasters_dir / "CROPLAND_worldcover.tif"

    if out_path.exists() and not force:
        logger.info(f"[{pair_id}] Cropland mask already present: {out_path}")
        return out_path

    s1_pre = sorted(glob.glob(str(rasters_dir / "S1_pre_*.tif")))
    if not s1_pre:
        logger.warning(f"[{pair_id}] No S1_pre raster; cannot derive native grid, skipping")
        return None

    with rasterio.open(s1_pre[0]) as src:
        target_shape = src.shape
        target_transform = src.transform
        target_crs = src.crs

        from rasterio.warp import transform_bounds

        bounds_4326 = transform_bounds(target_crs, "EPSG:4326", *src.bounds)

    mask = _worldcover_cropland_on_grid(bounds_4326, target_shape, target_transform, target_crs)

    rasters_dir.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        out_path,
        "w",
        driver="GTiff",
        height=target_shape[0],
        width=target_shape[1],
        count=1,
        dtype=np.uint8,
        crs=target_crs,
        transform=target_transform,
        compress="deflate",
        nodata=0,
    ) as dst:
        dst.write(mask, 1)

    pct = 100.0 * float(mask.sum()) / mask.size
    logger.info(f"[{pair_id}] Wrote {out_path} (cropland {pct:.2f}% of AOI)")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch ESA WorldCover cropland masks for all AOIs")
    parser.add_argument("--pairs", type=Path, default=Path("hydrowatch_amur/pairs.csv"))
    parser.add_argument("--data-dir", type=Path, default=Path("hydrowatch_amur"))
    parser.add_argument("--force", action="store_true", help="Overwrite existing masks")
    args = parser.parse_args()

    pairs_df = pd.read_csv(args.pairs)
    for idx, row in pairs_df.iterrows():
        logger.info(f"[{idx + 1}/{len(pairs_df)}] {row['pair_id']}")
        try:
            fetch_pair(row, args.data_dir, force=args.force)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"[{row['pair_id']}] Failed: {exc}")


if __name__ == "__main__":
    main()
