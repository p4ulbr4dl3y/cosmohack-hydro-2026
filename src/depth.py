"""Оценка глубины воды и классификация риска проходимости спасательной техники МЧС.

Основано на профилировании уровня воды по краевым границам HAND/DEM:
Depth = Elevation_edge - DEM_pixel (or HAND_edge - HAND_pixel).

Разделяет глубину воды на классы риска проходимости техники МЧС:
- Низкий риск (< 0.5 м): доступно для обычных полноприводных грузовиков и KamAZ
- Средний риск (0.5 м - 1.5 м): только гусеничные плавающие транспортеры PTS-M
- Высокий риск (> 1.5 м): только лодки и спасательные катера
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.ndimage import binary_erosion, distance_transform_edt

# Пороги проходимости МЧС в метрах
DEPTH_LOW_THRESHOLD_M: float = 0.5
DEPTH_MEDIUM_THRESHOLD_M: float = 1.5


def estimate_water_depth(
    flood_mask: np.ndarray,
    elevation: np.ndarray,
    method: str = "nearest_edge",
    edge_percentile: float = 95.0,
    max_depth_m: float = 30.0,
) -> np.ndarray:
    """Вычисляет попиксельную оценку глубины воды по маске затопления.

    Аргументы
    ----------
    flood_mask : np.ndarray
        Двумерный булев массив или массив uint8 (1 - затоплено, 0 - сухо).
    elevation : np.ndarray
        Двумерный массив float с DEM или HAND (превышение над ближайшим водотоком).
    method : str
        Метод оценки уровня воды на краях:
        - "nearest_edge": локальный уровень воды, распространяемый от ближайшего краевого пикселя затопления.
        - "global_edge": единый статистический уровень воды (edge_percentile) по всем краевым пикселям.
    edge_percentile : float
        Перцентиль (0-100) для отсева выбросов при расчёте краевых уровней воды.
    max_depth_m : float
        Правдоподобный максимум глубины воды для отсечения артефактов DEM.

    Возвращает
    -------
    np.ndarray
        Двумерный массив float32 с оценкой глубины воды в метрах (0.0 на суше).
    """
    if flood_mask.shape != elevation.shape:
        raise ValueError(f"Shape mismatch: flood_mask {flood_mask.shape} vs elevation {elevation.shape}")

    f_bool = (flood_mask == 1) if flood_mask.dtype != bool else flood_mask
    depth = np.zeros(elevation.shape, dtype=np.float32)

    if not np.any(f_bool):
        return depth

    # Определение краевых пикселей границы: затопленные пиксели, соседние с незатопленной местностью
    # border_value=1 считает границы массива продолжением затопленной местности, избегая искусственных краевых границ
    edge = f_bool ^ binary_erosion(f_bool, border_value=1)

    # Откат ко всей маске затопления, если она полностью заполнена или эрозия удалила всё
    if not np.any(edge):
        edge = f_bool.copy()

    # Отбор корректных конечных значений высоты на краях
    valid_edge = edge & np.isfinite(elevation)
    if not np.any(valid_edge):
        return depth

    if method == "global_edge":
        edge_vals = elevation[valid_edge]
        h_edge = float(np.percentile(edge_vals, edge_percentile))
        depth[f_bool] = np.maximum(0.0, h_edge - elevation[f_bool])
    else:
        # По умолчанию: локальный профиль уровня воды, распространяемый от ближайшего краевого пикселя
        # distance_transform_edt возвращает координаты ближайшего истинного пикселя в valid_edge
        _, (indices_y, indices_x) = distance_transform_edt(~valid_edge, return_indices=True)
        edge_elevation = elevation[indices_y, indices_x]
        depth[f_bool] = np.maximum(0.0, edge_elevation[f_bool] - elevation[f_bool])

    # Очистка неконечных значений и ограничение физически правдоподобной максимальной глубиной
    depth[~np.isfinite(depth)] = 0.0
    depth = np.clip(depth, 0.0, max_depth_m)
    depth[~f_bool] = 0.0
    return depth.astype(np.float32)


def classify_depth_risk(
    depth: np.ndarray,
    flood_mask: np.ndarray | None = None,
    px_ha: float = 0.01,
) -> dict[str, Any]:
    """Разделяет глубину воды на классы риска проходимости техники МЧС.

    Классы:
    - Низкий риск (< 0.5 м): доступно для полноприводных грузовиков и KamAZ
    - Средний риск (0.5 м - 1.5 м): только гусеничные плавающие транспортеры PTS-M
    - Высокий риск (> 1.5 м): только лодки и спасательные катера

    Аргументы
    ----------
    depth : np.ndarray
        Двумерный массив float с глубиной воды в метрах.
    flood_mask : np.ndarray | None
        Необязательная явная маска затопления. Если None, учитываются пиксели с глубиной > 0.
    px_ha : float
        Площадь одного пикселя в гектарах (по умолчанию: 0.01 га для разрешения Sentinel 10 м).

    Возвращает
    -------
    dict[str, Any]
        Словарь со статистикой:
        - low_risk_ha, low_risk_pct
        - medium_risk_ha, medium_risk_pct
        - high_risk_ha, high_risk_pct
        - mean_depth_m, max_depth_m
    """
    if flood_mask is None:
        f_bool = depth > 0
    elif flood_mask.dtype != bool:
        f_bool = flood_mask == 1
    else:
        f_bool = flood_mask

    tot_pixels = int(f_bool.sum())
    if tot_pixels == 0:
        return {
            "low_risk_ha": 0.0,
            "low_risk_pct": 0.0,
            "medium_risk_ha": 0.0,
            "medium_risk_pct": 0.0,
            "high_risk_ha": 0.0,
            "high_risk_pct": 0.0,
            "mean_depth_m": 0.0,
            "max_depth_m": 0.0,
            "mchs_traversability": {
                "low_risk_kamaz": "Accessible by regular all-wheel trucks / KamAZ (< 0.5 m)",
                "medium_risk_pts_m": "PTS-M tracked amphibious transporters only (0.5 - 1.5 m)",
                "high_risk_boats": "Watercraft / rescue boats only (> 1.5 m)",
            },
        }

    d_flood = depth[f_bool]
    low_mask = d_flood < DEPTH_LOW_THRESHOLD_M
    med_mask = (d_flood >= DEPTH_LOW_THRESHOLD_M) & (d_flood <= DEPTH_MEDIUM_THRESHOLD_M)
    high_mask = d_flood > DEPTH_MEDIUM_THRESHOLD_M

    low_count = int(low_mask.sum())
    med_count = int(med_mask.sum())
    high_count = int(high_mask.sum())

    low_ha = round(low_count * px_ha, 2)
    med_ha = round(med_count * px_ha, 2)
    high_ha = round(high_count * px_ha, 2)

    low_pct = round((low_count / tot_pixels) * 100.0, 2)
    med_pct = round((med_count / tot_pixels) * 100.0, 2)
    high_pct = round((high_count / tot_pixels) * 100.0, 2)

    valid_d = d_flood[np.isfinite(d_flood)]
    mean_d = round(float(np.mean(valid_d)), 2) if len(valid_d) > 0 else 0.0
    max_d = round(float(np.max(valid_d)), 2) if len(valid_d) > 0 else 0.0

    return {
        "low_risk_ha": low_ha,
        "low_risk_pct": low_pct,
        "medium_risk_ha": med_ha,
        "medium_risk_pct": med_pct,
        "high_risk_ha": high_ha,
        "high_risk_pct": high_pct,
        "mean_depth_m": mean_d,
        "max_depth_m": max_d,
        "mchs_traversability": {
            "low_risk_kamaz": "Accessible by regular all-wheel trucks / KamAZ (< 0.5 m)",
            "medium_risk_pts_m": "PTS-M tracked amphibious transporters only (0.5 - 1.5 m)",
            "high_risk_boats": "Watercraft / rescue boats only (> 1.5 m)",
        },
    }
