import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import planetary_computer as pc
import pystac_client
import rasterio
from pyproj import Transformer
from rasterio.warp import Resampling, reproject
from rasterio.windows import from_bounds


def get_stac_catalog():
    return pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=pc.sign_inplace,
    )

def download_s1_raster(catalog, items, target_bounds, target_shape, target_transform, out_path):
    """
    Downloads and mosaics VV and VH from items, converts to dB, computes VV/VH ratio,
    and writes to out_path matching target grid (EPSG:32652, 10m).
    """
    height, width = target_shape
    vv_mosaic = np.full((height, width), np.nan, dtype=np.float32)
    vh_mosaic = np.full((height, width), np.nan, dtype=np.float32)

    left, bottom, right, top = target_bounds

    for item in items:
        # VV
        if "vv" in item.assets:
            vv_href = item.assets["vv"].href
            with rasterio.open(vv_href) as src:
                # Check intersection
                src_b = src.bounds
                if not (src_b.left >= right or src_b.right <= left or src_b.bottom >= top or src_b.top <= bottom):
                    win = from_bounds(left, bottom, right, top, src.transform)
                    data = src.read(1, window=win, out_shape=(height, width), resampling=Resampling.bilinear)
                    nodata = src.nodata if src.nodata is not None else -32768.0
                    mask = (data != nodata) & (~np.isnan(data)) & (data > 0)
                    vv_mosaic[mask] = data[mask]

        # VH
        if "vh" in item.assets:
            vh_href = item.assets["vh"].href
            with rasterio.open(vh_href) as src:
                src_b = src.bounds
                if not (src_b.left >= right or src_b.right <= left or src_b.bottom >= top or src_b.top <= bottom):
                    win = from_bounds(left, bottom, right, top, src.transform)
                    data = src.read(1, window=win, out_shape=(height, width), resampling=Resampling.bilinear)
                    nodata = src.nodata if src.nodata is not None else -32768.0
                    mask = (data != nodata) & (~np.isnan(data)) & (data > 0)
                    vh_mosaic[mask] = data[mask]

    # Convert linear power to dB
    vv_db = 10.0 * np.log10(np.maximum(vv_mosaic, 1e-6))
    vh_db = 10.0 * np.log10(np.maximum(vh_mosaic, 1e-6))

    # Missing values fill with plausible values / nan
    vv_db[np.isnan(vv_mosaic)] = -999.0
    vh_db[np.isnan(vh_mosaic)] = -999.0

    ratio_db = np.where((vv_db > -900) & (vh_db > -900), vv_db - vh_db, -999.0).astype(np.float32)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with rasterio.open(
        out_path,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=3,
        dtype=np.float32,
        crs='EPSG:32652',
        transform=target_transform,
        nodata=-999.0,
        compress='deflate',
    ) as dst:
        dst.write(vv_db.astype(np.float32), 1)
        dst.write(vh_db.astype(np.float32), 2)
        dst.write(ratio_db, 3)
        dst.set_band_description(1, 'VV')
        dst.set_band_description(2, 'VH')
        dst.set_band_description(3, 'VV_VH_ratio')

    print(f"  -> Saved {out_path} ({height}x{width}, 3 bands: VV, VH, ratio)")

