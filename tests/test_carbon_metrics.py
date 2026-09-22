"""Модульные тесты расчётов углерода по методологии IPCC и метрик ESG для паводков."""

import math

from src.carbon_metrics import (
    calculate_carbon_credits,
    calculate_stock_difference,
    compute_flood_carbon_impact,
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
    """Проверка углеродного следа паводка и оценки ущерба биомассе."""
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
