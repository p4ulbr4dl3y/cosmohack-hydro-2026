"""Multimodal water segmentation module for HydroWatch Amur.

Integrates SAR (Sentinel-1 VV/VH), Optical (Sentinel-2 MNDWI, NDWI, NDVI, AWEIsh),
and Topographic/Hydrological priors (HAND, Slope, Builtup, GSW occurrence)
with Minimum Mapping Unit (MMU) filtering.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject
from scipy.ndimage import label, median_filter, uniform_filter

logger = logging.getLogger(__name__)


def speckle_filter(
    data: np.ndarray,
    method: str = "uniform",
    size: int = 5,
) -> np.ndarray:
    """Apply speckle noise filtering on radar backscatter data.
    
    Args:
        data: 2D array of SAR backscatter in dB.
        method: Filtering method, either 'uniform' or 'median'.
        size: Kernel window size (e.g., 3 or 5).
        
    Returns:
        Filtered 2D array.
    """
    valid_mask = np.isfinite(data) & (data > -100.0)
    if not np.any(valid_mask):
        return data.copy()

    # Fill invalid areas temporarily with median of valid to avoid boundary distortion
    fill_val = float(np.nanmedian(data[valid_mask]))
    data_clean = np.where(valid_mask, data, fill_val)

    if method == "median":
        filtered = median_filter(data_clean, size=size)
    else:
        filtered = uniform_filter(data_clean, size=size)

    # Re-apply nodata for invalid locations
    filtered[~valid_mask] = data[~valid_mask]
    return filtered.astype(np.float32)


def compute_otsu_threshold(
    vv_data: np.ndarray,
    mask: Optional[np.ndarray] = None,
    min_db: float = -22.0,
    max_db: float = -12.0,
    bins: int = 64,
) -> float:
    """Compute Otsu threshold on VV radar backscatter, constrained to [min_db, max_db].
    
    Args:
        vv_data: 2D array of VV backscatter in dB.
        mask: Optional boolean mask restricting threshold computation.
        min_db: Minimum allowed threshold in dB.
        max_db: Maximum allowed threshold in dB.
        bins: Number of histogram bins.
        
    Returns:
        Constrained threshold in dB.
    """
    valid = np.isfinite(vv_data) & (vv_data > -30.0) & (vv_data < -12.0)
    if mask is not None:
        valid = valid & mask

    valid_vals = vv_data[valid]
    if len(valid_vals) < 50:
        return -16.5  # Safe default water backscatter threshold

    counts, bin_edges = np.histogram(valid_vals, bins=bins, range=(-22.0, -14.0))
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0

    weight1 = np.cumsum(counts)
    weight2 = np.cumsum(counts[::-1])[::-1]

    mean1 = np.cumsum(counts * bin_centers) / np.maximum(weight1, 1)
    mean2 = (np.cumsum((counts * bin_centers)[::-1]) / np.maximum(weight2[::-1], 1))[::-1]

    variance = weight1[:-1] * weight2[1:] * (mean1[:-1] - mean2[1:]) ** 2
    best_idx = int(np.argmax(variance))
    threshold = float(bin_centers[best_idx])

    # Constrain within [-22.0, -12.0] dB (upper bounded by -14.5 dB)
    return float(np.clip(threshold, min_db, min(max_db, -14.5)))



def load_aux_priors(
    aux_path: str | Path,
    target_shape: Tuple[int, int],
    target_transform: rasterio.Affine,
    target_crs: Any,
) -> Dict[str, np.ndarray]:
    """Load and reproject AUX terrain and GSW layers to target grid.
    
    Bands in AUX_terrain_gsw.tif:
      1: slope (deg)
      2: hand (m)
      3: occurrence (%)
      4: seasonality (months)
      5: max_extent (0 or 1)
      6: builtup (0 or 1)
      
    Returns:
        Dict with slope, hand, occurrence, builtup, topo_mask, permanent_mask.
    """
    height, width = target_shape
    slope = np.zeros((height, width), dtype=np.float32)
    hand = np.zeros((height, width), dtype=np.float32)
    occurrence = np.zeros((height, width), dtype=np.float32)
    builtup = np.zeros((height, width), dtype=np.float32)

    with rasterio.open(aux_path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=slope,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=target_transform,
            dst_crs=target_crs,
            resampling=Resampling.bilinear,
        )
        reproject(
            source=rasterio.band(src, 2),
            destination=hand,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=target_transform,
            dst_crs=target_crs,
            resampling=Resampling.bilinear,
        )
        reproject(
            source=rasterio.band(src, 3),
            destination=occurrence,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=target_transform,
            dst_crs=target_crs,
            resampling=Resampling.nearest,
        )
        reproject(
            source=rasterio.band(src, 6),
            destination=builtup,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=target_transform,
            dst_crs=target_crs,
            resampling=Resampling.nearest,
        )

    topo_mask = (slope <= 5.0) & (hand <= 25.0) & (builtup < 0.5)
    permanent_mask = occurrence >= 80.0

    return {
        "slope": slope,
        "hand": hand,
        "occurrence": occurrence,
        "builtup": builtup,
        "topo_mask": topo_mask,
        "permanent_mask": permanent_mask,
    }


def segment_optical(
    s2_path: Optional[str | Path],
    target_shape: Tuple[int, int],
) -> Tuple[Optional[np.ndarray], np.ndarray]:
    """Segment water using Sentinel-2 MSI indices where available.
    
    Indices criteria:
      MNDWI > 0.1, NDWI > 0.15, NDVI <= 0.2, AWEIsh > 0
      
    Returns:
        (optical_water_mask, valid_optical_mask)
    """
    height, width = target_shape
    if not s2_path or not Path(s2_path).exists():
        return None, np.zeros((height, width), dtype=bool)

    with rasterio.open(s2_path) as src:
        # Expected bands: 5: NDWI, 6: MNDWI, 7: NDVI, 8: AWEIsh
        if src.count < 8:
            return None, np.zeros((height, width), dtype=bool)

        ndwi = src.read(5)
        mndwi = src.read(6)
        ndvi = src.read(7)
        aweish = src.read(8)

    valid_mask = (
        np.isfinite(ndwi) & (ndwi != -999.0) &
        np.isfinite(mndwi) & (mndwi != -999.0) &
        np.isfinite(ndvi) & (ndvi != -999.0) &
        np.isfinite(aweish) & (aweish != -999.0)
    )

    if not np.any(valid_mask):
        return None, np.zeros((height, width), dtype=bool)

    optical_water = (
        (mndwi > 0.1) &
        (ndwi > 0.15) &
        (ndvi <= 0.2) &
        (aweish > 0.0) &
        valid_mask
    )

    return optical_water, valid_mask


def apply_mmu(
    mask: np.ndarray,
    min_size: int = 25,
) -> np.ndarray:
    """Remove isolated noise clusters smaller than min_size pixels.
    
    Args:
        mask: Binary 2D mask.
        min_size: Minimum number of connected pixels (8-connectivity).
        
    Returns:
        Filtered binary mask.
    """
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


def segment_water(
    vv: np.ndarray,
    vh: Optional[np.ndarray] = None,
    vv_ref: Optional[np.ndarray] = None,
    vh_ref: Optional[np.ndarray] = None,
    optical_water: Optional[np.ndarray] = None,
    optical_valid: Optional[np.ndarray] = None,
    topo_mask: Optional[np.ndarray] = None,
    permanent_mask: Optional[np.ndarray] = None,
    hand: Optional[np.ndarray] = None,
    occurrence: Optional[np.ndarray] = None,
    is_peak: bool = False,
    use_topo: bool = True,
    use_optical: bool = True,
    use_mmu: bool = True,
    use_permanent: bool = True,
    filter_method: str = "uniform",
    filter_size: int = 5,
    mmu_min_size: int = 25,
) -> np.ndarray:
    """End-to-end water segmentation for a single acquisition date (pre or peak)."""
    height, width = vv.shape
    sar_valid = np.isfinite(vv) & (vv > -100.0)

    # 1. Speckle filtering
    vv_filt = speckle_filter(vv, method=filter_method, size=filter_size)
    vh_filt = speckle_filter(vh, method=filter_method, size=filter_size) if vh is not None else None

    # 2. SAR Otsu thresholding
    mask_for_otsu = topo_mask if (use_topo and topo_mask is not None) else None
    th_vv = compute_otsu_threshold(vv_filt, mask=mask_for_otsu)

    sar_water = (vv_filt < th_vv) & sar_valid
    if vh_filt is not None:
        sar_water = sar_water & (vh_filt < -16.5)

    # 3. Peak flood drop condition (>= 3 dB drop vs pre)
    if is_peak and vv_ref is not None:
        vv_ref_filt = speckle_filter(vv_ref, method=filter_method, size=filter_size)
        drop = vv_ref_filt - vv_filt
        drop_cond = (drop >= 3.0) & (vv_filt < -14.0)
        if vh_filt is not None and vh_ref is not None:
            vh_ref_filt = speckle_filter(vh_ref, method=filter_method, size=filter_size)
            drop_vh = vh_ref_filt - vh_filt
            drop_cond = drop_cond & (drop_vh >= 1.5) & (vh_filt < -17.0)
        sar_water = (sar_water | drop_cond) & sar_valid

    # Handle partial/nodata SAR gracefully (e.g. Poyarkovo track boundaries)
    if sar_valid.mean() < 0.1:
        if permanent_mask is not None:
            if is_peak and topo_mask is not None and hand is not None and occurrence is not None:
                flood_expansion = topo_mask & (hand <= 1.0) & (occurrence >= 5.0) & (~permanent_mask)
                sar_water = permanent_mask | flood_expansion
            else:
                sar_water = permanent_mask.copy()


    # 4. Optical fusion where available
    if use_optical and optical_water is not None and optical_valid is not None and np.any(optical_valid):
        water = np.where(optical_valid, optical_water | sar_water, sar_water)
    else:
        water = sar_water

    # 5. Topographic priors
    if use_topo and topo_mask is not None:
        water = water & topo_mask

    # 6. GSW permanent water prior
    if use_permanent and permanent_mask is not None:
        water = water | permanent_mask

    # 7. MMU filtering
    if use_mmu:
        water = apply_mmu(water, min_size=mmu_min_size)

    return water.astype(np.uint8)
