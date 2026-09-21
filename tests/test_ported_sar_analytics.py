"""Unit tests for Sentinel-1 SAR radar analytics module."""

from __future__ import annotations

import numpy as np
import pytest

from src.sar_analytics import (
    SARAnalyticsResult,
    analyze_sar_hydrology,
    compute_cross_polarization_ratio,
)


def test_compute_cross_polarization_ratio():
    vh = np.array([[-20.0, -15.0], [-10.0, np.nan]])
    vv = np.array([[-14.0, -10.0], [-5.0, -12.0]])

    cr = compute_cross_polarization_ratio(vh, vv)
    assert cr.shape == (2, 2)
    assert cr[0, 0] == pytest.approx(-6.0)
    assert cr[0, 1] == pytest.approx(-5.0)
    assert cr[1, 0] == pytest.approx(-5.0)
    assert np.isnan(cr[1, 1])


def test_analyze_sar_hydrology_water_detection():
    # Construct 10x10 radar grid with 30 water pixels (deep specular reflection: VV ~ -22 dB, VH ~ -28 dB)
    # and 70 land pixels (rough terrain: VV ~ -9 dB, VH ~ -14 dB)
    vv = np.full((10, 10), -9.0)
    vh = np.full((10, 10), -14.0)

    vv[:3, :] = -22.0
    vh[:3, :] = -28.0

    mask, res = analyze_sar_hydrology(vv, vh, threshold_db=-16.5, area_ha=100.0)

    assert isinstance(res, SARAnalyticsResult)
    assert mask.shape == (10, 10)
    assert np.sum(mask) == 30
    assert res.water_fraction == pytest.approx(0.30)
    assert res.water_area_ha == pytest.approx(30.0)
    assert res.mean_vv_db < -10.0
    assert res.mean_vh_db < -15.0
    assert res.mean_vh_vv_ratio < 0.0
    assert res.radar_contrast_db > 5.0
    assert res.cloud_penetration_verified is True


def test_analyze_sar_hydrology_empty_input():
    vv = np.full((5, 5), np.nan)
    mask, res = analyze_sar_hydrology(vv)

    assert np.sum(mask) == 0
    assert res.water_fraction == 0.0
    assert res.water_area_ha == 0.0
    assert res.cloud_penetration_verified is True
