"""Pydantic schemas for HydroWatch Amur FastAPI service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel


class LandcoverDistribution(BaseModel):
    """Distribution of landcover classes and historical water in flood zone."""

    model_config = ConfigDict(extra="ignore")

    builtup_ha: float = Field(default=0.0, description="Flooded built-up / urban area in hectares")
    builtup_pct: float = Field(default=0.0, description="Percentage of flood area on built-up land")
    cropland_ha: float = Field(default=0.0, description="Flooded cropland (ESA WorldCover class 40) in hectares")
    cropland_pct: float = Field(default=0.0, description="Percentage of flood area on cropland")
    natural_vegetation_ha: float = Field(default=0.0, description="Flooded natural land / vegetation in hectares")
    natural_vegetation_pct: float = Field(default=0.0, description="Percentage of flood area on natural land")
    historic_water_extent_ha: float = Field(
        default=0.0, description="Flooded area overlapping JRC GSW maximum water extent"
    )
    historic_water_extent_pct: float = Field(default=0.0, description="Percentage overlapping historic maximum extent")
    new_flood_extent_ha: float = Field(
        default=0.0, description="Flooded area beyond historic maximum water extent (anomalous flood)"
    )
    new_flood_extent_pct: float = Field(default=0.0, description="Percentage of anomalous flood area")
    mean_hand_m: float = Field(default=0.0, description="Mean Height Above Nearest Drainage in flooded area (meters)")
    source: str = Field(
        default="ESA WorldCover v200 Built-up/Cropland & JRC GSW v1.4",
        description="Data sources for landcover and baseline water",
    )


class PairInfo(BaseModel):
    """Metadata passport for an AOI monitoring pair."""

    model_config = ConfigDict(extra="ignore")

    pair_id: str = Field(description="Unique identifier of the flood or baseline pair")
    aoi_id: str = Field(description="AOI settlement / reach code")
    aoi_name: str = Field(description="Human-readable AOI settlement name")
    event_id: str = Field(description="Hydrological event identifier")
    event_name: str = Field(description="Descriptive event name")
    event_kind: str = Field(description="'flood' or 'baseline'")
    year: int = Field(description="Observation year")
    sensor_sar: str = Field(default="", description="SAR sensor, e.g. Sentinel-1")
    sensor_optical: str = Field(default="", description="Optical sensor, e.g. Sentinel-2")
    date_pre_sar: str = Field(default="", description="SAR reference date before event (YYYY-MM-DD)")
    date_peak_sar: str = Field(default="", description="SAR peak flood date (YYYY-MM-DD)")
    date_pre_opt: str = Field(default="", description="Optical pre-flood date if available")
    date_peak_opt: str = Field(default="", description="Optical peak date if available")
    aoi_km2: float = Field(description="Area of Interest size in square kilometers")
    aoi_ha: float = Field(description="Area of Interest size in hectares")
    bounds_4326: list[float] = Field(description="Bounding box [min_lon, min_lat, max_lon, max_lat] in EPSG:4326")
    center_4326: list[float] = Field(description="Center coordinate [lat, lon] in EPSG:4326")


class PairsListResponse(RootModel[list[PairInfo]]):
    """List of all monitored pairs with metadata."""

    root: list[PairInfo] = Field(description="Collection of monitored AOI pairs")


class ReportResponse(BaseModel):
    """Detailed hydrological summary report for a pair."""

    model_config = ConfigDict(extra="ignore")

    pair_id: str = Field(description="Pair identifier")
    aoi_id: str = Field(description="AOI code")
    aoi_name: str = Field(description="AOI name")
    event_id: str = Field(description="Event code")
    event_name: str = Field(description="Event name")
    event_kind: str = Field(description="Event kind ('flood' or 'baseline')")
    year: int = Field(description="Observation year")
    sensor_sar: str = Field(default="", description="SAR sensor identifier, e.g. sentinel1")
    sensor_optical: str = Field(default="", description="Optical sensor identifier, e.g. sentinel2")
    date_pre_sar: str = Field(default="", description="Pre-flood SAR date")
    date_peak_sar: str = Field(default="", description="Peak flood SAR date")
    date_pre_opt: str = Field(default="", description="Pre-flood optical date")
    date_peak_opt: str = Field(default="", description="Peak flood optical date")
    bounds_4326: list[float] = Field(description="AOI bounds [min_lon, min_lat, max_lon, max_lat]")
    center_4326: list[float] = Field(description="AOI center coordinates [lat, lon]")
    aoi_ha: float = Field(description="AOI total area in hectares")
    aoi_km2: float = Field(description="AOI total area in square kilometers")
    flood_ha: float = Field(description="Net flood inundation area in hectares")
    flood_km2: float = Field(description="Net flood inundation area in square kilometers")
    water_pre_ha: float = Field(description="Pre-flood water area in hectares")
    water_pre_km2: float = Field(description="Pre-flood water area in square kilometers")
    water_peak_ha: float = Field(description="Peak water area in hectares")
    water_peak_km2: float = Field(description="Peak water area in square kilometers")
    permanent_ha: float = Field(description="Permanent baseline water area in hectares")
    receded_ha: float = Field(default=0.0, description="Area of receded water before peak in hectares")
    water_gain_ha: float = Field(description="Net water surface expansion in hectares")
    water_gain_pct: float = Field(description="Percentage expansion relative to pre-flood water")
    share_of_aoi: float = Field(description="Flood area fraction of entire AOI")
    flood_share_pct: float = Field(description="Flood area percentage of entire AOI")
    generated_at: str = Field(default="", description="UTC timestamp when the report was generated")
    landcover: LandcoverDistribution = Field(description="Vulnerability and landcover breakdown")


class PredictSummary(BaseModel):
    """Summary metrics of flood inference."""

    model_config = ConfigDict(extra="ignore")

    flood_ha: float = Field(description="Flood inundation area in hectares")
    flood_km2: float = Field(description="Flood inundation area in square kilometers")
    water_pre_ha: float = Field(description="Pre-event water area in hectares")
    water_peak_ha: float = Field(description="Peak water area in hectares")
    water_gain_ha: float = Field(description="Water surface gain in hectares")
    water_gain_pct: float = Field(description="Water gain percentage")
    receded_ha: float = Field(default=0.0, description="Receded water area in hectares")
    share_of_aoi: float = Field(default=0.0, description="Inundated fraction of AOI")
    landcover: LandcoverDistribution | dict[str, Any] = Field(
        default_factory=dict, description="Landcover breakdown in flood zone"
    )


class PredictMetadata(BaseModel):
    """Spatial and temporal metadata for inference output."""

    model_config = ConfigDict(extra="ignore")

    aoi_id: str
    aoi_name: str
    event_id: str
    event_name: str
    event_kind: str
    year: int
    date_pre_sar: str = ""
    date_peak_sar: str = ""
    bounds_4326: list[float]
    center_4326: list[float]


class PredictResponse(BaseModel):
    """Response payload for spatial-temporal flood prediction."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field(default="success", description="Status indicator")
    pair_id: str = Field(description="Resolved pair identifier")
    query_bounds: list[float] | None = Field(default=None, description="User queried bounds")
    query_polygon: dict[str, Any] | None = Field(default=None, description="User queried GeoJSON polygon")
    query_dates: dict[str, str | None] | None = Field(default=None, description="User requested query dates")
    scene_dates: dict[str, str | None] | None = Field(default=None, description="Actual SAR scene dates used")
    requested_dates: dict[str, str | None] | None = Field(default=None, description="Validated requested dates")
    summary: PredictSummary = Field(description="Hydrological area calculations")
    metadata: PredictMetadata = Field(description="AOI passport metadata")
    geojson: dict[str, Any] | None = Field(default=None, description="Vector flood polygons in GeoJSON format")


