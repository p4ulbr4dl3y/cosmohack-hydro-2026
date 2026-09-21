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
from rasterio.warp import Resampling

from src.config import HydroConfig
from src.filters import apply_mmu as _filters_apply_mmu
from src.filters import refined_lee_filter as _filters_refined_lee_filter
from src.filters import speckle_filter as _filters_speckle_filter
from src.geo_utils import clip_by_aoi, read_raster_with_meta, resample_to_target
from src.indices import segment_optical as _indices_segment_optical

logger = logging.getLogger(__name__)

__all__ = [
    "HydroConfig",
    "load_config",
    "refined_lee_filter",
    "speckle_filter",
    "compute_otsu_threshold",
    "load_aux_priors",
    "segment_optical",
    "apply_mmu",
    "detect_flooded_vegetation",
    "segment_water",
    "read_raster_with_meta",
    "resample_to_target",
    "clip_by_aoi",
]

# Default config cache
_CONFIG_CACHE: dict[str, Any] | None = None


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load configuration dictionary from config.yaml or HydroConfig."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None and config_path is None:
        return _CONFIG_CACHE

    cfg_obj = HydroConfig.from_yaml(config_path)
    cfg = cfg_obj.to_dict()

    defaults = {
        "otsu_min_db": -22.0,
        "otsu_max_db": -12.0,
        "otsu_bins": 64,
        "otsu_valid_min_db": -30.0,
        "otsu_valid_max_db": -12.0,
        "otsu_min_valid_pixels": 50,
        "otsu_fallback_db": -16.5,
        "sar_nodata_max_db": -100.0,
        "builtup_max_fraction": 0.5,
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
    """Apply genuine Refined Lee filter using local mean and variance."""
    return _filters_refined_lee_filter(data=data, size=size, n_looks=n_looks)


def speckle_filter(
    data: np.ndarray | None,
    method: str = "lee",
    size: int = 7,
) -> np.ndarray | None:
    """Apply speckle noise filtering on radar backscatter data."""
    return _filters_speckle_filter(data=data, method=method, size=size)


def compute_otsu_threshold(
    vv_data: np.ndarray,
    mask: np.ndarray | None = None,
    min_db: float | None = None,
    max_db: float | None = None,
    bins: int | None = None,
    valid_min_db: float | None = None,
    valid_max_db: float | None = None,
    min_valid_pixels: int | None = None,
    fallback_db: float | None = None,
) -> float:
    """Compute Otsu threshold on VV radar backscatter, clipped to [min_db, max_db].

    The histogram is built over the *full* validity window
    [valid_min_db, valid_max_db] so both the water mode (~ -20 dB) and the dry-land
    mode (~ -8 dB) are represented; Otsu on a truncated single-mode tail is
    meaningless. The resulting threshold is then clipped into the physically
    admissible corridor [min_db, max_db] (task spec: [-22, -12] dB).

    Pixels outside [valid_min_db, valid_max_db] are treated as nodata and excluded
    from the histogram; if fewer than min_valid_pixels remain, fallback_db is returned.
    """
    cfg = load_config()
    min_val = min_db if min_db is not None else float(cfg["otsu_min_db"])
    max_val = max_db if max_db is not None else float(cfg["otsu_max_db"])
    num_bins = bins if bins is not None else int(cfg["otsu_bins"])
    valid_min = valid_min_db if valid_min_db is not None else float(cfg["otsu_valid_min_db"])
    valid_max = valid_max_db if valid_max_db is not None else float(cfg["otsu_valid_max_db"])
    min_pixels = min_valid_pixels if min_valid_pixels is not None else int(cfg["otsu_min_valid_pixels"])
    fallback = fallback_db if fallback_db is not None else float(cfg["otsu_fallback_db"])

    valid = np.isfinite(vv_data) & (vv_data > valid_min) & (vv_data < valid_max)
    if mask is not None:
        valid = valid & mask

    valid_vals = vv_data[valid]
    if len(valid_vals) < min_pixels:
        return fallback

    # Histogram spans the full validity window (both modes), threshold is clipped afterwards.
    counts, bin_edges = np.histogram(valid_vals, bins=num_bins, range=(valid_min, valid_max))
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0

    weight1 = np.cumsum(counts)
    weight2 = np.cumsum(counts[::-1])[::-1]

    mean1 = np.cumsum(counts * bin_centers) / np.maximum(weight1, 1)
    mean2 = (np.cumsum((counts * bin_centers)[::-1]) / np.maximum(weight2[::-1], 1))[::-1]

    variance = weight1[:-1] * weight2[1:] * (mean1[:-1] - mean2[1:]) ** 2
    # The between-class variance is flat across an empty gap between two modes.
    # Pick the centre of the maximal plateau rather than the first bin, which
    # otherwise biases the threshold towards the water (dark) mode.
    best = float(variance.max())
    plateau_idx = np.flatnonzero(variance >= best * (1.0 - 1e-9))
    best_idx = int(plateau_idx[len(plateau_idx) // 2])
    threshold = float(bin_centers[best_idx])

    if not np.isfinite(threshold):
        return fallback

    return float(np.clip(threshold, min_val, max_val))


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

    slope = resample_to_target(
        source_path=aux_path,
        band=1,
        target_shape=target_shape,
        target_transform=target_transform,
        target_crs=target_crs,
        resampling=Resampling.bilinear,
    )
    hand = resample_to_target(
        source_path=aux_path,
        band=2,
        target_shape=target_shape,
        target_transform=target_transform,
        target_crs=target_crs,
        resampling=Resampling.bilinear,
    )
    occurrence = resample_to_target(
        source_path=aux_path,
        band=3,
        target_shape=target_shape,
        target_transform=target_transform,
        target_crs=target_crs,
        resampling=Resampling.nearest,
    )
    builtup = resample_to_target(
        source_path=aux_path,
        band=6,
        target_shape=target_shape,
        target_transform=target_transform,
        target_crs=target_crs,
        resampling=Resampling.nearest,
    )

    # Sanitize invalid or corrupted nodata values (e.g. -inf in Svobodny 2021-08)
    valid_slope = np.isfinite(slope) & (slope >= 0.0)
    valid_hand = np.isfinite(hand) & (hand >= 0.0)
    topo_mask = valid_slope & valid_hand & (slope <= slope_max) & (hand <= hand_max)
    permanent_mask = (occurrence >= gsw_min) & np.isfinite(occurrence)

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
    """Segment water using Sentinel-2 MSI indices where available."""
    cfg = load_config()
    mndwi_min = float(cfg["optical_mndwi_min"])
    aweish_min = float(cfg["optical_aweish_min"])
    ndvi_max = float(cfg["optical_ndvi_max"])
    return _indices_segment_optical(
        s2_path=s2_path,
        target_shape=target_shape,
        mndwi_min=mndwi_min,
        aweish_min=aweish_min,
        ndvi_max=ndvi_max,
    )


def apply_mmu(
    mask: np.ndarray,
    min_size: int | None = None,
) -> np.ndarray:
    """Remove isolated noise clusters smaller than min_size pixels (config-aware wrapper)."""
    if min_size is None:
        cfg = load_config()
        min_size = int(cfg["mmu_min_pixels"])
    return _filters_apply_mmu(mask, min_size=min_size)


def detect_flooded_vegetation(
    vv: np.ndarray,
    vh: np.ndarray | None,
    vv_ref: np.ndarray | None,
    vh_ref: np.ndarray | None,
    hand: np.ndarray | None = None,
    slope: np.ndarray | None = None,
    builtup: np.ndarray | None = None,
    filter_method: str = "lee",
    filter_size: int = 7,
) -> np.ndarray:
    """Detect sub-canopy (flooded) vegetation via the double-bounce mechanism.

    Double bounce = open water + vertical stem. Physically the *pre* date pixel is
    dry vegetation (bright VV, e.g. ~ -8 dB) and it becomes flooded at peak, so VH
    rises. A pixel that was already open water at the pre date cannot produce a
    double bounce, so the pre-date VV must be >= ``double_bounce_vv_pre_min_db``.

    Per task spec section 5 the flooded vegetation is a separate product layer and
    is NOT part of the open-water mirror, hence this mask is returned separately and
    never merged into :func:`segment_water`.
    """
    if vh is None or vh_ref is None or vv_ref is None:
        return np.zeros(vv.shape, dtype=bool)

    cfg = load_config()
    db_delta = float(cfg["double_bounce_delta_vh_db"])
    db_hand_max = float(cfg["double_bounce_hand_max_m"])
    db_slope_max = float(cfg.get("double_bounce_slope_max_deg", 3.0))
    db_vv_pre_min = float(cfg.get("double_bounce_vv_pre_min_db", -14.0))
    nodata_max_db = float(cfg.get("sar_nodata_max_db", -100.0))
    builtup_max = float(cfg.get("builtup_max_fraction", 0.5))

    sar_valid = np.isfinite(vv) & (vv > nodata_max_db)
    vv_ref_filt = speckle_filter(vv_ref, method=filter_method, size=filter_size)
    vh_filt = speckle_filter(vh, method=filter_method, size=filter_size)
    vh_ref_filt = speckle_filter(vh_ref, method=filter_method, size=filter_size)
    delta_vh = vh_filt - vh_ref_filt

    builtup_clean = (builtup < builtup_max) if builtup is not None else True
    cond = (delta_vh >= db_delta) & (vv_ref_filt >= db_vv_pre_min) & builtup_clean & sar_valid
    if hand is not None:
        cond = cond & (hand <= db_hand_max)
    if slope is not None:
        cond = cond & (slope <= db_slope_max)

    return cond


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
    sar_drop_vv_max = float(cfg.get("sar_drop_vv_max_db", -14.0))
    sar_drop_vh_min = float(cfg.get("sar_drop_vh_min_db", 1.5))
    sar_drop_vh_max = float(cfg.get("sar_drop_vh_max_db", -17.0))
    mmu_pixels = mmu_min_size if mmu_min_size is not None else int(cfg["mmu_min_pixels"])
    nodata_max_db = float(cfg.get("sar_nodata_max_db", -100.0))
    builtup_max = float(cfg.get("builtup_max_fraction", 0.5))
    sar_valid_frac_min = float(cfg.get("sar_valid_frac_min", 0.1))
    fb_hand_max = float(cfg.get("fallback_hand_max_m", 1.0))
    fb_occ_min = float(cfg.get("fallback_occurrence_min_pct", 5.0))

    sar_valid = np.isfinite(vv) & (vv > nodata_max_db)

    # 1. Speckle filtering (7x7 Refined Lee by default)
    vv_filt = speckle_filter(vv, method=filter_method, size=filter_size)
    vh_filt = speckle_filter(vh, method=filter_method, size=filter_size) if vh is not None else None

    # 2. SAR Otsu thresholding within floodplain
    mask_for_otsu = topo_mask if (use_topo and topo_mask is not None) else None
    th_vv = compute_otsu_threshold(vv_filt, mask=mask_for_otsu)

    # Open water by constrained Otsu within floodplain (exclude dry built-up asphalt)
    builtup_clean = (builtup < builtup_max) if builtup is not None else True
    otsu_water = (vv_filt < th_vv) & sar_valid & builtup_clean
    if vh_filt is not None:
        otsu_water = otsu_water & (vh_filt < vh_thresh)

    sar_water = otsu_water

    # 3. Peak flood change detection & double bounce
    if is_peak and vv_ref is not None:
        vv_ref_filt = speckle_filter(vv_ref, method=filter_method, size=filter_size)
        drop = vv_ref_filt - vv_filt
        drop_cond = (drop >= drop_thresh) & (vv_filt < sar_drop_vv_max)
        if vh_filt is not None and vh_ref is not None:
            vh_ref_filt = speckle_filter(vh_ref, method=filter_method, size=filter_size)
            drop_vh = vh_ref_filt - vh_filt
            drop_cond = drop_cond & (drop_vh >= sar_drop_vh_min) & (vh_filt < sar_drop_vh_max)

        # Peak water combines drop >= 3dB and constrained Otsu water.
        # Sub-canopy flooded vegetation (double bounce) is intentionally NOT merged
        # into the open-water mirror (task spec section 5); see detect_flooded_vegetation().
        sar_water = (sar_water | drop_cond) & sar_valid

    # Handle partial/nodata SAR gracefully (e.g. Poyarkovo track boundaries).
    # Explicit, config-driven heuristic: when SAR coverage is too sparse to be
    # trusted (< sar_valid_frac_min of the AOI), fall back to permanent GSW water
    # plus a conservative low-HAND floodplain expansion instead of SAR Otsu.
    if sar_valid.mean() < sar_valid_frac_min and permanent_mask is not None:
        if is_peak and topo_mask is not None and hand is not None and occurrence is not None:
            flood_expansion = topo_mask & (hand <= fb_hand_max) & (occurrence >= fb_occ_min) & (~permanent_mask)
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
