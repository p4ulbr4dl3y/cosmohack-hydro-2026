"""Temporal dynamics analysis module for HydroWatch Amur.

Computes pre-flood water, peak water, newly flooded areas (flood),
and receded water between paired acquisitions.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np


def compute_temporal_dynamics(
    water_pre: np.ndarray,
    water_peak: np.ndarray,
    permanent: Optional[np.ndarray] = None,
    pixel_size_m: float = 10.0,
) -> Dict[str, np.ndarray | float]:
    """Compute temporal flood and water mirror dynamics.
    
    Formulas:
      flood   = (water_peak == 1) & (water_pre == 0) & (permanent == 0)
      receded = (water_pre == 1) & (water_peak == 0)
      
    Args:
        water_pre: Binary mask of water on pre-event date (uint8, 0/1).
        water_peak: Binary mask of water on peak date (uint8, 0/1).
        permanent: Optional binary mask of permanent water (GSW >= 80%).
        pixel_size_m: Pixel resolution in meters (default 10.0m = 0.01 ha/px).
        
    Returns:
        Dict containing:
          'water_pre': uint8 array
          'water_peak': uint8 array
          'flood': uint8 array
          'receded': uint8 array
          'permanent': uint8 array (if provided or zeros)
          'flood_ha': float
          'water_pre_ha': float
          'water_peak_ha': float
          'receded_ha': float
          'permanent_ha': float
    """
    height, width = water_pre.shape
    if permanent is None:
        perm_mask = np.zeros((height, width), dtype=bool)
    else:
        perm_mask = permanent.astype(bool)

    pre_bool = water_pre.astype(bool)
    peak_bool = water_peak.astype(bool)

    # 1. Flood: water on peak, not on pre, and not permanent
    flood_bool = peak_bool & (~pre_bool) & (~perm_mask)
    flood = flood_bool.astype(np.uint8)

    # 2. Receded: water on pre, not on peak
    receded_bool = pre_bool & (~peak_bool)
    receded = receded_bool.astype(np.uint8)

    # Area in hectares (1 px = pixel_size_m^2 m^2; 1 ha = 10,000 m^2)
    px_ha = (pixel_size_m * pixel_size_m) / 10000.0

    flood_ha = float(np.sum(flood) * px_ha)
    water_pre_ha = float(np.sum(water_pre) * px_ha)
    water_peak_ha = float(np.sum(water_peak) * px_ha)
    receded_ha = float(np.sum(receded) * px_ha)
    permanent_ha = float(np.sum(perm_mask) * px_ha)

    return {
        "water_pre": water_pre.astype(np.uint8),
        "water_peak": water_peak.astype(np.uint8),
        "flood": flood,
        "receded": receded,
        "permanent": perm_mask.astype(np.uint8),
        "flood_ha": round(flood_ha, 2),
        "water_pre_ha": round(water_pre_ha, 2),
        "water_peak_ha": round(water_peak_ha, 2),
        "receded_ha": round(receded_ha, 2),
        "permanent_ha": round(permanent_ha, 2),
    }
