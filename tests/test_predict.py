"""Tests for predict module and end-to-end inference pipeline."""

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin

from src.predict import main as predict_main
from src.predict import process_pair, run_prediction


@pytest.fixture
def synthetic_pair_env(tmp_path):
    data_dir = tmp_path / "hydrowatch_amur"
    rasters_dir = data_dir / "rasters" / "pair1"
    ref_dir = data_dir / "reference_masks"
    rasters_dir.mkdir(parents=True)
    ref_dir.mkdir(parents=True)

    transform = from_origin(127.0, 50.0, 10.0, 10.0)
    crs = "EPSG:32652"
    shape = (30, 30)

    # 1. Reference mask (10m res, 30x30)
    ref_tif = ref_dir / "ref_pair1.tif"
    ref_data = np.zeros(shape, dtype=np.uint8)
    ref_data[10:20, 10:20] = 1  # 100 pixels flood
    with rasterio.open(
        ref_tif,
        "w",
        driver="GTiff",
        height=30,
        width=30,
        count=1,
        dtype=np.uint8,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(ref_data, 1)

    # 2. S1 pre & peak
    s1_pre_tif = rasters_dir / "S1_pre_20200101.tif"
    s1_peak_tif = rasters_dir / "S1_peak_20200115.tif"

    s1_pre = np.full((2, 30, 30), -12.0, dtype=np.float32)
    s1_pre[1, :, :] = -18.0  # VH

    s1_peak = np.full((2, 30, 30), -12.0, dtype=np.float32)
    s1_peak[0, 10:20, 10:20] = -22.0  # VV drop: flooded
    s1_peak[1, :, :] = -20.0  # VH

    for path, data in [(s1_pre_tif, s1_pre), (s1_peak_tif, s1_peak)]:
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=30,
            width=30,
            count=2,
            dtype=np.float32,
            crs=crs,
            transform=transform,
        ) as dst:
            dst.write(data)

    # 3. AUX terrain gsw (6 bands)
    aux_tif = rasters_dir / "AUX_terrain_gsw.tif"
    aux_data = np.zeros((6, 30, 30), dtype=np.float32)
    aux_data[0, :, :] = 1.0  # slope
    aux_data[1, :, :] = 5.0  # hand
    aux_data[2, :, :] = 0.0  # gsw occurrence
    aux_data[5, :, :] = 0.0  # builtup
    with rasterio.open(
        aux_tif,
        "w",
        driver="GTiff",
        height=30,
        width=30,
        count=6,
        dtype=np.float32,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(aux_data)

    # 4. S2 optical pre & peak (8 bands)
    s2_data = np.full((8, 30, 30), 0.0, dtype=np.float32)
    s2_data[5, :, :] = 0.3  # MNDWI
    s2_data[6, :, :] = 0.1  # NDVI
    s2_data[7, :, :] = 0.2  # AWEIsh
    for name in ["SENTINEL2_pre_20200101.tif", "SENTINEL2_peak_20200115.tif"]:
        with rasterio.open(
            rasters_dir / name,
            "w",
            driver="GTiff",
            height=30,
            width=30,
            count=8,
            dtype=np.float32,
            crs=crs,
            transform=transform,
        ) as dst:
            dst.write(s2_data)

    row = pd.Series(
        {
            "pair_id": "pair_test",
            "rasters_dir": "rasters/pair1",
            "reference_mask": "reference_masks/ref_pair1.tif",
        }
    )

    return {
        "data_dir": data_dir,
        "row": row,
        "predictions_dir": tmp_path / "predictions",
    }


def test_process_pair_all_ablations(synthetic_pair_env):
    data_dir = synthetic_pair_env["data_dir"]
    row = synthetic_pair_env["row"]
    pred_dir = synthetic_pair_env["predictions_dir"]

    # Test ablation modes 1, 2, 3, 4
    for mode in [1, 2, 3, 4]:
        res = process_pair(row, data_dir, pred_dir, ablation_mode=mode)
        assert res["pair_id"] == "pair_test"
        assert res["flood_ha"] >= 0
        assert res["water_peak_ha"] >= 0
        assert (pred_dir / "pair_test_flood.tif").exists()
        assert (pred_dir / "pair_test_water_pre.tif").exists()
        assert (pred_dir / "pair_test_water_peak.tif").exists()


def test_run_prediction_and_main(synthetic_pair_env, tmp_path, monkeypatch):
    data_dir = synthetic_pair_env["data_dir"]
    row = synthetic_pair_env["row"]
    pred_dir = synthetic_pair_env["predictions_dir"]

    pairs_csv = data_dir / "pairs.csv"
    pd.DataFrame([row.to_dict()]).to_csv(pairs_csv, index=False)
    sub_csv = tmp_path / "sub.csv"

    sub_df = run_prediction(
        pairs_csv_path=pairs_csv,
        data_dir=data_dir,
        output_csv_path=sub_csv,
        predictions_dir=pred_dir,
        ablation_mode=4,
    )
    assert len(sub_df) == 1
    assert sub_csv.exists()

    # CLI main
    sub_cli_csv = tmp_path / "sub_cli.csv"
    monkeypatch.setattr(
        "sys.argv",
        [
            "predict.py",
            "--pairs",
            str(pairs_csv),
            "--data_dir",
            str(data_dir),
            "--output_csv",
            str(sub_cli_csv),
            "--predictions_dir",
            str(pred_dir),
            "--ablation_mode",
            "4",
        ],
    )
    predict_main()
    assert sub_cli_csv.exists()
