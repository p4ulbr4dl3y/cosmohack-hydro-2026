"""Unit tests for multi-spectral remote sensing and SCL cloud masking module."""

from __future__ import annotations

import numpy as np
import pytest

from src.remote_sensing import (
    SCLClass,
    apply_sentinel2_radiometry,
    calculate_aweish,
    calculate_dnbr,
    calculate_dndvi,
    calculate_mndwi,
    calculate_nbr,
    calculate_ndvi,
    calculate_ndwi,
    create_scl_valid_mask,
    mask_scene_clouds,
    normalized_difference,
)


def test_scl_classes_and_masking():
    # Construct SCL array with vegetation (4), water (6), clouds (9), shadows (3)
    scl = np.array([
        [SCLClass.VEGETATION, SCLClass.WATER],
        [SCLClass.CLOUD_HIGH_PROBABILITY, SCLClass.CLOUD_SHADOWS],
    ], dtype=np.uint8)

    valid_mask = create_scl_valid_mask(scl)
    assert valid_mask.shape == (2, 2)
    assert valid_mask[0, 0] is True or valid_mask[0, 0] == 1
    assert valid_mask[0, 1] is True or valid_mask[0, 1] == 1
    assert valid_mask[1, 0] is False or valid_mask[1, 0] == 0
    assert valid_mask[1, 1] is False or valid_mask[1, 1] == 0

    # Test masking 2D and 3D
    refl_2d = np.ones((2, 2), dtype=np.float32)
    masked_2d = mask_scene_clouds(refl_2d, scl)
    assert np.isnan(masked_2d[1, 0])
    assert np.isnan(masked_2d[1, 1])
    assert masked_2d[0, 0] == 1.0

    refl_3d = np.ones((3, 2, 2), dtype=np.float32)
    masked_3d = mask_scene_clouds(refl_3d, scl)
    assert np.isnan(masked_3d[0, 1, 0])
    assert masked_3d[0, 0, 0] == 1.0


def test_normalized_difference_physical_bounds():
    a = np.array([0.4, 0.2, -0.05, 0.0])
    b = np.array([0.1, 0.6, 0.1, 0.0])

    res = normalized_difference(a, b)
    assert res[0] == pytest.approx((0.4 - 0.1) / (0.4 + 0.1))
    assert res[1] == pytest.approx((0.2 - 0.6) / (0.2 + 0.6))
    # Unphysical negative or zero denominator values masked to NaN
    assert np.isnan(res[3])


def test_spectral_indices():
    green = np.array([[0.3, 0.1]])
    nir = np.array([[0.1, 0.5]])
    swir = np.array([[0.05, 0.2]])
    red = np.array([[0.1, 0.1]])
    blue = np.array([[0.2, 0.1]])

    ndwi = calculate_ndwi(green, nir)
    assert ndwi[0, 0] > 0.0  # Green > NIR -> water signal

    mndwi = calculate_mndwi(green, swir)
    assert mndwi[0, 0] > 0.0

    ndvi = calculate_ndvi(nir, red)
    assert ndvi[0, 1] > 0.5  # High vegetation

    nbr = calculate_nbr(nir, swir)
    assert nbr.shape == (1, 2)

    aweish = calculate_aweish(blue, green, nir, swir, swir)
    assert aweish.shape == (1, 2)

    dnbr = calculate_dnbr(np.array([0.8]), np.array([0.2]))
    assert dnbr[0] == pytest.approx(0.6)

    dndvi = calculate_dndvi(np.array([0.7]), np.array([0.3]))
    assert dndvi[0] == pytest.approx(0.4)


def test_apply_sentinel2_radiometry():
    dn = np.array([[1000, 2000], [0, 5000]], dtype=np.int16)

    # Baseline >= 04.00 (scale 0.0001, offset -0.1)
    refl_ge04 = apply_sentinel2_radiometry(dn, baseline="05.00")
    assert refl_ge04[0, 0] == pytest.approx(0.0, abs=1e-5)
    assert refl_ge04[0, 1] == pytest.approx(0.1, abs=1e-5)
    assert np.isnan(refl_ge04[1, 0])  # nodata = 0 masked to NaN

    # Baseline < 04.00 (scale 0.0001, offset 0.0)
    refl_lt04 = apply_sentinel2_radiometry(dn, baseline="03.01")
    assert refl_lt04[0, 0] == pytest.approx(1000 * 0.0001)  # 0.1