def download_s2_raster(catalog, items, target_bounds, target_shape, target_transform, out_path):
    """
    Downloads S2 L2A bands (B03, B04, B08, B11) and computes water indices.
    """
    height, width = target_shape
    left, bottom, right, top = target_bounds

    bands_data = {
        'B03': np.full((height, width), np.nan, dtype=np.float32),
        'B04': np.full((height, width), np.nan, dtype=np.float32),
        'B08': np.full((height, width), np.nan, dtype=np.float32),
        'B11': np.full((height, width), np.nan, dtype=np.float32),
    }

    for item in items:
        for b_name in ['B03', 'B04', 'B08', 'B11']:
            asset_key = b_name.lower()
            if asset_key in item.assets:
                href = item.assets[asset_key].href
                with rasterio.open(href) as src:
                    # reprojection into target EPSG:32652 grid
                    data = np.full((height, width), np.nan, dtype=np.float32)
                    reproject(
                        source=rasterio.band(src, 1),
                        destination=data,
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=target_transform,
                        dst_crs='EPSG:32652',
                        resampling=Resampling.bilinear,
                        dst_nodata=np.nan,
                    )
                    mask = (~np.isnan(data)) & (data > 0)
                    bands_data[b_name][mask] = data[mask] / 10000.0  # Surface reflectance [0, 1]

    b3 = bands_data['B03']
    b4 = bands_data['B04']
    b8 = bands_data['B08']
    b11 = bands_data['B11']

    # Compute indices
    denom_ndwi = np.maximum(b3 + b8, 1e-6)
    ndwi = np.where(~np.isnan(b3) & ~np.isnan(b8), (b3 - b8) / denom_ndwi, -999.0).astype(np.float32)

    denom_mndwi = np.maximum(b3 + b11, 1e-6)
    mndwi = np.where(~np.isnan(b3) & ~np.isnan(b11), (b3 - b11) / denom_mndwi, -999.0).astype(np.float32)

    denom_ndvi = np.maximum(b8 + b4, 1e-6)
    ndvi = np.where(~np.isnan(b8) & ~np.isnan(b4), (b8 - b4) / denom_ndvi, -999.0).astype(np.float32)

    # AWEIsh = B03 + 2.5*B02 - 1.5*(B08 + B11) - 0.25*B12 (approx with B03, B04, B08, B11)
    # Standard AWEIsh: 4*(Green - SWIR1) - (0.25*NIR + 2.75*SWIR2)
    aweish = np.where(~np.isnan(b3) & ~np.isnan(b11) & ~np.isnan(b8),
                      (b3 - b11) - 0.25 * b8, -999.0).astype(np.float32)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with rasterio.open(
        out_path,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=8,
        dtype=np.float32,
        crs='EPSG:32652',
        transform=target_transform,
        nodata=-999.0,
        compress='deflate',
    ) as dst:
        dst.write(np.nan_to_num(b3, nan=-999.0).astype(np.float32), 1)
        dst.write(np.nan_to_num(b4, nan=-999.0).astype(np.float32), 2)
        dst.write(np.nan_to_num(b8, nan=-999.0).astype(np.float32), 3)
        dst.write(np.nan_to_num(b11, nan=-999.0).astype(np.float32), 4)
        dst.write(ndwi, 5)
        dst.write(mndwi, 6)
        dst.write(ndvi, 7)
        dst.write(aweish, 8)
        dst.set_band_description(1, 'B3')
        dst.set_band_description(2, 'B4')
        dst.set_band_description(3, 'B8')
        dst.set_band_description(4, 'B11')
        dst.set_band_description(5, 'NDWI')
        dst.set_band_description(6, 'MNDWI')
        dst.set_band_description(7, 'NDVI')
        dst.set_band_description(8, 'AWEIsh')

    print(f"  -> Saved {out_path} (8 bands)")

