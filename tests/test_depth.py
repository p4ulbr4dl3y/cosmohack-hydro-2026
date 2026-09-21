"""Comprehensive unit tests for water depth estimation, MCHS traversability risk classification,
and hydrological station gauge records.
"""

from __future__ import annotations

import numpy as np
import pytest

from hydrowatch_amur.tables.hydro_gauges import (
    HYDROLOGICAL_GAUGES,
    get_gauge_for_aoi,
    get_gauge_status,
)
from src.depth import (
    DEPTH_LOW_THRESHOLD_M,
    DEPTH_MEDIUM_THRESHOLD_M,
    classify_depth_risk,
    estimate_water_depth,
)


class TestDepthEstimation:
    def test_estimate_water_depth_empty_mask(self):
        shape = (50, 50)
        mask = np.zeros(shape, dtype=bool)
        dem = np.full(shape, 100.0, dtype=np.float32)
        depth = estimate_water_depth(mask, dem)
        assert depth.shape == shape
        assert np.all(depth == 0.0)

    def test_estimate_water_depth_shape_mismatch(self):
        mask = np.zeros((10, 10), dtype=bool)
        dem = np.zeros((20, 20), dtype=np.float32)
        with pytest.raises(ValueError, match="Shape mismatch"):
            estimate_water_depth(mask, dem)

    def test_estimate_water_depth_global_edge(self):
        shape = (10, 10)
        mask = np.zeros(shape, dtype=bool)
        mask[2:8, 2:8] = True
        dem = np.full(shape, 10.0, dtype=np.float32)
        # Inside center is lower: 8.0 m (depth should be 2.0 m)
        dem[4:6, 4:6] = 8.0

        depth = estimate_water_depth(mask, dem, method="global_edge", edge_percentile=95.0)
        assert depth[0, 0] == 0.0
        assert depth[4, 4] == pytest.approx(2.0, abs=0.01)
        assert depth[2, 2] == pytest.approx(0.0, abs=0.01)

    def test_estimate_water_depth_nearest_edge(self):
        shape = (20, 20)
        mask = np.zeros(shape, dtype=bool)
        mask[5:15, 5:15] = True
        # Ramp elevation from 10 to 20
        y, _x = np.indices(shape)
        dem = y.astype(np.float32) + 10.0

        depth = estimate_water_depth(mask, dem, method="nearest_edge")
        assert depth.shape == shape
        assert np.all(depth[~mask] == 0.0)
        assert np.all(depth >= 0.0)

    def test_estimate_water_depth_single_pixel_erosion_fallback(self):
        shape = (10, 10)
        mask = np.ones(shape, dtype=bool)
        dem = np.full(shape, 15.0, dtype=np.float32)
        # Full mask has no edge with default zero-padding erosion if borders are True
        # binary_erosion(np.ones(...), border_value=1) -> all True, edge is all False
        from scipy.ndimage import binary_erosion

        eroded = binary_erosion(mask, border_value=1)
        assert np.all(eroded)
        # Test our function fallback when mask is completely filled
        depth = estimate_water_depth(mask, dem)
        assert depth.shape == shape

    def test_estimate_water_depth_nan_in_elevation(self):
        shape = (10, 10)
        mask = np.zeros(shape, dtype=bool)
        mask[2:8, 2:8] = True
        dem = np.full(shape, 10.0, dtype=np.float32)
        dem[0:2, :] = np.nan
        dem[5, 5] = np.nan

        depth = estimate_water_depth(mask, dem)
        assert np.all(np.isfinite(depth))
        assert depth[5, 5] == 0.0

    def test_estimate_water_depth_all_edge_nan(self):
        shape = (10, 10)
        mask = np.zeros(shape, dtype=bool)
        mask[2:8, 2:8] = True
        dem = np.full(shape, np.nan, dtype=np.float32)
        depth = estimate_water_depth(mask, dem)
        assert np.all(depth == 0.0)

    def test_classify_depth_risk_uint8_mask(self):
        depth = np.array([[0.2, 0.6], [1.8, 0.0]], dtype=np.float32)
        mask = np.array([[1, 1], [1, 0]], dtype=np.uint8)
        res = classify_depth_risk(depth, flood_mask=mask)
        assert res["low_risk_pct"] == pytest.approx(33.33, abs=0.1)
        assert res["medium_risk_pct"] == pytest.approx(33.33, abs=0.1)
        assert res["high_risk_pct"] == pytest.approx(33.33, abs=0.1)


