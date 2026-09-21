"""Multi-spectral Remote Sensing & Optical Preprocessing Module.

Supports Sentinel-2 Level-2A data handling, Scene Classification Layer (SCL)
cloud/shadow filtering, radiometric calibration, and spectral index calculations
(NDWI, MNDWI, NDVI, NBR, AWEIsh, dNBR, dNDVI) with physical noise suppression.
"""

from __future__ import annotations

from enum import IntEnum

import numpy as np


class SCLClass(IntEnum):
    """Sentinel-2 Scene Classification Layer (SCL) class codes."""

    NO_DATA = 0
    SATURATED_OR_DEFECTIVE = 1
    DARK_AREA_PIXELS = 2
    CLOUD_SHADOWS = 3
    VEGETATION = 4
    NOT_VEGETATED = 5
    WATER = 6
    UNCLASSIFIED = 7
    CLOUD_MEDIUM_PROBABILITY = 8
    CLOUD_HIGH_PROBABILITY = 9
    THIN_CIRRUS = 10
    SNOW_OR_ICE = 11


DEFAULT_VALID_SCL_CLASSES: tuple[int, ...] = (
    SCLClass.VEGETATION,
    SCLClass.NOT_VEGETATED,
    SCLClass.WATER,
    SCLClass.UNCLASSIFIED,
)

DEFAULT_MASKED_SCL_CLASSES: tuple[int, ...] = (
    SCLClass.CLOUD_SHADOWS,
    SCLClass.CLOUD_MEDIUM_PROBABILITY,
    SCLClass.CLOUD_HIGH_PROBABILITY,
    SCLClass.THIN_CIRRUS,
    SCLClass.SNOW_OR_ICE,
)


def create_scl_valid_mask(
    scl: np.ndarray,
    valid_classes: tuple[int, ...] = DEFAULT_VALID_SCL_CLASSES,
    mask_classes: tuple[int, ...] = DEFAULT_MASKED_SCL_CLASSES,
) -> np.ndarray:
    """Generate boolean mask of cloud-free and valid pixels from Sentinel-2 SCL."""
    valid_mask = np.isin(scl, valid_classes)
    invalid_mask = np.isin(scl, mask_classes)
    return valid_mask & (~invalid_mask)


def mask_scene_clouds(
    reflectance: np.ndarray,
    scl: np.ndarray | None,
    valid_classes: tuple[int, ...] = DEFAULT_VALID_SCL_CLASSES,
    mask_classes: tuple[int, ...] = DEFAULT_MASKED_SCL_CLASSES,
) -> np.ndarray:
    """Mask clouds, shadows, and invalid pixels with NaN in reflectance arrays."""
    masked = reflectance.astype(np.float32, copy=True)
    if scl is None:
        return masked

    valid_mask = create_scl_valid_mask(scl, valid_classes=valid_classes, mask_classes=mask_classes)
    if masked.ndim == 3:
        masked[:, ~valid_mask] = np.nan
    else:
        masked[~valid_mask] = np.nan
    return masked


def normalized_difference(
    band_a: np.ndarray,
    band_b: np.ndarray,
    mask: np.ndarray | None = None,
    eps: float = 1e-6,
) -> np.ndarray:
    """Calculate normalized difference: (band_a - band_b) / (band_a + band_b).

    Physically bounded to [-1.0, 1.0]. Negative reflectances or Sen2Cor processing
    artifacts producing unphysical ratios outside [-1.0, 1.0] are masked to NaN.

    Args:
        band_a: First spectral band (e.g. Green, NIR).
        band_b: Second spectral band (e.g. NIR, SWIR, Red).
        mask: Optional boolean valid mask.
        eps: Minimum positive denominator value.

    Returns:
        Float32 array of normalized index.
    """
    a = np.asarray(band_a, dtype=np.float32)
    b = np.asarray(band_b, dtype=np.float32)

    denom = a + b
    num = a - b

    valid = np.isfinite(a) & np.isfinite(b) & (denom > eps) & ~((a <= 0.0) & (b <= 0.0))
    if mask is not None:
        valid = valid & mask

    index = np.full_like(a, np.nan, dtype=np.float32)
    np.divide(num, denom, out=index, where=valid)

    # Filter unphysical mathematical noise outside [-1.0, 1.0]
    unphysical = valid & ((index < -1.0) | (index > 1.0))
    index[unphysical] = np.nan
    return index


