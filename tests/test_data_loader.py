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

    for layer in ["flood", "water_pre", "water_peak", "invalid_layer_defaults_to_flood"]:
        gj = loader.get_geojson(pair_id, layer=layer)
        assert gj is not None
        assert gj["type"] == "FeatureCollection"
        assert len(gj["features"]) > 0


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
