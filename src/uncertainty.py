"""Оценка пространственной неопределённости и доверительных интервалов для гидрологического мониторинга.

Основано на теории пространственной автокорреляции (Chave et al. 2004, 2014, IPCC GPG)
и распространении ошибок дистанционного зондирования. Остаточные ошибки спутниковой классификации
(спекл-шум, смешанные пиксели, оконтуривание границ) обладают пространственной ковариацией
(по умолчанию rho = 0.20), то есть эффективное число независимых выборок N_eff << N_valid.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import norm


@dataclass(frozen=True)
class FloodUncertaintyResult:
    """Анализ неопределённости и сценарные доверительные границы площади затопления и воды."""

    area_ha: float
    sigma_independent_ha: float
    sigma_correlated_ha: float
    sigma_effective_ha: float
    relative_uncertainty_pct: float
    confidence_level: float
    z_score: float
    lower_bound_ha: float
    upper_bound_ha: float
    margin_ha: float
    effective_n_pixels: float
    total_valid_pixels: int
    spatial_correlation: float


def compute_flood_area_uncertainty(
    mask: np.ndarray,
    pixel_area_ha: float = 0.01,
    pixel_sd_rate: float = 0.08,
    spatial_correlation: float = 0.20,
    confidence_level: float = 0.95,
) -> FloodUncertaintyResult:
    """Вычисляет пространственную неопределённость и доверительный интервал [L, U] картируемой площади воды/затопления.

    Учитывает пространственную автокорреляцию (rho = 0.20) между соседними пикселями,
    предотвращая ложное допущение, что все спутниковые пиксели статистически независимы.

    Аргументы:
        mask: двумерная бинарная маска (0 или 1, bool или числовая) классифицированной воды и затопления.
        pixel_area_ha: номинальная площадь одного пикселя в гектарах (по умолчанию 0.01 га для 10 м).
        pixel_sd_rate: базовая относительная стандартная ошибка на пиксель из-за
                       спекла, краевых эффектов и смешанных пикселей (по умолчанию 8%).
        spatial_correlation: коэффициент пространственной автокорреляции rho (по умолчанию 0.20).
        confidence_level: доверительный уровень (по умолчанию 0.95 - z = 1.960; 0.90 - z = 1.645).

    Возвращает:
        Датакласс FloodUncertaintyResult с границами [lower_bound_ha, upper_bound_ha].
    """
    arr = np.asarray(mask, dtype=bool)
    n_pixels = int(np.count_nonzero(arr))

    if n_pixels == 0:
        z = float(norm.ppf((1.0 + confidence_level) / 2.0))
        return FloodUncertaintyResult(
            area_ha=0.0,
            sigma_independent_ha=0.0,
            sigma_correlated_ha=0.0,
            sigma_effective_ha=0.0,
            relative_uncertainty_pct=0.0,
            confidence_level=confidence_level,
            z_score=round(z, 3),
            lower_bound_ha=0.0,
            upper_bound_ha=0.0,
            margin_ha=0.0,
            effective_n_pixels=0.0,
            total_valid_pixels=0,
            spatial_correlation=spatial_correlation,
        )

    area_ha = float(n_pixels * pixel_area_ha)

    # Независимая дисперсия: sum( (pixel_area * sd_pixel)^2 )
    sigma_per_pixel = pixel_area_ha * pixel_sd_rate
    var_independent = n_pixels * (sigma_per_pixel**2)
    sigma_ind = math.sqrt(var_independent)

    # Коррелированная стандартная ошибка: sum( pixel_area * sd_pixel )
    sigma_corr = n_pixels * sigma_per_pixel

    # Эффективная стандартная ошибка, объединяющая независимую и коррелированную компоненты
    rho = float(np.clip(spatial_correlation, 0.0, 1.0))
    sigma_eff = math.sqrt((1.0 - rho) * (sigma_ind**2) + rho * (sigma_corr**2))

    # Эффективное число независимых пиксельных наблюдений
    n_eff = float(n_pixels / (1.0 + (n_pixels - 1) * rho)) if (1.0 + (n_pixels - 1) * rho) > 0 else 1.0

    z = float(norm.ppf((1.0 + confidence_level) / 2.0))
    margin = float(z * sigma_eff)
    lower_bound = max(0.0, area_ha - margin)
    upper_bound = area_ha + margin
    rel_pct = (margin / area_ha * 100.0) if area_ha > 0 else 0.0

    return FloodUncertaintyResult(
        area_ha=round(area_ha, 2),
        sigma_independent_ha=round(sigma_ind, 2),
        sigma_correlated_ha=round(sigma_corr, 2),
        sigma_effective_ha=round(sigma_eff, 2),
        relative_uncertainty_pct=round(rel_pct, 2),
        confidence_level=confidence_level,
        z_score=round(z, 3),
        lower_bound_ha=round(lower_bound, 2),
        upper_bound_ha=round(upper_bound, 2),
        margin_ha=round(margin, 2),
        effective_n_pixels=round(n_eff, 1),
        total_valid_pixels=n_pixels,
        spatial_correlation=rho,
    )


def simulate_flood_uncertainty_monte_carlo(
    area_ha: float,
    sigma_effective_ha: float,
    n_trials: int = 2000,
    seed: int = 42,
) -> dict[str, float]:
    """Симуляция распространения ошибок методом Монте-Карло для оценок площади затопления.

    Формирует n_trials синтетических реализаций для эмпирической оценки перцентилей
    (P5, P25, P50, P75, P95).

    Аргументы:
        area_ha: центральная оценка площади затопления в гектарах.
        sigma_effective_ha: эффективная стандартная ошибка в гектарах.
        n_trials: число выборок Монте-Карло (по умолчанию 2000).
        seed: зерно генератора случайных чисел для детерминированной воспроизводимости.

    Возвращает:
        Словарь со сводной статистикой: mean, std, p05, p50, p95.
    """
    if area_ha <= 0.0 or sigma_effective_ha <= 0.0:
        return {
            "mean": area_ha,
            "std": 0.0,
            "p05": area_ha,
            "p50": area_ha,
            "p95": area_ha,
        }

    rng = np.random.default_rng(seed)
    # Логнормальное распределение, чтобы избежать нефизичных отрицательных значений площади
    sigma_ratio = sigma_effective_ha / area_ha
    sigma_log = math.sqrt(math.log(1.0 + sigma_ratio**2))
    mu_log = math.log(area_ha) - 0.5 * (sigma_log**2)

    samples = rng.lognormal(mean=mu_log, sigma=sigma_log, size=n_trials)

    return {
        "mean": round(float(np.mean(samples)), 2),
        "std": round(float(np.std(samples)), 2),
        "p05": round(float(np.percentile(samples, 5.0)), 2),
        "p50": round(float(np.percentile(samples, 50.0)), 2),
        "p95": round(float(np.percentile(samples, 95.0)), 2),
    }
