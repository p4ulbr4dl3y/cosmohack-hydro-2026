"""Tests for DataLoader without pre-existing cache to exercise full raster processing."""

import pytest

from src.service.data_loader import DataLoader


def test_data_loader_fresh_cache_report(tmp_path):
    # Initialize DataLoader with a clean temporary cache directory
    loader = DataLoader(cache_dir=tmp_path / "cache")

    pair_id = "flood_2019_07_amur__blagoveshchensk"
    # Computing report directly from prediction & AUX rasters
    rep = loader.get_report(pair_id)
    assert rep is not None
    assert rep["pair_id"] == pair_id
    assert rep["flood_ha"] > 0
    assert "landcover" in rep
    assert rep["landcover"]["natural_vegetation_ha"] > 0
    assert rep["landcover"]["builtup_pct"] >= 0

    # Ensure cache file was written
    cache_file = tmp_path / "cache" / f"report_{pair_id}.json"
    assert cache_file.exists()

    # Second call uses memory/disk cache
    rep2 = loader.get_report(pair_id)
    assert rep2 == rep


def test_data_loader_fresh_cache_geojson(tmp_path):
    loader = DataLoader(cache_dir=tmp_path / "cache")
    pair_id = "flood_2019_07_amur__blagoveshchensk"

    for layer in ["flood", "water_pre", "water_peak"]:
        gj = loader.get_geojson(pair_id, layer=layer)
        assert gj is not None
        assert gj["type"] == "FeatureCollection"
        assert len(gj["features"]) > 0

    assert loader.get_geojson(pair_id, layer="invalid_layer") is None


def test_data_loader_predict_spatial_temporal(tmp_path):
    loader = DataLoader(cache_dir=tmp_path / "cache")
    pair_id = "flood_2019_07_amur__blagoveshchensk"

    # 1. By pair_id
    res1 = loader.predict_spatial_temporal(pair_id=pair_id)
    assert res1["status"] == "success"
    assert res1["pair_id"] == pair_id
    assert "summary" in res1

    # 2. By overlapping bounds without pair_id
    bounds = [127.21, 50.12, 127.85, 50.45]
    res2 = loader.predict_spatial_temporal(bounds=bounds)
    assert res2["status"] == "success"
    assert "blagoveshchensk" in res2["pair_id"]

    # 3. Unknown pair_id raises ValueError
    with pytest.raises(ValueError):
        loader.predict_spatial_temporal(pair_id="non_existent_pair")


def test_data_loader_unknown_pair_returns_none(tmp_path):
    loader = DataLoader(cache_dir=tmp_path / "cache")
    assert loader.get_pair_meta("invalid_id") is None
    assert loader.get_report("invalid_id") is None
    assert loader.get_geojson("invalid_id") is None
    assert loader.get_shapefile_zip("invalid_id") is None


def test_data_loader_missing_pairs_csv(tmp_path):
    with pytest.raises(FileNotFoundError, match="pairs.csv not found"):
        DataLoader(data_dir=tmp_path / "nonexistent", cache_dir=tmp_path / "cache")


def test_data_loader_report_no_submission_csv(tmp_path):
    loader = DataLoader(
        submission_csv=tmp_path / "missing_sub.csv",
        cache_dir=tmp_path / "cache",
    )
    rep = loader.get_report("flood_2019_07_amur__blagoveshchensk")
    assert rep is not None
    assert rep["flood_ha"] > 0
    assert rep["water_pre_ha"] == 0.0
    assert rep["water_peak_ha"] == rep["flood_ha"]


def test_data_loader_get_pairs(tmp_path):
    loader = DataLoader(cache_dir=tmp_path / "cache")
    pairs = loader.get_pairs()
    assert isinstance(pairs, list)
    assert len(pairs) > 0


def test_data_loader_report_disk_cache_hit(tmp_path):
    loader1 = DataLoader(cache_dir=tmp_path / "cache")
    rep1 = loader1.get_report("flood_2019_07_amur__blagoveshchensk")
    assert rep1 is not None

    # Instantiate new DataLoader with same cache_dir to hit disk cache
    loader2 = DataLoader(cache_dir=tmp_path / "cache")
    rep2 = loader2.get_report("flood_2019_07_amur__blagoveshchensk")
    assert rep2 == rep1


