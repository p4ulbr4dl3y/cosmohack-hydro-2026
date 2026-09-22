"""Экспериментальный модуль экспресс-оценки углеродного воздействия и Green AI.

Внимание: является ориентировочной прокси-оценкой биомассы на основе методологических принципов
IPCC / VM0047 (без статуса юридически обязывающего или сертифицированного аудита углеродных офсетов):
1. Метод разницы запасов (экспресс-прокси):
   - c_i = b_i * CF (CF = 0.47 т C / т сухого вещества, значение IPCC по умолчанию);
   - C_t = sum(a_i * c_i) (т C);
   - delta_C = C_t1 - C_t0 (т C);
   - E = -delta_C * (44 / 12) (т CO2-экв.);
   - e = E / (A * delta_t) (т CO2-экв. / га / год).

2. Потенциал оценки углеродного баланса Q (модельный ориентир):
   - R = E_base - E_proj - LK (LK = 0);
   - H = max(|E_proj - L|, |U - E_proj|);
   - if R <= 0 or H/R >= 1.0 => Q = 0;
   - если R > 0 и H/R < 1.0:
     - UNC = min(1.0, max(0.0, H/R - 0.10));
     - R_adj = R * (1 - UNC);
     - B = 0.15 * R_adj (15% рисковой буферный резерв);
     - Q = floor(R_adj * 0.85) (целые единицы углеродных кредитов);
     - оценки V = Q * p для p в [500, 1500, 4000] руб./кредит.

3. Региональные коэффициенты биомассы бассейна реки Амур (Tier 1 vs Tier 2 прокси):
   - Tier 1: общемировые показатели IPCC для умеренной зоны;
   - Tier 2: региональные коэффициенты Приамурья (пойменные ивняки и ольшаники,
     пойменные луга Амура, дубово-берёзовые леса, соевая пашня).

4. Green AI метрики инференса нейросетевых и радарных конвейеров (расчет по TDP):
   - оценочное энергопотребление CPU инференса (кВт·ч);
   - углеродный след инференса (г CO2-экв.) с учётом регионального коэффициента
     энергосистемы Дальнего Востока РФ (ОЭС Востока / Амурская область ~0.35-0.45 кг CO2e/кВт·ч).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

# --- Базовые константы IPCC ---
CF_AGB: float = 0.47  # Доля углерода в надземной сухой биомассе (т C / т сухого вещества)
CO2_PER_C: float = 44.0 / 12.0  # Молярное отношение CO2 к углероду (44/12)
DEFAULT_BUFFER_RATE: float = 0.15  # 15% рисковой буферный резерв
DEFAULT_UNCERTAINTY_THRESHOLD: float = 0.10  # 10% допуск без вычета
DEFAULT_PRICES_RUB: tuple[int, int, int] = (500, 1500, 4000)

# --- Коэффициенты биомассы по уровням детализации (Tier 1 и Tier 2) ---

# IPCC Tier 1 (значения по умолчанию для умеренной зоны, т сухого вещества / га)
TIER1_BIOMASS_DENSITY: dict[str, float] = {
    "cropland": 7.5,  # Сельскохозяйственная пашня
    "forest": 45.0,  # Смешанный лес умеренной зоны
    "wetland": 12.0,  # Кустарник и водно-болотные угодья
    "grassland": 5.0,  # Луга и травяная растительность
    "open_soil": 2.0,  # Залежь и открытый грунт
    "settlement": 1.0,  # Городская застройка
}

# IPCC Tier 2: Региональные коэффициенты бассейна реки Амур / Дальний Восток (т сухого вещества / га)
# Основано на данных Института водных и экологических проблем ДВО РАН и регионального кадастра парниковых газов РФ
TIER2_FAR_EAST_BIOMASS_DENSITY: dict[str, float] = {
    # Специфические категории Приамурья:
    "floodplain_willow_alder_shrubland": 25.0,  # Пойменные ивняки и ольшаники (Salix spp., Alnus spp.)
    "amur_floodplain_meadows": 11.0,  # Вейниковые и осоковые пойменные луга (Calamagrostis langsdorffii, Carex)
    "oak_birch_woodland": 75.0,  # Дубово-берёзовые леса (Quercus mongolica, Betula platyphylla/dahurica)
    "soybean_cropland": 7.0,  # Соевые агроценозы Приамурья (Зейско-Буреинская равнина)
    # Маппинг канонических классов покрова на региональные аналоги Tier 2:
    "cropland": 7.0,  # Соевая пашня
    "forest": 75.0,  # Дубово-берёзовые леса
    "wetland": 25.0,  # Пойменные ивняки и ольшаники
    "grassland": 11.0,  # Пойменные луга Приамурья
    "open_soil": 2.0,  # Открытый грунт и залежь
    "settlement": 1.0,  # Застройка
    # Русскоязычные алиасы
    "соевая_пашня": 7.0,
    "дубово_березовый_лес": 75.0,
    "пойменные_ивняки": 25.0,
    "пойменные_луга": 11.0,
}

# Обратная совместимость: BIOMASS_DENSITY_MAP указывает на Tier 1
BIOMASS_DENSITY_MAP: dict[str, float] = dict(TIER1_BIOMASS_DENSITY)

# --- Green AI: Константы оборудования и региональной энергосистемы ---

# Оценки TDP процессоров (Ватт)
CPU_TDP_PRESETS: dict[str, float] = {
    "standard_cpu": 65.0,  # Стандартный настольный/серверный x86_64 CPU (65 Вт)
    "apple_silicon": 30.0,  # Apple Silicon SoC серии M (30 Вт)
    "server_cpu": 125.0,  # Высокопроизводительный серверный CPU (125 Вт)
    "laptop_cpu": 28.0,  # Мобильный процессор ноутбука (28 Вт)
    "edge_device": 15.0,  # Граничное / встраиваемое устройство (15 Вт)
}
DEFAULT_CPU_TDP_WATTS: float = 65.0

# Региональные коэффициенты углеродоёмкости электроэнергии (кг CO2-экв. / кВт·ч)
# Для Амурской области / Дальнего Востока РФ (ОЭС Востока): ~0.35-0.45 кг CO2e/кВт·ч
REGIONAL_GRID_EMISSION_FACTORS: dict[str, float] = {
    "amur_far_east": 0.38,  # ОЭС Востока / Амурская область (смешанная гидро-угольная генерация)
    "russia_average": 0.35,  # Средний коэффициент энергосистемы РФ
    "hydro_clean": 0.05,  # Локальный каскад Зейской и Бурейской ГЭС
    "coal_heavy": 0.65,  # Угольные ТЭС Дальнего Востока (Райчихинская, Благовещенская ТЭЦ)
    "global_average": 0.475,  # Мировое среднее значение (IEA)
}
DEFAULT_GRID_EMISSION_FACTOR_KG_KWH: float = 0.38  # Амурская область / Дальний Восток РФ


@dataclass(frozen=True)
class CarbonCreditResult:
    """Результат расчёта углеродных кредитов по базовому сценарию."""

    is_available: bool
    status: str
    E_proj_tCO2e: float
    E_base_tCO2e: float
    LK_tCO2e: float
    R_tCO2e: float
    H_tCO2e: float
    H_over_R: float | None
    UNC_deduction_rate: float
    R_adj_tCO2e: float
    buffer_reserve_B_tCO2e: float
    Q_credits: int
    fractional_remainder: float
    valuations_rub: dict[int, float] = field(default_factory=dict)
    area_ha: float = 0.0
    delta_t_years: int = 1
    error_message: str | None = None


@dataclass(frozen=True)
class FloodCarbonImpact:
    """Анализ углеродного следа ущерба от паводка и ESG-воздействия."""

    pair_id: str
    flood_ha: float
    biomass_loss_dry_matter_t: float
    carbon_loss_tC: float
    emissions_equivalent_tCO2e: float
    cropland_loss_tC: float
    forest_loss_tC: float
    credit_potential: CarbonCreditResult
    notes: str
    tier: int = 1
    tier_name: str = "IPCC Tier 1 (общемировые значения по умолчанию)"
    biomass_density_factors: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class GreenAIMetrics:
    """Метрики Green AI: энергопотребление и углеродный след CPU-инференса нейросетей."""

    duration_seconds: float
    energy_kwh: float
    carbon_emissions_gCO2e: float
    carbon_emissions_kgCO2e: float
    tdp_watts: float
    cpu_utilization: float
    pue: float
    grid_emission_factor_kg_per_kwh: float
    hardware_preset: str | None = None
    grid_region: str | None = None
    notes: str = ""


def get_biomass_density_map(tier: int | str = 1) -> dict[str, float]:
    """Возвращает справочник плотности биомассы (т сух. в-ва / га) для выбранного уровня Tier.

    - tier=1: Общемировые коэффициенты IPCC Tier 1 по умолчанию для умеренной зоны;
    - tier=2: Региональные коэффициенты IPCC Tier 2 для бассейна реки Амур (Дальний Восток РФ:
      соевые агроценозы, дубово-берёзовые леса, пойменные ивняки и ольшаники, пойменные луга).
    """
    tier_str = str(tier).strip().lower()
    if tier_str in ("2", "tier2", "tier_2", "regional", "far_east", "amur"):
        return dict(TIER2_FAR_EAST_BIOMASS_DENSITY)
    return dict(TIER1_BIOMASS_DENSITY)


def get_biomass_density(landcover_type: str, tier: int | str = 1) -> float:
    """Возвращает удельную плотность биомассы (т сух. в-ва / га) для типа покрова и выбранного Tier."""
    density_map = get_biomass_density_map(tier)
    normalized = landcover_type.strip().lower()

    if normalized in density_map:
        return density_map[normalized]

    # Семантический разбор для расширенных запросов
    if any(k in normalized for k in ("cropland", "сельхоз", "пашн", "soy", "соя")):
        return density_map.get("soybean_cropland", density_map.get("cropland", 7.5))
    if any(k in normalized for k in ("forest", "лес", "oak", "дуб", "birch", "берез")):
        return density_map.get("oak_birch_woodland", density_map.get("forest", 45.0))
    if any(k in normalized for k in ("shrub", "willow", "ивн", "ольш", "wetland", "болот")):
        return density_map.get("floodplain_willow_alder_shrubland", density_map.get("wetland", 12.0))
    if any(k in normalized for k in ("meadow", "луг", "grass", "трава")):
        return density_map.get("amur_floodplain_meadows", density_map.get("grassland", 5.0))
    if any(k in normalized for k in ("soil", "грунт", "залеж")):
        return density_map.get("open_soil", 2.0)
    if any(k in normalized for k in ("settle", "город", "посел", "застрой")):
        return density_map.get("settlement", 1.0)

    return density_map.get("open_soil", 2.0)


def calculate_stock_difference(
    b_start_t_ha: float,
    b_end_t_ha: float,
    area_ha: float,
    delta_t_years: int = 1,
    cf: float = CF_AGB,
    co2_per_c: float = CO2_PER_C,
) -> dict[str, float]:
    """Вычисляет разницу запасов и выбросы между двумя моментами времени."""
    if area_ha <= 0 or delta_t_years <= 0:
        raise ValueError("Площадь и delta_t должны быть положительными")

    c_start = b_start_t_ha * cf
    c_end = b_end_t_ha * cf
    c_tot_start = c_start * area_ha
    c_tot_end = c_end * area_ha

    delta_c = c_tot_end - c_tot_start
    e_proj = -delta_c * co2_per_c
    e_annual = e_proj / (area_ha * delta_t_years)

    return {
        "c_mean_start_tC_ha": round(c_start, 4),
        "c_mean_end_tC_ha": round(c_end, 4),
        "C_total_start_tC": round(c_tot_start, 2),
        "C_total_end_tC": round(c_tot_end, 2),
        "delta_C_tC": round(delta_c, 2),
        "E_proj_tCO2e": round(e_proj, 2),
        "e_tCO2e_ha_yr": round(e_annual, 4),
    }


def calculate_carbon_credits(
    E_proj_tCO2e: float,
    E_base_tCO2e: float,
    H_tCO2e: float,
    area_ha: float,
    delta_t_years: int = 1,
    LK_tCO2e: float = 0.0,
    prices_rub: tuple[int, int, int] = DEFAULT_PRICES_RUB,
    buffer_rate: float = DEFAULT_BUFFER_RATE,
    unc_threshold: float = DEFAULT_UNCERTAINTY_THRESHOLD,
) -> CarbonCreditResult:
    """Вычисляет потенциальные углеродные кредиты Q по официальной методике соревнования.

    Правила:
    - R = E_base - E_proj - LK;
    - если area <= 0, delta_t <= 0 или H < 0: недопустимо;
    - если R <= 0: Q = 0 (нет чистого сокращения);
    - если H/R >= 1.0: Q = 0 (неопределённость слишком высока);
    - если R > 0 и H/R < 1.0:
      - UNC = min(1.0, max(0.0, H/R - unc_threshold));
      - R_adj = R * (1.0 - UNC);
      - B = R_adj * buffer_rate;
      - Q = floor(R_adj * (1.0 - buffer_rate));
      - V = Q * p.
    """
    if (
        area_ha <= 0
        or delta_t_years <= 0
        or H_tCO2e < 0
        or not all(math.isfinite(x) for x in (E_proj_tCO2e, E_base_tCO2e, H_tCO2e, LK_tCO2e))
    ):
        return CarbonCreditResult(
            is_available=False,
            status="invalid_inputs",
            E_proj_tCO2e=E_proj_tCO2e,
            E_base_tCO2e=E_base_tCO2e,
            LK_tCO2e=LK_tCO2e,
            R_tCO2e=0.0,
            H_tCO2e=H_tCO2e,
            H_over_R=None,
            UNC_deduction_rate=0.0,
            R_adj_tCO2e=0.0,
            buffer_reserve_B_tCO2e=0.0,
            Q_credits=0,
            fractional_remainder=0.0,
            valuations_rub=dict.fromkeys(prices_rub, 0.0),
            area_ha=area_ha,
            delta_t_years=delta_t_years,
            error_message="Недопустимые входные данные: площадь и delta_t должны быть положительными, H неотрицателен, все значения конечны",
        )

    R = E_base_tCO2e - E_proj_tCO2e - LK_tCO2e

    if R <= 0.0:
        return CarbonCreditResult(
            is_available=True,
            status="no_net_reduction",
            E_proj_tCO2e=round(E_proj_tCO2e, 3),
            E_base_tCO2e=round(E_base_tCO2e, 3),
            LK_tCO2e=LK_tCO2e,
            R_tCO2e=round(R, 3),
            H_tCO2e=round(H_tCO2e, 3),
            H_over_R=None,
            UNC_deduction_rate=0.0,
            R_adj_tCO2e=0.0,
            buffer_reserve_B_tCO2e=0.0,
            Q_credits=0,
            fractional_remainder=0.0,
            valuations_rub=dict.fromkeys(prices_rub, 0.0),
            area_ha=area_ha,
            delta_t_years=delta_t_years,
        )

    h_over_r = H_tCO2e / R

    if h_over_r >= 1.0:
        return CarbonCreditResult(
            is_available=True,
            status="uncertainty_too_high",
            E_proj_tCO2e=round(E_proj_tCO2e, 3),
            E_base_tCO2e=round(E_base_tCO2e, 3),
            LK_tCO2e=LK_tCO2e,
            R_tCO2e=round(R, 3),
            H_tCO2e=round(H_tCO2e, 3),
            H_over_R=round(h_over_r, 4),
            UNC_deduction_rate=1.0,
            R_adj_tCO2e=0.0,
            buffer_reserve_B_tCO2e=0.0,
            Q_credits=0,
            fractional_remainder=0.0,
            valuations_rub=dict.fromkeys(prices_rub, 0.0),
            area_ha=area_ha,
            delta_t_years=delta_t_years,
        )

    unc_rate = min(1.0, max(0.0, h_over_r - unc_threshold))
    r_adj = R * (1.0 - unc_rate)
    b_reserve = r_adj * buffer_rate
    issuance_raw = r_adj * (1.0 - buffer_rate)
    q_credits = int(math.floor(issuance_raw))
    remainder = float(issuance_raw - q_credits)

    valuations = {p: float(q_credits * p) for p in prices_rub}

    return CarbonCreditResult(
        is_available=True,
        status="success",
        E_proj_tCO2e=round(E_proj_tCO2e, 3),
        E_base_tCO2e=round(E_base_tCO2e, 3),
        LK_tCO2e=LK_tCO2e,
        R_tCO2e=round(R, 3),
        H_tCO2e=round(H_tCO2e, 3),
        H_over_R=round(h_over_r, 4),
        UNC_deduction_rate=round(unc_rate, 4),
        R_adj_tCO2e=round(r_adj, 3),
        buffer_reserve_B_tCO2e=round(b_reserve, 3),
        Q_credits=q_credits,
        fractional_remainder=round(remainder, 4),
        valuations_rub=valuations,
        area_ha=area_ha,
        delta_t_years=delta_t_years,
    )


def compute_flood_carbon_impact(
    pair_id: str,
    flood_ha: float,
    landcover_ha: dict[str, float] | None = None,
    tier: int | str = 1,
) -> FloodCarbonImpact:
    """Вычисляет потери запаса углерода и эквивалент выбросов от затопления.

    Параметры:
    - pair_id: идентификатор пары снимков;
    - flood_ha: площадь затопления в гектарах;
    - landcover_ha: распределение площадей по типам покрова;
    - tier: уровень детализации коэффициентов биомассы (1 = IPCC Tier 1, 2 = Приамурье Tier 2).
    """
    tier_num = 2 if str(tier).strip().lower() in ("2", "tier2", "tier_2", "regional", "far_east", "amur") else 1
    tier_name = (
        "Tier 2 (региональные коэффициенты Дальнего Востока: Приамурье/бассейн Амура)"
        if tier_num == 2
        else "IPCC Tier 1 (общемировые значения по умолчанию)"
    )
    density_map = get_biomass_density_map(tier=tier_num)

    lc = landcover_ha or {}

    # Эвристические доли для грубой экспресс-оценки при отсутствии детальной маски землепользования:
    # соя/пашня ~45%, дубово-березовые леса ~15%, пойменный кустарник ~30%
    crop_ha = float(lc.get("soybean_cropland", lc.get("cropland", lc.get("сельхоз", lc.get("пашня", flood_ha * 0.45)))))
    forest_ha = float(lc.get("oak_birch_woodland", lc.get("forest", lc.get("лес", flood_ha * 0.15))))
    wetland_ha = float(
        lc.get("floodplain_willow_alder_shrubland", lc.get("wetland", lc.get("кустарник", flood_ha * 0.30)))
    )
    meadow_ha = float(lc.get("amur_floodplain_meadows", lc.get("grassland", lc.get("meadow", lc.get("луг", 0.0)))))
    other_ha = max(0.0, flood_ha - (crop_ha + forest_ha + wetland_ha + meadow_ha))

    crop_density = density_map.get("soybean_cropland", density_map.get("cropland", 7.5))
    forest_density = density_map.get("oak_birch_woodland", density_map.get("forest", 45.0))
    wetland_density = density_map.get("floodplain_willow_alder_shrubland", density_map.get("wetland", 12.0))
    meadow_density = density_map.get(
        "amur_floodplain_meadows", density_map.get("grassland", 11.0 if tier_num == 2 else 5.0)
    )
    other_density = density_map.get("open_soil", 2.0)

    # Допущения по потерям биомассы при затоплении:
    # 80% смыв/гибель посевов на пашне, 20% в лесу (подлесок), 10% в пойменных зарослях, 30% на лугах, 10% на открытом грунте
    crop_biomass_loss = crop_ha * (crop_density * 0.80)
    forest_biomass_loss = forest_ha * (forest_density * 0.20)
    wetland_biomass_loss = wetland_ha * (wetland_density * 0.10)
    meadow_biomass_loss = meadow_ha * (meadow_density * 0.30)
    other_biomass_loss = other_ha * (other_density * 0.10)

    total_biomass_loss = (
        crop_biomass_loss + forest_biomass_loss + wetland_biomass_loss + meadow_biomass_loss + other_biomass_loss
    )
    total_carbon_loss_tC = total_biomass_loss * CF_AGB
    crop_carbon_loss_tC = crop_biomass_loss * CF_AGB
    forest_carbon_loss_tC = forest_biomass_loss * CF_AGB

    emissions_equivalent_tCO2e = total_carbon_loss_tC * CO2_PER_C

    # Сценарий предотвращения паводка относительно базовой линии
    E_proj = 0.0
    E_base = emissions_equivalent_tCO2e
    H_uncertainty = emissions_equivalent_tCO2e * 0.18

    credit_res = calculate_carbon_credits(
        E_proj_tCO2e=E_proj,
        E_base_tCO2e=E_base,
        H_tCO2e=H_uncertainty,
        area_ha=max(flood_ha, 1.0),
        delta_t_years=1,
    )

    notes = (
        f"Оценка углеродного ущерба паводка {pair_id} [{tier_name}]: "
        f"затоплено {flood_ha:.1f} га, потери живой биомассы {total_biomass_loss:.1f} т сух. в-ва, "
        f"эквивалент потерь углерода {emissions_equivalent_tCO2e:.1f} т CO2-экв."
    )

    return FloodCarbonImpact(
        pair_id=pair_id,
        flood_ha=round(flood_ha, 2),
        biomass_loss_dry_matter_t=round(total_biomass_loss, 2),
        carbon_loss_tC=round(total_carbon_loss_tC, 2),
        emissions_equivalent_tCO2e=round(emissions_equivalent_tCO2e, 2),
        cropland_loss_tC=round(crop_carbon_loss_tC, 2),
        forest_loss_tC=round(forest_carbon_loss_tC, 2),
        credit_potential=credit_res,
        notes=notes,
        tier=tier_num,
        tier_name=tier_name,
        biomass_density_factors={
            "cropland": crop_density,
            "forest": forest_density,
            "wetland": wetland_density,
            "grassland": meadow_density,
            "open_soil": other_density,
        },
    )


# --- Green AI: Вычисления энергопотребления и углеродного следа инференса ---


def calculate_green_ai_inference(
    duration_seconds: float,
    tdp_watts: float | str = DEFAULT_CPU_TDP_WATTS,
    grid_emission_factor_kg_per_kwh: float | str = DEFAULT_GRID_EMISSION_FACTOR_KG_KWH,
    cpu_utilization: float = 1.0,
    pue: float = 1.0,
) -> GreenAIMetrics:
    """Вычисляет энергопотребление (кВт·ч) и углеродный след (г CO2e) инференса на CPU.

    Формулы:
    - Энергия: E (кВт·ч) = (TDP_W * utilization * PUE * duration_s) / 3_600_000
    - Углеродный след:
        C (кг CO2e) = E (кВт·ч) * grid_factor (кг CO2e/кВт·ч)
        C (г CO2e)  = C (кг CO2e) * 1000

    Параметры:
    - duration_seconds: время выполнения инференса в секундах (>= 0);
    - tdp_watts: мощность процессора в Ваттах (float) или имя пресета
      ("standard_cpu" = 65W, "apple_silicon" = 30W, "server_cpu" = 125W, "laptop_cpu" = 28W);
    - grid_emission_factor_kg_per_kwh: удельный фактор выбросов энергосети (кг CO2e/кВт·ч)
      или имя региона ("amur_far_east" = 0.38, "russia_average" = 0.35, "hydro_clean" = 0.05);
    - cpu_utilization: коэффициент загрузки CPU (от 0.0 до 1.0, по умолчанию 1.0 = 100%);
    - pue: Power Usage Effectiveness серверной инфраструктуры (>= 1.0, по умолчанию 1.0).
    """
    if duration_seconds < 0:
        raise ValueError(f"duration_seconds должен быть неотрицательным, получено {duration_seconds}")
    if cpu_utilization < 0.0 or cpu_utilization > 1.0:
        raise ValueError(f"cpu_utilization должен быть в диапазоне от 0.0 до 1.0, получено {cpu_utilization}")
    if pue < 1.0:
        raise ValueError(f"PUE должен быть >= 1.0, получено {pue}")

    hw_preset = None
    if isinstance(tdp_watts, str):
        hw_preset = tdp_watts.strip().lower()
        if hw_preset not in CPU_TDP_PRESETS:
            valid = ", ".join(CPU_TDP_PRESETS.keys())
            raise ValueError(f"Неизвестный пресет TDP процессора '{tdp_watts}'. Доступные пресеты: {valid}")
        tdp_val = CPU_TDP_PRESETS[hw_preset]
    else:
        tdp_val = float(tdp_watts)
        if tdp_val < 0:
            raise ValueError(f"tdp_watts должен быть неотрицательным, получено {tdp_watts}")

    region_preset = None
    if isinstance(grid_emission_factor_kg_per_kwh, str):
        region_preset = grid_emission_factor_kg_per_kwh.strip().lower()
        if region_preset not in REGIONAL_GRID_EMISSION_FACTORS:
            valid = ", ".join(REGIONAL_GRID_EMISSION_FACTORS.keys())
            raise ValueError(
                f"Неизвестный пресет фактора выбросов энергосети '{grid_emission_factor_kg_per_kwh}'. Доступные: {valid}"
            )
        grid_factor = REGIONAL_GRID_EMISSION_FACTORS[region_preset]
    else:
        grid_factor = float(grid_emission_factor_kg_per_kwh)
        if grid_factor < 0:
            raise ValueError(
                f"grid_emission_factor_kg_per_kwh должен быть неотрицательным, получено {grid_emission_factor_kg_per_kwh}"
            )

    # Вычисление энергопотребления в кВт·ч: E = P * t = (W * s) / 3_600_000
    energy_kwh = (tdp_val * cpu_utilization * pue * duration_seconds) / 3_600_000.0
    carbon_kg = energy_kwh * grid_factor
    carbon_g = carbon_kg * 1000.0

    notes = (
        f"Инференс Green AI на CPU: {duration_seconds:.3f} с, TDP {tdp_val:.1f} Вт "
        f"({cpu_utilization * 100:.0f}% загрузки, PUE={pue:.2f}) -> {energy_kwh:.6f} кВт·ч, "
        f"{carbon_g:.4f} г CO2e (фактор энергосети {grid_factor:.3f} кг CO2e/кВт·ч)"
    )

    return GreenAIMetrics(
        duration_seconds=round(duration_seconds, 6),
        energy_kwh=round(energy_kwh, 8),
        carbon_emissions_gCO2e=round(carbon_g, 6),
        carbon_emissions_kgCO2e=round(carbon_kg, 8),
        tdp_watts=round(tdp_val, 2),
        cpu_utilization=round(cpu_utilization, 4),
        pue=round(pue, 4),
        grid_emission_factor_kg_per_kwh=round(grid_factor, 4),
        hardware_preset=hw_preset,
        grid_region=region_preset,
        notes=notes,
    )


# Алиас для calculate_green_ai_inference
compute_green_ai_metrics = calculate_green_ai_inference


class GreenAITracker:
    """Контекстный менеджер для профилирования энергопотребления и углеродного следа инференса."""

    def __init__(
        self,
        tdp_watts: float | str = DEFAULT_CPU_TDP_WATTS,
        grid_emission_factor_kg_per_kwh: float | str = DEFAULT_GRID_EMISSION_FACTOR_KG_KWH,
        cpu_utilization: float = 1.0,
        pue: float = 1.0,
    ) -> None:
        self.tdp_watts = tdp_watts
        self.grid_factor = grid_emission_factor_kg_per_kwh
        self.cpu_utilization = cpu_utilization
        self.pue = pue
        self.start_time: float = 0.0
        self.duration_seconds: float = 0.0
        self.metrics: GreenAIMetrics | None = None

    def __enter__(self) -> GreenAITracker:
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object) -> None:
        self.duration_seconds = max(0.0, time.perf_counter() - self.start_time)
        self.metrics = calculate_green_ai_inference(
            duration_seconds=self.duration_seconds,
            tdp_watts=self.tdp_watts,
            grid_emission_factor_kg_per_kwh=self.grid_factor,
            cpu_utilization=self.cpu_utilization,
            pue=self.pue,
        )
