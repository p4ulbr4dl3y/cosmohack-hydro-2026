"""Подавление спекла и морфологическая постобработка радиолокационных изображений."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import label, median_filter, uniform_filter

from src.config import LEE_LOOKS, LEE_SIZE, MMU_MIN_PIXELS, SAR_NODATA_MAX_DB


def refined_lee_filter(
    data: np.ndarray,
    size: int = LEE_SIZE,
    n_looks: float = LEE_LOOKS,
) -> np.ndarray:
    """Применяет спекл-фильтр Lee MMSE по локальному среднему и дисперсии.

    Это классический фильтр Lee с минимумом среднеквадратичной ошибки и квадратным
    окном, а НЕ направленный вариант "Refined Lee" (использующий субокна,
    выровненные по краям). Формула:
        W = (Var(I) - mean(I)^2 / n_looks) / Var(I)
        I_hat = mean(I) + W * (I - mean(I))

    Аргументы:
        data: двумерный массив обратного рассеяния SAR в дБ.
        size: размер апертуры окна (по умолчанию 7 для фильтра 7x7).
        n_looks: эквивалентное число накоплений (4.4 для Sentinel-1 IW GRD).

    Возвращает:
        Отфильтрованный двумерный массив в дБ.
    """
    valid_mask = np.isfinite(data) & (data > SAR_NODATA_MAX_DB)
    if not np.any(valid_mask):
        return data.copy()

    fill_val = float(np.nanmedian(data[valid_mask]))
    data_clean = np.where(valid_mask, data, fill_val)

    # Перевод дБ в линейную шкалу интенсивности
    linear = 10.0 ** (data_clean / 10.0)

    # Вычисление локального среднего и дисперсии по окну size x size
    mean_linear = uniform_filter(linear, size=size)
    mean_sq_linear = uniform_filter(linear**2, size=size)
    var_linear = np.maximum(mean_sq_linear - mean_linear**2, 0.0)

    # Весовой коэффициент Lee
    theoretical_var = (mean_linear**2) / n_looks
    var_clean = np.maximum(var_linear, 1e-10)
    w = np.clip((var_linear - theoretical_var) / var_clean, 0.0, 1.0)

    filtered_linear = mean_linear + w * (linear - mean_linear)
    filtered_linear = np.maximum(filtered_linear, 1e-10)
    filtered_db = 10.0 * np.log10(filtered_linear)

    filtered_db[~valid_mask] = data[~valid_mask]
    return filtered_db.astype(np.float32)


def speckle_filter(
    data: np.ndarray | None,
    method: str = "lee",
    size: int = LEE_SIZE,
) -> np.ndarray | None:
    """Применяет подавление спекла к данным обратного рассеяния радара.

    Аргументы:
        data: двумерный массив обратного рассеяния SAR в дБ или None.
        method: метод фильтрации: 'lee' (по умолчанию, Lee MMSE 7x7), 'uniform' или 'median'.
        size: размер окна ядра (например, 5 или 7).

    Возвращает:
        Отфильтрованный двумерный массив или None, если входные данные равны None.
    """
    if data is None:
        return None
    valid_mask = np.isfinite(data) & (data > SAR_NODATA_MAX_DB)
    if not np.any(valid_mask):
        return data.copy()

    if method == "lee":
        return refined_lee_filter(data, size=size, n_looks=LEE_LOOKS)

    fill_val = float(np.nanmedian(data[valid_mask]))
    data_clean = np.where(valid_mask, data, fill_val)

    filtered = median_filter(data_clean, size=size) if method == "median" else uniform_filter(data_clean, size=size)

    filtered[~valid_mask] = data[~valid_mask]
    return filtered.astype(np.float32)


def apply_mmu(
    mask: np.ndarray,
    min_size: int | None = None,
) -> np.ndarray:
    """Удаляет изолированные кластеры шума меньше min_size пикселей.

    Аргументы:
        mask: двумерный булев или целочисленный бинарный массив.
        min_size: минимальное число смежных связанных пикселей.

    Возвращает:
        Очищенный бинарный массив.
    """
    if min_size is None:
        min_size = MMU_MIN_PIXELS

    if not np.any(mask):
        return mask.copy()

    structure = np.ones((3, 3), dtype=np.uint8)
    labeled, num_features = label(mask, structure=structure)
    if num_features == 0:
        return mask.copy()

    counts = np.bincount(labeled.ravel())
    remove_mask = (counts < min_size)[labeled]
    cleaned = mask & (~remove_mask)
    return cleaned


def apply_hydrological_connectivity(
    flood_mask: np.ndarray,
    seed_mask: np.ndarray,
) -> np.ndarray:
    """Фильтрует кластеры затопления по гидрологической связности с опорной водной сетью.

    Оставляет только компоненты связности (8-связность) flood_mask, которые касаются
    или пересекают seed_mask (обычно постоянная речная вода, например GSW occurrence >= 80%).
    Изолированные лужи и ложные срабатывания вдали от речной дренажной сети устраняются.
    """
    if not np.any(flood_mask) or not np.any(seed_mask):
        return np.zeros_like(flood_mask)

    binary_flood = flood_mask > 0
    structure = np.ones((3, 3), dtype=bool)
    labeled, num_features = label(binary_flood, structure=structure)
    if num_features == 0:
        return flood_mask.copy()

    # Расширение опорной маски на 1 пиксель структурой 3x3, чтобы соседние компоненты затопления касались опоры
    from scipy.ndimage import binary_dilation

    seed_dilated = binary_dilation(seed_mask > 0, structure=structure)

    seed_labels = np.unique(labeled[seed_dilated])
    seed_labels = seed_labels[seed_labels != 0]

    if len(seed_labels) == 0:
        return np.zeros_like(flood_mask)

    keep_mask = np.isin(labeled, seed_labels)
    return (binary_flood & keep_mask).astype(flood_mask.dtype)


def apply_morphological_closing(
    mask: np.ndarray,
    kernel_size: int = 5,
) -> np.ndarray:
    """Закрывает мелкие спекл-провалы и разрывы от волн внутри водных объектов дисковым ядром."""
    if not np.any(mask):
        return mask.copy()

    from scipy.ndimage import binary_closing

    y, x = np.ogrid[-(kernel_size // 2) : (kernel_size // 2) + 1, -(kernel_size // 2) : (kernel_size // 2) + 1]
    kernel = (x**2 + y**2) <= (kernel_size // 2) ** 2
    closed = binary_closing(mask > 0, structure=kernel)
    return closed.astype(mask.dtype)


def apply_planar_hand_filter(
    flood_mask: np.ndarray,
    seed_mask: np.ndarray,
    hand: np.ndarray | None,
    percentile: float = 90.0,
    tolerance_m: float = 1.5,
) -> np.ndarray:
    """Отсекает затопление выше уровня воды у русла реки (HAND) плюс допуск.

    Гидравлический речной паводок имеет связную плоскостную водную
    поверхность. Отметка воды не может превышать 90-й процентиль HAND
    непосредственно у границы русла реки плюс допуск 1.5 м.

    Args:
        flood_mask: 2D булев или целочисленный бинарный массив пикселей-кандидатов затопления.
        seed_mask: 2D булев массив постоянной или сезонной опорной сети русел рек.
        hand: 2D массив float высот над ближайшим водотоком (HAND) в метрах.
        percentile: Процентиль границы русла для восстановления уровня воды (по умолчанию 90.0).
        tolerance_m: Допуск по высоте выше границы русла в метрах (по умолчанию 1.5 м).

    Returns:
        Отфильтрованная бинарная маска затопления.
    """
    if hand is None or not np.any(flood_mask) or not np.any(seed_mask):
        return flood_mask.copy()

    structure = np.ones((3, 3), dtype=bool)
    from scipy.ndimage import binary_dilation

    seed_dilated = binary_dilation(seed_mask > 0, structure=structure)
    river_boundary = seed_dilated & (~(seed_mask > 0))

    boundary_hand = hand[river_boundary & np.isfinite(hand) & (hand >= 0.0)]
    if len(boundary_hand) == 0:
        return flood_mask.copy()

    max_hand = float(np.percentile(boundary_hand, percentile)) + float(tolerance_m)
    valid_elev = np.isfinite(hand) & (hand <= max_hand)

    return (flood_mask & valid_elev).astype(flood_mask.dtype)