def calculate_ndwi(green: np.ndarray, nir: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Compute McFeeters Normalized Difference Water Index: NDWI = (Green - NIR) / (Green + NIR)."""
    return normalized_difference(green, nir, mask=mask)


def calculate_mndwi(green: np.ndarray, swir: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Compute Xu Modified NDWI: MNDWI = (Green - SWIR) / (Green + SWIR)."""
    return normalized_difference(green, swir, mask=mask)


def calculate_ndvi(nir: np.ndarray, red: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Compute Normalized Difference Vegetation Index: NDVI = (NIR - Red) / (NIR + Red)."""
    return normalized_difference(nir, red, mask=mask)


def calculate_nbr(nir: np.ndarray, swir2: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Compute Normalized Burn / Moisture Ratio: NBR = (NIR - SWIR2) / (NIR + SWIR2)."""
    return normalized_difference(nir, swir2, mask=mask)


def calculate_aweish(
    blue: np.ndarray,
    green: np.ndarray,
    nir: np.ndarray,
    swir1: np.ndarray,
    swir2: np.ndarray,
    mask: np.ndarray | None = None,
) -> np.ndarray:
    """Compute Automated Water Extraction Index (shadow variant):

    AWEIsh = Blue + 2.5*Green - 1.5*(NIR + SWIR1) - 0.25*SWIR2.
    """
    b = np.asarray(blue, dtype=np.float32)
    g = np.asarray(green, dtype=np.float32)
    n = np.asarray(nir, dtype=np.float32)
    s1 = np.asarray(swir1, dtype=np.float32)
    s2 = np.asarray(swir2, dtype=np.float32)

    res = b + 2.5 * g - 1.5 * (n + s1) - 0.25 * s2
    if mask is not None:
        res[~mask] = np.nan
    return res


def calculate_dnbr(nbr_pre: np.ndarray, nbr_post: np.ndarray) -> np.ndarray:
    """Compute differential NBR: dNBR = NBR_pre - NBR_post."""
    return (np.asarray(nbr_pre, dtype=np.float32) - np.asarray(nbr_post, dtype=np.float32)).astype(np.float32)


def calculate_dndvi(ndvi_pre: np.ndarray, ndvi_post: np.ndarray) -> np.ndarray:
    """Compute differential NDVI: dNDVI = NDVI_pre - NDVI_post."""
    return (np.asarray(ndvi_pre, dtype=np.float32) - np.asarray(ndvi_post, dtype=np.float32)).astype(np.float32)


def apply_sentinel2_radiometry(
    data: np.ndarray,
    baseline: str | float | None = "05.00",
    scale: float = 0.0001,
    offset: float | None = None,
    nodata: float | int = 0,
) -> np.ndarray:
    """Apply radiometric scaling and offset to Sentinel-2 DN values.

    For baseline >= 04.00, offset is -0.1 (Reflectance = DN * 0.0001 - 0.1).
    For baseline < 04.00, offset is 0.0 (Reflectance = DN * 0.0001).
    """
    arr = data.astype(np.float32, copy=True)
    nodata_mask = arr == nodata

    is_ge_04 = True
    if baseline is not None:
        try:
            parts = str(baseline).split(".")
            is_ge_04 = int(parts[0]) >= 4
        except Exception:
            is_ge_04 = True

    eff_offset = (-0.1 if is_ge_04 else 0.0) if offset is None else float(offset)
    arr = arr * scale + eff_offset
    arr[nodata_mask] = np.nan
    return arr
