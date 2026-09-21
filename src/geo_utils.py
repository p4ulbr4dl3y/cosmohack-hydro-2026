"""Spatial and raster geospatial utility functions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import Resampling, reproject


def read_raster_with_meta(
    path: str | Path,
    band: int | list[int] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Read raster array and its profile/metadata.

    Args:
        path: Path to raster file.
        band: 1-based band index, list of band indices, or None to read all bands.

    Returns:
        (data, meta):
            data: np.ndarray (2D if single band, 3D if multiple bands).
            meta: rasterio profile dictionary.
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
    """Reproject and resample a raster band to match target grid geometry.

    Args:
        source_path: Path to source raster.
        band: 1-based band index.
        target_shape: (height, width) of output grid.
        target_transform: Affine transform of output grid.
        target_crs: CRS of output grid.
        resampling: Resampling algorithm (default bilinear).
        dst_nodata: Output nodata value.

    Returns:
        Resampled 2D float32 numpy array.
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
    """Clip binary or categorical 2D raster mask by AOI polygon geometry.

    Pixels strictly outside the AOI geometry are set to 0.

    Args:
        mask: 2D numpy array.
        aoi_geom: Shapely geometry or iterable of geometries.
        transform: Affine transform of the raster.
        crs: Optional CRS (for sanity or coordinate transforms if geometry needs reprojection).

    Returns:
        Clipped 2D numpy array with same dtype as input.
    """
    geoms = [aoi_geom] if not isinstance(aoi_geom, (list, tuple, gpd.GeoSeries)) else list(aoi_geom)
    inside_mask = geometry_mask(geoms, out_shape=mask.shape, transform=transform, invert=True)
    return np.where(inside_mask, mask, 0).astype(mask.dtype)
