"""Пространственные и растровые геопространственные утилиты."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import rasterio
import shapely
from pyproj import Geod
from rasterio.features import geometry_mask
from rasterio.transform import Affine
from rasterio.warp import Resampling, reproject
from shapely.geometry import box, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.prepared import prep

WGS84_GEOD = Geod(ellps="WGS84")
MAX_AOI_AREA_KM2 = 25000.0  # Максимально допустимая площадь AOI для региональных гидрологических бассейнов (25 000 км²)


def read_raster_with_meta(
    path: str | Path,
    band: int | list[int] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Читает растровый массив и его профиль с метаданными.

    Аргументы:
        path: путь к растровому файлу.
        band: индекс канала с нумерацией от 1, список индексов каналов или None для чтения всех каналов.

    Возвращает:
        (data, meta):
            data: np.ndarray (двумерный для одного канала, трёхмерный для нескольких каналов).
            meta: словарь профиля rasterio.
    """
    with rasterio.open(path) as src:
        meta = src.profile.copy()
        if band is None:
            data = src.read()
        elif isinstance(band, int):
            data = src.read(band)
        else:
            data = src.read(band)
    return data, meta


def resample_to_target(
    source_path: str | Path,
    band: int,
    target_shape: tuple[int, int],
    target_transform: rasterio.Affine,
    target_crs: Any,
    resampling: Resampling = Resampling.bilinear,
    dst_nodata: float | None = None,
) -> np.ndarray:
    """Перепроецирует и пересэмплирует растровый канал под геометрию целевой сетки.

    Аргументы:
        source_path: путь к исходному растру.
        band: индекс канала с нумерацией от 1.
        target_shape: (height, width) выходной сетки.
        target_transform: аффинное преобразование выходной сетки.
        target_crs: CRS выходной сетки.
        resampling: алгоритм пересэмплирования (по умолчанию билинейный).
        dst_nodata: выходное значение nodata.

    Возвращает:
        Пересэмплированный двумерный массив numpy float32.
    """
    height, width = target_shape
    destination = np.zeros((height, width), dtype=np.float32)
    with rasterio.open(source_path) as src:
        reproject(
            source=rasterio.band(src, band),
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=target_transform,
            dst_crs=target_crs,
            resampling=resampling,
            dst_nodata=dst_nodata,
        )
    return destination


def clip_by_aoi(
    mask: np.ndarray,
    aoi_geom: Any,
    transform: rasterio.Affine,
    crs: Any = None,
) -> np.ndarray:
    """Обрезает бинарную или категориальную двумерную растровую маску по полигону AOI.

    Пиксели строго вне геометрии AOI обнуляются.

    Аргументы:
        mask: двумерный массив numpy.
        aoi_geom: геометрия Shapely или итерируемая коллекция геометрий.
        transform: аффинное преобразование растра.
        crs: необязательный CRS (для проверки или преобразования координат, если геометрию нужно перепроецировать).

    Возвращает:
        Обрезанный двумерный массив numpy с тем же dtype, что и на входе.
    """
    geoms = [aoi_geom] if not isinstance(aoi_geom, (list, tuple, gpd.GeoSeries)) else list(aoi_geom)
    inside_mask = geometry_mask(geoms, out_shape=mask.shape, transform=transform, invert=True)
    return np.where(inside_mask, mask, 0).astype(mask.dtype)


def get_wgs84_geod() -> Geod:
    """Возвращает экземпляр Geod WGS84 для точных эллипсоидальных расчётов."""
    return WGS84_GEOD


def calculate_polygon_area_ha(geometry: BaseGeometry, geod: Geod | None = None) -> float:
    """Вычисляет точную эллипсоидальную площадь геометрии в гектарах на WGS84.

    Устраняет искажение плоской проекции на больших речных бассейнах.

    Аргументы:
        geometry: геометрия Shapely.
        geod: необязательный экземпляр Geod из PyProj (по умолчанию WGS84).

    Возвращает:
        Площадь в гектарах.
    """
    if geometry.is_empty:
        return 0.0
    g = geod or WGS84_GEOD
    area_m2, _ = g.geometry_area_perimeter(geometry)
    return float(abs(area_m2) / 10000.0)


