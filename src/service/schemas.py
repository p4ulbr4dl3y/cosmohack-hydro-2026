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


class DepthStatistics(BaseModel):
    """Water depth and MCHS vehicle traversability risk breakdown."""

    model_config = ConfigDict(extra="ignore")

    low_risk_ha: float = Field(
        default=0.0, description="Flood area with depth < 0.5 m (regular trucks / KamAZ accessible)"
    )
    low_risk_pct: float = Field(default=0.0, description="Percentage of flood area in low risk class")
    medium_risk_ha: float = Field(
        default=0.0, description="Flood area with depth 0.5 - 1.5 m (PTS-M tracked amphibious transporters only)"
    )
    medium_risk_pct: float = Field(default=0.0, description="Percentage of flood area in medium risk class")
    high_risk_ha: float = Field(
        default=0.0, description="Flood area with depth > 1.5 m (boats, water rescue crafts only)"
    )
    high_risk_pct: float = Field(default=0.0, description="Percentage of flood area in high risk class")
    mean_depth_m: float = Field(default=0.0, description="Mean water depth across flooded area (meters)")
    max_depth_m: float = Field(default=0.0, description="Maximum estimated water depth in flooded area (meters)")
    mchs_traversability: dict[str, str] = Field(
        default_factory=dict, description="Human-readable MCHS vehicle classification descriptions"
    )


class GaugeStatus(BaseModel):
    """Hydrological station gauge status and water levels relative to critical marks."""

    model_config = ConfigDict(extra="ignore")

    station_id: str = Field(description="Rosgidromet observation station code")
    station_name: str = Field(description="Station name / settlement")
    river: str = Field(description="Monitored river name")
    observed_level_cm: float = Field(description="Observed / peak water level in cm")
    npu_cm: float = Field(description="Normal Pool Level / Floodplain benchmark (НПУ) in cm")
    nya_cm: float = Field(description="Adverse phenomenon level (НЯ) in cm")
    oya_cm: float = Field(description="Hazardous phenomenon level (ОЯ) in cm")
    exceeds_npu: bool = Field(description="True if water level reached or exceeded NPU")
    exceeds_oya: bool = Field(description="True if water level reached or exceeded hazardous OYA level")
    stage_risk: str = Field(description="Risk stage: normal, floodplain_npu, warning_nya, danger_oya")


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
    depth_statistics: DepthStatistics = Field(
        default_factory=DepthStatistics, description="Water depth and MCHS vehicle traversability risk statistics"
    )
    gauge_status: GaugeStatus | None = Field(
        default=None, description="Hydrological station water level benchmark and danger stage"
    )


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
    depth_statistics: DepthStatistics | dict[str, Any] = Field(
        default_factory=dict, description="Water depth and MCHS vehicle traversability risk statistics"
    )
    gauge_status: GaugeStatus | dict[str, Any] | None = Field(
        default=None, description="Hydrological station gauge status"
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


class DepthRiskZone(BaseModel):
    """Statistical breakdown of flood risk zone by depth and terrain HAND."""

    model_config = ConfigDict(extra="ignore")

    depth_range: str = Field(description="Depth and terrain HAND criteria")
    area_ha: float = Field(description="Flooded area in hectares in this depth category")
    share_pct: float = Field(description="Percentage share of total flood area")
    description: str = Field(description="Operational impact and vehicle access description")


class DepthRiskBreakdown(BaseModel):
    """Risk breakdown across high, moderate, and low depth tiers."""

    model_config = ConfigDict(extra="ignore")

    high_risk: DepthRiskZone = Field(description="High risk zone (> 1.5 m water depth)")
    moderate_risk: DepthRiskZone = Field(description="Moderate risk zone (0.5 - 1.5 m water depth)")
    low_risk: DepthRiskZone = Field(description="Low risk zone (< 0.5 m water depth)")


class TransportInfrastructureRisk(BaseModel):
    """Estimated transport network cut-off and isolation risk."""

    model_config = ConfigDict(extra="ignore")

    cutoff_segments_count: int = Field(description="Estimated number of cut-off / submerged road segments")
    estimated_cutoff_km: float = Field(description="Estimated linear length of submerged road segments in km")
    risk_level: str = Field(description="Risk level classification: критический, высокий, умеренный, штатный")
    description: str = Field(description="Operational assessment and traffic impact summary")


class MchsDispatchResponse(BaseModel):
    """Official MCHS operational emergency field dispatch conforming to EMERCOM standards."""

    model_config = ConfigDict(extra="ignore")

    document_header: str = Field(description="Formal official document header")
    form_code: str = Field(description="Russian EMERCOM report form code (e.g. 1/ЧС)")
    department: str = Field(description="Supervising EMERCOM department and crisis management center")
    dispatch_id: str = Field(description="Unique dispatch identifier")
    pair_id: str = Field(description="Monitored pair identifier")
    timestamp_utc: str = Field(description="Report generation timestamp in UTC")
    status: str = Field(description="Operational emergency status")
    event_type: str = Field(description="Emergency event type and classification")
    event_id: str = Field(description="Event identifier code")
    event_name: str = Field(description="Descriptive event name")
    aoi_id: str = Field(description="Area of interest code")
    aoi_name: str = Field(description="Area of interest name")
    date_peak: str = Field(description="Peak observation date (YYYY-MM-DD)")
    date_pre: str = Field(description="Pre-event baseline observation date (YYYY-MM-DD)")
    affected_municipalities: list[str] = Field(description="List of affected municipal districts / urban okrugs")
    flooded_total_ha: float = Field(description="Total flooded area in hectares")
    flooded_total_km2: float = Field(description="Total flooded area in square kilometers")
    flooded_builtup_area_ha: float = Field(description="Flooded built-up / residential area in hectares")
    flooded_builtup_ha: float = Field(description="Alias for flooded built-up area in hectares")
    flooded_cropland_area_ha: float = Field(description="Flooded agricultural / cropland area in hectares")
    flooded_cropland_ha: float = Field(description="Alias for flooded cropland area in hectares")
    flooded_natural_ha: float = Field(description="Flooded natural / floodplain land in hectares")
    estimated_cutoff_transport_segments: int = Field(description="Estimated number of cut-off transport segments")
    transport_infrastructure: TransportInfrastructureRisk = Field(description="Transport infrastructure risk detail")
    depth_risk_breakdown: DepthRiskBreakdown = Field(description="Water depth risk breakdown")
    operational_summary: str = Field(description="Executive operational summary")
    recommended_actions: list[str] = Field(description="List of prioritized emergency response actions")
