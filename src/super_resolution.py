"""Модуль суперразрешения и понижения разрешения с сохранением массы.

Понижает разрешение грубых вспомогательных растров (например, occurrence GSW 30 м, производные DEM
или грубые оптические индексы) до разрешения Sentinel 10 м с использованием весов-проводников
высокого разрешения (например, MNDWI/NDVI Sentinel-2 или интенсивность SAR Sentinel-1) со строгим
сохранением интегралов (сохранение массы).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SuperResolutionResult:
    """Результат обработки суперразрешения с сохранением массы."""

    original_shape: tuple[int, int]
    upscaled_shape: tuple[int, int]
    upscale_factor: int
    mean_original: float
    mean_superres: float
    conservation_error_pct: float


def super_resolve_raster_10m(
    coarse_raster: np.ndarray,
    guide_10m: np.ndarray | None = None,
    upscale_factor: int = 3,
    min_guide_val: float = 0.01,
) -> tuple[np.ndarray, SuperResolutionResult]:
    """Понижает разрешение грубого растра до сетки высокого разрешения со строгим сохранением интегралов.

    Для каждой грубой ячейки (r, c) распределяет значение по (upscale_factor x upscale_factor)
    субпикселям пропорционально весам проводника:
        w_sub = max(min_guide_val, guide_sub) / sum(max(min_guide_val, guide_sub))
        fine_val = coarse_val * (w_sub * upscale_factor^2)
    Это гарантирует, что среднее субпикселей равно coarse_val.

    Аргументы:
        coarse_raster: двумерный массив грубых значений (например, 30 м).
        guide_10m: двумерный массив признаков-проводников 10 м (например, MNDWI, обратное рассеяние VV или NDVI).
                   Если None, используется равномерное понижение разрешения методом ближайшего соседа.
        upscale_factor: коэффициент понижения разрешения (по умолчанию 3, например с 30 м до 10 м).
        min_guide_val: базовый минимум для весов, предотвращающий деление на ноль.

    Возвращает:
        (superres_raster, result_dataclass)
    """
    coarse = np.asarray(coarse_raster, dtype=np.float64)
    h_orig, w_orig = coarse.shape
    h_target, w_target = h_orig * upscale_factor, w_orig * upscale_factor

    if guide_10m is not None:
        guide = np.asarray(guide_10m, dtype=np.float64)
        if guide.shape != (h_target, w_target):
            guide = np.repeat(np.repeat(coarse, upscale_factor, axis=0), upscale_factor, axis=1)
    else:
        guide = np.ones((h_target, w_target), dtype=np.float64)

    superres = np.zeros((h_target, w_target), dtype=np.float64)
    n_sub = upscale_factor * upscale_factor

    for r in range(h_orig):
        for c in range(w_orig):
            val = coarse[r, c]
            if not np.isfinite(val) or val == 0:
                continue

            r_slice = slice(r * upscale_factor, (r + 1) * upscale_factor)
            c_slice = slice(c * upscale_factor, (c + 1) * upscale_factor)

            sub_guide = np.maximum(min_guide_val, guide[r_slice, c_slice])
            sum_guide = np.sum(sub_guide)

            if sum_guide > 0:
                weights = sub_guide / sum_guide
                superres[r_slice, c_slice] = val * (weights * n_sub)
            else:
                superres[r_slice, c_slice] = val

    mean_orig = float(np.nanmean(coarse)) if np.any(np.isfinite(coarse)) else 0.0
    mean_super = float(np.nanmean(superres)) if np.any(np.isfinite(superres)) else 0.0

    conservation_err = 0.0
    if mean_orig > 0:
        conservation_err = float(abs(mean_super - mean_orig) / mean_orig * 100.0)

    result = SuperResolutionResult(
        original_shape=(h_orig, w_orig),
        upscaled_shape=(h_target, w_target),
        upscale_factor=upscale_factor,
        mean_original=round(mean_orig, 4),
        mean_superres=round(mean_super, 4),
        conservation_error_pct=round(conservation_err, 4),
    )
    return superres, result