class TestRiskClassification:
    def test_classify_depth_risk_empty(self):
        res = classify_depth_risk(np.array([], dtype=np.float32))
        assert res["low_risk_ha"] == 0.0
        assert res["medium_risk_ha"] == 0.0
        assert res["high_risk_ha"] == 0.0
        assert res["mean_depth_m"] == 0.0
        assert "mchs_traversability" in res

    def test_classify_depth_risk_distribution(self):
        depth = np.array(
            [
                [0.2, 0.4],  # 2 pixels < 0.5 m (Low)
                [1.0, 1.2],  # 2 pixels 0.5 - 1.5 m (Medium)
                [2.0, 3.0],  # 2 pixels > 1.5 m (High)
            ],
            dtype=np.float32,
        )
        mask = np.ones((3, 2), dtype=bool)
        res = classify_depth_risk(depth, flood_mask=mask, px_ha=0.1)

        assert res["low_risk_ha"] == pytest.approx(0.2, abs=0.01)
        assert res["medium_risk_ha"] == pytest.approx(0.2, abs=0.01)
        assert res["high_risk_ha"] == pytest.approx(0.2, abs=0.01)
        assert res["low_risk_pct"] == pytest.approx(33.33, abs=0.1)
        assert res["medium_risk_pct"] == pytest.approx(33.33, abs=0.1)
        assert res["high_risk_pct"] == pytest.approx(33.33, abs=0.1)
        assert res["mean_depth_m"] == pytest.approx(1.30, abs=0.05)
        assert res["max_depth_m"] == pytest.approx(3.0, abs=0.01)

    def test_threshold_constants(self):
        assert DEPTH_LOW_THRESHOLD_M == 0.5
        assert DEPTH_MEDIUM_THRESHOLD_M == 1.5


class TestHydroGauges:
    def test_gauges_database_contents(self):
        required_stations = ["blagoveshchensk", "svobodny", "belogorsk", "poyarkovo", "konstantinovka"]
        for st in required_stations:
            assert st in HYDROLOGICAL_GAUGES
            g = HYDROLOGICAL_GAUGES[st]
            assert "station_id" in g
            assert "station_name" in g
            assert "river" in g
            assert "critical_levels_cm" in g
            crit = g["critical_levels_cm"]
            assert "npu" in crit
            assert "oya" in crit
            assert crit["oya"] > crit["npu"]

    def test_get_gauge_for_aoi(self):
        g = get_gauge_for_aoi("Blagoveshchensk")
        assert g is not None
        assert g["station_name"] == "Благовещенск"

        assert get_gauge_for_aoi("unknown_place") is None

    def test_get_gauge_status_stages(self):
        # Blagoveshchensk 2021-06 event: 839 cm (> OYA 800) -> danger_oya
        st_2021 = get_gauge_status("blagoveshchensk", "flood_2021_06_amur")
        assert st_2021 is not None
        assert st_2021["observed_level_cm"] == 839
        assert st_2021["exceeds_oya"] is True
        assert st_2021["exceeds_npu"] is True
        assert st_2021["stage_risk"] == "danger_oya"

        # Baseline 2018 event: 240 cm (< NPU 600) -> normal
        st_base = get_gauge_status("blagoveshchensk", "baseline_2018_09_low")
        assert st_base is not None
        assert st_base["observed_level_cm"] == 240
        assert st_base["exceeds_npu"] is False
        assert st_base["stage_risk"] == "normal"

        # Non-existent event or aoi
        assert get_gauge_status("blagoveshchensk", "non_existent_event") is None
        assert get_gauge_status("non_existent_aoi", "flood_2019_07_amur") is None
