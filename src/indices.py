"""Optical index calculations and multispectral water segmentation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

from src.config import (
    OPTICAL_AWEISH_MIN,
    OPTICAL_MNDWI_MIN,
    OPTICAL_NDVI_MAX,
)


def calculate_optical_indices(
    green: np.ndarray,
    nir: np.ndarray,
    swir1: np.ndarray,
    swir2: np.ndarray,
) -> dict[str, np.ndarray]:
    """Calculate standard optical water and vegetation indices from spectral bands.

    Indices:
        - NDWI = (Green - NIR) / (Green + NIR)
        - MNDWI = (Green - SWIR1) / (Green + SWIR1)
        - NDVI = (NIR - Red) / (NIR + Red)  [approx or if Red given, here NIR/SWIR]
        - AWEIsh = Blue + 2.5 * Green - 1.5 * (NIR + SWIR1) - 0.25 * SWIR2
    """
    eps = 1e-7
    ndwi = (green - nir) / np.maximum(green + nir, eps)
    mndwi = (green - swir1) / np.maximum(green + swir1, eps)
    return {"ndwi": ndwi, "mndwi": mndwi}


def segment_optical(
    s2_path: str | Path | None,
    target_shape: tuple[int, int],
    mndwi_min: float = OPTICAL_MNDWI_MIN,
    aweish_min: float = OPTICAL_AWEISH_MIN,
    ndvi_max: float = OPTICAL_NDVI_MAX,
) -> tuple[np.ndarray | None, np.ndarray]:
    """Segment water using Sentinel-2 MSI indices where available.

    Turbid flood water has negative NDWI, so NDWI is not required.
    Uses: (MNDWI > mndwi_min or AWEIsh > aweish_min) & (NDVI <= ndvi_max).

    Args:
        s2_path: Path to Sentinel-2 MSI GeoTIFF file.
        target_shape: (height, width) expected output shape.
        mndwi_min: Minimum MNDWI threshold (default 0.1).
        aweish_min: Minimum AWEIsh threshold (default 0.0).
        ndvi_max: Maximum NDVI threshold (default 0.3).

    Returns:
        (optical_water, valid_mask):
            optical_water: 2D boolean array or None if file absent or no valid pixels.
            valid_mask: 2D boolean array indicating valid MSI pixels.
    """
    height, width = target_shape
    if not s2_path or not Path(s2_path).exists():
        return None, np.zeros((height, width), dtype=bool)

    with rasterio.open(s2_path) as src:
        # Expected bands: 5: NDWI, 6: MNDWI, 7: NDVI, 8: AWEIsh
        if src.count < 8:
            return None, np.zeros((height, width), dtype=bool)

        mndwi = src.read(6)
        ndvi = src.read(7)
        aweish = src.read(8)

    valid_mask = (
        np.isfinite(mndwi)
        & (mndwi != -999.0)
        & np.isfinite(ndvi)
        & (ndvi != -999.0)
        & np.isfinite(aweish)
        & (aweish != -999.0)
    )

    if not np.any(valid_mask):
        return None, np.zeros((height, width), dtype=bool)

    # Turbid water fix: MNDWI > 0.1 or AWEIsh > 0, NDVI <= 0.3
    optical_water = ((mndwi > mndwi_min) | (aweish > aweish_min)) & (ndvi <= ndvi_max) & valid_mask

    return optical_water, valid_mask
