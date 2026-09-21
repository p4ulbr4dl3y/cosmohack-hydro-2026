"""Configuration and hyperparameters for HydroWatch Amur."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Global constants / default values
LEE_LOOKS: float = 4.4
LEE_SIZE: int = 7
OTSU_MIN_DB: float = -22.0
OTSU_MAX_DB: float = -12.0
OTSU_BINS: int = 64
OTSU_VALID_MIN_DB: float = -30.0
OTSU_VALID_MAX_DB: float = -12.0
OTSU_MIN_VALID_PIXELS: int = 50
OTSU_FALLBACK_DB: float = -16.5
SAR_NODATA_MAX_DB: float = -100.0
BUILTUP_MAX_FRACTION: float = 0.5
SAR_FLOOD_DROP_DB: float = 3.0
VH_THRESHOLD_DB: float = -16.5
SAR_DROP_VV_MAX_DB: float = -14.0
SAR_DROP_VH_MIN_DB: float = 1.5
SAR_DROP_VH_MAX_DB: float = -17.0
DOUBLE_BOUNCE_DELTA_VH_DB: float = 2.0
DOUBLE_BOUNCE_HAND_MAX_M: float = 3.0
DOUBLE_BOUNCE_SLOPE_MAX_DEG: float = 3.0
DOUBLE_BOUNCE_VV_PRE_MIN_DB: float = -14.0
SLOPE_MAX_DEG: float = 5.0
HAND_MAX_M: float = 25.0
# Radar-shadow geometry (orbit/aspect-aware guard). Sentinel-1 IW carries no per-pixel
# incidence-angle band in this dataset, so the nominal mid-swath look angle is used
# together with the orbit pass; facets at/above the shadow limit are geometrically dark.
SAR_NOMINAL_INCIDENCE_DEG: float = 38.0
RADAR_SHADOW_MIN_INCIDENCE_DEG: float = 90.0
# Row block size for windowed (rasterio.windows.Window) reads of the full S1 scenes.
SAR_READ_BLOCK_ROWS: int = 1024
GSW_OCCURRENCE_MIN_PCT: float = 80.0
OPTICAL_MNDWI_MIN: float = 0.1
OPTICAL_AWEISH_MIN: float = 0.0
OPTICAL_NDVI_MAX: float = 0.3
MMU_MIN_PIXELS: int = 25
PIXEL_SIZE_M: float = 10.0
PIXEL_SIZE_HA: float = 0.01


@dataclass
class HydroConfig:
    """Dataclass holding all hydrological segmentation and processing parameters."""

    lee_looks: float = LEE_LOOKS
    lee_size: int = LEE_SIZE
    otsu_min_db: float = OTSU_MIN_DB
    otsu_max_db: float = OTSU_MAX_DB
    otsu_bins: int = OTSU_BINS
    otsu_valid_min_db: float = OTSU_VALID_MIN_DB
    otsu_valid_max_db: float = OTSU_VALID_MAX_DB
    otsu_min_valid_pixels: int = OTSU_MIN_VALID_PIXELS
    otsu_fallback_db: float = OTSU_FALLBACK_DB
    sar_nodata_max_db: float = SAR_NODATA_MAX_DB
    builtup_max_fraction: float = BUILTUP_MAX_FRACTION
    sar_flood_drop_db: float = SAR_FLOOD_DROP_DB
    vh_threshold_db: float = VH_THRESHOLD_DB
    sar_drop_vv_max_db: float = SAR_DROP_VV_MAX_DB
    sar_drop_vh_min_db: float = SAR_DROP_VH_MIN_DB
    sar_drop_vh_max_db: float = SAR_DROP_VH_MAX_DB
    double_bounce_delta_vh_db: float = DOUBLE_BOUNCE_DELTA_VH_DB
    double_bounce_hand_max_m: float = DOUBLE_BOUNCE_HAND_MAX_M
    double_bounce_slope_max_deg: float = DOUBLE_BOUNCE_SLOPE_MAX_DEG
    double_bounce_vv_pre_min_db: float = DOUBLE_BOUNCE_VV_PRE_MIN_DB
    slope_max_deg: float = SLOPE_MAX_DEG
    hand_max_m: float = HAND_MAX_M
    sar_nominal_incidence_deg: float = SAR_NOMINAL_INCIDENCE_DEG
    radar_shadow_min_incidence_deg: float = RADAR_SHADOW_MIN_INCIDENCE_DEG
    sar_read_block_rows: int = SAR_READ_BLOCK_ROWS
    gsw_occurrence_min_pct: float = GSW_OCCURRENCE_MIN_PCT
    optical_mndwi_min: float = OPTICAL_MNDWI_MIN
    optical_aweish_min: float = OPTICAL_AWEISH_MIN
    optical_ndvi_max: float = OPTICAL_NDVI_MAX
    mmu_min_pixels: int = MMU_MIN_PIXELS
    pixel_size_m: float = PIXEL_SIZE_M
    pixel_size_ha: float = PIXEL_SIZE_HA
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path | None = None) -> HydroConfig:
        """Load HydroConfig from a YAML file, falling back to defaults if not found."""
        path = Path(__file__).resolve().parent.parent / "config.yaml" if path is None else Path(path)

        data: dict[str, Any] = {}
        if path.exists():
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        init_kwargs: dict[str, Any] = {}
        extra: dict[str, Any] = {}

        for k, v in data.items():
            if k in field_names and k != "extra":
                init_kwargs[k] = v
            else:
                extra[k] = v

        return cls(**init_kwargs, extra=extra)

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary matching original load_config schema."""
        res: dict[str, Any] = {
            "otsu_min_db": self.otsu_min_db,
            "otsu_max_db": self.otsu_max_db,
            "otsu_bins": self.otsu_bins,
            "otsu_valid_min_db": self.otsu_valid_min_db,
            "otsu_valid_max_db": self.otsu_valid_max_db,
            "otsu_min_valid_pixels": self.otsu_min_valid_pixels,
            "otsu_fallback_db": self.otsu_fallback_db,
            "sar_nodata_max_db": self.sar_nodata_max_db,
            "builtup_max_fraction": self.builtup_max_fraction,
            "sar_flood_drop_db": self.sar_flood_drop_db,
            "vh_threshold_db": self.vh_threshold_db,
            "sar_drop_vv_max_db": self.sar_drop_vv_max_db,
            "sar_drop_vh_min_db": self.sar_drop_vh_min_db,
            "sar_drop_vh_max_db": self.sar_drop_vh_max_db,
            "double_bounce_delta_vh_db": self.double_bounce_delta_vh_db,
            "double_bounce_hand_max_m": self.double_bounce_hand_max_m,
            "double_bounce_slope_max_deg": self.double_bounce_slope_max_deg,
            "double_bounce_vv_pre_min_db": self.double_bounce_vv_pre_min_db,
            "slope_max_deg": self.slope_max_deg,
            "hand_max_m": self.hand_max_m,
            "sar_nominal_incidence_deg": self.sar_nominal_incidence_deg,
            "radar_shadow_min_incidence_deg": self.radar_shadow_min_incidence_deg,
            "sar_read_block_rows": self.sar_read_block_rows,
            "gsw_occurrence_min_pct": self.gsw_occurrence_min_pct,
            "optical_mndwi_min": self.optical_mndwi_min,
            "optical_aweish_min": self.optical_aweish_min,
            "optical_ndvi_max": self.optical_ndvi_max,
            "mmu_min_pixels": self.mmu_min_pixels,
            "pixel_size_m": self.pixel_size_m,
            "pixel_size_ha": self.pixel_size_ha,
        }
        res.update(self.extra)
        return res
