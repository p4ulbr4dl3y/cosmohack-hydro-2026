"""Модульные тесты модуля суперразрешения и даунскейлинга с сохранением массы."""

from __future__ import annotations

import numpy as np
import pytest

from src.super_resolution import (
    SuperResolutionResult,
    super_resolve_raster_10m,
)


def test_super_resolve_raster_mass_conservation():
    # Грубый растр 4x4 с различающимися положительными значениями
    coarse = np.array(
        [
            [10.0, 20.0, 0.0, 50.0],
            [30.0, 40.0, 60.0, 10.0],
            [5.0, 15.0, 25.0, 35.0],
            [0.0, 10.0, 20.0, 30.0],
        ],
        dtype=np.float64,
    )

    # Направляющий растр высокого разрешения (понижение разрешения в 3 раза, сетка 12x12)
    guide = np.random.default_rng(42).uniform(0.1, 1.0, size=(12, 12))

    fine, res = super_resolve_raster_10m(coarse, guide_10m=guide, upscale_factor=3)

    assert isinstance(res, SuperResolutionResult)
    assert fine.shape == (12, 12)
    assert res.upscaled_shape == (12, 12)
    assert res.upscale_factor == 3
    # Ошибка сохранения массы должна быть практически нулевой (< 0.001%)
    assert res.conservation_error_pct < 0.01

    # Проверка сохранения массы по блокам: среднее окна 3x3 мелкого растра равно грубому пикселю
    for r in range(4):
        for c in range(4):
            sub_mean = np.mean(fine[r * 3 : (r + 1) * 3, c * 3 : (c + 1) * 3])
            assert sub_mean == pytest.approx(coarse[r, c], rel=1e-4, abs=1e-4)


def test_super_resolve_raster_zero_input():
    coarse = np.zeros((3, 3), dtype=np.float64)
    fine, res = super_resolve_raster_10m(coarse, upscale_factor=2)

    assert fine.shape == (6, 6)
    assert np.all(fine == 0.0)
    assert res.conservation_error_pct == 0.0