class PredictionTaskResponse(BaseModel):
    """Status payload for an asynchronous prediction task."""

    model_config = ConfigDict(extra="ignore")

    task_id: str = Field(description="Unique prediction task identifier")
    status: str = Field(
        default="completed",
        description="Lifecycle status of prediction task: 'pending', 'processing', 'completed', 'failed'",
    )
    progress: float = Field(default=1.0, ge=0.0, le=1.0, description="Execution progress ratio from 0.0 to 1.0")
    result: PredictResponse | None = Field(default=None, description="Prediction result payload upon task completion")
    error: str | None = Field(default=None, description="Error explanation if task failed")


class PredictRequest(BaseModel):
    """Request payload for spatial-temporal flood prediction."""

    model_config = ConfigDict(extra="ignore")

    pair_id: str | None = Field(default=None, description="Pair identifier, e.g. flood_2019_07_amur__blagoveshchensk")
    bounds: list[float] | None = Field(default=None, description="[min_lon, min_lat, max_lon, max_lat] in EPSG:4326")
    polygon: dict[str, Any] | None = Field(
        default=None, description="GeoJSON geometry (Polygon) in EPSG:4326; takes precedence over bounds"
    )
    date_pre: str | None = Field(default=None, description="Pre-flood reference date (YYYY-MM-DD)")
    date_peak: str | None = Field(default=None, description="Peak flood date (YYYY-MM-DD)")
    task_id: str | None = Field(default=None, description="Optional asynchronous tracking task identifier")


