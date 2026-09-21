"""Mass-Preserving Super-Resolution & Downscaling Module.

Downscales coarse auxiliary rasters (e.g. 30m GSW occurrence, DEM derivatives,
or coarse optical indices) to 10m Sentinel resolution using high-resolution guide
weights (e.g. Sentinel-2 MNDWI/NDVI or Sentinel-1 SAR intensity) with rigorous
conservation of integrals (Mass Conservation).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SuperResolutionResult:
    """Outcome of mass-conserving super-resolution processing."""

    original_shape: tuple[int, int]
    upscaled_shape: tuple[int, int]
    upscale_factor: int
    mean_original: float
    mean_superres: float
    conservation_error_pct: float


def super_resolve_raster_10m(
    coarse_raster: np.ndarray,
    guide_10m: np.ndarray | None = None,
    upscale_factor: int = 3,
    min_guide_val: float = 0.01,
) -> tuple[np.ndarray, SuperResolutionResult]:
    """Downscale coarse raster to high-resolution grid with strict integral conservation.

    For each coarse cell (r, c), allocates value across (upscale_factor x upscale_factor)
    sub-pixels proportionally to the guide weights:
        w_sub = max(min_guide_val, guide_sub) / sum(max(min_guide_val, guide_sub))
        fine_val = coarse_val * (w_sub * upscale_factor^2)
    This guarantees that the mean of the sub-pixels equals coarse_val.

    Args:
        coarse_raster: 2D array of coarse values (e.g., 30m).
        guide_10m: 2D array of 10m guide features (e.g., MNDWI, VV backscatter, or NDVI).
                   If None, uniform nearest downscaling is used.
        upscale_factor: Downscaling factor (default 3, e.g. 30m to 10m).
        min_guide_val: Baseline floor for weights to prevent zero divisions.

    Returns:
        (superres_raster, result_dataclass)
    """
    coarse = np.asarray(coarse_raster, dtype=np.float64)
    h_orig, w_orig = coarse.shape
    h_target, w_target = h_orig * upscale_factor, w_orig * upscale_factor

    if guide_10m is not None:
        guide = np.asarray(guide_10m, dtype=np.float64)
        if guide.shape != (h_target, w_target):
            guide = np.repeat(np.repeat(coarse, upscale_factor, axis=0), upscale_factor, axis=1)
    else:
        guide = np.ones((h_target, w_target), dtype=np.float64)

    superres = np.zeros((h_target, w_target), dtype=np.float64)
    n_sub = upscale_factor * upscale_factor

    for r in range(h_orig):
        for c in range(w_orig):
            val = coarse[r, c]
            if not np.isfinite(val) or val == 0:
                continue

            r_slice = slice(r * upscale_factor, (r + 1) * upscale_factor)
            c_slice = slice(c * upscale_factor, (c + 1) * upscale_factor)

            sub_guide = np.maximum(min_guide_val, guide[r_slice, c_slice])
            sum_guide = np.sum(sub_guide)

            if sum_guide > 0:
                weights = sub_guide / sum_guide
                superres[r_slice, c_slice] = val * (weights * n_sub)
            else:
                superres[r_slice, c_slice] = val

    mean_orig = float(np.nanmean(coarse)) if np.any(np.isfinite(coarse)) else 0.0
    mean_super = float(np.nanmean(superres)) if np.any(np.isfinite(superres)) else 0.0

    conservation_err = 0.0
    if mean_orig > 0:
        conservation_err = float(abs(mean_super - mean_orig) / mean_orig * 100.0)

    result = SuperResolutionResult(
        original_shape=(h_orig, w_orig),
        upscaled_shape=(h_target, w_target),
        upscale_factor=upscale_factor,
        mean_original=round(mean_orig, 4),
        mean_superres=round(mean_super, 4),
        conservation_error_pct=round(conservation_err, 4),
    )
    return superres, result
