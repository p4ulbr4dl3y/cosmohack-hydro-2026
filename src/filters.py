"""Speckle filtering and morphology post-processing for radar imagery."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import label, median_filter, uniform_filter

from src.config import LEE_LOOKS, LEE_SIZE, MMU_MIN_PIXELS, SAR_NODATA_MAX_DB


def refined_lee_filter(
    data: np.ndarray,
    size: int = LEE_SIZE,
    n_looks: float = LEE_LOOKS,
) -> np.ndarray:
    """Apply Lee MMSE speckle filter using local mean and variance.

    This is the classical Lee minimum-mean-square-error filter with a square
    window, NOT the directional "Refined Lee" variant (which uses edge-aligned
    sub-windows). Formula:
        W = (Var(I) - mean(I)^2 / n_looks) / Var(I)
        I_hat = mean(I) + W * (I - mean(I))

    Args:
        data: 2D array of SAR backscatter in dB.
        size: Window aperture size (default 7 for 7x7 filter).
        n_looks: Equivalent number of looks (4.4 for Sentinel-1 IW GRD).

    Returns:
        Filtered 2D array in dB.
    """
    valid_mask = np.isfinite(data) & (data > SAR_NODATA_MAX_DB)
    if not np.any(valid_mask):
        return data.copy()

    fill_val = float(np.nanmedian(data[valid_mask]))
    data_clean = np.where(valid_mask, data, fill_val)

    # Convert dB to linear intensity scale
    linear = 10.0 ** (data_clean / 10.0)

    # Compute local mean and variance over size x size window
    mean_linear = uniform_filter(linear, size=size)
    mean_sq_linear = uniform_filter(linear**2, size=size)
    var_linear = np.maximum(mean_sq_linear - mean_linear**2, 0.0)

    # Lee weighting factor
    theoretical_var = (mean_linear**2) / n_looks
    var_clean = np.maximum(var_linear, 1e-10)
    w = np.clip((var_linear - theoretical_var) / var_clean, 0.0, 1.0)

    filtered_linear = mean_linear + w * (linear - mean_linear)
    filtered_linear = np.maximum(filtered_linear, 1e-10)
    filtered_db = 10.0 * np.log10(filtered_linear)

    filtered_db[~valid_mask] = data[~valid_mask]
    return filtered_db.astype(np.float32)


def speckle_filter(
    data: np.ndarray | None,
    method: str = "lee",
    size: int = LEE_SIZE,
) -> np.ndarray | None:
    """Apply speckle noise filtering on radar backscatter data.

    Args:
        data: 2D array of SAR backscatter in dB or None.
        method: Filtering method, 'lee' (default, Lee MMSE 7x7), 'uniform', or 'median'.
        size: Kernel window size (e.g. 5 or 7).

    Returns:
        Filtered 2D array or None if input data is None.
    """
    if data is None:
        return None
    valid_mask = np.isfinite(data) & (data > SAR_NODATA_MAX_DB)
    if not np.any(valid_mask):
        return data.copy()

    if method == "lee":
        return refined_lee_filter(data, size=size, n_looks=LEE_LOOKS)

    fill_val = float(np.nanmedian(data[valid_mask]))
    data_clean = np.where(valid_mask, data, fill_val)

    filtered = median_filter(data_clean, size=size) if method == "median" else uniform_filter(data_clean, size=size)

    filtered[~valid_mask] = data[~valid_mask]
    return filtered.astype(np.float32)


def apply_mmu(
    mask: np.ndarray,
    min_size: int | None = None,
) -> np.ndarray:
    """Remove isolated noise clusters smaller than min_size pixels.

    Args:
        mask: 2D boolean or integer binary array.
        min_size: Minimum number of contiguous connected pixels.

    Returns:
        Cleaned binary array.
    """
    if min_size is None:
        min_size = MMU_MIN_PIXELS

    if not np.any(mask):
        return mask.copy()

    structure = np.ones((3, 3), dtype=np.uint8)
    labeled, num_features = label(mask, structure=structure)
    if num_features == 0:
        return mask.copy()

    counts = np.bincount(labeled.ravel())
    remove_mask = (counts < min_size)[labeled]
    cleaned = mask & (~remove_mask)
    return cleaned
