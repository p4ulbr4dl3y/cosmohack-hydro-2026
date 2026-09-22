"""Схемы Pydantic для сервиса FastAPI HydroWatch Amur."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel


class LandcoverDistribution(BaseModel):
    """Распределение классов типов поверхности и исторической воды в зоне затопления."""

    model_config = ConfigDict(extra="ignore")

    builtup_ha: float = Field(default=0.0, description="Затопленная застроенная / городская территория, га")
    builtup_pct: float = Field(default=0.0, description="Доля площади затопления на застроенных землях, %")
    cropland_ha: float = Field(default=0.0, description="Затопленная пашня (класс 40 ESA WorldCover), га")
    cropland_pct: float = Field(default=0.0, description="Доля площади затопления на пашне, %")
    natural_vegetation_ha: float = Field(default=0.0, description="Затопленные естественные земли / растительность, га")
    natural_vegetation_pct: float = Field(default=0.0, description="Доля площади затопления на естественных землях, %")
    historic_water_extent_ha: float = Field(
        default=0.0, description="Площадь затопления в границах исторического максимума воды JRC GSW, га"
    )
    historic_water_extent_pct: float = Field(default=0.0, description="Доля в границах исторического максимума, %")
    new_flood_extent_ha: float = Field(
        default=0.0, description="Площадь затопления за пределами исторического максимума воды (аномальный паводок), га"
    )
    new_flood_extent_pct: float = Field(default=0.0, description="Доля аномальной площади затопления, %")
    mean_hand_m: float = Field(
        default=0.0, description="Средняя высота над ближайшим водотоком (HAND) в зоне затопления, м"
    )
    source: str = Field(
        default="ESA WorldCover v200 Built-up/Cropland & JRC GSW v1.4",
        description="Источники данных по типам поверхности и базовой воде",
    )


class DepthStatistics(BaseModel):
    """Разбивка рисков по глубине воды и проходимости техники МЧС."""

    model_config = ConfigDict(extra="ignore")

    low_risk_ha: float = Field(
        default=0.0, description="Площадь затопления с глубиной < 0.5 м (проходимо грузовиками / КамАЗ)"
    )
    low_risk_pct: float = Field(default=0.0, description="Доля площади затопления в классе низкого риска, %")
    medium_risk_ha: float = Field(
        default=0.0,
        description="Площадь затопления с глубиной 0.5 - 1.5 м (только гусеничные плавающие транспортеры ПТС-М)",
    )
    medium_risk_pct: float = Field(default=0.0, description="Доля площади затопления в классе среднего риска, %")
    high_risk_ha: float = Field(
        default=0.0, description="Площадь затопления с глубиной > 1.5 м (только лодки и спасательные плавсредства)"
    )
    high_risk_pct: float = Field(default=0.0, description="Доля площади затопления в классе высокого риска, %")
    mean_depth_m: float = Field(default=0.0, description="Средняя глубина воды по зоне затопления, м")
    max_depth_m: float = Field(default=0.0, description="Максимальная расчетная глубина воды в зоне затопления, м")
    mchs_traversability: dict[str, str] = Field(
        default_factory=dict, description="Читаемые описания классификации техники МЧС"
    )


class GaugeStatus(BaseModel):
    """Состояние гидрологического поста и уровни воды относительно критических отметок."""

    model_config = ConfigDict(extra="ignore")

    station_id: str = Field(description="Код наблюдательного поста Росгидромета")
    station_name: str = Field(description="Название поста / населенного пункта")
    river: str = Field(description="Название наблюдаемой реки")
    observed_level_cm: float = Field(description="Наблюдаемый / пиковый уровень воды, см")
    npu_cm: float = Field(description="Нормальный подпорный уровень / отметка поймы (НПУ), см")
    nya_cm: float = Field(description="Уровень неблагоприятного явления (НЯ), см")
    oya_cm: float = Field(description="Уровень опасного явления (ОЯ), см")
    exceeds_npu: bool = Field(description="Истина, если уровень воды достиг или превысил НПУ")
    exceeds_oya: bool = Field(description="Истина, если уровень воды достиг или превысил опасный уровень ОЯ")
    stage_risk: str = Field(description="Стадия риска: normal, floodplain_npu, warning_nya, danger_oya")


class PairInfo(BaseModel):
    """Паспорт метаданных наблюдаемой пары AOI."""

    model_config = ConfigDict(extra="ignore")

    pair_id: str = Field(description="Уникальный идентификатор пары паводка или базового уровня")
    aoi_id: str = Field(description="Код населенного пункта / участка AOI")
    aoi_name: str = Field(description="Читаемое название населенного пункта AOI")
    event_id: str = Field(description="Идентификатор гидрологического события")
    event_name: str = Field(description="Описательное название события")
    event_kind: str = Field(description="'flood' или 'baseline'")
    year: int = Field(description="Год наблюдения")
    sensor_sar: str = Field(default="", description="Радиолокационный сенсор, напр. Sentinel-1")
    sensor_optical: str = Field(default="", description="Оптический сенсор, напр. Sentinel-2")
    date_pre_sar: str = Field(default="", description="Опорная дата радиолокационной съемки до события (ГГГГ-ММ-ДД)")
    date_peak_sar: str = Field(default="", description="Дата пика паводка по радиолокационной съемке (ГГГГ-ММ-ДД)")
    date_pre_opt: str = Field(default="", description="Оптическая дата до паводка, если доступна")
    date_peak_opt: str = Field(default="", description="Оптическая дата пика, если доступна")
    aoi_km2: float = Field(description="Размер зоны интереса, км2")
    aoi_ha: float = Field(description="Размер зоны интереса, га")
    bounds_4326: list[float] = Field(
        description="Ограничивающий прямоугольник [min_lon, min_lat, max_lon, max_lat] в EPSG:4326"
    )
    center_4326: list[float] = Field(description="Координата центра [lat, lon] в EPSG:4326")


class PairsListResponse(RootModel[list[PairInfo]]):
    """Список всех наблюдаемых пар с метаданными."""

    root: list[PairInfo] = Field(description="Набор наблюдаемых пар AOI")


class ReportResponse(BaseModel):
    """Подробный сводный гидрологический отчёт для пары."""

    model_config = ConfigDict(extra="ignore")

    pair_id: str = Field(description="Идентификатор пары")
    aoi_id: str = Field(description="Код AOI")
    aoi_name: str = Field(description="Название AOI")
    event_id: str = Field(description="Код события")
    event_name: str = Field(description="Название события")
    event_kind: str = Field(description="Тип события ('flood' или 'baseline')")
    year: int = Field(description="Год наблюдения")
    sensor_sar: str = Field(default="", description="Идентификатор радиолокационного сенсора, напр. sentinel1")
    sensor_optical: str = Field(default="", description="Идентификатор оптического сенсора, напр. sentinel2")
    date_pre_sar: str = Field(default="", description="Дата радиолокационной съемки до паводка")
    date_peak_sar: str = Field(default="", description="Дата радиолокационной съемки пика паводка")
    date_pre_opt: str = Field(default="", description="Оптическая дата до паводка")
    date_peak_opt: str = Field(default="", description="Оптическая дата пика паводка")
    bounds_4326: list[float] = Field(description="Границы AOI [min_lon, min_lat, max_lon, max_lat]")
    center_4326: list[float] = Field(description="Координаты центра AOI [lat, lon]")
    aoi_ha: float = Field(description="Общая площадь AOI, га")
    aoi_km2: float = Field(description="Общая площадь AOI, км2")
    flood_ha: float = Field(description="Чистая площадь затопления, га")
    flood_km2: float = Field(description="Чистая площадь затопления, км2")
    water_pre_ha: float = Field(description="Площадь воды до паводка, га")
    water_pre_km2: float = Field(description="Площадь воды до паводка, км2")
    water_peak_ha: float = Field(description="Площадь воды на пике, га")
    water_peak_km2: float = Field(description="Площадь воды на пике, км2")
    permanent_ha: float = Field(description="Площадь постоянной базовой воды, га")
    receded_ha: float = Field(default=0.0, description="Площадь спада воды до пика, га")
    water_gain_ha: float = Field(description="Чистый прирост зеркала воды, га")
    water_gain_pct: float = Field(description="Процент прироста относительно воды до паводка")
    share_of_aoi: float = Field(description="Доля площади затопления от всей AOI")
    flood_share_pct: float = Field(description="Процент площади затопления от всей AOI")
    generated_at: str = Field(default="", description="Отметка времени UTC формирования отчета")
    landcover: LandcoverDistribution = Field(description="Разбивка уязвимости и типов поверхности")
    depth_statistics: DepthStatistics = Field(
        default_factory=DepthStatistics, description="Статистика глубины воды и проходимости техники МЧС"
    )
    gauge_status: GaugeStatus | None = Field(
        default=None, description="Отметки уровня воды гидрологического поста и стадия опасности"
    )
    uncertainty: FloodUncertaintyResponse | None = Field(
        default=None, description="Оценка пространственной неопределенности"
    )
    audit: HydroAuditCertificateResponse | None = Field(
        default=None, description="Криптографический аудиторский сертификат Merkle"
    )
    sar_analytics: SARAnalyticsResponse | None = Field(
        default=None, description="Радиолокационная поляриметрическая аналитика Sentinel-1"
    )
    meteo: dict[str, Any] | None = Field(
        default=None, description="Гидрометеорологический контекст и прекурсоры осадков ERA5"
    )
    carbon_impact: FloodCarbonImpactResponse | None = Field(
        default=None, description="Углеродные и биомассовые потери по IPCC"
    )
    competition_score: dict[str, Any] | None = Field(
        default=None, description="Сходимость официальной соревновательной метрики"
    )
    anomaly_note: dict[str, Any] | None = Field(
        default=None,
        description="Детальный анализ расхождения физической наземной истины и эталона для известных аномалий",
    )


class PredictSummary(BaseModel):
    """Сводные метрики вывода по затоплению."""

    model_config = ConfigDict(extra="ignore")

    flood_ha: float = Field(description="Площадь затопления, га")
    flood_km2: float = Field(description="Площадь затопления, км2")
    water_pre_ha: float = Field(description="Площадь воды до события, га")
    water_peak_ha: float = Field(description="Площадь воды на пике, га")
    water_gain_ha: float = Field(description="Прирост зеркала воды, га")
    water_gain_pct: float = Field(description="Процент прироста воды")
    receded_ha: float = Field(default=0.0, description="Площадь спада воды, га")
    share_of_aoi: float = Field(default=0.0, description="Доля затопления от AOI")
    landcover: LandcoverDistribution | dict[str, Any] = Field(
        default_factory=dict, description="Разбивка типов поверхности в зоне затопления"
    )
    depth_statistics: DepthStatistics | dict[str, Any] = Field(
        default_factory=dict, description="Статистика глубины воды и проходимости техники МЧС"
    )
    gauge_status: GaugeStatus | dict[str, Any] | None = Field(
        default=None, description="Состояние гидрологического поста"
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

    status: str = Field(default="success", description="Индикатор состояния")
    pair_id: str = Field(description="Определенный идентификатор пары")
    query_bounds: list[float] | None = Field(default=None, description="Запрошенные пользователем границы")
    query_polygon: dict[str, Any] | None = Field(default=None, description="Запрошенный пользователем полигон GeoJSON")
    query_dates: dict[str, str | None] | None = Field(default=None, description="Запрошенные пользователем даты")
    scene_dates: dict[str, str | None] | None = Field(
        default=None, description="Фактические использованные даты радиолокационных сцен"
    )
    requested_dates: dict[str, str | None] | None = Field(default=None, description="Проверенные запрошенные даты")
    summary: PredictSummary = Field(description="Гидрологические расчеты площадей")
    metadata: PredictMetadata = Field(description="Паспортные метаданные AOI")
    geojson: dict[str, Any] | None = Field(default=None, description="Векторные полигоны затопления в формате GeoJSON")


class PredictionTaskResponse(BaseModel):
    """Нагрузка статуса для асинхронной задачи прогнозирования."""

    model_config = ConfigDict(extra="ignore")

    task_id: str = Field(description="Уникальный идентификатор задачи прогноза")
    status: str = Field(
        default="completed",
        description="Статус жизненного цикла задачи прогноза: 'pending', 'processing', 'completed', 'failed'",
    )
    progress: float = Field(default=1.0, ge=0.0, le=1.0, description="Доля выполнения от 0.0 до 1.0")
    result: PredictResponse | None = Field(
        default=None, description="Полезная нагрузка результата прогноза по завершении задачи"
    )
    error: str | None = Field(default=None, description="Описание ошибки, если задача завершилась сбоем")


class PredictRequest(BaseModel):
    """Нагрузка запроса для пространственно-временного прогноза затопления."""

    model_config = ConfigDict(extra="ignore")

    pair_id: str | None = Field(
        default=None, description="Идентификатор пары, напр. flood_2019_07_amur__blagoveshchensk"
    )
    bounds: list[float] | None = Field(default=None, description="[min_lon, min_lat, max_lon, max_lat] в EPSG:4326")
    polygon: dict[str, Any] | None = Field(
        default=None, description="Геометрия GeoJSON (Polygon) в EPSG:4326; имеет приоритет над границами"
    )
    date_pre: str | None = Field(default=None, description="Опорная дата до паводка (ГГГГ-ММ-ДД)")
    date_peak: str | None = Field(default=None, description="Дата пика паводка (ГГГГ-ММ-ДД)")
    task_id: str | None = Field(
        default=None, description="Необязательный идентификатор задачи асинхронного отслеживания"
    )


class DepthRiskZone(BaseModel):
    """Статистическая разбивка зоны риска затопления по глубине и рельефу HAND."""

    model_config = ConfigDict(extra="ignore")

    depth_range: str = Field(description="Критерии глубины и рельефа HAND")
    area_ha: float = Field(description="Площадь затопления в этой категории глубины, га")
    share_pct: float = Field(description="Доля от общей площади затопления, %")
    description: str = Field(description="Описание операционных последствий и доступа техники")


class DepthRiskBreakdown(BaseModel):
    """Разбивка риска по высокому, умеренному и низкому уровням глубины."""

    model_config = ConfigDict(extra="ignore")

    high_risk: DepthRiskZone = Field(description="Зона высокого риска (глубина > 1.5 м)")
    moderate_risk: DepthRiskZone = Field(description="Зона умеренного риска (глубина 0.5 - 1.5 м)")
    low_risk: DepthRiskZone = Field(description="Зона низкого риска (глубина < 0.5 м)")


class TransportInfrastructureRisk(BaseModel):
    """Оценка риска отсечения и изоляции транспортной сети."""

    model_config = ConfigDict(extra="ignore")

    cutoff_segments_count: int = Field(description="Оценка числа отрезанных / подтопленных участков дорог")
    estimated_cutoff_km: float = Field(description="Оценка линейной длины подтопленных участков дорог, км")
    risk_level: str = Field(description="Классификация уровня риска: критический, высокий, умеренный, штатный")
    description: str = Field(description="Операционная оценка и сводка влияния на транспорт")


class MchsDispatchResponse(BaseModel):
    """Официальное оперативное полевое донесение МЧС по стандартам EMERCOM."""

    model_config = ConfigDict(extra="ignore")

    document_header: str = Field(description="Официальный заголовок документа")
    form_code: str = Field(description="Код формы донесения МЧС России (напр. 1/ЧС)")
    department: str = Field(description="Курирующее подразделение МЧС и центр управления в кризисных ситуациях")
    dispatch_id: str = Field(description="Уникальный идентификатор донесения")
    pair_id: str = Field(description="Идентификатор наблюдаемой пары")
    timestamp_utc: str = Field(description="Отметка времени формирования отчета в UTC")
    status: str = Field(description="Операционный статус чрезвычайной ситуации")
    event_type: str = Field(description="Тип и классификация чрезвычайного события")
    event_id: str = Field(description="Код идентификатора события")
    event_name: str = Field(description="Описательное название события")
    aoi_id: str = Field(description="Код зоны интереса")
    aoi_name: str = Field(description="Название зоны интереса")
    date_peak: str = Field(description="Дата пикового наблюдения (ГГГГ-ММ-ДД)")
    date_pre: str = Field(description="Дата базового наблюдения до события (ГГГГ-ММ-ДД)")
    affected_municipalities: list[str] = Field(
        description="Список пострадавших муниципальных районов / городских округов"
    )
    flooded_total_ha: float = Field(description="Общая площадь затопления, га")
    flooded_total_km2: float = Field(description="Общая площадь затопления, км2")
    flooded_builtup_area_ha: float = Field(description="Затопленная застроенная / жилая территория, га")
    flooded_builtup_ha: float = Field(description="Синоним затопленной застроенной территории, га")
    flooded_cropland_area_ha: float = Field(description="Затопленная сельскохозяйственная / пахотная территория, га")
    flooded_cropland_ha: float = Field(description="Синоним затопленной пахотной территории, га")
    flooded_natural_ha: float = Field(description="Затопленные естественные / пойменные земли, га")
    estimated_cutoff_transport_segments: int = Field(description="Оценка числа отрезанных транспортных участков")
    transport_infrastructure: TransportInfrastructureRisk = Field(
        description="Детализация риска транспортной инфраструктуры"
    )
    depth_risk_breakdown: DepthRiskBreakdown = Field(description="Разбивка риска по глубине воды")
    operational_summary: str = Field(description="Операционная сводка для руководства")
    recommended_actions: list[str] = Field(description="Список приоритетных действий по реагированию")


class HydroAuditCertificateResponse(BaseModel):
    """Схема ответа криптографического аудиторского сертификата Merkle."""

    model_config = ConfigDict(extra="ignore")

    certificate_id: str = Field(description="Уникальный идентификатор сертификата")
    pair_id: str = Field(description="Идентификатор пары")
    aoi_id: str = Field(description="Код AOI")
    issued_at: str = Field(description="Отметка времени выпуска в UTC по ISO-8601")
    merkle_root: str = Field(description="Шестнадцатеричный корень дерева Merkle SHA-256")
    leaf_count: int = Field(description="Общее число проверенных компонентов/листьев дерева")
    status: str = Field(description="Статус проверки: 'VERIFIED'")
    algorithm: str = Field(description="Версия протокола аудита")
    signature_hash: str = Field(description="Канонический дайджест подписи целостности SHA-256")
    summary: dict[str, Any] = Field(description="Сводные гидрологические метрики")
    leaves: list[dict[str, Any]] = Field(description="Проверенные листовые узлы Merkle")

    # Псевдонимы для совместимости с фронтендом
    merkle_root_sha256: str | None = Field(default=None, description="Синоним merkle_root")
    inputs_hash_sha256: str | None = Field(default=None, description="Дайджест SHA-256 входных сцен")
    parameters_hash_sha256: str | None = Field(default=None, description="Дайджест SHA-256 параметров обработки")
    results_hash_sha256: str | None = Field(default=None, description="Дайджест SHA-256 выходных масок затопления")
    timestamp: str | None = Field(default=None, description="Синоним issued_at")
    verified: bool = Field(default=True, description="Булев статус проверки")


class FloodUncertaintyResponse(BaseModel):
    """Схема ответа пространственной неопределённости и доверительных интервалов."""

    model_config = ConfigDict(extra="ignore")

    pair_id: str = Field(description="Идентификатор пары")
    area_ha: float = Field(description="Центральная площадь затопления, га")
    confidence_level: float = Field(description="Статистический уровень доверия (напр. 0.95)")
    lower_bound_ha: float = Field(description="Консервативная нижняя граница L, га")
    upper_bound_ha: float = Field(description="Верхняя граница U, га")
    margin_ha: float = Field(description="Абсолютный запас неопределенности H, га")
    relative_uncertainty_pct: float = Field(description="Относительный запас неопределенности, %")
    sigma_effective_ha: float = Field(description="Эффективная стандартная ошибка с пространственной ковариацией, га")
    effective_n_pixels: float = Field(description="Эффективное число независимых наблюдений")
    spatial_correlation: float = Field(description="Принятая пространственная автокорреляция ошибки rho")


class SARAnalyticsResponse(BaseModel):
    """Схема ответа радиолокационной аналитики Sentinel-1."""

    model_config = ConfigDict(extra="ignore")

    pair_id: str = Field(description="Идентификатор пары")
    water_fraction: float = Field(description="Доля площади с зеркальным отражением воды")
    water_area_ha: float = Field(description="Площадь зеркала воды по оценке SAR, га")
    mean_vv_db: float = Field(description="Среднее обратное рассеяние VV, дБ")
    mean_vh_db: float = Field(description="Среднее обратное рассеяние VH, дБ")
    mean_vh_vv_ratio: float = Field(description="Среднее отношение кросс-поляризации (VH - VV), дБ")
    radar_contrast_db: float = Field(description="Радиолокационный контраст между водой и сушей, дБ")
    cloud_penetration_verified: bool = Field(description="Подтверждено ли всепогодное проникновение сквозь облака")
    double_bounce_fraction: float = Field(description="Доля предполагаемой сигнатуры затопленной растительности")


class OverlayMetadataResponse(BaseModel):
    """Ответ с метаданными для растрового PNG-оверлея карты."""

    model_config = ConfigDict(extra="ignore")

    pair_id: str = Field(description="Идентификатор пары")
    layer: str = Field(description="Название слоя: 'flood', 'water_pre', 'water_peak'")
    bounds: list[list[float]] = Field(description="Координаты оверлея Leaflet WGS84 [[south, west], [north, east]]")
    width: int = Field(description="Ширина изображения в пикселях")
    height: int = Field(description="Высота изображения в пикселях")
    crs: str = Field(description="Исходная система координат")
    overlay_url: str = Field(description="Прямой URL для получения прозрачного PNG-оверлея")


class OfficialMetricsResponse(BaseModel):
    """Разбивка актуальной официальной оценки соревнования (docs/TASK_SPEC.md)."""

    model_config = ConfigDict(extra="ignore")

    score: float = Field(
        description="Официальная метрика = 0.45*Q_flood + 0.25*Q_water_peak + 0.15*Q_water_pre + 0.15*Spec_base"
    )
    q_flood: float = Field(description="Средняя сходимость площади затопления Q_flood")
    q_water_peak: float = Field(description="Средняя сходимость площади воды на пике Q_water_peak")
    q_water_pre: float = Field(description="Средняя сходимость площади воды до паводка Q_water_pre")
    spec_base: float = Field(description="Специфичность базового меженного уровня Spec_base")
    num_events: int = Field(description="Число оцененных паводковых событий (8)")
    num_baselines: int = Field(description="Число оцененных базовых меженных пар (3)")
    technical_points: float = Field(description="Нормализованные баллы по техническим критериям оценки (0-7)")
    details: list[dict[str, Any]] = Field(description="Детальная сходимость по каждой паре")


class SubmissionValidationResponse(BaseModel):
    """Отчёт проверки submission.csv и растровых масок (docs/CRITERIA.md)."""

    model_config = ConfigDict(extra="ignore")

    is_valid: bool = Field(description="Соответствует ли посылка всем обязательным критериям соревнования")
    num_pairs: int = Field(description="Общее число оцененных пар в посылке")
    passed_checks: list[str] = Field(description="Список проверенных правил")
    errors: list[str] = Field(description="Критические ошибки, дисквалифицирующие посылку")
    warnings: list[str] = Field(description="Предупреждения или некритические замечания")
    discrepancies: list[dict[str, Any]] = Field(
        description="Анализ расхождения растра и CSV по каждой паре (правило 2%)"
    )


class FloodCarbonImpactResponse(BaseModel):
    """Оценка потерь биомассы и запасов углерода для паводковых событий."""

    model_config = ConfigDict(extra="ignore")

    pair_id: str = Field(description="Идентификатор пары")
    flood_ha: float = Field(description="Общая площадь затопления, га")
    biomass_loss_dry_matter_t: float = Field(description="Оценка уничтоженной/смытой сухой биомассы, т")
    carbon_loss_tC: float = Field(description="Потеря запаса углерода, т C (CF=0.47)")
    emissions_equivalent_tCO2e: float = Field(description="Эквивалент выбросов, т CO2e (коэффициент 44/12)")
    cropland_loss_tC: float = Field(description="Углерод, потерянный на сельхозземлях, т C")
    forest_loss_tC: float = Field(description="Углерод, потерянный в затопленных лесах/древесном покрове, т C")
    credit_potential: dict[str, Any] = Field(description="Потенциал углеродных кредитов Q и оценки")
    notes: str = Field(description="Методическое пояснение")


ReportResponse.model_rebuild()
