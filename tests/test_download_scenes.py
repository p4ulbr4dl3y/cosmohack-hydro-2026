"""Tests for the Sentinel-1/2 scene downloader (audit finding 1.1).

The downloader reads assets from Microsoft Planetary Computer, whose asset keys
are lowercase for S1 ("vv"/"vh") and uppercase for S2 ("B03"). A historical bug
used ``b_name.lower()`` for S2, so the lookup never matched and every band was
written as nodata.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from download_all_scenes import download_s1_raster, download_s2_raster  # noqa: E402


class _FakeAsset:
    def __init__(self, href: str):
        self.href = href


class _FakeItem:
    """Minimal STAC item stub carrying asset hrefs."""

    def __init__(self, assets: dict[str, str]):
        self.assets = {k: _FakeAsset(v) for k, v in assets.items()}


@pytest.fixture
def s2_bands(tmp_path):
    """Write six single-band S2 rasters (reflectance * 10000)."""
    transform = from_origin(500000.0, 5600000.0, 10.0, 10.0)
    shape = (12, 12)
    hrefs = {}
    for name in ("B02", "B03", "B04", "B08", "B11", "B12"):
        p = tmp_path / f"{name}.tif"
        data = np.full(shape, 1500, dtype=np.uint16)
        with rasterio.open(
            p,
            "w",
            driver="GTiff",
            height=shape[0],
            width=shape[1],
            count=1,
            dtype=np.uint16,
            crs="EPSG:32652",
            transform=transform,
        ) as dst:
            dst.write(data, 1)
        hrefs[name] = str(p)
    return hrefs, transform, shape


def test_download_s2_uses_uppercase_asset_keys(tmp_path, s2_bands):
    """Uppercase PC asset keys must be resolved (regression: b_name.lower())."""
    hrefs, transform, shape = s2_bands
    # Deliberately only provide uppercase keys, as Planetary Computer does.
    item = _FakeItem(hrefs)
    out = tmp_path / "SENTINEL2_peak.tif"
    bounds = (499900.0, 5599880.0, 500020.0, 5600000.0)

    download_s2_raster(None, [item], bounds, shape, transform, str(out))

    assert out.exists()
    with rasterio.open(out) as src:
        assert src.count == 8
        mndwi = src.read(6)
    valid = mndwi[mndwi != -999.0]
    assert valid.size > 0, "optical bands must not be entirely nodata"
    # Equal reflectance in all bands -> MNDWI == 0
    assert np.allclose(valid, 0.0, atol=1e-4)


def test_download_s2_marks_cloudy_scl_pixels_as_nodata(tmp_path, s2_bands):
    """SCL cloud classes must invalidate the corresponding index pixels."""
    hrefs, transform, shape = s2_bands

    # SCL raster: left half clear (class 4 = vegetation), right half cloud (class 9)
    scl_path = tmp_path / "SCL.tif"
    scl = np.full(shape, 4, dtype=np.uint8)
    scl[:, shape[1] // 2 :] = 9
    with rasterio.open(
        scl_path,
        "w",
        driver="GTiff",
        height=shape[0],
        width=shape[1],
        count=1,
        dtype=np.uint8,
        crs="EPSG:32652",
        transform=transform,
    ) as dst:
        dst.write(scl, 1)

    item = _FakeItem({**hrefs, "SCL": str(scl_path)})
    out = tmp_path / "SENTINEL2_scl.tif"
    bounds = (499900.0, 5599880.0, 500020.0, 5600000.0)
    download_s2_raster(None, [item], bounds, shape, transform, str(out))

    with rasterio.open(out) as src:
        mndwi = src.read(6)
    assert np.all(mndwi[:, : shape[1] // 2] != -999.0)
    assert np.all(mndwi[:, shape[1] // 2 :] == -999.0)


def test_download_s1_uses_lowercase_asset_keys(tmp_path):
    """S1 assets on Planetary Computer are lowercase ('vv'/'vh')."""
    transform = from_origin(500000.0, 5600000.0, 10.0, 10.0)
    shape = (8, 8)
    vv = np.full(shape, 1000.0, dtype=np.float32)
    vh = np.full(shape, 100.0, dtype=np.float32)
    paths = {}
    for name, arr in (("vv", vv), ("vh", vh)):
        p = tmp_path / f"{name}.tif"
        with rasterio.open(
            p,
            "w",
            driver="GTiff",
            height=shape[0],
            width=shape[1],
            count=1,
            dtype=np.float32,
            crs="EPSG:32652",
            transform=transform,
        ) as dst:
            dst.write(arr, 1)
        paths[name] = str(p)

    item = _FakeItem(paths)
    out = tmp_path / "S1_peak.tif"
    bounds = (500000.0, 5599920.0, 500080.0, 5600000.0)
    download_s1_raster(None, [item], bounds, shape, transform, str(out))

    assert out.exists()
    with rasterio.open(out) as src:
        assert src.count == 3
        vv_db = src.read(1)
    assert np.allclose(vv_db, 30.0, atol=1e-3)  # 10*log10(1000) = 30 dB
