"""Схемы Pydantic для сервиса FastAPI HydroWatch Amur."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel


class LandcoverDistribution(BaseModel):
    """Распределение классов типов поверхности и исторической воды в зоне затопления."""

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
    """Разбивка рисков по глубине воды и проходимости техники МЧС."""

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
    """Состояние гидрологического поста и уровни воды относительно критических отметок."""

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
    """Паспорт метаданных наблюдаемой пары AOI."""

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
    """Список всех наблюдаемых пар с метаданными."""

    root: list[PairInfo] = Field(description="Collection of monitored AOI pairs")


class ReportResponse(BaseModel):
    """Подробный сводный гидрологический отчёт для пары."""

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
    """Сводные метрики вывода по затоплению."""

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
    """Пространственные и временные метаданные выходных данных вывода."""

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
    """Нагрузка ответа для пространственно-временного прогноза затопления."""

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
    """Нагрузка статуса для асинхронной задачи прогнозирования."""

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
    """Нагрузка запроса для пространственно-временного прогноза затопления."""

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
    """Статистическая разбивка зоны риска затопления по глубине и рельефу HAND."""

    model_config = ConfigDict(extra="ignore")

    depth_range: str = Field(description="Depth and terrain HAND criteria")
    area_ha: float = Field(description="Flooded area in hectares in this depth category")
    share_pct: float = Field(description="Percentage share of total flood area")
    description: str = Field(description="Operational impact and vehicle access description")


class DepthRiskBreakdown(BaseModel):
    """Разбивка риска по высокому, умеренному и низкому уровням глубины."""

    model_config = ConfigDict(extra="ignore")

    high_risk: DepthRiskZone = Field(description="High risk zone (> 1.5 m water depth)")
    moderate_risk: DepthRiskZone = Field(description="Moderate risk zone (0.5 - 1.5 m water depth)")
    low_risk: DepthRiskZone = Field(description="Low risk zone (< 0.5 m water depth)")


class TransportInfrastructureRisk(BaseModel):
    """Оценка риска отсечения и изоляции транспортной сети."""

    model_config = ConfigDict(extra="ignore")

    cutoff_segments_count: int = Field(description="Estimated number of cut-off / submerged road segments")
    estimated_cutoff_km: float = Field(description="Estimated linear length of submerged road segments in km")
    risk_level: str = Field(description="Risk level classification: критический, высокий, умеренный, штатный")
    description: str = Field(description="Operational assessment and traffic impact summary")


class MchsDispatchResponse(BaseModel):
    """Официальное оперативное полевое донесение МЧС по стандартам EMERCOM."""

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


class HydroAuditCertificateResponse(BaseModel):
    """Схема ответа криптографического аудиторского сертификата Merkle."""

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

    # Псевдонимы для совместимости с фронтендом
    merkle_root_sha256: str | None = Field(default=None, description="Alias for merkle_root")
    inputs_hash_sha256: str | None = Field(default=None, description="SHA-256 digest of input scenes")
    parameters_hash_sha256: str | None = Field(default=None, description="SHA-256 digest of processing parameters")
    results_hash_sha256: str | None = Field(default=None, description="SHA-256 digest of output flood masks")
    timestamp: str | None = Field(default=None, description="Alias for issued_at")
    verified: bool = Field(default=True, description="Verification status boolean")


class FloodUncertaintyResponse(BaseModel):
    """Схема ответа пространственной неопределённости и доверительных интервалов."""

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
    """Схема ответа радиолокационной аналитики Sentinel-1."""

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
    """Ответ с метаданными для растрового PNG-оверлея карты."""

    model_config = ConfigDict(extra="ignore")

    pair_id: str = Field(description="Pair identifier")
    layer: str = Field(description="Layer name: 'flood', 'water_pre', 'water_peak'")
    bounds: list[list[float]] = Field(description="Leaflet WGS84 overlay coordinates [[south, west], [north, east]]")
    width: int = Field(description="Image pixel width")
    height: int = Field(description="Image pixel height")
    crs: str = Field(description="Source Coordinate Reference System")
    overlay_url: str = Field(description="Direct URL to fetch transparent PNG overlay")


class OfficialMetricsResponse(BaseModel):
    """Разбивка актуальной официальной оценки соревнования (docs/TASK_SPEC.md)."""

    model_config = ConfigDict(extra="ignore")

    score: float = Field(
        description="Official Score = 0.45*Q_flood + 0.25*Q_water_peak + 0.15*Q_water_pre + 0.15*Spec_base"
    )
    q_flood: float = Field(description="Mean flood area convergence score Q_flood")
    q_water_peak: float = Field(description="Mean peak water area convergence score Q_water_peak")
    q_water_pre: float = Field(description="Mean pre-flood water area convergence score Q_water_pre")
    spec_base: float = Field(description="Baseline low-water specificity Spec_base")
    num_events: int = Field(description="Number of evaluated flood events (8)")
    num_baselines: int = Field(description="Number of evaluated baseline low-water pairs (3)")
    technical_points: float = Field(description="Normalized points for technical evaluation criteria (0-7)")
    details: list[dict[str, Any]] = Field(description="Detailed per-pair convergence stats")


class SubmissionValidationResponse(BaseModel):
    """Отчёт проверки submission.csv и растровых масок (docs/CRITERIA.md)."""

    model_config = ConfigDict(extra="ignore")

    is_valid: bool = Field(description="Whether submission meets all mandatory competition criteria")
    num_pairs: int = Field(description="Total evaluated pairs in submission")
    passed_checks: list[str] = Field(description="List of verified rule checks")
    errors: list[str] = Field(description="Critical errors that disqualify submission")
    warnings: list[str] = Field(description="Warnings or non-critical issues")
    discrepancies: list[dict[str, Any]] = Field(description="Per-pair raster vs CSV divergence analysis (2% rule)")


class FloodCarbonImpactResponse(BaseModel):
    """Оценка потерь биомассы и запасов углерода для паводковых событий."""

    model_config = ConfigDict(extra="ignore")

    pair_id: str = Field(description="Pair identifier")
    flood_ha: float = Field(description="Total inundated area in hectares")
    biomass_loss_dry_matter_t: float = Field(description="Estimated dry biomass destroyed/washed out (tonnes)")
    carbon_loss_tC: float = Field(description="Carbon stock loss (tonnes C, CF=0.47)")
    emissions_equivalent_tCO2e: float = Field(description="Emissions equivalent (tonnes CO2e, ratio 44/12)")
    cropland_loss_tC: float = Field(description="Carbon lost on agricultural lands (t C)")
    forest_loss_tC: float = Field(description="Carbon lost in flooded forests/tree cover (t C)")
    credit_potential: dict[str, Any] = Field(description="Mitigation carbon credits potential Q and valuations")
    notes: str = Field(description="Methodological explanatory summary")
