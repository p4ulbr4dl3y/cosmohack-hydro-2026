"""Модульные тесты модуля пространственной неопределённости и доверительных интервалов."""

from __future__ import annotations

import numpy as np
import pytest

from src.uncertainty import (
    FloodUncertaintyResult,
    compute_flood_area_uncertainty,
    simulate_flood_uncertainty_monte_carlo,
)


def test_compute_flood_area_uncertainty_basic():
    # 10 000 пикселей при 0.01 га/пиксель = 100 га
    mask = np.ones((100, 100), dtype=bool)

    res = compute_flood_area_uncertainty(
        mask,
        pixel_area_ha=0.01,
        pixel_sd_rate=0.08,
        spatial_correlation=0.20,
        confidence_level=0.95,
    )

    assert isinstance(res, FloodUncertaintyResult)
    assert res.area_ha == pytest.approx(100.0)
    assert res.total_valid_pixels == 10000
    assert res.effective_n_pixels < 10000  # пространственная корреляция уменьшает эффективное число выборок
    assert res.lower_bound_ha < res.area_ha < res.upper_bound_ha
    assert res.margin_ha > 0.0
    assert res.relative_uncertainty_pct > 0.0
    assert res.z_score == pytest.approx(1.96, abs=0.01)


def test_compute_flood_area_uncertainty_empty():
    mask = np.zeros((10, 10), dtype=bool)
    res = compute_flood_area_uncertainty(mask)

    assert res.area_ha == 0.0
    assert res.lower_bound_ha == 0.0
    assert res.upper_bound_ha == 0.0
    assert res.margin_ha == 0.0


def test_simulate_flood_uncertainty_monte_carlo():
    sim = simulate_flood_uncertainty_monte_carlo(area_ha=500.0, sigma_effective_ha=25.0, n_trials=1000)

    assert 480.0 < sim["mean"] < 520.0
    assert 20.0 < sim["std"] < 30.0
    assert sim["p05"] < sim["p50"] < sim["p95"]

    # Обработка нулевого входа
    zero_sim = simulate_flood_uncertainty_monte_carlo(0.0, 0.0)
    assert zero_sim["mean"] == 0.0
    assert zero_sim["std"] == 0.0
