"""Модульные тесты расчётов углерода по методологии IPCC, регионального Tier 2 и Green AI."""

import math
import time

import pytest

from src.carbon_metrics import (
    BIOMASS_DENSITY_MAP,
    CPU_TDP_PRESETS,
    DEFAULT_CPU_TDP_WATTS,
    DEFAULT_GRID_EMISSION_FACTOR_KG_KWH,
    REGIONAL_GRID_EMISSION_FACTORS,
    TIER1_BIOMASS_DENSITY,
    TIER2_FAR_EAST_BIOMASS_DENSITY,
    GreenAIMetrics,
    GreenAITracker,
    calculate_carbon_credits,
    calculate_green_ai_inference,
    calculate_stock_difference,
    compute_flood_carbon_impact,
    compute_green_ai_metrics,
    get_biomass_density,
    get_biomass_density_map,
)


def test_ipcc_synthetic_case_from_specs():
    """Проверка точного синтетического случая из спецификации конкурса:

    - A = 100 ha, delta_t = 1 yr;
    - биомасса b: 100 -> 104 t dry matter / ha;
    - c: 47.0 -> 48.88 t C / ha;
    - delta_C = 188.0 t C;
    - E_proj = -689.333 t CO2e, e = -6.893 t CO2e/ha/yr;
    - E_base = -172.333 t CO2e => R = 517.0 t CO2e;
    - H = 103.4 => H/R = 0.20 => UNC = 0.10 => R_adj = 465.3 => B = 69.795, Q = 395;
    - оценки V = 395 * [500, 1500, 4000].
    """
    diff = calculate_stock_difference(
        b_start_t_ha=100.0,
        b_end_t_ha=104.0,
        area_ha=100.0,
        delta_t_years=1,
    )

    assert math.isclose(diff["c_mean_start_tC_ha"], 47.0, rel_tol=1e-5)
    assert math.isclose(diff["c_mean_end_tC_ha"], 48.88, rel_tol=1e-5)
    assert math.isclose(diff["delta_C_tC"], 188.0, rel_tol=1e-5)
    assert math.isclose(diff["E_proj_tCO2e"], -689.33, rel_tol=1e-3)
    assert math.isclose(diff["e_tCO2e_ha_yr"], -6.8933, rel_tol=1e-3)

    # Расчёт кредитов
    E_base = -172.33333333333334
    res = calculate_carbon_credits(
        E_proj_tCO2e=diff["E_proj_tCO2e"],
        E_base_tCO2e=E_base,
        H_tCO2e=103.4,
        area_ha=100.0,
        delta_t_years=1,
    )

    assert res.is_available is True
    assert res.status == "success"
    assert math.isclose(res.R_tCO2e, 517.0, rel_tol=1e-3)
    assert math.isclose(res.H_over_R, 0.20, rel_tol=1e-3)
    assert math.isclose(res.UNC_deduction_rate, 0.10, rel_tol=1e-3)
    assert math.isclose(res.R_adj_tCO2e, 465.3, rel_tol=1e-3)
    assert math.isclose(res.buffer_reserve_B_tCO2e, 69.795, rel_tol=1e-3)
    assert res.Q_credits == 395

    assert res.valuations_rub[500] == 395 * 500
    assert res.valuations_rub[1500] == 395 * 1500
    assert res.valuations_rub[4000] == 395 * 4000


def test_credit_edge_cases():
    """Проверка граничных условий генерации углеродных кредитов."""
    # R <= 0 -> Q = 0
    res_zero = calculate_carbon_credits(
        E_proj_tCO2e=100.0,
        E_base_tCO2e=50.0,
        H_tCO2e=10.0,
        area_ha=100.0,
    )
    assert res_zero.status == "no_net_reduction"
    assert res_zero.Q_credits == 0

    # H/R >= 1.0 -> Q = 0
    res_high_unc = calculate_carbon_credits(
        E_proj_tCO2e=-500.0,
        E_base_tCO2e=0.0,
        H_tCO2e=600.0,
        area_ha=100.0,
    )
    assert res_high_unc.status == "uncertainty_too_high"
    assert res_high_unc.Q_credits == 0


