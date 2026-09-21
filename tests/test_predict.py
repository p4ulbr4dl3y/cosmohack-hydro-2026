"""Tests for predict module and end-to-end inference pipeline."""

import runpy

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Polygon

from src.predict import main as predict_main
from src.predict import process_pair, read_sar_bands, run_prediction
from src.predict import resolve_orbit_pass as predict_resolve_orbit_pass


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
        # Sub-canopy flooded vegetation is always emitted as a separate layer
        assert (pred_dir / "pair_test_flooded_vegetation.tif").exists()
        with rasterio.open(pred_dir / "pair_test_flooded_vegetation.tif") as src:
            fv = src.read(1)
        assert fv.dtype == np.uint8
        assert set(np.unique(fv)).issubset({0, 1})


def test_flooded_vegetation_layer_emitted_separately(synthetic_pair_env):
    """Sub-canopy flooded vegetation is a distinct product layer, not merged in."""
    data_dir = synthetic_pair_env["data_dir"]
    row = synthetic_pair_env["row"]
    pred_dir = synthetic_pair_env["predictions_dir"]

    res = process_pair(row, data_dir, pred_dir, ablation_mode=4)
    fv_path = pred_dir / "pair_test_flooded_vegetation.tif"
    assert fv_path.exists()

    with rasterio.open(pred_dir / "pair_test_flood.tif") as flood_src, rasterio.open(fv_path) as fv_src:
        flood_src.read(1)
        fv_src.read(1)
        # Same grid as the flood product
        assert flood_src.transform == fv_src.transform
        assert flood_src.crs == fv_src.crs

    # The returned summary carries only the open-water areas; flooded vegetation
    # is deliberately excluded from flood_ha / water_peak_ha.
    assert "flooded_vegetation_ha" not in res


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


def test_process_pair_missing_s1_rasters_raises(synthetic_pair_env):
    """Missing S1 pre/peak rasters raises FileNotFoundError (line 63)."""
    empty_rasters = synthetic_pair_env["data_dir"] / "rasters" / "empty_pair"
    empty_rasters.mkdir(parents=True, exist_ok=True)
    bad_row = pd.Series(
        {
            "pair_id": "empty_pair",
            "rasters_dir": "rasters/empty_pair",
            "reference_mask": "reference_masks/ref_pair1.tif",
        }
    )
    with pytest.raises(FileNotFoundError, match="Missing S1 pre/peak rasters"):
        process_pair(bad_row, synthetic_pair_env["data_dir"], synthetic_pair_env["predictions_dir"])


def test_process_pair_no_reference_mask_fallback(synthetic_pair_env):
    """Reference mask non-existent derives geometry from s1_pre (lines 72-75)."""
    row = synthetic_pair_env["row"].copy()
    row["pair_id"] = "no_ref_pair"
    row["reference_mask"] = "reference_masks/non_existent.tif"
    res = process_pair(row, synthetic_pair_env["data_dir"], synthetic_pair_env["predictions_dir"], ablation_mode=1)
    assert res["pair_id"] == "no_ref_pair"
    assert (synthetic_pair_env["predictions_dir"] / "no_ref_pair_flood.tif").exists()


def test_process_pair_geometry_comes_from_s1_not_reference(synthetic_pair_env):
    """Output grid is the native Sentinel-1 grid even when a mismatched reference exists."""
    data_dir = synthetic_pair_env["data_dir"]
    rasters_dir = data_dir / "rasters" / "pair1"

    # Rewrite BOTH S1 scenes onto a coarser grid (20x20, 20 m pixels)
    coarse_transform = from_origin(127.0, 50.0, 20.0, 20.0)
    for name, band0 in [("S1_pre_20200101.tif", -13.0), ("S1_peak_20200115.tif", -20.0)]:
        coarse = np.full((2, 20, 20), band0, dtype=np.float32)
        coarse[1] = band0 - 6.0
        with rasterio.open(
            rasters_dir / name,
            "w",
            driver="GTiff",
            height=20,
            width=20,
            count=2,
            dtype=np.float32,
            crs="EPSG:32652",
            transform=coarse_transform,
        ) as dst:
            dst.write(coarse)

    row = synthetic_pair_env["row"].copy()
    row["pair_id"] = "grid_from_s1"
    res = process_pair(row, data_dir, synthetic_pair_env["predictions_dir"], ablation_mode=1)
    assert res["pair_id"] == "grid_from_s1"

    # Reference grid is 30x30 / 10 m: the prediction must follow S1 instead
    with rasterio.open(synthetic_pair_env["predictions_dir"] / "grid_from_s1_flood.tif") as out:
        assert out.shape == (20, 20)
        assert out.transform == coarse_transform


