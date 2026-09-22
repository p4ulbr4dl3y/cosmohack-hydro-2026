"""Spatial Uncertainty & Confidence Interval Estimation for Hydrological Monitoring.

Based on spatial autocorrelation theory (Chave et al. 2004, 2014, IPCC GPG)
and remote sensing error propagation. Residual satellite classification errors
(speckle noise, mixed pixels, boundary delineation) exhibit spatial covariance
(default rho = 0.20), meaning effective independent samples N_eff << N_valid.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import norm


@dataclass(frozen=True)
class FloodUncertaintyResult:
    """Uncertainty analysis and scenario confidence bounds for flood/water area."""

    area_ha: float
    sigma_independent_ha: float
    sigma_correlated_ha: float
    sigma_effective_ha: float
    relative_uncertainty_pct: float
    confidence_level: float
    z_score: float
    lower_bound_ha: float
    upper_bound_ha: float
    margin_ha: float
    effective_n_pixels: float
    total_valid_pixels: int
    spatial_correlation: float


def compute_flood_area_uncertainty(
    mask: np.ndarray,
    pixel_area_ha: float = 0.01,
    pixel_sd_rate: float | None = None,
    spatial_correlation: float | None = None,
    confidence_level: float = 0.95,
    has_optical: bool | None = None,
) -> FloodUncertaintyResult:
    """Compute spatial uncertainty and confidence interval [L, U] for mapped flood/water area.

    Accounts for spatial autocorrelation and boundary mixed-pixel error propagation:
    - If optical data (Sentinel-2) is available alongside SAR, dual-sensor consensus
      suppresses speckle and mixed pixel variance, lowering base pixel_sd_rate (~4.5%).
    - Under heavy cloud cover (pure SAR), radar speckle and wind roughness increase
      base pixel_sd_rate (~8.5%).
    - Morphology factor: elongated river floodplains and fragmented patches exhibit higher
      boundary mixed-pixel fractions, increasing error and decreasing spatial correlation scale.

    Args:
        mask: 2D binary mask (0 or 1, bool or numeric) of classified water/flood.
        pixel_area_ha: Nominal area of one pixel in hectares (default 0.01 ha for 10m).
        pixel_sd_rate: Optional override of baseline fractional standard deviation per pixel.
        spatial_correlation: Optional override of spatial autocorrelation coefficient rho.
        confidence_level: Confidence level (default 0.95 -> z = 1.960; 0.90 -> z = 1.645).
        has_optical: Whether cloud-free optical Sentinel-2 data is available for the pair.

    Returns:
        FloodUncertaintyResult dataclass with bounds [lower_bound_ha, upper_bound_ha].
    """
    arr = np.asarray(mask, dtype=bool)
    n_pixels = int(np.count_nonzero(arr))

    if n_pixels == 0:
        z = float(norm.ppf((1.0 + confidence_level) / 2.0))
        return FloodUncertaintyResult(
            area_ha=0.0,
            sigma_independent_ha=0.0,
            sigma_correlated_ha=0.0,
            sigma_effective_ha=0.0,
            relative_uncertainty_pct=0.0,
            confidence_level=confidence_level,
            z_score=round(z, 3),
            lower_bound_ha=0.0,
            upper_bound_ha=0.0,
            margin_ha=0.0,
            effective_n_pixels=0.0,
            total_valid_pixels=0,
            spatial_correlation=spatial_correlation if spatial_correlation is not None else 0.20,
        )

    area_ha = float(n_pixels * pixel_area_ha)

    # 1. Morphological boundary roughness (shoreline mixed-pixel ratio)
    boundary_ratio = 0.15
    if arr.ndim == 2 and arr.shape[0] > 1 and arr.shape[1] > 1:
        from scipy.ndimage import binary_dilation
        # Dilation identifies all neighboring background pixels that form the perimeter
        dilated = binary_dilation(arr)
        perimeter_pixels = int(np.count_nonzero(dilated ^ arr))
        boundary_ratio = float(perimeter_pixels / max(n_pixels, 1))

    # 2. Dynamic pixel SD rate based on sensor fusion and boundary roughness
    if pixel_sd_rate is not None:
        effective_sd = float(pixel_sd_rate)
    else:
        # Base error: lower with dual-sensor optical consensus, higher with single-sensor SAR
        if has_optical is True:
            base_sd = 0.048  # 4.8% base error when optical confirms water
        elif has_optical is False:
            base_sd = 0.088  # 8.8% base error under single-sensor radar
        else:
            base_sd = 0.070  # Default intermediate value

        # Boundary penalty: mixed pixels on shoreline have higher classification variance
        boundary_penalty = 0.50 * min(1.0, boundary_ratio)
        effective_sd = base_sd * (1.0 + boundary_penalty)

    # 3. Dynamic spatial autocorrelation rho based on cluster compactness
    if spatial_correlation is not None:
        rho = float(np.clip(spatial_correlation, 0.0, 1.0))
    else:
        # Compact flood lakes have higher spatial correlation (~0.24-0.28)
        # Narrow, dendritic streams have lower correlation scale (~0.12-0.18)
        auto_rho = 0.26 - 0.15 * min(1.0, boundary_ratio)
        rho = float(np.clip(auto_rho, 0.10, 0.32))

    # Independent variance: sum( (pixel_area * sd_pixel)^2 )
    sigma_per_pixel = pixel_area_ha * effective_sd
    var_independent = n_pixels * (sigma_per_pixel**2)
    sigma_ind = math.sqrt(var_independent)

    # Correlated standard deviation: sum( pixel_area * sd_pixel )
    sigma_corr = n_pixels * sigma_per_pixel

    # Effective standard error combining independent and correlated components
    sigma_eff = math.sqrt((1.0 - rho) * (sigma_ind**2) + rho * (sigma_corr**2))

    # Effective number of independent pixel observations
    denom = 1.0 + (n_pixels - 1) * rho
    n_eff = float(n_pixels / denom) if denom > 0 else 1.0

    z = float(norm.ppf((1.0 + confidence_level) / 2.0))
    margin = float(z * sigma_eff)
    lower_bound = max(0.0, area_ha - margin)
    upper_bound = area_ha + margin
    rel_pct = (margin / area_ha * 100.0) if area_ha > 0 else 0.0

    return FloodUncertaintyResult(
        area_ha=round(area_ha, 2),
        sigma_independent_ha=round(sigma_ind, 2),
        sigma_correlated_ha=round(sigma_corr, 2),
        sigma_effective_ha=round(sigma_eff, 2),
        relative_uncertainty_pct=round(rel_pct, 2),
        confidence_level=confidence_level,
        z_score=round(z, 3),
        lower_bound_ha=round(lower_bound, 2),
        upper_bound_ha=round(upper_bound, 2),
        margin_ha=round(margin, 2),
        effective_n_pixels=round(n_eff, 1),
        total_valid_pixels=n_pixels,
        spatial_correlation=round(rho, 3),
    )



def simulate_flood_uncertainty_monte_carlo(
    area_ha: float,
    sigma_effective_ha: float,
    n_trials: int = 2000,
    seed: int = 42,
) -> dict[str, float]:
    """Monte Carlo error propagation simulation for flood area estimates.

    Generates n_trials synthetic realizations to empirically evaluate percentiles
    (P5, P25, P50, P75, P95).

    Args:
        area_ha: Central flood area estimate in hectares.
        sigma_effective_ha: Effective standard deviation in hectares.
        n_trials: Number of Monte Carlo samples (default 2000).
        seed: Random seed for deterministic reproducibility.

    Returns:
        Dict with summary statistics: mean, std, p05, p50, p95.
    """
    if area_ha <= 0.0 or sigma_effective_ha <= 0.0:
        return {
            "mean": area_ha,
            "std": 0.0,
            "p05": area_ha,
            "p50": area_ha,
            "p95": area_ha,
        }

    rng = np.random.default_rng(seed)
    # Log-normal distribution to avoid unphysical negative area values
    sigma_ratio = sigma_effective_ha / area_ha
    sigma_log = math.sqrt(math.log(1.0 + sigma_ratio**2))
    mu_log = math.log(area_ha) - 0.5 * (sigma_log**2)

    samples = rng.lognormal(mean=mu_log, sigma=sigma_log, size=n_trials)

    return {
        "mean": round(float(np.mean(samples)), 2),
        "std": round(float(np.std(samples)), 2),
        "p05": round(float(np.percentile(samples, 5.0)), 2),
        "p50": round(float(np.percentile(samples, 50.0)), 2),
        "p95": round(float(np.percentile(samples, 95.0)), 2),
    }
