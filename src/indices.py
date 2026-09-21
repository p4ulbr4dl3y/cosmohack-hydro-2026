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
    blue: np.ndarray | None = None,
    red: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Calculate optical water and vegetation indices from Sentinel-2 MSI bands.

    Always returned:
        - NDWI = (Green - NIR) / (Green + NIR)
        - MNDWI = (Green - SWIR1) / (Green + SWIR1)

    Returned when the required band is supplied:
        - NDVI = (NIR - Red) / (NIR + Red)              [requires ``red``]
        - AWEIsh = Blue + 2.5*Green - 1.5*(NIR + SWIR1) - 0.25*SWIR2
                                                        [requires ``blue``]

    ``swir2`` is only used by AWEIsh.

    Args:
        green: Green band (B03).
        nir: Near-infrared band (B08).
        swir1: Short-wave infrared 1 band (B11).
        swir2: Short-wave infrared 2 band (B12), used by AWEIsh.
        blue: Optional blue band (B02) required for AWEIsh.
        red: Optional red band (B04) required for NDVI.

    Returns:
        Mapping of index name to 2D array.
    """
    eps = 1e-7
    ndwi = (green - nir) / np.maximum(green + nir, eps)
    mndwi = (green - swir1) / np.maximum(green + swir1, eps)
    indices = {"ndwi": ndwi, "mndwi": mndwi}
    if red is not None:
        indices["ndvi"] = (nir - red) / np.maximum(nir + red, eps)
    if blue is not None:
        indices["aweish"] = blue + 2.5 * green - 1.5 * (nir + swir1) - 0.25 * swir2
    return indices


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