def test_process_pair_aoi_geojson_clipping(synthetic_pair_env):
    """AOI polygon boundary clipping filters out pixels outside AOI (lines 176-185)."""
    data_dir = synthetic_pair_env["data_dir"]
    vectors_dir = data_dir / "vectors"
    vectors_dir.mkdir(parents=True, exist_ok=True)

    # Polygon covering half the domain: x from 127 to 200, y from -100 to 50
    poly = Polygon([(127.0, 50.0), (200.0, 50.0), (200.0, -100.0), (127.0, -100.0)])
    gdf = gpd.GeoDataFrame({"aoi_id": ["aoi_clip_test"]}, geometry=[poly], crs="EPSG:32652")
    gdf.to_file(vectors_dir / "aoi.geojson", driver="GeoJSON")

    row = synthetic_pair_env["row"].copy()
    row["pair_id"] = "clipped_pair"
    row["aoi_id"] = "aoi_clip_test"

    res = process_pair(row, data_dir, synthetic_pair_env["predictions_dir"], ablation_mode=1)
    assert res["pair_id"] == "clipped_pair"
    assert (synthetic_pair_env["predictions_dir"] / "clipped_pair_flood.tif").exists()


def test_process_pair_aoi_clipping_exception(synthetic_pair_env, monkeypatch):
    """Exception during AOI clipping is logged and handled gracefully (lines 186-187)."""
    data_dir = synthetic_pair_env["data_dir"]
    vectors_dir = data_dir / "vectors"
    vectors_dir.mkdir(parents=True, exist_ok=True)
    # Corrupt aoi.geojson file
    (vectors_dir / "aoi.geojson").write_text("invalid json content", encoding="utf-8")

    row = synthetic_pair_env["row"].copy()
    row["pair_id"] = "corrupt_aoi_pair"
    row["aoi_id"] = "some_aoi"

    res = process_pair(row, data_dir, synthetic_pair_env["predictions_dir"], ablation_mode=1)
    assert res["pair_id"] == "corrupt_aoi_pair"


def test_process_pair_area_mismatch_warning_and_assert(synthetic_pair_env, monkeypatch):
    """Area mismatch >= 2.0% logs warning and raises AssertionError (line 243)."""
    calls = 0
    real_sum = np.sum

    def fake_sum(a, *args, **kwargs):
        nonlocal calls
        calls += 1
        val = real_sum(a, *args, **kwargs)
        if calls == 9:  # raster_flood_px in area verification
            return val + 500
        return val

    monkeypatch.setattr("src.predict.np.sum", fake_sum)
    row = synthetic_pair_env["row"].copy()
    row["pair_id"] = "mismatch_pair"

    with pytest.raises(AssertionError, match="Area verification failed"):
        process_pair(row, synthetic_pair_env["data_dir"], synthetic_pair_env["predictions_dir"], ablation_mode=1)


def test_predict_main_module_execution(synthetic_pair_env, monkeypatch):
    """Execute predict.py as __main__ (line 305)."""
    pairs_csv = synthetic_pair_env["data_dir"] / "pairs.csv"
    pd.DataFrame([synthetic_pair_env["row"].to_dict()]).to_csv(pairs_csv, index=False)
    sub_csv = synthetic_pair_env["predictions_dir"] / "dummy_main_sub.csv"

    monkeypatch.setattr(
        "sys.argv",
        [
            "predict.py",
            "--pairs",
            str(pairs_csv),
            "--data_dir",
            str(synthetic_pair_env["data_dir"]),
            "--output_csv",
            str(sub_csv),
            "--predictions_dir",
            str(synthetic_pair_env["predictions_dir"]),
            "--ablation_mode",
            "1",
        ],
    )
    runpy.run_module("src.predict", run_name="__main__")
    assert sub_csv.exists()


def test_read_sar_bands_is_bit_identical_to_whole_array_read(synthetic_pair_env):
    """D9: windowed SAR reads must reproduce src.read() byte for byte, block-size agnostic."""
    s1_pre_tif = synthetic_pair_env["data_dir"] / "rasters" / "pair1" / "S1_pre_20200101.tif"

    with rasterio.open(s1_pre_tif) as src:
        vv_ref = src.read(1)
        vh_ref = src.read(2)

    for block_rows in (1, 3, 7, 30, 1024):
        vv, vh = read_sar_bands(s1_pre_tif, block_rows=block_rows)
        assert vv.dtype == vv_ref.dtype
        assert vh.dtype == vh_ref.dtype
        assert np.array_equal(vv, vv_ref)
        assert np.array_equal(vh, vh_ref)