def process_all():
    catalog = get_stac_catalog()
    pairs = pd.read_csv("hydrowatch_amur/pairs.csv")
    transformer = Transformer.from_crs("EPSG:32652", "EPSG:4326", always_xy=True)

    for idx, row in pairs.iterrows():
        ref_tif = os.path.join("hydrowatch_amur", row.reference_mask)
        with rasterio.open(ref_tif) as src:
            target_bounds = src.bounds
            target_shape = src.shape
            target_transform = src.transform

        minx, miny = transformer.transform(target_bounds.left, target_bounds.bottom)
        maxx, maxy = transformer.transform(target_bounds.right, target_bounds.top)
        bbox = [minx, miny, maxx, maxy]

        rasters_dir = os.path.join("hydrowatch_amur", row.rasters_dir)
        print("\n==========================================")
        print(f"[{idx+1}/{len(pairs)}] Processing {row.pair_id}...")

        # 1. S1 Pre
        s1_pre_path = os.path.join(rasters_dir, f"S1_pre_{row.date_pre_sar}.tif")
        if not os.path.exists(s1_pre_path):
            d_pre = datetime.strptime(row.date_pre_sar, "%Y-%m-%d")
            dt_str = f"{(d_pre - timedelta(days=1)).strftime('%Y-%m-%d')}/{(d_pre + timedelta(days=1)).strftime('%Y-%m-%d')}"
            items = [item for item in catalog.search(
                collections=["sentinel-1-rtc"],
                bbox=bbox,
                datetime=dt_str,
            ).items() if item.properties.get("sat:relative_orbit") == int(row.relative_orbit)]
            print(f"Fetching S1 Pre ({row.date_pre_sar}, orbit {row.relative_orbit}): {len(items)} items")
            if items:
                download_s1_raster(catalog, items, target_bounds, target_shape, target_transform, s1_pre_path)
        else:
            print(f"S1 Pre already exists: {s1_pre_path}")

        # 2. S1 Peak
        s1_peak_path = os.path.join(rasters_dir, f"S1_peak_{row.date_peak_sar}.tif")
        if not os.path.exists(s1_peak_path):
            d_peak = datetime.strptime(row.date_peak_sar, "%Y-%m-%d")
            dt_str = f"{(d_peak - timedelta(days=1)).strftime('%Y-%m-%d')}/{(d_peak + timedelta(days=1)).strftime('%Y-%m-%d')}"
            items = [item for item in catalog.search(
                collections=["sentinel-1-rtc"],
                bbox=bbox,
                datetime=dt_str,
            ).items() if item.properties.get("sat:relative_orbit") == int(row.relative_orbit)]
            print(f"Fetching S1 Peak ({row.date_peak_sar}, orbit {row.relative_orbit}): {len(items)} items")
            if items:
                download_s1_raster(catalog, items, target_bounds, target_shape, target_transform, s1_peak_path)
        else:
            print(f"S1 Peak already exists: {s1_peak_path}")

        # 3. Sentinel-2 (if applicable)
        if pd.notna(row.date_pre_opt):
            s2_pre_path = os.path.join(rasters_dir, f"SENTINEL2_pre_{row.date_pre_opt}.tif")
            if not os.path.exists(s2_pre_path):
                d_opt_pre = datetime.strptime(row.date_pre_opt, "%Y-%m-%d")
                dt_str = f"{(d_opt_pre - timedelta(days=1)).strftime('%Y-%m-%d')}/{(d_opt_pre + timedelta(days=1)).strftime('%Y-%m-%d')}"
                items = list(catalog.search(
                    collections=["sentinel-2-l2a"],
                    bbox=bbox,
                    datetime=dt_str,
                ).items())
                print(f"Fetching S2 Pre ({row.date_pre_opt}): {len(items)} items")
                if items:
                    download_s2_raster(catalog, items, target_bounds, target_shape, target_transform, s2_pre_path)
            else:
                print(f"S2 Pre already exists: {s2_pre_path}")

        if pd.notna(row.date_peak_opt):
            s2_peak_path = os.path.join(rasters_dir, f"SENTINEL2_peak_{row.date_peak_opt}.tif")
            if not os.path.exists(s2_peak_path):
                d_opt_peak = datetime.strptime(row.date_peak_opt, "%Y-%m-%d")
                dt_str = f"{(d_opt_peak - timedelta(days=1)).strftime('%Y-%m-%d')}/{(d_opt_peak + timedelta(days=1)).strftime('%Y-%m-%d')}"
                items = list(catalog.search(
                    collections=["sentinel-2-l2a"],
                    bbox=bbox,
                    datetime=dt_str,
                ).items())
                print(f"Fetching S2 Peak ({row.date_peak_opt}): {len(items)} items")
                if items:
                    download_s2_raster(catalog, items, target_bounds, target_shape, target_transform, s2_peak_path)
            else:
                print(f"S2 Peak already exists: {s2_peak_path}")

    print("\nAll scenes processed successfully!")

if __name__ == "__main__":
    process_all()