def test_flood_carbon_impact():
    """Проверка углеродного следа паводка и оценки ущерба биомассе по умолчанию."""
    impact = compute_flood_carbon_impact(
        pair_id="flood_2019_07_amur__belogorsk",
        flood_ha=187.19,
        landcover_ha={"cropland": 100.0, "forest": 30.0, "wetland": 57.19},
    )

    assert impact.pair_id == "flood_2019_07_amur__belogorsk"
    assert impact.flood_ha == 187.19
    assert impact.biomass_loss_dry_matter_t > 0
    assert impact.carbon_loss_tC > 0
    assert impact.emissions_equivalent_tCO2e > 0
    assert impact.credit_potential.Q_credits >= 0
    assert impact.tier == 1


# --- Тесты Green AI метрик инференса ---


def test_green_ai_inference_standard_cpu():
    """Проверка Green AI для стандартного CPU (65 Вт) и энергосистемы Приамурья."""
    # 10 секунд работы при 65W TDP и 0.38 кг CO2e / кВт·ч
    duration_s = 10.0
    metrics = calculate_green_ai_inference(
        duration_seconds=duration_s,
        tdp_watts="standard_cpu",
        grid_emission_factor_kg_per_kwh="amur_far_east",
    )

    expected_kwh = (65.0 * 1.0 * 1.0 * duration_s) / 3_600_000.0
    expected_carbon_g = expected_kwh * 0.38 * 1000.0

    assert isinstance(metrics, GreenAIMetrics)
    assert math.isclose(metrics.tdp_watts, 65.0, rel_tol=1e-4)
    assert math.isclose(metrics.grid_emission_factor_kg_per_kwh, 0.38, rel_tol=1e-4)
    assert math.isclose(metrics.energy_kwh, expected_kwh, rel_tol=1e-4)
    assert math.isclose(metrics.carbon_emissions_gCO2e, expected_carbon_g, rel_tol=1e-4)
    assert math.isclose(metrics.carbon_emissions_kgCO2e, expected_kwh * 0.38, rel_tol=1e-4)
    assert metrics.hardware_preset == "standard_cpu"
    assert metrics.grid_region == "amur_far_east"
    assert "Green AI" in metrics.notes


def test_green_ai_inference_apple_silicon():
    """Проверка Green AI для энергоэффективного чипа Apple Silicon (30 Вт)."""
    duration_s = 20.0
    metrics = calculate_green_ai_inference(
        duration_seconds=duration_s,
        tdp_watts="apple_silicon",
        grid_emission_factor_kg_per_kwh=0.40,
    )

    expected_kwh = (30.0 * 1.0 * 1.0 * duration_s) / 3_600_000.0
    expected_carbon_g = expected_kwh * 0.40 * 1000.0

    assert math.isclose(metrics.tdp_watts, 30.0, rel_tol=1e-4)
    assert math.isclose(metrics.energy_kwh, expected_kwh, rel_tol=1e-4)
    assert math.isclose(metrics.carbon_emissions_gCO2e, expected_carbon_g, rel_tol=1e-4)
    assert metrics.hardware_preset == "apple_silicon"


def test_green_ai_inference_custom_parameters():
    """Проверка расчёта с произвольным TDP, частичной утилизацией и PUE ЦОД."""
    metrics = calculate_green_ai_inference(
        duration_seconds=3600.0,  # 1 час
        tdp_watts=100.0,  # 100 Вт
        grid_emission_factor_kg_per_kwh=0.35,  # 0.35 кг CO2e/кВт·ч
        cpu_utilization=0.5,  # 50% загрузки
        pue=1.2,  # PUE дата-центра
    )

    # 100 Вт * 0.5 * 1.2 = 60 Вт эффективной мощности
    # За 1 час = 0.060 кВт·ч
    assert math.isclose(metrics.energy_kwh, 0.060, rel_tol=1e-4)
    # 0.060 кВт·ч * 0.35 кг CO2e/кВт·ч = 0.021 кг CO2e = 21 г CO2e
    assert math.isclose(metrics.carbon_emissions_gCO2e, 21.0, rel_tol=1e-4)
    assert math.isclose(metrics.carbon_emissions_kgCO2e, 0.021, rel_tol=1e-4)