def test_read_sar_bands_streams_in_row_windows(synthetic_pair_env, monkeypatch):
    """D9: the read path must issue one windowed read per row block, not one whole-array read."""
    s1_pre_tif = synthetic_pair_env["data_dir"] / "rasters" / "pair1" / "S1_pre_20200101.tif"
    windows: list[object] = []

    real_read = rasterio.io.DatasetReader.read

    def spy_read(self, indexes=None, out=None, window=None, **kwargs):
        windows.append(window)
        return real_read(self, indexes=indexes, out=out, window=window, **kwargs)

    monkeypatch.setattr(rasterio.io.DatasetReader, "read", spy_read)
    read_sar_bands(s1_pre_tif, block_rows=7)

    # 30 rows / 7 per block -> 5 blocks (7,7,7,7,2), each read for 2 bands
    assert len(windows) == 10
    assert all(w is not None for w in windows)
    # Every window is a partial strip; no window spans the whole scene (30 rows)
    heights = [w.height for w in windows]
    assert max(heights) == 7 and min(heights) == 2
    assert {w.width for w in windows} == {30}


def test_read_sar_bands_single_band_raster_has_no_vh(tmp_path):
    """A single-band S1 scene yields vh=None, matching the previous src.count check."""
    tif = tmp_path / "single_band.tif"
    with rasterio.open(
        tif,
        "w",
        driver="GTiff",
        height=5,
        width=5,
        count=1,
        dtype=np.float32,
        crs="EPSG:32652",
        transform=from_origin(127.0, 50.0, 10.0, 10.0),
    ) as dst:
        dst.write(np.full((1, 5, 5), -12.0, dtype=np.float32))

    vv, vh = read_sar_bands(tif, block_rows=2)
    assert vv.shape == (5, 5)
    assert vh is None


def test_resolve_orbit_pass_reads_pairs_row():
    """D3: the pairs-row orbit_pass label is threaded to the segmentation guard."""
    assert predict_resolve_orbit_pass(pd.Series({"orbit_pass": "DESCENDING"})) == "DESCENDING"
    assert predict_resolve_orbit_pass(pd.Series({"orbit_pass": "ascending"})) == "ascending"
    assert predict_resolve_orbit_pass(pd.Series({"orbit_pass": "  "})) is None
    assert predict_resolve_orbit_pass(pd.Series({"pair_id": "x"})) is None


def test_process_pair_threads_orbit_pass_into_segmentation(synthetic_pair_env, monkeypatch):
    """D3: process_pair forwards the row's orbit_pass to segment_water for both dates."""
    from src.predict import process_pair as real_process_pair
    from src.segmentation import segment_water as real_segment_water

    captured: list[str | None] = []

    def spy_segment_water(*args, **kwargs):
        captured.append(kwargs.get("orbit_pass"))
        return real_segment_water(*args, **kwargs)

    monkeypatch.setattr("src.predict.segment_water", spy_segment_water)

    row = synthetic_pair_env["row"].copy()
    row["orbit_pass"] = "DESCENDING"
    row["pair_id"] = "orbit_threaded"

    real_process_pair(row, synthetic_pair_env["data_dir"], synthetic_pair_env["predictions_dir"], ablation_mode=4)

    # Two calls: pre and peak acquisitions of the same pair
    assert captured == ["DESCENDING", "DESCENDING"]


def test_process_pair_without_orbit_pass_column_is_inert(synthetic_pair_env, monkeypatch):
    """D3: a pairs row lacking orbit_pass disables the guard (no-op, default None)."""
    from src.predict import process_pair as real_process_pair
    from src.segmentation import segment_water as real_segment_water

    captured: list[str | None] = []

    def spy_segment_water(*args, **kwargs):
        captured.append(kwargs.get("orbit_pass"))
        return real_segment_water(*args, **kwargs)

    monkeypatch.setattr("src.predict.segment_water", spy_segment_water)

    row = synthetic_pair_env["row"].copy()
    row["pair_id"] = "no_orbit"
    assert "orbit_pass" not in row.index

    real_process_pair(row, synthetic_pair_env["data_dir"], synthetic_pair_env["predictions_dir"], ablation_mode=1)

    assert captured == [None, None]
