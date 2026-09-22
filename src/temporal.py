"""Модуль анализа временной динамики для HydroWatch Amur.

Вычисляет воду до паводка, воду на пике, вновь затопленные площади
и отступившую воду между парными съёмками.
"""

from __future__ import annotations

import numpy as np


def compute_receded_ha(
    water_pre_mask: np.ndarray,
    water_peak_mask: np.ndarray,
    px_ha: float,
    inside: np.ndarray | None = None,
) -> float:
    """Вычисляет площадь отступившей воды в гектарах.

    Отступившие пиксели это те, что были водой на дату до паводка, но больше
    не являются водой на дату пика: (water_pre == 1) & (water_peak == 0).

    Аргументы:
        water_pre_mask: бинарная маска воды на дату до события (uint8, 0/1).
        water_peak_mask: бинарная маска воды на дату пика (uint8, 0/1).
        px_ha: площадь одного пикселя в гектарах.
        inside: необязательная булева маска, ограничивающая вычисление пространственной
            геометрией запроса (той же формы, что и водные маски).

    Возвращает:
        Площадь отступившей воды в гектарах, округлённая до 2 знаков.
    """
    receded_bool = water_pre_mask.astype(bool) & (~water_peak_mask.astype(bool))
    if inside is not None:
        receded_bool = receded_bool & inside.astype(bool)
    receded_ha = float(np.sum(receded_bool) * px_ha)
    return round(receded_ha, 2)


def compute_temporal_dynamics(
    water_pre: np.ndarray,
    water_peak: np.ndarray,
    permanent: np.ndarray | None = None,
    pixel_size_m: float = 10.0,
) -> dict[str, np.ndarray | float]:
    """Вычисляет временную динамику затопления и водного зеркала.

    Формулы:
      flood   = (water_peak == 1) & (water_pre == 0) & (permanent == 0)
      receded = (water_pre == 1) & (water_peak == 0)

    Аргументы:
        water_pre: бинарная маска воды на дату до события (uint8, 0/1).
        water_peak: бинарная маска воды на дату пика (uint8, 0/1).
        permanent: необязательная бинарная маска постоянной воды (GSW >= 80%).
        pixel_size_m: разрешение пикселя в метрах (по умолчанию 10.0 м = 0.01 га/пикс.).

    Возвращает:
        Словарь, содержащий:
          'water_pre': uint8 array
          'water_peak': uint8 array
          'flood': uint8 array
          'receded': uint8 array
          'permanent': массив uint8 (если передан, иначе нули)
          'flood_ha': float
          'water_pre_ha': float
          'water_peak_ha': float
          'receded_ha': float
          'permanent_ha': float
    """
    height, width = water_pre.shape
    perm_mask = np.zeros((height, width), dtype=bool) if permanent is None else permanent.astype(bool)

    pre_bool = water_pre.astype(bool)
    peak_bool = water_peak.astype(bool)

    # 1. Затопление: вода на пике, но не на pre и не постоянная
    flood_bool = peak_bool & (~pre_bool) & (~perm_mask)
    flood = flood_bool.astype(np.uint8)

    # 2. Отступившая вода: вода на pre, но не на пике
    receded_bool = pre_bool & (~peak_bool)
    receded = receded_bool.astype(np.uint8)

    # Площадь в гектарах (1 пикс. = pixel_size_m^2 м^2; 1 га = 10 000 м^2)
    px_ha = (pixel_size_m * pixel_size_m) / 10000.0

    flood_ha = float(np.sum(flood_bool) * px_ha)
    water_pre_ha = float(np.sum(pre_bool) * px_ha)
    water_peak_ha = float(np.sum(peak_bool) * px_ha)
    receded_ha = float(np.sum(receded_bool) * px_ha)
    permanent_ha = float(np.sum(perm_mask) * px_ha)

    return {
        "water_pre": water_pre.astype(np.uint8),
        "water_peak": water_peak.astype(np.uint8),
        "flood": flood,
        "receded": receded,
        "permanent": perm_mask.astype(np.uint8),
        "flood_ha": round(flood_ha, 2),
        "water_pre_ha": round(water_pre_ha, 2),
        "water_peak_ha": round(water_peak_ha, 2),
        "receded_ha": round(receded_ha, 2),
        "permanent_ha": round(permanent_ha, 2),
    }
