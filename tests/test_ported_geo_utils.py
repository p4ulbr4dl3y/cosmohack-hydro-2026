"""Модульные тесты продвинутых геопространственных утилит, портированных из geo-carbon-mrv."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Polygon, box

from src.geo_utils import (
    calculate_polygon_area_ha,
    compute_coverage_stats,
    compute_pixel_area_grid,
    compute_pixel_box_area_ha,
    extract_raster_pixel_intersections,
    find_raster_coverage,
    get_wgs84_geod,
    load_geometry,
    validate_aoi_geometry,
)


def test_get_wgs84_geod():
    geod = get_wgs84_geod()
    assert geod is not None
    assert geod.a == 6378137.0


def test_calculate_polygon_area_ha_basic():
    # Квадрат 1 градус x 1 градус на экваторе составляет примерно 111km x 111km = 12,300 km² ~ 1.23e6 ha
    poly = box(0.0, 0.0, 1.0, 1.0)
    area_ha = calculate_polygon_area_ha(poly)
    assert 1.2e6 < area_ha < 1.3e6

    # Пустая геометрия возвращает 0
    empty_poly = Polygon()
    assert calculate_polygon_area_ha(empty_poly) == 0.0


def test_load_geometry_variations(tmp_path: Path):
    poly = box(127.0, 50.0, 128.0, 51.0)

    # 1. Непосредственно геометрия Shapely
    loaded1 = load_geometry(poly)
    assert loaded1.equals(poly)

    # 2. Самопересекающаяся геометрия (автоматически исправляется)
    bowtie = Polygon([(0, 0), (0, 2), (2, 0), (2, 2), (0, 0)])
    loaded_bow = load_geometry(bowtie)
    assert loaded_bow.is_valid

    # 3. Словарь Feature GeoJSON
    feat_dict = {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
        "properties": {},
    }
    loaded2 = load_geometry(feat_dict)
    assert loaded2.is_valid
    assert loaded2.area == pytest.approx(1.0)

    # 4. FeatureCollection GeoJSON
    fc_dict = {"type": "FeatureCollection", "features": [feat_dict]}
    loaded3 = load_geometry(fc_dict)
    assert loaded3.is_valid

    # 5. Строка JSON
    loaded4 = load_geometry(json.dumps(feat_dict))
    assert loaded4.is_valid

    # 6. Путь к файлу JSON
    fpath = tmp_path / "test_geom.geojson"
    fpath.write_text(json.dumps(fc_dict), encoding="utf-8")
    loaded5 = load_geometry(fpath)
    assert loaded5.is_valid

    # Ошибка некорректной строки
    with pytest.raises(ValueError):
        load_geometry("not a json string and not a file")

    # Ошибка неподдерживаемого типа
    with pytest.raises(TypeError):
        load_geometry(12345)  # type: ignore


def test_validate_aoi_geometry():
    small_poly = box(127.0, 50.0, 127.1, 50.1)
    is_valid, area_ha, err = validate_aoi_geometry(small_poly, max_area_km2=500.0)
    assert is_valid is True
    assert area_ha > 0.0
    assert err is None

    # Пустая геометрия
    is_valid, area_ha, err = validate_aoi_geometry(Polygon())
    assert is_valid is False
    assert "пуста" in err.lower()

    # Превышение лимита площади
    is_valid, area_ha, err = validate_aoi_geometry(small_poly, max_area_km2=0.001)
    assert is_valid is False
    assert "превышает лимит" in err.lower()


def test_compute_pixel_box_area_ha():
    area_ha = compute_pixel_box_area_ha(127.0, 50.0, 127.01, 50.01)
    assert area_ha > 0.0
    assert isinstance(area_ha, float)


def test_compute_pixel_area_grid():
    transform = from_origin(127.0, 50.1, 0.01, 0.01)
    shape_hw = (10, 10)

    # Полигон, покрывающий центральные 4 пикселя
    poly = box(127.02, 50.02, 127.06, 50.06)
    grid = compute_pixel_area_grid(poly, transform, shape_hw)

    assert grid.shape == (10, 10)
    assert np.all(grid >= 0.0)
    assert np.sum(grid) > 0.0

    # Пустой полигон даёт нулевую сетку
    empty_grid = compute_pixel_area_grid(Polygon(), transform, shape_hw)
    assert np.all(empty_grid == 0.0)


def test_coverage_stats_and_intersections(tmp_path: Path):
    poly = box(127.2, 50.2, 127.4, 50.4)
    req_ha, cov_ha, pct = compute_coverage_stats(poly, covered_area_ha=100.0)
    assert req_ha > 0.0
    assert 0.0 <= pct <= 100.0

    # Тест с растром MemoryFile
    transform = from_origin(127.0, 50.5, 0.01, 0.01)
    tif_path = tmp_path / "test_scene.tif"
    with rasterio.open(
        tif_path,
        "w",
        driver="GTiff",
        height=50,
        width=50,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(np.ones((1, 50, 50), dtype=np.float32))

    grid, trans, shp, tot = extract_raster_pixel_intersections(tif_path, poly)
    assert shp == (50, 50)
    assert tot > 0.0

    coverage_items = find_raster_coverage(poly, {"site_1": tif_path})
    assert len(coverage_items) == 1
    assert coverage_items[0]["site_id"] == "site_1"
