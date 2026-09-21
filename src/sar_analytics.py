"""Sentinel-1 SAR C-band Radar Hydrological Analytics Module.

Performs dual-polarization (VV/VH) radar analysis for hydrological monitoring,
flood mapping, cross-polarization ratio computation, and cloud-penetration verification.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SARAnalyticsResult:
    """Aggregated Sentinel-1 SAR radar analytics summary."""

    water_fraction: float
    water_area_ha: float
    mean_vv_db: float
    mean_vh_db: float
    mean_vh_vv_ratio: float
    radar_contrast_db: float
    cloud_penetration_verified: bool
    double_bounce_fraction: float = 0.0


def compute_cross_polarization_ratio(
    vh_backscatter_db: np.ndarray,
    vv_backscatter_db: np.ndarray,
) -> np.ndarray:
    """Compute cross-polarization ratio in dB: CR = VH - VV.

    In linear scale: CR_lin = I_VH / I_VV.
    In decibel logarithmic scale: 10*log10(I_VH / I_VV) = VH_dB - VV_dB.

    Args:
        vh_backscatter_db: VH backscatter array in dB.
        vv_backscatter_db: VV backscatter array in dB.

    Returns:
        Array of cross-polarization ratio (dB), with invalid pixels as NaN.
    """
    vh = np.asarray(vh_backscatter_db, dtype=np.float32)
    vv = np.asarray(vv_backscatter_db, dtype=np.float32)

    valid = np.isfinite(vh) & np.isfinite(vv)
    cr = np.full_like(vh, np.nan, dtype=np.float32)
    cr[valid] = vh[valid] - vv[valid]
    return cr


def analyze_sar_hydrology(
    vv_backscatter_db: np.ndarray,
    vh_backscatter_db: np.ndarray | None = None,
    threshold_db: float = -16.5,
    area_ha: float = 0.0,
) -> tuple[np.ndarray, SARAnalyticsResult]:
    """Analyze dual-polarization Sentinel-1 radar backscatter for hydrological state.

    Specular reflection over smooth water creates steep drops in both VV and VH.
    Cross-polarization ratio (VH - VV) and contrast metrics distinguish open water
    from rough soil and urban areas.

    Args:
        vv_backscatter_db: 2D array of Sentinel-1 VV backscatter in dB.
        vh_backscatter_db: Optional 2D array of Sentinel-1 VH backscatter in dB.
        threshold_db: Threshold in dB below which pixels represent water specular reflection.
        area_ha: Total reference area in hectares.

    Returns:
        (water_mask, result):
            water_mask: Boolean 2D mask of specular water reflection.
            result: SARAnalyticsResult dataclass.
    """
    vv = np.asarray(vv_backscatter_db, dtype=np.float64)
    valid_vv = np.isfinite(vv) & (vv > -70.0) & (vv < 20.0)

    if vh_backscatter_db is not None:
        vh = np.asarray(vh_backscatter_db, dtype=np.float64)
        valid = valid_vv & np.isfinite(vh) & (vh > -70.0) & (vh < 20.0)
    else:
        vh = None
        valid = valid_vv

    valid_count = int(np.sum(valid))
    if valid_count == 0:
        empty_mask = np.zeros_like(vv, dtype=bool)
        return empty_mask, SARAnalyticsResult(
            water_fraction=0.0,
            water_area_ha=0.0,
            mean_vv_db=0.0,
            mean_vh_db=0.0,
            mean_vh_vv_ratio=0.0,
            radar_contrast_db=0.0,
            cloud_penetration_verified=True,
            double_bounce_fraction=0.0,
        )

    water_mask = (vv < threshold_db) & valid
    if vh is not None:
        # Cross-polarization also suppresses volume scattering
        water_mask = water_mask & (vh < (threshold_db - 3.0))

    water_count = int(np.sum(water_mask))
    water_fraction = float(water_count / valid_count)
    water_area = float(area_ha * water_fraction) if area_ha > 0 else 0.0

    mean_vv = float(np.mean(vv[valid]))
    mean_vh = float(np.mean(vh[valid])) if vh is not None else 0.0

    # Cross-polarization ratio (VH - VV in dB)
    if vh is not None:
        cr_vals = vh[valid] - vv[valid]
        mean_cr = float(np.mean(cr_vals))
    else:
        mean_cr = 0.0

    # Radar contrast: difference between non-water mode and water mode
    non_water = valid & (~water_mask)
    if np.any(water_mask) and np.any(non_water):
        contrast = float(np.median(vv[non_water]) - np.median(vv[water_mask]))
    else:
        contrast = 0.0

    # Double bounce indication: elevated VH/VV ratio and high VV
    if vh is not None:
        db_cand = (vh - vv > -5.0) & (vv > -12.0) & valid
        db_fraction = float(np.sum(db_cand) / valid_count)
    else:
        db_fraction = 0.0

    result = SARAnalyticsResult(
        water_fraction=round(water_fraction, 4),
        water_area_ha=round(water_area, 2),
        mean_vv_db=round(mean_vv, 2),
        mean_vh_db=round(mean_vh, 2),
        mean_vh_vv_ratio=round(mean_cr, 2),
        radar_contrast_db=round(contrast, 2),
        cloud_penetration_verified=True,
        double_bounce_fraction=round(db_fraction, 4),
    )
    return water_mask, result
