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
from src.filters import apply_hydrological_connectivity as _filters_apply_hydrological_connectivity
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
    "radar_shadow_mask",
    "segment_optical",
    "apply_mmu",
    "apply_hydrological_connectivity",
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
        "sar_nominal_incidence_deg": 38.0,
        "radar_shadow_min_incidence_deg": 90.0,
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
    """Apply Lee MMSE speckle filter (7x7 square window, n_looks=4.4).

    This is the classical Lee minimum-mean-square-error filter with a square
    window. The directional edge-aligned "Refined Lee" variant is NOT implemented.
    """
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
    """Load and reproject AUX terrain and GSW layers to target grid.

    Besides slope/HAND/GSW layers, a terrain ``aspect`` layer is derived from the HAND
    relief grid: HAND increases monotonically upslope near the drainage network, so the
    horizontal direction of its steepest ascent approximates the terrain upslope azimuth.
    The dataset ships no DEM-derived aspect band, so this proxy is used only by the
    orbit-aware radar-shadow guard (:func:`radar_shadow_mask`) and only acts on facets
    steep enough to be geometrically shadowed (> 52 deg for the nominal 38 deg incidence).
    """
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

    # Terrain aspect (downslope azimuth, degrees clockwise from north) from the HAND
    # relief. HAND grows going upslope, so the direction of steepest descent is the
    # terrain aspect used by the radar-shadow geometry.
    dy = np.gradient(hand, axis=0)  # d(HAND)/d(row); rows increase southwards
    dx = np.gradient(hand, axis=1)  # d(HAND)/d(col); cols increase eastwards
    # Downslope vector in (north, east) = (dy, -dx) -> azimuth = atan2(east, north)
    aspect = np.degrees(np.arctan2(-dx, dy)) % 360.0
    aspect = np.where(np.isfinite(aspect), aspect, 0.0).astype(np.float32)

    return {
        "slope": slope,
        "hand": hand,
        "aspect": aspect,
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


def apply_hydrological_connectivity(
    flood_mask: np.ndarray,
    seed_mask: np.ndarray,
) -> np.ndarray:
    """Filter flood clusters by hydrological connectivity to permanent seed network."""
    return _filters_apply_hydrological_connectivity(flood_mask=flood_mask, seed_mask=seed_mask)


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


def radar_shadow_mask(
    slope: np.ndarray | None,
    aspect: np.ndarray | None,
    orbit_pass: str | None,
    nominal_incidence_deg: float | None = None,
    shadow_min_incidence_deg: float | None = None,
) -> np.ndarray | None:
    """Flag terrain facets that are geometrically in the Sentinel-1 radar shadow.

    Geometry
    --------
    Sentinel-1 is a *right-looking* side-looking radar, so the side it illuminates
    depends on the flight direction:

      * descending pass (satellite flying N->S) -> looks **west**,  sensor azimuth ~270 deg
      * ascending  pass (satellite flying S->N) -> looks **east**,  sensor azimuth ~90 deg

    A facet of slope ``s`` whose steepest descent points to azimuth ``A`` is illuminated
    at a *local* incidence angle that differs from the flat-terrain (nominal) incidence
    ``theta_0`` by the projection of the range slope onto the sensor-target plane. With
    ``L`` the target-to-sensor azimuth (the upslope unit vector is ``-(downslope)``),

        cos(theta_local) = cos(s) * cos(theta_0) + sin(s) * sin(theta_0) * cos(A - L)

    When the facet descends *towards* the sensor (``A -> L``) the local incidence shrinks
    (foreshortening, the near-range slope is still imaged) and ``theta_local`` tends to
    ``|s - theta_0|``. When it descends *away* from the sensor (``A -> L + 180 deg``) the
    local incidence grows, ``theta_local -> s + theta_0``, and once ``theta_local >= 90 deg``
    the surface normal points away from the line of sight: the beam grazes the crest and
    never reaches that facet. Backscatter then collapses to system noise (sigma0 < -24 dB)
    and a naive Otsu classifier calls it open water -- a systematic false positive.

    This is exactly why ascending != descending: the shadowed aspect flips by 180 deg
    between passes, so the same hillside is in shadow on one orbit and fully imaged on the
    other. Orbit direction is therefore a physically meaningful input, not a label.

    Assumptions (conservative by design)
    ------------------------------------
    * The dataset carries no per-pixel incidence-angle band, so the mid-swath nominal
      incidence (``SAR_NOMINAL_INCIDENCE_DEG``, ~38 deg for S1 IW) is used as ``theta_0``.
    * ``aspect`` is the downslope azimuth in degrees clockwise from north, derived from the
      AUX HAND relief (see :func:`load_aux_priors`); it is a proxy, not a DEM aspect band.
    * Only the strict self-shadow criterion is applied (``theta_local`` at/above
      ``RADAR_SHADOW_MIN_INCIDENCE_DEG``, i.e. slope steeper than ``90 - theta_0`` ~ 52 deg
      when facing perfectly away). Cast/self-shadow from neighbouring ridges needs a DEM
      profile along the range direction and is deliberately NOT modelled here. Foreshortened
      near-range slopes are never suppressed.

    Returns:
        Boolean array of shadowed pixels, or ``None`` when the guard cannot be evaluated
        (missing slope/aspect layers or an unrecognised ``orbit_pass``). ``None`` means
        "no suppression", so callers can treat it as a no-op.
    """
    if slope is None or aspect is None or orbit_pass is None:
        return None

    pass_norm = str(orbit_pass).strip().upper()
    if pass_norm.startswith("D"):
        look_azimuth_deg = 270.0  # descending, right-looking -> illuminates from the west
    elif pass_norm.startswith("A"):
        look_azimuth_deg = 90.0  # ascending, right-looking -> illuminates from the east
    else:
        return None

    cfg = load_config()
    theta0 = (
        nominal_incidence_deg
        if nominal_incidence_deg is not None
        else float(cfg.get("sar_nominal_incidence_deg", 38.0))
    )
    shadow_min = (
        shadow_min_incidence_deg
        if shadow_min_incidence_deg is not None
        else float(cfg.get("radar_shadow_min_incidence_deg", 90.0))
    )

    slope_arr = np.asarray(slope, dtype=np.float64)
    aspect_arr = np.asarray(aspect, dtype=np.float64)
    # Some AOIs carry NaN/inf in the slope/aspect bands; the libm cos/sin below would
    # raise on them. Substitute a neutral 0 deg for those pixels and let `finite` keep
    # them out of the returned mask (non-finite pixels stay unshadowed, as before).
    finite = np.isfinite(slope_arr) & np.isfinite(aspect_arr)

    theta0_rad = np.radians(theta0)
    slope_rad = np.radians(np.where(finite, slope_arr, 0.0))
    psi = np.radians(look_azimuth_deg - np.where(finite, aspect_arr, look_azimuth_deg))
    # cos(theta_local) = cos(theta0)cos(s) + sin(theta0)sin(s)cos(L - A):
    # downslope azimuth A == look azimuth L -> foreshortened near-range slope (theta_local
    # shrinks); A == L + 180 -> back slope (theta_local grows towards s + theta0).
    cos_incidence = np.cos(slope_rad) * np.cos(theta0_rad) + np.sin(slope_rad) * np.sin(theta0_rad) * np.cos(psi)
    local_incidence_deg = np.degrees(np.arccos(np.clip(cos_incidence, -1.0, 1.0)))

    return finite & (local_incidence_deg >= shadow_min)


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
    aspect: np.ndarray | None = None,
    orbit_pass: str | None = None,
    is_peak: bool = False,
    use_topo: bool = True,
    use_optical: bool = True,
    use_mmu: bool = True,
    use_permanent: bool = True,
    filter_method: str = "lee",
    filter_size: int = 7,
    mmu_min_size: int | None = None,
) -> np.ndarray:
    """End-to-end water segmentation for a single acquisition date (pre or peak).

    The optional ``aspect`` (downslope azimuth, degrees from north) and ``orbit_pass``
    arguments enable an orbit-aware radar-shadow guard: facets steeper than the local
    incidence limit *and* facing away from the sensor look direction are suppressed
    before the topographic priors, because they carry no radar signal and would
    otherwise be misread as open water. The guard is inert (no-op) when either argument
    is ``None``, so existing callers keep their previous behaviour. See
    :func:`radar_shadow_mask` for the geometry and its stated assumptions.
    """
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

    # 1. Speckle filtering (Lee MMSE, 7x7 square window by default; the
    #    directional edge-aligned "Refined Lee" variant is NOT implemented)
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

    # 3b. Orbit-aware radar-shadow guard. Facets in geometric shadow (steep slope facing
    #     away from the look direction) return only thermal noise, which the Otsu path
    #     above misreads as open water. Suppress them on the SAR-derived mask only, so
    #     independent evidence (optical water, GSW permanent prior) is preserved.
    shadow = radar_shadow_mask(slope, aspect, orbit_pass)
    if shadow is not None:
        sar_water = sar_water & ~shadow

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