def test_data_loader_shapefile_with_features(tmp_path):
    loader = DataLoader(cache_dir=tmp_path / "cache")
    shp_bytes = loader.get_shapefile_zip("flood_2019_07_amur__blagoveshchensk", layer="flood")
    assert shp_bytes is not None
    assert len(shp_bytes) > 0


def test_data_loader_report_missing_rasters(tmp_path):
    import shutil

    from src.service.data_loader import DATA_DIR

    fake_data = tmp_path / "data"
    fake_data.mkdir()
    shutil.copy(DATA_DIR / "pairs.csv", fake_data / "pairs.csv")

    # With submission.csv present: line 235 with valid numbers
    loader = DataLoader(
        data_dir=fake_data,
        predictions_dir=tmp_path / "empty_preds",
        cache_dir=tmp_path / "cache1",
    )
    rep = loader.get_report("flood_2019_07_amur__blagoveshchensk")
    assert rep is not None
    assert rep["permanent_ha"] >= 0.0

    # Without submission.csv: line 235 fallback and lines 238, 240, 242
    loader_no_sub = DataLoader(
        data_dir=fake_data,
        predictions_dir=tmp_path / "empty_preds",
        submission_csv=tmp_path / "no_sub.csv",
        cache_dir=tmp_path / "cache2",
    )
    rep_no_sub = loader_no_sub.get_report("flood_2019_07_amur__blagoveshchensk")
    assert rep_no_sub is not None
    assert rep_no_sub["flood_ha"] == 0.0
    assert rep_no_sub["water_pre_ha"] == 0.0


def test_data_loader_receded_ha_exception(tmp_path, monkeypatch):
    loader = DataLoader(cache_dir=tmp_path / "cache")

    def mock_compute(*args, **kwargs):
        raise RuntimeError("Test receded error")

    monkeypatch.setattr("src.service.data_loader.compute_receded_ha", mock_compute)
    rep = loader.get_report("flood_2019_07_amur__blagoveshchensk")
    assert rep["receded_ha"] == 0.0


def test_data_loader_geojson_missing_rasters(tmp_path):
    loader = DataLoader(
        predictions_dir=tmp_path / "empty_preds",
        cache_dir=tmp_path / "cache",
    )
    assert loader.get_geojson("flood_2019_07_amur__blagoveshchensk", layer="flood") is None


def test_data_loader_predict_non_overlapping_bounds(tmp_path):
    loader = DataLoader(cache_dir=tmp_path / "cache")
    with pytest.raises(ValueError, match="do not overlap"):
        loader.predict_spatial_temporal(bounds=[0.0, 0.0, 1.0, 1.0])


def test_data_loader_empty_raster_geojson_and_shapefile(tmp_path):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    preds_dir = tmp_path / "preds"
    preds_dir.mkdir(parents=True, exist_ok=True)
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    tif_path = preds_dir / f"{pair_id}_flood.tif"

    transform = from_origin(127.5, 50.5, 0.0001, 0.0001)
    with rasterio.open(
        tif_path,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype=rasterio.uint8,
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(np.zeros((10, 10), dtype=np.uint8), 1)

    loader = DataLoader(
        predictions_dir=preds_dir,
        cache_dir=tmp_path / "cache",
    )
    gj = loader.get_geojson(pair_id, layer="flood")
    assert gj is not None
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) == 0

    shp_zip = loader.get_shapefile_zip(pair_id, layer="flood")
    assert shp_zip is not None
    assert len(shp_zip) > 0


def test_data_loader_predict_default_first_pair(tmp_path):
    loader = DataLoader(cache_dir=tmp_path / "cache")
    res = loader.predict_spatial_temporal()
    assert res["status"] == "success"
    assert res["pair_id"] == loader._pairs_cache[0]["pair_id"]
