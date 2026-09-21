"""Carbon and ESG impact evaluation module for flood damage assessment.

Implements standard IPCC and Verra VM0047 methodologies for biomass and carbon stock calculation:
1. Stock difference method:
   - c_i = b_i * CF (CF = 0.47 t C / t dry matter, IPCC default)
   - C_t = sum(a_i * c_i) (t C)
   - delta_C = C_t1 - C_t0 (t C)
   - E = -delta_C * (44 / 12) (t CO2e)
   - e = E / (A * delta_t) (t CO2e / ha / year)

2. Carbon credit issuance potential Q:
   - R = E_base - E_proj - LK (LK = 0)
   - H = max(|E_proj - L|, |U - E_proj|)
   - If R <= 0 or H/R >= 1.0 => Q = 0
   - If R > 0 and H/R < 1.0:
     - UNC = min(1.0, max(0.0, H/R - 0.10))
     - R_adj = R * (1 - UNC)
     - B = 0.15 * R_adj (15% risk buffer reserve)
     - Q = floor(R_adj * 0.85) (integer carbon credit units)
     - Valuations V = Q * p for p in [500, 1500, 4000] RUB/credit

3. Flood vegetation carbon loss footprint:
   - Cropland biomass washout: ~5.0-10.0 t dry matter/ha
   - Forest understory / flooded vegetation loss: ~15.0-30.0 t dry matter/ha
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# IPCC Default constants
CF_AGB: float = 0.47  # Carbon fraction of above-ground dry biomass (t C / t dry matter)
CO2_PER_C: float = 44.0 / 12.0  # Molar ratio of CO2 to Carbon (44/12)
DEFAULT_BUFFER_RATE: float = 0.15  # 15% risk buffer reserve
DEFAULT_UNCERTAINTY_THRESHOLD: float = 0.10  # 10% tolerance without deduction
DEFAULT_PRICES_RUB: tuple[int, int, int] = (500, 1500, 4000)

# Typical biomass density by landcover for Amur basin (t dry matter / ha)
BIOMASS_DENSITY_MAP: dict[str, float] = {
    "cropland": 7.5,      # Agricultural cropland
    "forest": 45.0,       # Mixed temperate forest
    "wetland": 12.0,      # Shrubland and wetland
    "open_soil": 2.0,     # Fallow / bare soil
    "settlement": 1.0,    # Urban / built-up
}


@dataclass(frozen=True)
class CarbonCreditResult:
    """Carbon credit calculation result under baseline scenario."""

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
    """Flood damage carbon footprint and ESG impact analysis."""

    pair_id: str
    flood_ha: float
    biomass_loss_dry_matter_t: float
    carbon_loss_tC: float
    emissions_equivalent_tCO2e: float
    cropland_loss_tC: float
    forest_loss_tC: float
    credit_potential: CarbonCreditResult
    notes: str


def calculate_stock_difference(
    b_start_t_ha: float,
    b_end_t_ha: float,
    area_ha: float,
    delta_t_years: int = 1,
    cf: float = CF_AGB,
    co2_per_c: float = CO2_PER_C,
) -> dict[str, float]:
    """Calculate stock difference and emissions between two time steps."""
    if area_ha <= 0 or delta_t_years <= 0:
        raise ValueError("Area and delta_t must be positive")

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
    """Calculate potential carbon credits Q following official competition methodology.

    Rules:
    - R = E_base - E_proj - LK
    - If area <= 0, delta_t <= 0, or H < 0: invalid
    - If R <= 0: Q = 0 (no net reduction)
    - If H/R >= 1.0: Q = 0 (uncertainty too high)
    - If R > 0 and H/R < 1.0:
      - UNC = min(1.0, max(0.0, H/R - unc_threshold))
      - R_adj = R * (1.0 - UNC)
      - B = R_adj * buffer_rate
      - Q = floor(R_adj * (1.0 - buffer_rate))
      - V = Q * p
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
            error_message="Invalid inputs: area and delta_t must be positive, H non-negative, all values finite",
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
) -> FloodCarbonImpact:
    """Calculate carbon stock loss and emissions equivalent from flood inundation."""
    lc = landcover_ha or {}
    crop_ha = float(lc.get("cropland", lc.get("сельхоз", flood_ha * 0.45)))
    forest_ha = float(lc.get("forest", lc.get("лес", flood_ha * 0.15)))
    wetland_ha = float(lc.get("wetland", flood_ha * 0.30))
    other_ha = max(0.0, flood_ha - (crop_ha + forest_ha + wetland_ha))

    # Biomass loss assumptions: 80% loss in crop, 20% loss in forest (understory), 10% in wetland
    crop_biomass_loss = crop_ha * (BIOMASS_DENSITY_MAP["cropland"] * 0.80)
    forest_biomass_loss = forest_ha * (BIOMASS_DENSITY_MAP["forest"] * 0.20)
    wetland_biomass_loss = wetland_ha * (BIOMASS_DENSITY_MAP["wetland"] * 0.10)
    other_biomass_loss = other_ha * (BIOMASS_DENSITY_MAP["open_soil"] * 0.10)

    total_biomass_loss = crop_biomass_loss + forest_biomass_loss + wetland_biomass_loss + other_biomass_loss
    total_carbon_loss_tC = total_biomass_loss * CF_AGB
    crop_carbon_loss_tC = crop_biomass_loss * CF_AGB
    forest_carbon_loss_tC = forest_biomass_loss * CF_AGB

    emissions_equivalent_tCO2e = total_carbon_loss_tC * CO2_PER_C

    # Credit potential scenario: preventing flood damage yields credits against baseline
    # Scenario: baseline with flood vs mitigation project avoiding flood
    E_proj = 0.0  # Zero flood in mitigation scenario
    E_base = emissions_equivalent_tCO2e  # Emissions under actual flood event
    H_uncertainty = emissions_equivalent_tCO2e * 0.18  # 18% spatial uncertainty

    credit_res = calculate_carbon_credits(
        E_proj_tCO2e=E_proj,
        E_base_tCO2e=E_base,
        H_tCO2e=H_uncertainty,
        area_ha=max(flood_ha, 1.0),
        delta_t_years=1,
    )

    notes = (
        f"Оценка углеродного ущерба паводка {pair_id}: "
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
    )
