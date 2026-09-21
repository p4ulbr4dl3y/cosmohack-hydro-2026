"""Multimodal water segmentation module for HydroWatch Amur.

Integrates SAR (Sentinel-1 VV/VH), Optical (Sentinel-2 MNDWI, NDVI, AWEIsh),
and Topographic/Hydrological priors (HAND, Slope, Builtup, GSW occurrence)
with Minimum Mapping Unit (MMU) filtering.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import yaml
from rasterio.warp import Resampling, reproject
from scipy.ndimage import label, median_filter, uniform_filter

logger = logging.getLogger(__name__)

# Default config cache
_CONFIG_CACHE: dict[str, Any] | None = None


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load configuration dictionary from config.yaml."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None and config_path is None:
        return _CONFIG_CACHE

    config_path = Path(__file__).resolve().parent.parent / "config.yaml" if config_path is None else Path(config_path)

    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}

    defaults = {
        "otsu_min_db": -22.0,
        "otsu_max_db": -12.0,
        "otsu_bins": 64,
        "sar_flood_drop_db": 3.0,
        "vh_threshold_db": -16.5,
        "double_bounce_delta_vh_db": 2.0,
        "double_bounce_hand_max_m": 3.0,
        "slope_max_deg": 5.0,
        "hand_max_m": 25.0,
        "gsw_occurrence_min_pct": 80.0,
        "optical_mndwi_min": 0.1,
        "optical_aweish_min": 0.0,
        "optical_ndvi_max": 0.3,
        "mmu_min_pixels": 25,
    }
    for k, v in defaults.items():
        cfg.setdefault(k, v)

    _CONFIG_CACHE = cfg
    return cfg


def refined_lee_filter(
    data: np.ndarray,
    size: int = 7,
    n_looks: float = 4.4,
) -> np.ndarray:
    """Apply genuine Refined Lee filter using local mean and variance.

    Formula:
        W = (Var(I) - mean(I)^2 / n_looks) / Var(I)
        I_hat = mean(I) + W * (I - mean(I))

    Args:
        data: 2D array of SAR backscatter in dB.
        size: Window aperture size (default 7 for 7x7 filter).
        n_looks: Equivalent number of looks (4.4 for Sentinel-1 IW GRD).

    Returns:
        Filtered 2D array in dB.
    """
    valid_mask = np.isfinite(data) & (data > -100.0)
    if not np.any(valid_mask):
        return data.copy()

    fill_val = float(np.nanmedian(data[valid_mask]))
    data_clean = np.where(valid_mask, data, fill_val)

    # Convert dB to linear intensity scale
    linear = 10.0 ** (data_clean / 10.0)

    # Compute local mean and variance over size x size window
    mean_linear = uniform_filter(linear, size=size)
    mean_sq_linear = uniform_filter(linear ** 2, size=size)
    var_linear = np.maximum(mean_sq_linear - mean_linear ** 2, 0.0)

    # Lee weighting factor
    theoretical_var = (mean_linear ** 2) / n_looks
    var_clean = np.maximum(var_linear, 1e-10)
    w = np.clip((var_linear - theoretical_var) / var_clean, 0.0, 1.0)

    filtered_linear = mean_linear + w * (linear - mean_linear)
    filtered_linear = np.maximum(filtered_linear, 1e-10)
    filtered_db = 10.0 * np.log10(filtered_linear)

    filtered_db[~valid_mask] = data[~valid_mask]
    return filtered_db.astype(np.float32)


def speckle_filter(
    data: np.ndarray,
    method: str = "lee",
    size: int = 7,
) -> np.ndarray:
    """Apply speckle noise filtering on radar backscatter data.

    Args:
        data: 2D array of SAR backscatter in dB.
        method: Filtering method, 'lee' (default 7x7 Refined Lee), 'uniform', or 'median'.
        size: Kernel window size (e.g. 5 or 7).

    Returns:
        Filtered 2D array.
    """
    if data is None:
        return None
    valid_mask = np.isfinite(data) & (data > -100.0)
    if not np.any(valid_mask):
        return data.copy()

    if method == "lee":
        return refined_lee_filter(data, size=size, n_looks=4.4)

    fill_val = float(np.nanmedian(data[valid_mask]))
    data_clean = np.where(valid_mask, data, fill_val)

    filtered = median_filter(data_clean, size=size) if method == "median" else uniform_filter(data_clean, size=size)

    filtered[~valid_mask] = data[~valid_mask]
    return filtered.astype(np.float32)


def compute_otsu_threshold(
    vv_data: np.ndarray,
    mask: np.ndarray | None = None,
    min_db: float | None = None,
    max_db: float | None = None,
    bins: int | None = None,
) -> float:
    """Compute Otsu threshold on VV radar backscatter, constrained to [min_db, max_db]."""
    cfg = load_config()
    min_val = min_db if min_db is not None else float(cfg["otsu_min_db"])
    max_val = max_db if max_db is not None else float(cfg["otsu_max_db"])
    num_bins = bins if bins is not None else int(cfg["otsu_bins"])

    valid = np.isfinite(vv_data) & (vv_data > -30.0) & (vv_data < -12.0)
    if mask is not None:
        valid = valid & mask

    valid_vals = vv_data[valid]
    if len(valid_vals) < 50:
        return -16.5

    counts, bin_edges = np.histogram(valid_vals, bins=num_bins, range=(-22.0, -14.0))
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0

    weight1 = np.cumsum(counts)
    weight2 = np.cumsum(counts[::-1])[::-1]

    mean1 = np.cumsum(counts * bin_centers) / np.maximum(weight1, 1)
    mean2 = (np.cumsum((counts * bin_centers)[::-1]) / np.maximum(weight2[::-1], 1))[::-1]

    variance = weight1[:-1] * weight2[1:] * (mean1[:-1] - mean2[1:]) ** 2
    best_idx = int(np.argmax(variance))
    threshold = float(bin_centers[best_idx])

    return float(np.clip(threshold, min_val, min(max_val, -14.5)))


def load_aux_priors(
    aux_path: str | Path,
    target_shape: tuple[int, int],
    target_transform: rasterio.Affine,
    target_crs: Any,
) -> dict[str, np.ndarray]:
    """Load and reproject AUX terrain and GSW layers to target grid."""
    cfg = load_config()
    slope_max = float(cfg["slope_max_deg"])
    hand_max = float(cfg["hand_max_m"])
    gsw_min = float(cfg["gsw_occurrence_min_pct"])

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

    topo_mask = (slope <= slope_max) & (hand <= hand_max) & (builtup < 0.5)
    permanent_mask = occurrence >= gsw_min

    return {
        "slope": slope,
        "hand": hand,
        "occurrence": occurrence,
        "builtup": builtup,
        "topo_mask": topo_mask,
        "permanent_mask": permanent_mask,
    }


def segment_optical(
    s2_path: str | Path | None,
    target_shape: tuple[int, int],
) -> tuple[np.ndarray | None, np.ndarray]:
    """Segment water using Sentinel-2 MSI indices where available.

    Turbid flood water has negative NDWI, so NDWI is not required.
    Uses: (MNDWI > 0.1 or AWEIsh > 0.0) & (NDVI <= 0.3).
    """
    cfg = load_config()
    mndwi_min = float(cfg["optical_mndwi_min"])
    aweish_min = float(cfg["optical_aweish_min"])
    ndvi_max = float(cfg["optical_ndvi_max"])

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
        np.isfinite(mndwi) & (mndwi != -999.0) &
        np.isfinite(ndvi) & (ndvi != -999.0) &
        np.isfinite(aweish) & (aweish != -999.0)
    )

    if not np.any(valid_mask):
        return None, np.zeros((height, width), dtype=bool)

    # Turbid water fix: MNDWI > 0.1 or AWEIsh > 0, NDVI <= 0.3
    optical_water = (
        ((mndwi > mndwi_min) | (aweish > aweish_min)) &
        (ndvi <= ndvi_max) &
        valid_mask
    )

    return optical_water, valid_mask


def apply_mmu(
    mask: np.ndarray,
    min_size: int | None = None,
) -> np.ndarray:
    """Remove isolated noise clusters smaller than min_size pixels."""
    if min_size is None:
        cfg = load_config()
        min_size = int(cfg["mmu_min_pixels"])

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
    vh: np.ndarray | None = None,
    vv_ref: np.ndarray | None = None,
    vh_ref: np.ndarray | None = None,
    optical_water: np.ndarray | None = None,
    optical_valid: np.ndarray | None = None,
    topo_mask: np.ndarray | None = None,
    permanent_mask: np.ndarray | None = None,
    hand: np.ndarray | None = None,
    slope: np.ndarray | None = None,
    builtup: np.ndarray | None = None,
    occurrence: np.ndarray | None = None,
    is_peak: bool = False,
    use_topo: bool = True,
    use_optical: bool = True,
    use_mmu: bool = True,
    use_permanent: bool = True,
    filter_method: str = "lee",
    filter_size: int = 7,
    mmu_min_size: int | None = None,
) -> np.ndarray:
    """End-to-end water segmentation for a single acquisition date (pre or peak)."""
    cfg = load_config()
    drop_thresh = float(cfg["sar_flood_drop_db"])
    vh_thresh = float(cfg["vh_threshold_db"])
    db_delta = float(cfg["double_bounce_delta_vh_db"])
    db_hand_max = float(cfg["double_bounce_hand_max_m"])
    mmu_pixels = mmu_min_size if mmu_min_size is not None else int(cfg["mmu_min_pixels"])

    sar_valid = np.isfinite(vv) & (vv > -100.0)

    # 1. Speckle filtering (7x7 Refined Lee by default)
    vv_filt = speckle_filter(vv, method=filter_method, size=filter_size)
    vh_filt = speckle_filter(vh, method=filter_method, size=filter_size) if vh is not None else None

    # 2. SAR Otsu thresholding within floodplain
    mask_for_otsu = topo_mask if (use_topo and topo_mask is not None) else None
    th_vv = compute_otsu_threshold(vv_filt, mask=mask_for_otsu)

    # Open water by constrained Otsu within floodplain
    otsu_water = (vv_filt < th_vv) & sar_valid
    if vh_filt is not None:
        otsu_water = otsu_water & (vh_filt < vh_thresh)

    sar_water = otsu_water

    # 3. Peak flood change detection & double bounce
    if is_peak and vv_ref is not None:
        vv_ref_filt = speckle_filter(vv_ref, method=filter_method, size=filter_size)
        drop = vv_ref_filt - vv_filt
        drop_cond = (drop >= drop_thresh) & (vv_filt < -14.0)
        if vh_filt is not None and vh_ref is not None:
            vh_ref_filt = speckle_filter(vh_ref, method=filter_method, size=filter_size)
            drop_vh = vh_ref_filt - vh_filt
            drop_cond = drop_cond & (drop_vh >= 1.5) & (vh_filt < -17.0)

        # Peak water combines drop >= 3dB and constrained Otsu water
        sar_water = (sar_water | drop_cond) & sar_valid

        # Sub-canopy double bounce detection: Delta_VH >= 2.0 dB at HAND <= 3m and slope <= 3 deg
        # No restrictive vh < -16.5 gate on flooded vegetation!
        if vh_filt is not None and vh_ref is not None and hand is not None and slope is not None:
            vh_ref_filt = speckle_filter(vh_ref, method=filter_method, size=filter_size)
            delta_vh = vh_filt - vh_ref_filt
            builtup_clean = builtup < 0.5 if builtup is not None else True
            db_cond = (
                (delta_vh >= db_delta) &
                (hand <= db_hand_max) &
                (slope <= 3.0) &
                builtup_clean &
                sar_valid &
                (vv_ref_filt < -14.0)
            )
            sar_water = (sar_water | db_cond) & sar_valid

    # Handle partial/nodata SAR gracefully (e.g. Poyarkovo track boundaries)
    if sar_valid.mean() < 0.1 and permanent_mask is not None:
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
        water = apply_mmu(water, min_size=mmu_pixels)

    return water.astype(np.uint8)
