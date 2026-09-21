"""Download and reproject Sentinel-2 L2A scenes via Planetary Computer STAC."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import planetary_computer as pc
import pystac_client
import rasterio
from pyproj import Transformer
from rasterio.warp import Resampling, reproject


def get_stac_catalog():
    return pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=pc.sign_inplace,
    )


def download_s2_raster(catalog, items, target_bounds, target_shape, target_transform, out_path):
    height, width = target_shape
    band_names = ["B02", "B03", "B04", "B08", "B11", "B12"]
    bands_data = {b: np.full((height, width), np.nan, dtype=np.float32) for b in band_names}
    scl_data = np.full((height, width), 255, dtype=np.uint8)

    print(f"Downloading {len(items)} S2 scene(s) into {out_path}...")
    for item_idx, item in enumerate(items):
        print(f"  Item {item_idx + 1}/{len(items)}: {item.id}")
        for b_name in band_names:
            if b_name not in item.assets:
                continue
            href = item.assets[b_name].href
            with (
                rasterio.Env(GDAL_HTTP_TIMEOUT=30, GDAL_HTTP_MAX_RETRY=3, VSI_CACHE=True),
                rasterio.open(href) as src,
            ):
                data = np.full((height, width), np.nan, dtype=np.float32)
                reproject(
                    source=rasterio.band(src, 1),
                    destination=data,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=target_transform,
                    dst_crs="EPSG:32652",
                    resampling=Resampling.bilinear,
                    dst_nodata=np.nan,
                )
                mask = (~np.isnan(data)) & (data > 0)
                existing = ~np.isnan(bands_data[b_name])
                update_mask = mask & (~existing)
                bands_data[b_name][update_mask] = data[update_mask] / 10000.0

        if "SCL" in item.assets:
            with (
                rasterio.Env(GDAL_HTTP_TIMEOUT=30, GDAL_HTTP_MAX_RETRY=3, VSI_CACHE=True),
                rasterio.open(item.assets["SCL"].href) as src,
            ):
                scl = np.full((height, width), 255, dtype=np.uint8)
                reproject(
                    source=rasterio.band(src, 1),
                    destination=scl,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=target_transform,
                    dst_crs="EPSG:32652",
                    resampling=Resampling.nearest,
                )
                scl_mask = scl != 255
                scl_data[scl_mask] = scl[scl_mask]

    b2 = bands_data["B02"]
    b3 = bands_data["B03"]
    b4 = bands_data["B04"]
    b8 = bands_data["B08"]
    b11 = bands_data["B11"]
    b12 = bands_data["B12"]

    scl_invalid = np.isin(scl_data, [3, 8, 9, 10, 11])

    def _valid(*arrs):
        m = np.ones((height, width), dtype=bool)
        for a in arrs:
            m &= ~np.isnan(a)
        return m & ~scl_invalid

    denom_ndwi = np.maximum(b3 + b8, 1e-6)
    ndwi = np.where(_valid(b3, b8), (b3 - b8) / denom_ndwi, -999.0).astype(np.float32)

    denom_mndwi = np.maximum(b3 + b11, 1e-6)
    mndwi = np.where(_valid(b3, b11), (b3 - b11) / denom_mndwi, -999.0).astype(np.float32)

    denom_ndvi = np.maximum(b8 + b4, 1e-6)
    ndvi = np.where(_valid(b8, b4), (b8 - b4) / denom_ndvi, -999.0).astype(np.float32)

    aweish = np.where(
        _valid(b2, b3, b8, b11, b12),
        b2 + 2.5 * b3 - 1.5 * (b8 + b11) - 0.25 * b12,
        -999.0,
    ).astype(np.float32)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with rasterio.open(
        out_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=8,
        dtype=np.float32,
        crs="EPSG:32652",
        transform=target_transform,
        nodata=-999.0,
        compress="deflate",
    ) as dst:
        dst.write(np.nan_to_num(b3, nan=-999.0).astype(np.float32), 1)
        dst.write(np.nan_to_num(b4, nan=-999.0).astype(np.float32), 2)
        dst.write(np.nan_to_num(b8, nan=-999.0).astype(np.float32), 3)
        dst.write(np.nan_to_num(b11, nan=-999.0).astype(np.float32), 4)
        dst.write(ndwi, 5)
        dst.write(mndwi, 6)
        dst.write(ndvi, 7)
        dst.write(aweish, 8)
        dst.set_band_description(1, "B3")
        dst.set_band_description(2, "B4")
        dst.set_band_description(3, "B8")
        dst.set_band_description(4, "B11")
        dst.set_band_description(5, "NDWI")
        dst.set_band_description(6, "MNDWI")
        dst.set_band_description(7, "NDVI")
        dst.set_band_description(8, "AWEIsh")

    valid_cnt = np.count_nonzero(mndwi != -999.0)
    print(f"Saved {out_path} (valid pixels: {valid_cnt}/{height * width})")


def fetch_optical_scenes(
    pairs_csv_path: str | Path = "hydrowatch_amur/pairs.csv",
    data_dir: str | Path = "hydrowatch_amur",
    pair_id: str | None = None,
) -> None:
    catalog = get_stac_catalog()
    pairs = pd.read_csv(pairs_csv_path)
    if pair_id:
        pairs = pairs[pairs["pair_id"] == pair_id]
        if pairs.empty:
            print(f"Error: pair_id '{pair_id}' not found in {pairs_csv_path}")
            return

    transformer = Transformer.from_crs("EPSG:32652", "EPSG:4326", always_xy=True)
    data_dir = Path(data_dir)

    for _idx, row in pairs.iterrows():
        ref_tif = (
            Path(data_dir).parent / str(row.reference_mask)
            if not (data_dir / str(row.reference_mask)).exists()
            else data_dir / str(row.reference_mask)
        )
        with rasterio.open(ref_tif) as src:
            target_bounds = src.bounds
            target_shape = src.shape
            target_transform = src.transform

        minx, miny = transformer.transform(target_bounds.left, target_bounds.bottom)
        maxx, maxy = transformer.transform(target_bounds.right, target_bounds.top)
        bbox = [minx, miny, maxx, maxy]

        rasters_dir = (
            Path(data_dir).parent / str(row.rasters_dir)
            if not (data_dir / str(row.rasters_dir)).exists()
            else data_dir / str(row.rasters_dir)
        )

        if pd.notna(row.date_pre_opt):
            s2_pre_path = os.path.join(rasters_dir, f"SENTINEL2_pre_{row.date_pre_opt}.tif")
            skip = False
            if os.path.exists(s2_pre_path):
                with rasterio.open(s2_pre_path) as chk:
                    m = chk.read(6)
                    if np.count_nonzero((m != -999.0) & np.isfinite(m)) > 0:
                        print(f"[{row.pair_id}] Already valid S2 pre: {s2_pre_path}")
                        skip = True
            if not skip:
                d_opt_pre = datetime.strptime(row.date_pre_opt, "%Y-%m-%d")
                dt_str = (
                    f"{(d_opt_pre - timedelta(days=1)).strftime('%Y-%m-%d')}/"
                    f"{(d_opt_pre + timedelta(days=1)).strftime('%Y-%m-%d')}"
                )
                items = list(catalog.search(collections=["sentinel-2-l2a"], bbox=bbox, datetime=dt_str).items())
                print(f"[{row.pair_id}] Found {len(items)} items for S2 pre {row.date_pre_opt}")
                if items:
                    download_s2_raster(catalog, items, target_bounds, target_shape, target_transform, s2_pre_path)

        if pd.notna(row.date_peak_opt):
            s2_peak_path = os.path.join(rasters_dir, f"SENTINEL2_peak_{row.date_peak_opt}.tif")
            skip = False
            if os.path.exists(s2_peak_path):
                with rasterio.open(s2_peak_path) as chk:
                    m = chk.read(6)
                    if np.count_nonzero((m != -999.0) & np.isfinite(m)) > 0:
                        print(f"[{row.pair_id}] Already valid S2 peak: {s2_peak_path}")
                        skip = True
            if not skip:
                d_opt_peak = datetime.strptime(row.date_peak_opt, "%Y-%m-%d")
                dt_str = (
                    f"{(d_opt_peak - timedelta(days=1)).strftime('%Y-%m-%d')}/"
                    f"{(d_opt_peak + timedelta(days=1)).strftime('%Y-%m-%d')}"
                )
                items = list(catalog.search(collections=["sentinel-2-l2a"], bbox=bbox, datetime=dt_str).items())
                print(f"[{row.pair_id}] Found {len(items)} items for S2 peak {row.date_peak_opt}")
                if items:
                    download_s2_raster(catalog, items, target_bounds, target_shape, target_transform, s2_peak_path)


def main():
    fetch_optical_scenes()


if __name__ == "__main__":
    main()