def load_geometry(source: str | Path | dict[str, Any] | BaseGeometry) -> BaseGeometry:
    """Загружает и исправляет геометрию из файла GeoJSON, словаря, строки JSON или объекта Shapely.

    Автоматически исправляет топологические аномалии через shapely.make_valid.

    Аргументы:
        source: путь к файлу, словарь GeoJSON, строка JSON или BaseGeometry.

    Возвращает:
        Корректная геометрия Shapely.
    """
    if isinstance(source, BaseGeometry):
        if not source.is_valid:
            source = shapely.make_valid(source)
        return source

    data: dict[str, Any]
    if isinstance(source, (str, Path)):
        p = Path(source)
        if p.is_file():
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        else:
            try:
                data = json.loads(str(source))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Failed to parse geometry from string or path: {source}") from exc
    elif isinstance(source, dict):
        data = source
    else:
        raise TypeError(f"Unsupported geometry source type: {type(source)}")

    obj_type = data.get("type")
    if obj_type == "FeatureCollection":
        features = data.get("features", [])
        if not features:
            raise ValueError("GeoJSON FeatureCollection is empty")
        geoms = [shape(f["geometry"]) for f in features if "geometry" in f and f["geometry"] is not None]
        if not geoms:
            raise ValueError("No valid geometries found in GeoJSON FeatureCollection")
        geom = unary_union(geoms)
    elif obj_type == "Feature":
        geom_dict = data.get("geometry")
        if not geom_dict:
            raise ValueError("Feature object has no geometry")
        geom = shape(geom_dict)
    elif obj_type in ("Polygon", "MultiPolygon", "GeometryCollection"):
        geom = shape(data)
    else:
        if "geometry" in data:
            geom = shape(data["geometry"])
        else:
            raise ValueError(f"Unknown GeoJSON structure: {obj_type}")

    if not geom.is_valid:
        geom = shapely.make_valid(geom)
    return geom


def validate_aoi_geometry(
    geometry: BaseGeometry,
    max_area_km2: float = MAX_AOI_AREA_KM2,
    geod: Geod | None = None,
) -> tuple[bool, float, str | None]:
    """Проверяет корректность геометрии и контролирует границы площади.

    Аргументы:
        geometry: BaseGeometry.
        max_area_km2: максимально допустимая площадь в км².
        geod: необязательный экземпляр Geod.

    Возвращает:
        (is_valid, area_ha, error_message).
    """
    if geometry.is_empty:
        return False, 0.0, "Geometry is empty"

    if not geometry.is_valid:
        geometry = shapely.make_valid(geometry)

    area_ha = calculate_polygon_area_ha(geometry, geod=geod)
    max_area_ha = max_area_km2 * 100.0

    if area_ha <= 0.0:
        return False, 0.0, "Geometry area is zero or negative"

    if area_ha > max_area_ha + 1e-6:
        return (
            False,
            area_ha,
            f"Polygon area ({area_ha:.2f} ha) exceeds limit {max_area_km2:.1f} km² ({max_area_ha:.1f} ha)",
        )

    return True, area_ha, None


def compute_pixel_box_area_ha(minx: float, miny: float, maxx: float, maxy: float, geod: Geod | None = None) -> float:
    """Вычисляет точную эллипсоидальную площадь ячейки ограничивающего прямоугольника в гектарах."""
    cell = box(minx, miny, maxx, maxy)
    return calculate_polygon_area_ha(cell, geod=geod)