def test_green_ai_alias_and_tracker():
    """Проверка алиаса compute_green_ai_metrics и контекстного менеджера GreenAITracker."""
    m_alias = compute_green_ai_metrics(5.0, tdp_watts=DEFAULT_CPU_TDP_WATTS)
    assert isinstance(m_alias, GreenAIMetrics)
    assert m_alias.duration_seconds == 5.0

    with GreenAITracker(tdp_watts="apple_silicon", grid_emission_factor_kg_per_kwh="amur_far_east") as tracker:
        time.sleep(0.01)

    assert tracker.metrics is not None
    assert tracker.metrics.duration_seconds >= 0.01
    assert tracker.metrics.energy_kwh > 0.0
    assert tracker.metrics.carbon_emissions_gCO2e > 0.0
    assert tracker.metrics.hardware_preset == "apple_silicon"


def test_green_ai_input_validation():
    """Проверка обработки некорректных входных данных."""
    with pytest.raises(ValueError, match="duration_seconds must be non-negative"):
        calculate_green_ai_inference(-1.0)

    with pytest.raises(ValueError, match="cpu_utilization must be between"):
        calculate_green_ai_inference(1.0, cpu_utilization=1.5)

    with pytest.raises(ValueError, match="PUE must be >= 1.0"):
        calculate_green_ai_inference(1.0, pue=0.8)

    with pytest.raises(ValueError, match="Unknown CPU TDP preset"):
        calculate_green_ai_inference(1.0, tdp_watts="quantum_core_9000")

    with pytest.raises(ValueError, match="Unknown grid emission factor preset"):
        calculate_green_ai_inference(1.0, grid_emission_factor_kg_per_kwh="mars_colony_grid")


# --- Тесты Tier 2 региональных коэффициентов бассейна р. Амур ---


def test_tier2_far_east_biomass_coefficients():
    """Проверка наличия специфических региональных коэффициентов Приамурья (Tier 2)."""
    assert "floodplain_willow_alder_shrubland" in TIER2_FAR_EAST_BIOMASS_DENSITY
    assert "amur_floodplain_meadows" in TIER2_FAR_EAST_BIOMASS_DENSITY
    assert "oak_birch_woodland" in TIER2_FAR_EAST_BIOMASS_DENSITY
    assert "soybean_cropland" in TIER2_FAR_EAST_BIOMASS_DENSITY

    # Проверка числовых значений региональной плотности биомассы
    assert TIER2_FAR_EAST_BIOMASS_DENSITY["floodplain_willow_alder_shrubland"] == 25.0
    assert TIER2_FAR_EAST_BIOMASS_DENSITY["amur_floodplain_meadows"] == 11.0
    assert TIER2_FAR_EAST_BIOMASS_DENSITY["oak_birch_woodland"] == 75.0
    assert TIER2_FAR_EAST_BIOMASS_DENSITY["soybean_cropland"] == 7.0


