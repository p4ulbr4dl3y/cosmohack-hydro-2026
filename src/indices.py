"""Расчёт оптических индексов и мультиспектральная сегментация воды."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

from src.config import (
    OPTICAL_AWEISH_MIN,
    OPTICAL_MNDWI_MIN,
    OPTICAL_NDVI_MAX,
)


def calculate_optical_indices(
    green: np.ndarray,
    nir: np.ndarray,
    swir1: np.ndarray,
    swir2: np.ndarray,
    blue: np.ndarray | None = None,
    red: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Вычисляет оптические водные и вегетационные индексы по каналам Sentinel-2 MSI.

    Возвращаются всегда:
        - NDWI = (Green - NIR) / (Green + NIR)
        - MNDWI = (Green - SWIR1) / (Green + SWIR1)

    Возвращаются при наличии требуемого канала:
        - NDVI = (NIR - Red) / (NIR + Red)              [требуется ``red``]
        - AWEIsh = Blue + 2.5*Green - 1.5*(NIR + SWIR1) - 0.25*SWIR2
                                                        [требуется ``blue``]

    ``swir2`` используется только в AWEIsh.

    Аргументы:
        green: зелёный канал (B03).
        nir: ближний инфракрасный канал (B08).
        swir1: коротковолновый инфракрасный канал 1 (B11).
        swir2: коротковолновый инфракрасный канал 2 (B12), используется в AWEIsh.
        blue: необязательный синий канал (B02), необходим для AWEIsh.
        red: необязательный красный канал (B04), необходим для NDVI.

    Возвращает:
        Сопоставление имени индекса и двумерного массива.
    """
    eps = 1e-7
    ndwi = (green - nir) / np.maximum(green + nir, eps)
    mndwi = (green - swir1) / np.maximum(green + swir1, eps)
    indices = {"ndwi": ndwi, "mndwi": mndwi}
    if red is not None:
        indices["ndvi"] = (nir - red) / np.maximum(nir + red, eps)
    if blue is not None:
        indices["aweish"] = blue + 2.5 * green - 1.5 * (nir + swir1) - 0.25 * swir2
    return indices


def segment_optical(
    s2_path: str | Path | None,
    target_shape: tuple[int, int],
    mndwi_min: float = OPTICAL_MNDWI_MIN,
    aweish_min: float = OPTICAL_AWEISH_MIN,
    ndvi_max: float = OPTICAL_NDVI_MAX,
) -> tuple[np.ndarray | None, np.ndarray]:
    """Сегментирует воду по индексам Sentinel-2 MSI там, где они доступны.

    Мутная паводковая вода имеет отрицательный NDWI, поэтому NDWI не требуется.
    Использует: (MNDWI > mndwi_min или AWEIsh > aweish_min) & (NDVI <= ndvi_max).

    Аргументы:
        s2_path: путь к файлу GeoTIFF Sentinel-2 MSI.
        target_shape: ожидаемая форма выхода (height, width).
        mndwi_min: минимальный порог MNDWI (по умолчанию 0.1).
        aweish_min: минимальный порог AWEIsh (по умолчанию 0.0).
        ndvi_max: максимальный порог NDVI (по умолчанию 0.3).

    Возвращает:
        (optical_water, valid_mask):
            optical_water: двумерный булев массив или None, если файл отсутствует или нет валидных пикселей.
            valid_mask: двумерный булев массив, отмечающий валидные пиксели MSI.
    """
    height, width = target_shape
    if not s2_path or not Path(s2_path).exists():
        return None, np.zeros((height, width), dtype=bool)

    with rasterio.open(s2_path) as src:
        # Ожидаемые каналы: 5: NDWI, 6: MNDWI, 7: NDVI, 8: AWEIsh
        if src.count < 8:
            return None, np.zeros((height, width), dtype=bool)

        mndwi = src.read(6)
        ndvi = src.read(7)
        aweish = src.read(8)

    valid_mask = (
        np.isfinite(mndwi)
        & (mndwi != -999.0)
        & np.isfinite(ndvi)
        & (ndvi != -999.0)
        & np.isfinite(aweish)
        & (aweish != -999.0)
    )

    if not np.any(valid_mask):
        return None, np.zeros((height, width), dtype=bool)

    # Поправка на мутную воду: MNDWI > 0.1 или AWEIsh > 0, NDVI <= 0.3
    optical_water = ((mndwi > mndwi_min) | (aweish > aweish_min)) & (ndvi <= ndvi_max) & valid_mask

    return optical_water, valid_mask