def compute_pixel_area_grid(
    geometry: BaseGeometry,
    transform: Affine,
    shape_hw: tuple[int, int],
    geod: Geod | None = None,
) -> np.ndarray:
    """Вычисляет эллипсоидальную площадь пересечения (га) каждого растрового пикселя с полигоном.

    Учитывает широтное сжатие для непроецированных и региональных сеток.

    Аргументы:
        geometry: геометрия Shapely.
        transform: аффинное преобразование растра.
        shape_hw: (height, width) растра.
        geod: необязательный экземпляр Geod.

    Возвращает:
        Двумерный массив float64 с площадями пересечения пикселей в гектарах.
    """
    height, width = shape_hw
    areas_grid = np.zeros((height, width), dtype=np.float64)

    if geometry.is_empty:
        return areas_grid

    g = geod or WGS84_GEOD
    prepared_geom = prep(geometry)

    ta, tb, tc = transform.a, transform.b, transform.c
    td, te, tf = transform.d, transform.e, transform.f

    row_areas_ha = np.zeros(height, dtype=np.float64)
    for r in range(height):
        x0_ref = tc + r * tb
        x1_ref = tc + ta + (r + 1) * tb
        y0_ref = tf + r * te
        y1_ref = tf + (r + 1) * te + td
        cell_ref = box(
            min(x0_ref, x1_ref),
            min(y0_ref, y1_ref),
            max(x0_ref, x1_ref),
            max(y0_ref, y1_ref),
        )
        row_areas_ha[r] = calculate_polygon_area_ha(cell_ref, geod=g)

    full_grid = np.tile(row_areas_ha[:, np.newaxis], (1, width))

    raster_box = box(
        min(tc, tc + width * ta),
        min(tf, tf + height * te),
        max(tc, tc + width * ta),
        max(tf, tf + height * te),
    )
    if prepared_geom.contains(raster_box):
        return full_grid.copy()

    geom_bounds = geometry.bounds
    inv_t = ~transform

    corners = [
        (geom_bounds[0], geom_bounds[1]),
        (geom_bounds[0], geom_bounds[3]),
        (geom_bounds[2], geom_bounds[1]),
        (geom_bounds[2], geom_bounds[3]),
    ]
    px_coords = [inv_t @ c for c in corners]
    cols = [pt[0] for pt in px_coords]
    rows = [pt[1] for pt in px_coords]

    c_min = max(0, int(np.floor(min(cols))) - 1)
    c_max = min(width, int(np.ceil(max(cols))) + 1)
    r_min = max(0, int(np.floor(min(rows))) - 1)
    r_max = min(height, int(np.ceil(max(rows))) + 1)

    if c_min >= c_max or r_min >= r_max:
        return areas_grid

    for r in range(r_min, r_max):
        r_y0 = tf + r * te
        r_y1 = tf + (r + 1) * te
        cell_row_area = row_areas_ha[r]
        for c in range(c_min, c_max):
            x0 = tc + c * ta + r * tb
            y0 = r_y0 + c * td
            x1 = tc + (c + 1) * ta + (r + 1) * tb
            y1 = r_y1 + (c + 1) * td

            minx = min(x0, x1)
            maxx = max(x0, x1)
            miny = min(y0, y1)
            maxy = max(y0, y1)

            cell = box(minx, miny, maxx, maxy)

            if prepared_geom.contains(cell):
                areas_grid[r, c] = cell_row_area
            elif prepared_geom.intersects(cell):
                intersection = cell.intersection(geometry)
                if not intersection.is_empty:
                    areas_grid[r, c] = calculate_polygon_area_ha(intersection, geod=g)

    return areas_grid


def extract_raster_pixel_intersections(
    raster_path: str | Path,
    geometry: BaseGeometry,
) -> tuple[np.ndarray, Affine, tuple[int, int], float]:
    """Извлекает сетку площадей пересечения пикселей и метаданные из GeoTIFF для заданной геометрии."""
    with rasterio.open(raster_path) as src:
        transform = src.transform
        shape_hw = (src.height, src.width)
        grid = compute_pixel_area_grid(geometry, transform, shape_hw)
        tot_area = float(np.sum(grid))
        return grid, transform, shape_hw, tot_area


def find_raster_coverage(
    geometry: BaseGeometry,
    raster_paths: dict[str, str | Path],
    min_area_ha: float = 1e-4,
) -> list[dict[str, Any]]:
    """Определяет пространственное покрытие геометрии по нескольким растровым кандидатам."""
    coverage_items: list[dict[str, Any]] = []
    if geometry.is_empty:
        return coverage_items

    for site_id, rpath in raster_paths.items():
        p = Path(rpath)
        if not p.is_file():
            continue
        try:
            with rasterio.open(p) as src:
                bounds = src.bounds
                r_box = box(bounds.left, bounds.bottom, bounds.right, bounds.top)
                if not geometry.intersects(r_box):
                    continue
                grid = compute_pixel_area_grid(geometry, src.transform, (src.height, src.width))
                area_ha = float(np.sum(grid))
                if area_ha > min_area_ha:
                    coverage_items.append(
                        {
                            "site_id": site_id,
                            "raster_path": p,
                            "area_ha": area_ha,
                            "pixel_areas_ha": grid,
                            "transform": src.transform,
                            "shape_hw": (src.height, src.width),
                            "crs": src.crs,
                            "bounds": [bounds.left, bounds.bottom, bounds.right, bounds.top],
                        }
                    )
        except Exception:
            continue
    return coverage_items


def compute_coverage_stats(
    geometry: BaseGeometry,
    covered_area_ha: float,
    geod: Geod | None = None,
) -> tuple[float, float, float]:
    """Вычисляет запрошенную площадь, покрытую площадь и процент покрытия."""
    requested_area_ha = calculate_polygon_area_ha(geometry, geod=geod)
    if requested_area_ha <= 0.0:
        return 0.0, covered_area_ha, 100.0
    pct = (covered_area_ha / requested_area_ha) * 100.0
    return requested_area_ha, covered_area_ha, float(np.clip(pct, 0.0, 100.0))
