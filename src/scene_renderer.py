"""Движок веб-визуализации растров и динамических PNG-оверлеев.

Формирует прозрачные RGBA PNG-оверлеи и вычисляет ограничивающие прямоугольники WGS84 для Leaflet
из растровых файлов GeoTIFF или бинарных и классифицированных масок numpy для немедленного веб-отображения.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.io import MemoryFile
from rasterio.warp import calculate_default_transform

#: Режимы отображения реальных сцен Sentinel-1/2. ``bands`` задаёт порядок каналов
#: исходного растра, попадающих в R, G, B выходного PNG (1-based).
#: ``s1_peak_2019-07-25.tif`` содержит каналы [VV, VH, VV_VH_ratio], а ``SENTINEL2_*.tif``
#: - [B3, B4, B8, B11, NDWI, MNDWI, NDVI, AWEIsh].
SCENE_MODES: dict[str, dict[str, Any]] = {
    "sar_vv": {"kind": "sar", "bands": (1,), "label": "Sentinel-1 SAR VV (пик)"},
    "sar_vh": {"kind": "sar", "bands": (2,), "label": "Sentinel-1 SAR VH (пик)"},
    "msi_true": {"kind": "optical", "bands": (2, 1, 3), "label": "Sentinel-2 True Color (B4/B3/B8)"},
    "msi_false": {"kind": "optical", "bands": (3, 2, 1), "label": "Sentinel-2 False Color (B8/B4/B3)"},
}

#: Ограничение стороны выходного PNG: снимок сцены в полном разрешении (4479x3682)
#: весит ~22 МБ и кодируется секунды, что неприемлемо для веб-подложки.
SCENE_MAX_DIM = 1600

#: Значение nodata оптических сцен (см. ``scripts/fetch_real_s2.py``).
OPTICAL_NODATA = -999.0


def get_scene_wgs84_bounds(tif_path: str | Path) -> list[list[float]]:
    """Вычисляет географические границы WGS84 в формате Leaflet [[south, west], [north, east]]."""
    with rasterio.open(tif_path) as src:
        dst_transform, width, height = calculate_default_transform(
            src.crs, "EPSG:4326", src.width, src.height, *src.bounds
        )
        west = float(dst_transform.c)
        north = float(dst_transform.f)
        east = float(west + width * dst_transform.a)
        south = float(north + height * dst_transform.e)
        return [
            [round(south, 6), round(west, 6)],
            [round(north, 6), round(east, 6)],
        ]


def normalize_band(
    arr: np.ndarray,
    p_low: float = 2.0,
    p_high: float = 98.0,
) -> np.ndarray:
    """Нормирует значения массива к 0..255 через перцентильное растяжение контраста."""
    valid = np.isfinite(arr)
    out = np.zeros_like(arr, dtype=np.uint8)
    if not np.any(valid):
        return out
    v = arr[valid]
    p_lo, p_hi = np.percentile(v, (p_low, p_high))
    if p_hi <= p_lo:
        p_hi = p_lo + 1e-4
    clipped = np.clip(v, p_lo, p_hi)
    out[valid] = np.clip(np.round((clipped - p_lo) / (p_hi - p_lo) * 255.0), 0, 255).astype(np.uint8)
    return out


def mask_to_rgba(
    mask: np.ndarray,
    color_rgb: tuple[int, int, int] = (239, 68, 68),  # По умолчанию: красно-оранжевое затопление
    alpha: int = 190,
) -> np.ndarray:
    """Преобразует бинарную маску (0 или 1) в массив RGBA-изображения.

    Пиксели со значением 0 полностью прозрачны. Пиксели со значением 1 имеют color_rgb с альфой.
    """
    h, w = mask.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    bool_mask = mask.astype(bool)

    rgba[bool_mask, 0] = color_rgb[0]
    rgba[bool_mask, 1] = color_rgb[1]
    rgba[bool_mask, 2] = color_rgb[2]
    rgba[bool_mask, 3] = alpha
    return rgba


def multi_water_to_rgba(
    water_pre: np.ndarray,
    water_peak: np.ndarray,
    flood: np.ndarray,
) -> np.ndarray:
    """Создаёт комплексный многокатегорийный гидрологический оверлей:

    - ранее существовавшая вода: тёмно-синий (30, 64, 175, 180);
    - расширение затопления на пике: ярко-красный (239, 68, 68, 210);
    - отступившая вода: жёлто-янтарный (245, 158, 11, 160).
    """
    h, w = flood.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)

    pre_b = water_pre.astype(bool)
    peak_b = water_peak.astype(bool)
    flood_b = flood.astype(bool)
    receded_b = pre_b & (~peak_b)

    # 1. Ранее существовавшая вода
    rgba[pre_b] = [30, 64, 175, 180]
    # 2. Отступившая вода
    rgba[receded_b] = [245, 158, 11, 160]
    # 3. Новое затопление (наивысший визуальный приоритет)
    rgba[flood_b] = [239, 68, 68, 220]

    return rgba


def render_rgba_to_png(rgba: np.ndarray) -> bytes:
    """Кодирует массив RGBA uint8 (H, W, 4) в стандартные байты PNG через rasterio."""
    h, w, c = rgba.shape
    if c != 4:
        raise ValueError(f"Expected 4 channels (RGBA), got {c}")

    # rasterio ожидает (channels, height, width)
    bands = np.transpose(rgba, (2, 0, 1))

    with MemoryFile() as mem:
        with mem.open(
            driver="PNG",
            height=h,
            width=w,
            count=4,
            dtype="uint8",
        ) as dst:
            dst.write(bands)
        return mem.read()


def render_gradient_mask_rgba(
    mask: np.ndarray,
    layer_type: str = "flood",
) -> np.ndarray:
    """Строит непрерывный батиметрический градиентный оверлей интенсивности для гидрологических масок.

    Использует евклидово преобразование расстояния для моделирования глубины воды и интенсивности затопления от края к глубокому центру.
    """
    h, w = mask.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    bool_mask = mask.astype(bool)
    if not np.any(bool_mask):
        return rgba

    from scipy.ndimage import distance_transform_edt

    dist = distance_transform_edt(bool_mask)
    valid_dist = dist[bool_mask]
    max_d = float(np.percentile(valid_dist, 95)) if len(valid_dist) > 0 else 1.0
    if max_d <= 0.0:
        max_d = 1.0
    norm = np.clip(dist / max_d, 0.0, 1.0)

    # Градиенты для разных слоёв
    norm_layer = layer_type.strip().lower()
    if norm_layer == "flood":
        # Берег и мелководье (янтарный и оранжевый) - средняя глубина (красный) - глубина (багровый)
        c0 = np.array([254, 215, 170], dtype=float)
        c1 = np.array([239, 68, 68], dtype=float)
        c2 = np.array([153, 27, 27], dtype=float)
    elif norm_layer == "water_peak":
        # Край затопления (светло-голубой) - средняя глубина (циан) - глубокий канал (тёмно-синий)
        c0 = np.array([186, 230, 253], dtype=float)
        c1 = np.array([14, 165, 233], dtype=float)
        c2 = np.array([30, 58, 138], dtype=float)
    else:  # water_pre или другие
        # Край (циан) - средняя глубина (синий) - глубина (тёмно-синий)
        c0 = np.array([165, 243, 252], dtype=float)
        c1 = np.array([37, 99, 235], dtype=float)
        c2 = np.array([30, 64, 175], dtype=float)

    # Двухэтапная кусочно-линейная интерполяция
    t = norm[bool_mask]
    rgb = np.zeros((len(t), 3), dtype=np.uint8)
    first_half = t < 0.5
    t1 = t[first_half] * 2.0
    rgb[first_half] = np.round(c0 + (c1 - c0) * t1[:, None]).astype(np.uint8)

    second_half = ~first_half
    t2 = (t[second_half] - 0.5) * 2.0
    rgb[second_half] = np.round(c1 + (c2 - c1) * t2[:, None]).astype(np.uint8)

    # Рампа альфы от 150 на краю до 230 на глубине
    alpha = np.round(150 + 80 * t).astype(np.uint8)

    rgba[bool_mask, 0:3] = rgb
    rgba[bool_mask, 3] = alpha
    return rgba


def render_mask_png(
    mask: np.ndarray,
    layer_type: str = "flood",
    gradient: bool = False,
) -> bytes:
    """Удобная вспомогательная функция для рендеринга маски сразу в байты PNG.

    Типы слоёв: 'flood' (красный), 'water_pre' (тёмно-синий), 'water_peak' (циан-синий).
    Если gradient=True, формируется непрерывная батиметрическая цветовая рампа интенсивности.
    """
    if gradient:
        rgba = render_gradient_mask_rgba(mask, layer_type=layer_type)
    else:
        colors = {
            "flood": (239, 68, 68),
            "water_pre": (30, 64, 175),
            "water_peak": (14, 165, 233),
        }
        rgb = colors.get(layer_type.lower(), (239, 68, 68))
        rgba = mask_to_rgba(mask, color_rgb=rgb, alpha=200)
    return render_rgba_to_png(rgba)


def render_scene_png(
    tif_path: str | Path,
    mode: str,
    max_dim: int = SCENE_MAX_DIM,
) -> tuple[bytes, list[list[float]], dict[str, Any]]:
    """Рендерит реальную сцену Sentinel-1/2 в PNG для использования как подложка карты.

    Режим ``mode`` берётся из :data:`SCENE_MODES`. Радиолокационные каналы (дБ) растягиваются
    перцентильно функцией :func:`normalize_band`, оптические (отражательная способность 0..1)
    масштабируются в 0..255. Пиксели nodata и невалидные остаются прозрачными, поэтому
    сцена накладывается на карту без чёрных прямоугольников.

    Возвращает ``(png_bytes, bounds_wgs84, meta)``.
    """
    cfg = SCENE_MODES.get(mode)
    if cfg is None:
        raise ValueError(f"Неизвестный режим сцены '{mode}'. Допустимо: {sorted(SCENE_MODES)}")

    p = Path(tif_path)
    if not p.is_file():
        raise FileNotFoundError(f"Файл сцены не найден: {p}")

    with rasterio.open(p) as src:
        scale = min(1.0, max_dim / float(max(src.width, src.height)))
        out_h = max(1, int(round(src.height * scale)))
        out_w = max(1, int(round(src.width * scale)))
        bands = src.read(
            indexes=list(cfg["bands"]),
            out_shape=(len(cfg["bands"]), out_h, out_w),
            resampling=Resampling.average,
        )
        nodata = src.nodata
        crs = str(src.crs)
        src_bounds = src.bounds

    is_sar = cfg["kind"] == "sar"
    channels: list[np.ndarray] = []
    for band in bands:
        band = band.astype(np.float32)
        valid = np.isfinite(band)
        if nodata is not None:
            valid &= band != nodata
        if not is_sar:
            valid &= band > 0.0
        if not np.any(valid):
            channels.append(np.zeros(band.shape, dtype=np.uint8))
            continue
        if is_sar:
            # Радиолокационные каналы в дБ растягиваются перцентильно (2-98%)
            gray = normalize_band(np.where(valid, band, np.nan))
            gray[~valid] = 0
        else:
            values = band[valid]
            lo, hi = np.percentile(values, (2.0, 98.0))
            if hi <= lo:
                hi = lo + 1e-6
            scaled = np.clip((band - lo) / (hi - lo), 0.0, 1.0) * 255.0
            gray = np.round(np.nan_to_num(scaled, nan=0.0)).astype(np.uint8)
            gray[~valid] = 0
        channels.append(gray)

    if len(channels) == 1:
        channels = channels * 3

    alpha = np.zeros(channels[0].shape, dtype=np.uint8)
    for ch in channels:
        alpha = np.maximum(alpha, ch)
    alpha[alpha > 0] = 255

    rgba = np.dstack([channels[0], channels[1], channels[2], alpha])
    png_bytes = render_rgba_to_png(rgba)
    bounds = get_scene_wgs84_bounds(p)
    meta = {
        "width": out_w,
        "height": out_h,
        "crs": crs,
        "bounds": bounds,
        "mode": mode,
        "bounds_native": [src_bounds.left, src_bounds.bottom, src_bounds.right, src_bounds.top],
    }
    return png_bytes, bounds, meta


def render_geotiff_overlay(
    tif_path: str | Path,
    layer_type: str = "flood",
) -> tuple[bytes, list[list[float]], dict[str, Any]]:
    """Загружает GeoTIFF, рендерит RGBA PNG и вычисляет ограничивающий прямоугольник WGS84 для Leaflet."""
    p = Path(tif_path)
    if not p.is_file():
        raise FileNotFoundError(f"Файл GeoTIFF не найден: {p}")

    with rasterio.open(p) as src:
        mask = src.read(1)
        bounds = get_scene_wgs84_bounds(p)
        meta = {
            "width": src.width,
            "height": src.height,
            "crs": str(src.crs),
            "bounds": bounds,
        }

    png_bytes = render_mask_png(mask, layer_type=layer_type)
    return png_bytes, bounds, meta