class HydroAuditCertificateResponse(BaseModel):
    """Cryptographic Merkle audit certificate response schema."""

    model_config = ConfigDict(extra="ignore")

    certificate_id: str = Field(description="Unique certificate identifier")
    pair_id: str = Field(description="Pair identifier")
    aoi_id: str = Field(description="AOI code")
    issued_at: str = Field(description="ISO-8601 UTC timestamp of issue")
    merkle_root: str = Field(description="Hexadecimal SHA-256 root of the Merkle tree")
    leaf_count: int = Field(description="Total audited components/leaves in the tree")
    status: str = Field(description="Verification status: 'VERIFIED'")
    algorithm: str = Field(description="Auditing protocol version")
    signature_hash: str = Field(description="Canonical SHA-256 integrity signature digest")
    summary: dict[str, Any] = Field(description="Summary hydrological metrics")
    leaves: list[dict[str, Any]] = Field(description="Audited Merkle leaf nodes")

    # Aliases for frontend compatibility
    merkle_root_sha256: str | None = Field(default=None, description="Alias for merkle_root")
    inputs_hash_sha256: str | None = Field(default=None, description="SHA-256 digest of input scenes")
    parameters_hash_sha256: str | None = Field(default=None, description="SHA-256 digest of processing parameters")
    results_hash_sha256: str | None = Field(default=None, description="SHA-256 digest of output flood masks")
    timestamp: str | None = Field(default=None, description="Alias for issued_at")
    verified: bool = Field(default=True, description="Verification status boolean")


class FloodUncertaintyResponse(BaseModel):
    """Spatial uncertainty and confidence intervals response schema."""

    model_config = ConfigDict(extra="ignore")

    pair_id: str = Field(description="Pair identifier")
    area_ha: float = Field(description="Central flood area in hectares")
    confidence_level: float = Field(description="Statistical confidence level (e.g. 0.95)")
    lower_bound_ha: float = Field(description="Conservative lower bound L (ha)")
    upper_bound_ha: float = Field(description="Upper bound U (ha)")
    margin_ha: float = Field(description="Absolute uncertainty margin H (ha)")
    relative_uncertainty_pct: float = Field(description="Relative uncertainty margin in percent")
    sigma_effective_ha: float = Field(description="Effective standard error with spatial covariance (ha)")
    effective_n_pixels: float = Field(description="Effective number of independent observations")
    spatial_correlation: float = Field(description="Assumed spatial error autocorrelation rho")


class SARAnalyticsResponse(BaseModel):
    """Sentinel-1 radar analytics response schema."""

    model_config = ConfigDict(extra="ignore")

    pair_id: str = Field(description="Pair identifier")
    water_fraction: float = Field(description="Fraction of area with water specular reflection")
    water_area_ha: float = Field(description="Water surface area estimated from SAR (ha)")
    mean_vv_db: float = Field(description="Mean VV backscatter in dB")
    mean_vh_db: float = Field(description="Mean VH backscatter in dB")
    mean_vh_vv_ratio: float = Field(description="Mean cross-polarization ratio (VH - VV) in dB")
    radar_contrast_db: float = Field(description="Radar contrast between water and land (dB)")
    cloud_penetration_verified: bool = Field(description="Whether all-weather cloud penetration is confirmed")
    double_bounce_fraction: float = Field(description="Fraction of suspected flooded vegetation signature")


class OverlayMetadataResponse(BaseModel):
    """Metadata response for raster PNG map overlay."""

    model_config = ConfigDict(extra="ignore")

    pair_id: str = Field(description="Pair identifier")
    layer: str = Field(description="Layer name: 'flood', 'water_pre', 'water_peak'")
    bounds: list[list[float]] = Field(description="Leaflet WGS84 overlay coordinates [[south, west], [north, east]]")
    width: int = Field(description="Image pixel width")
    height: int = Field(description="Image pixel height")
    crs: str = Field(description="Source Coordinate Reference System")
    overlay_url: str = Field(description="Direct URL to fetch transparent PNG overlay")

