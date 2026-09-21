import os

import pandas as pd
import rasterio


def inspect():
    base_dir = "hydrowatch_amur"
    pairs = pd.read_csv(os.path.join(base_dir, "pairs.csv"))
    print(f"Total pairs: {len(pairs)}")
    print(pairs[["pair_id", "aoi_id", "event_id", "date_pre_sar", "date_peak_sar", "aoi_km2"]])

    os.path.join(base_dir, "reference_masks")
    print("\n--- Inspecting Reference Masks ---")
    for row in pairs.itertuples():
        ref_tif = os.path.join(base_dir, row.reference_mask)
        if os.path.exists(ref_tif):
            with rasterio.open(ref_tif) as src:
                print(f"{row.pair_id}: shape={src.shape}, count={src.count}, crs={src.crs}, bounds={src.bounds}, res={src.res}")
        else:
            print(f"Missing: {ref_tif}")

    print("\n--- Inspecting AUX rasters ---")
    for row in pairs.itertuples():
        aux_tif = os.path.join(base_dir, row.rasters_dir, "AUX_terrain_gsw.tif")
        if os.path.exists(aux_tif):
            with rasterio.open(aux_tif) as src:
                print(f"{row.pair_id} AUX: shape={src.shape}, count={src.count}, crs={src.crs}, res={src.res}")
                src.tags()
                descriptions = [src.descriptions[i] for i in range(src.count)]
                print(f"  bands descriptions: {descriptions}")
                break

if __name__ == "__main__":
    inspect()