def test_tier_switching_methods():
    """Проверка переключения между Tier 1 (IPCC по умолчанию) и Tier 2 (Приамурье)."""
    # Справочники
    map_tier1 = get_biomass_density_map(tier=1)
    map_tier2 = get_biomass_density_map(tier=2)

    assert map_tier1["forest"] == 45.0
    assert map_tier2["forest"] == 75.0  # Дубово-берёзовые леса Дальнего Востока
    assert map_tier2["wetland"] == 25.0  # Пойменные ивняки и ольшаники
    assert map_tier1["cropland"] == 7.5
    assert map_tier2["cropland"] == 7.0  # Соевые агроценозы

    # Функция get_biomass_density с семантическим поиском
    assert get_biomass_density("oak_birch_woodland", tier=2) == 75.0
    assert get_biomass_density("floodplain_willow_alder_shrubland", tier=2) == 25.0
    assert get_biomass_density("amur_floodplain_meadows", tier=2) == 11.0
    assert get_biomass_density("soybean_cropland", tier=2) == 7.0

    # Разрешение семантических алиасов
    assert get_biomass_density("соевая пашня", tier=2) == 7.0
    assert get_biomass_density("дубово-березовый лес", tier=2) == 75.0
    assert get_biomass_density("пойменный ивняк", tier=2) == 25.0
    assert get_biomass_density("пойменный вейниковый луг", tier=2) == 11.0


def test_flood_carbon_impact_tier2_comparison():
    """Сравнение расчёта углеродного ущерба паводка при Tier 1 vs Tier 2."""
    landcover = {"cropland": 50.0, "forest": 40.0, "wetland": 30.0}
    flood_ha = 120.0

    impact_tier1 = compute_flood_carbon_impact(
        pair_id="flood_amur_test",
        flood_ha=flood_ha,
        landcover_ha=landcover,
        tier=1,
    )
    impact_tier2 = compute_flood_carbon_impact(
        pair_id="flood_amur_test",
        flood_ha=flood_ha,
        landcover_ha=landcover,
        tier=2,
    )

    assert impact_tier1.tier == 1
    assert impact_tier2.tier == 2
    assert "Tier 1" in impact_tier1.tier_name
    assert "Tier 2" in impact_tier2.tier_name

    # В бассейне Амура дубово-берёзовые леса (75 т/га) и пойменные заросли (25 т/га) плотнее Tier 1 defaults
    # Следовательно, биомасса и эквивалент потерь углерода при Tier 2 должны быть выше
    assert impact_tier2.biomass_loss_dry_matter_t > impact_tier1.biomass_loss_dry_matter_t
    assert impact_tier2.carbon_loss_tC > impact_tier1.carbon_loss_tC
    assert impact_tier2.emissions_equivalent_tCO2e > impact_tier1.emissions_equivalent_tCO2e


def test_flood_carbon_impact_explicit_tier2_categories():
    """Проверка расчёта с прямым указанием региональных категорий покрова Tier 2."""
    impact = compute_flood_carbon_impact(
        pair_id="flood_blagoveshchensk_2021",
        flood_ha=100.0,
        landcover_ha={
            "soybean_cropland": 50.0,
            "oak_birch_woodland": 20.0,
            "floodplain_willow_alder_shrubland": 20.0,
            "amur_floodplain_meadows": 10.0,
        },
        tier=2,
    )

    # Проверяем биомассу потерь:
    # соя: 50 * 7.0 * 0.80 = 280.0
    # дуб-береза: 20 * 75.0 * 0.20 = 300.0
    # ивняк: 20 * 25.0 * 0.10 = 50.0
    # луг: 10 * 11.0 * 0.30 = 33.0
    # итого: 663.0 т сухого вещества
    assert math.isclose(impact.biomass_loss_dry_matter_t, 663.0, rel_tol=1e-3)
    assert math.isclose(impact.carbon_loss_tC, 663.0 * 0.47, rel_tol=1e-3)
    assert impact.tier == 2


def test_backwards_compatibility():
    """Проверка полной обратной совместимости существующих констант и функций."""
    assert "cropland" in BIOMASS_DENSITY_MAP
    assert "forest" in BIOMASS_DENSITY_MAP
    assert BIOMASS_DENSITY_MAP == TIER1_BIOMASS_DENSITY
    assert DEFAULT_CPU_TDP_WATTS == 65.0
    assert 0.35 <= DEFAULT_GRID_EMISSION_FACTOR_KG_KWH <= 0.45
    assert "amur_far_east" in REGIONAL_GRID_EMISSION_FACTORS
    assert "apple_silicon" in CPU_TDP_PRESETS
