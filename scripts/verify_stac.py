import os
from datetime import datetime, timedelta

import pandas as pd
import planetary_computer as pc
import pystac_client
import rasterio
from pyproj import Transformer


def verify_all_pairs():
    pairs_path = "hydrowatch_amur/pairs.csv"
    pairs = pd.read_csv(pairs_path)

    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=pc.sign_inplace,
    )

    transformer = Transformer.from_crs("EPSG:32652", "EPSG:4326", always_xy=True)

    for idx, row in pairs.iterrows():
        ref_tif = os.path.join("hydrowatch_amur", row.reference_mask)
        with rasterio.open(ref_tif) as src:
            left, bottom, right, top = src.bounds
            target_shape = src.shape

        minx, miny = transformer.transform(left, bottom)
        maxx, maxy = transformer.transform(right, top)
        bbox = [minx, miny, maxx, maxy]

        # S1 Pre
        d_pre = datetime.strptime(row.date_pre_sar, "%Y-%m-%d")
        dt_pre_str = f"{(d_pre - timedelta(days=1)).strftime('%Y-%m-%d')}/{(d_pre + timedelta(days=1)).strftime('%Y-%m-%d')}"
        s1_pre_items = list(catalog.search(
            collections=["sentinel-1-rtc"],
            bbox=bbox,
            datetime=dt_pre_str,
        ).items())

        # S1 Peak
        d_peak = datetime.strptime(row.date_peak_sar, "%Y-%m-%d")
        dt_peak_str = f"{(d_peak - timedelta(days=1)).strftime('%Y-%m-%d')}/{(d_peak + timedelta(days=1)).strftime('%Y-%m-%d')}"
        s1_peak_items = list(catalog.search(
            collections=["sentinel-1-rtc"],
            bbox=bbox,
            datetime=dt_peak_str,
        ).items())

        print(f"[{idx+1}/11] {row.pair_id}:")
        print(f"  Target bounds: ({left}, {bottom}, {right}, {top}), shape: {target_shape}")
        print(f"  S1 Pre ({row.date_pre_sar}): found {len(s1_pre_items)} RTC items (relative_orbit={row.relative_orbit})")
        for item in s1_pre_items:
            print(f"    - {item.id}, orbit={item.properties.get('sat:relative_orbit')}")

        print(f"  S1 Peak ({row.date_peak_sar}): found {len(s1_peak_items)} RTC items")
        for item in s1_peak_items:
            print(f"    - {item.id}, orbit={item.properties.get('sat:relative_orbit')}")

if __name__ == "__main__":
    verify_all_pairs()
