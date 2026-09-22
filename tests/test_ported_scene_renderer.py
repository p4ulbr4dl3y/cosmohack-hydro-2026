"""Модульные тесты модуля визуализации веб-растров и рендеринга PNG-оверлеев."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from src.scene_renderer import (
    SCENE_MODES,
    get_scene_wgs84_bounds,
    mask_to_rgba,
    multi_water_to_rgba,
    normalize_band,
    render_geotiff_overlay,
    render_gradient_mask_rgba,
    render_mask_png,
    render_rgba_to_png,
    render_scene_png,
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


def _write_multiband_tif(path: Path, bands: list[np.ndarray], descriptions: list[str], nodata: float | None) -> None:
    height, width = bands[0].shape
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=len(bands),
        dtype="float32",
        crs="EPSG:32652",
        transform=from_origin(373530.0, 5590350.0, 10.0, 10.0),
        nodata=nodata,
    ) as dst:
        for idx, band in enumerate(bands, start=1):
            dst.write(band.astype(np.float32), idx)
            dst.set_band_description(idx, descriptions[idx - 1])


def test_render_scene_png_sar_single_and_false_colour(tmp_path: Path):
    vv = np.full((40, 40), -12.0, dtype=np.float32)
    vh = np.full((40, 40), -18.0, dtype=np.float32)
    ratio = vv - vh
    tif = tmp_path / "S1_peak_test.tif"
    _write_multiband_tif(tif, [vv, vh, ratio], ["VV", "VH", "VV_VH_ratio"], nodata=-999.0)

    png, bounds, meta = render_scene_png(tif, mode="sar_vv")
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert meta["mode"] == "sar_vv"
    assert meta["width"] == 40 and meta["height"] == 40
    assert len(bounds) == 2
    # Одиночный канал дублируется в RGB, а не остаётся серым с непрозрачной альфой
    assert len(SCENE_MODES["sar_vv"]["bands"]) == 1
    assert len(SCENE_MODES["sar_vh"]["bands"]) == 1
    assert len(SCENE_MODES["msi_true"]["bands"]) == 3
    assert len(SCENE_MODES["msi_false"]["bands"]) == 3


def test_render_scene_png_keeps_nodata_transparent(tmp_path: Path):
    band = np.full((20, 20), 0.25, dtype=np.float32)
    band[:10, :] = -999.0  # верхняя половина - nodata
    tif = tmp_path / "SENTINEL2_peak_test.tif"
    _write_multiband_tif(
        tif,
        [band, band, band, band],
        ["B3", "B4", "B8", "B11"],
        nodata=-999.0,
    )

    png, _bounds, meta = render_scene_png(tif, mode="msi_true", max_dim=20)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")

    with rasterio.open(tif) as src:
        arr = src.read(2)
    # Верхняя половина сцены без данных: подложка не должна рисовать чёрные полосы
    assert np.all(arr[:10, :] == -999.0)
    assert meta["height"] == 20


def test_render_scene_png_downscales_large_scenes(tmp_path: Path):
    band = np.full((400, 800), 0.3, dtype=np.float32)
    tif = tmp_path / "SENTINEL2_peak_big.tif"
    _write_multiband_tif(tif, [band, band, band, band], ["B3", "B4", "B8", "B11"], nodata=-999.0)

    _png, _bounds, meta = render_scene_png(tif, mode="msi_true", max_dim=100)
    # Подложка весит мегабайты при полном разрешении: сторона ограничена
    assert max(meta["width"], meta["height"]) <= 100
    assert meta["height"] < 400


def test_render_scene_png_rejects_unknown_mode(tmp_path: Path):
    band = np.zeros((5, 5), dtype=np.float32)
    tif = tmp_path / "scene.tif"
    _write_multiband_tif(tif, [band], ["VV"], nodata=None)

    try:
        render_scene_png(tif, mode="not_a_mode")
    except ValueError as exc:
        assert "not_a_mode" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Ожидалась ошибка ValueError для неизвестного режима")

    try:
        render_scene_png(tmp_path / "missing.tif", mode="sar_vv")
    except FileNotFoundError:
        pass
    else:  # pragma: no cover
        raise AssertionError("Ожидалась ошибка FileNotFoundError для отсутствующего файла")
