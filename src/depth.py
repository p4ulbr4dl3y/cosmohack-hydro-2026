"""Water depth estimation and MCHS rescue vehicle traversability risk classification.

Based on hydrodynamic HAND/DEM boundary edge water level profiling:
Depth = Elevation_edge - DEM_pixel (or HAND_edge - HAND_pixel).

Categorizes water depth into MCHS vehicle traversability risk classes:
- Low risk (< 0.5 m): accessible by regular all-wheel trucks / KamAZ
- Medium risk (0.5 m - 1.5 m): PTS-M tracked amphibious transporters only
- High risk (> 1.5 m): boats, water rescue crafts only
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.ndimage import binary_erosion, distance_transform_edt

# MCHS traversability thresholds in meters
DEPTH_LOW_THRESHOLD_M: float = 0.5
DEPTH_MEDIUM_THRESHOLD_M: float = 1.5


def estimate_water_depth(
    flood_mask: np.ndarray,
    elevation: np.ndarray,
    method: str = "nearest_edge",
    edge_percentile: float = 95.0,
    max_depth_m: float = 30.0,
) -> np.ndarray:
    """Calculate per-pixel estimated water depth over the flood mask.

    Parameters
    ----------
    flood_mask : np.ndarray
        2D boolean array or uint8 array (1 for flooded, 0 for dry).
    elevation : np.ndarray
        2D float array of DEM or HAND (Height Above Nearest Drainage).
    method : str
        Method for edge water level estimation:
        - "nearest_edge": local water level propagated from the nearest flood boundary pixel.
        - "global_edge": single statistical water level (edge_percentile) across all edge pixels.
    edge_percentile : float
        Percentile (0-100) to filter outliers when calculating edge water levels.
    max_depth_m : float
        Plausible maximum water depth cap to clip DEM artifacts.

    Returns
    -------
    np.ndarray
        2D float32 array with estimated water depth in meters (0.0 on dry land).
    """
    if flood_mask.shape != elevation.shape:
        raise ValueError(f"Shape mismatch: flood_mask {flood_mask.shape} vs elevation {elevation.shape}")

    f_bool = (flood_mask == 1) if flood_mask.dtype != bool else flood_mask
    depth = np.zeros(elevation.shape, dtype=np.float32)

    if not np.any(f_bool):
        return depth

    # Identify boundary edge pixels: flooded pixels adjacent to unflooded terrain
    # border_value=1 treats array boundaries as continuous flooded terrain, avoiding artificial boundary edges
    edge = f_bool ^ binary_erosion(f_bool, border_value=1)

    # Fallback to entire flood mask if completely filled or erosion removed everything
    if not np.any(edge):
        edge = f_bool.copy()

    # Mask valid finite elevation on edges
    valid_edge = edge & np.isfinite(elevation)
    if not np.any(valid_edge):
        return depth

    if method == "global_edge":
        edge_vals = elevation[valid_edge]
        h_edge = float(np.percentile(edge_vals, edge_percentile))
        depth[f_bool] = np.maximum(0.0, h_edge - elevation[f_bool])
    else:
        # Default: local water level profile propagated from nearest edge pixel
        # distance_transform_edt returns coordinates of nearest True pixel in valid_edge
        _, (indices_y, indices_x) = distance_transform_edt(~valid_edge, return_indices=True)
        edge_elevation = elevation[indices_y, indices_x]
        depth[f_bool] = np.maximum(0.0, edge_elevation[f_bool] - elevation[f_bool])

    # Clean non-finite and clip to physically plausible maximum depth
    depth[~np.isfinite(depth)] = 0.0
    depth = np.clip(depth, 0.0, max_depth_m)
    depth[~f_bool] = 0.0
    return depth.astype(np.float32)


def classify_depth_risk(
    depth: np.ndarray,
    flood_mask: np.ndarray | None = None,
    px_ha: float = 0.01,
) -> dict[str, Any]:
    """Categorize water depth into MCHS vehicle traversability risk classes.

    Classes:
    - Low risk (< 0.5 m): accessible by all-wheel trucks / KamAZ
    - Medium risk (0.5 m - 1.5 m): PTS-M tracked amphibious transporters only
    - High risk (> 1.5 m): boats, water rescue crafts only

    Parameters
    ----------
    depth : np.ndarray
        2D float array of water depth in meters.
    flood_mask : np.ndarray | None
        Optional explicit flood mask. If None, considers pixels with depth > 0.
    px_ha : float
        Area of one pixel in hectares (default: 0.01 ha for 10m Sentinel resolution).

    Returns
    -------
    dict[str, Any]
        Dictionary containing statistics:
        - low_risk_ha, low_risk_pct
        - medium_risk_ha, medium_risk_pct
        - high_risk_ha, high_risk_pct
        - mean_depth_m, max_depth_m
    """
    if flood_mask is None:
        f_bool = depth > 0
    elif flood_mask.dtype != bool:
        f_bool = flood_mask == 1
    else:
        f_bool = flood_mask

    tot_pixels = int(f_bool.sum())
    if tot_pixels == 0:
        return {
            "low_risk_ha": 0.0,
            "low_risk_pct": 0.0,
            "medium_risk_ha": 0.0,
            "medium_risk_pct": 0.0,
            "high_risk_ha": 0.0,
            "high_risk_pct": 0.0,
            "mean_depth_m": 0.0,
            "max_depth_m": 0.0,
            "mchs_traversability": {
                "low_risk_kamaz": "Accessible by regular all-wheel trucks / KamAZ (< 0.5 m)",
                "medium_risk_pts_m": "PTS-M tracked amphibious transporters only (0.5 - 1.5 m)",
                "high_risk_boats": "Watercraft / rescue boats only (> 1.5 m)",
            },
        }

    d_flood = depth[f_bool]
    low_mask = d_flood < DEPTH_LOW_THRESHOLD_M
    med_mask = (d_flood >= DEPTH_LOW_THRESHOLD_M) & (d_flood <= DEPTH_MEDIUM_THRESHOLD_M)
    high_mask = d_flood > DEPTH_MEDIUM_THRESHOLD_M

    low_count = int(low_mask.sum())
    med_count = int(med_mask.sum())
    high_count = int(high_mask.sum())

    low_ha = round(low_count * px_ha, 2)
    med_ha = round(med_count * px_ha, 2)
    high_ha = round(high_count * px_ha, 2)

    low_pct = round((low_count / tot_pixels) * 100.0, 2)
    med_pct = round((med_count / tot_pixels) * 100.0, 2)
    high_pct = round((high_count / tot_pixels) * 100.0, 2)

    valid_d = d_flood[np.isfinite(d_flood)]
    mean_d = round(float(np.mean(valid_d)), 2) if len(valid_d) > 0 else 0.0
    max_d = round(float(np.max(valid_d)), 2) if len(valid_d) > 0 else 0.0

    return {
        "low_risk_ha": low_ha,
        "low_risk_pct": low_pct,
        "medium_risk_ha": med_ha,
        "medium_risk_pct": med_pct,
        "high_risk_ha": high_ha,
        "high_risk_pct": high_pct,
        "mean_depth_m": mean_d,
        "max_depth_m": max_d,
        "mchs_traversability": {
            "low_risk_kamaz": "Accessible by regular all-wheel trucks / KamAZ (< 0.5 m)",
            "medium_risk_pts_m": "PTS-M tracked amphibious transporters only (0.5 - 1.5 m)",
            "high_risk_boats": "Watercraft / rescue boats only (> 1.5 m)",
        },
    }
