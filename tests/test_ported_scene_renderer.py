"""Модульные тесты модуля визуализации веб-растров и рендеринга PNG-оверлеев."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from src.scene_renderer import (
    get_scene_wgs84_bounds,
    mask_to_rgba,
    multi_water_to_rgba,
    normalize_band,
    render_geotiff_overlay,
    render_gradient_mask_rgba,
    render_mask_png,
    render_rgba_to_png,
)


def test_normalize_band():
    arr = np.linspace(10.0, 100.0, 100).reshape((10, 10))
    norm = normalize_band(arr)
    assert norm.shape == (10, 10)
    assert norm.dtype == np.uint8
    assert norm.min() == 0
    assert norm.max() == 255


def test_mask_to_rgba_and_png():
    mask = np.array([[1, 0], [0, 1]], dtype=np.uint8)
    rgba = mask_to_rgba(mask, color_rgb=(255, 0, 0), alpha=200)

    assert rgba.shape == (2, 2, 4)
    # Проверка прозрачного пикселя
    assert rgba[0, 1, 3] == 0
    # Проверка окрашенного пикселя
    assert rgba[0, 0, 0] == 255
    assert rgba[0, 0, 3] == 200

    png_bytes = render_rgba_to_png(rgba)
    assert isinstance(png_bytes, bytes)
    # Стандартный магический заголовок PNG
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_multi_water_to_rgba():
    w_pre = np.array([[1, 0], [0, 0]], dtype=np.uint8)
    w_peak = np.array([[1, 1], [0, 0]], dtype=np.uint8)
    flood = np.array([[0, 1], [0, 0]], dtype=np.uint8)

    rgba = multi_water_to_rgba(w_pre, w_peak, flood)
    assert rgba.shape == (2, 2, 4)
    # [0, 0] - вода до паводка (синий)
    assert rgba[0, 0, 0] == 30 and rgba[0, 0, 2] == 175
    # [0, 1] - новый паводок (красный)
    assert rgba[0, 1, 0] == 239 and rgba[0, 1, 1] == 68


def test_render_mask_png_and_geotiff_overlay(tmp_path: Path):
    mask = np.ones((20, 20), dtype=np.uint8)
    png_bytes = render_mask_png(mask, layer_type="flood")
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    # Создание временного GeoTIFF
    tif_path = tmp_path / "test_layer.tif"
    transform = from_origin(127.0, 50.2, 0.01, 0.01)
    with rasterio.open(
        tif_path,
        "w",
        driver="GTiff",
        height=20,
        width=20,
        count=1,
        dtype="uint8",
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(mask, 1)

    bounds = get_scene_wgs84_bounds(tif_path)
    assert len(bounds) == 2
    assert bounds[0][0] < bounds[1][0]  # юг < север
    assert bounds[0][1] < bounds[1][1]  # запад < восток

    png_overlay, overlay_bounds, meta = render_geotiff_overlay(tif_path, layer_type="flood")
    assert png_overlay.startswith(b"\x89PNG\r\n\x1a\n")
    assert overlay_bounds == bounds
    assert meta["width"] == 20


def test_render_gradient_mask_rgba():
    mask = np.zeros((30, 30), dtype=np.uint8)
    mask[5:25, 5:25] = 1
    rgba_flood = render_gradient_mask_rgba(mask, layer_type="flood")
    assert rgba_flood.shape == (30, 30, 4)
    # Центральный пиксель должен иметь цвет и высокую альфу
    assert rgba_flood[15, 15, 3] > 150
    # Фоновый пиксель должен быть прозрачным
    assert rgba_flood[0, 0, 3] == 0

    png_bytes = render_mask_png(mask, layer_type="flood", gradient=True)
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    rgba_peak = render_gradient_mask_rgba(mask, layer_type="water_peak")
    assert rgba_peak.shape == (30, 30, 4)
    assert rgba_peak[15, 15, 3] > 150
