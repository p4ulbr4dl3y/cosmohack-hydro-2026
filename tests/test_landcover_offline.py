"""Тесты стратификации землепользования и офлайн (встроенных) ресурсов фронтенда.

Покрывает замечания аудита 1.10: пашня раньше относилась к "natural_vegetation",
а дашборд зависел от размещённых на CDN Leaflet/Chart.js/шрифтов.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import shapely.geometry
from fastapi.testclient import TestClient
from rasterio.transform import from_origin

from src.service.app import app

client = TestClient(app)
STATIC_DIR = Path(__file__).resolve().parent.parent / "src" / "service" / "static"


def _make_pair_workspace(tmp_path, pair_id="test_pair"):
    """Сборка минимального data_dir с растром паводка, AUX и маской пашни."""
    data_dir = tmp_path / "data"
    rasters_dir = data_dir / "rasters" / "ev" / "aoi"
    rasters_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "vectors").mkdir(parents=True, exist_ok=True)

    transform = from_origin(500000.0, 5600000.0, 10.0, 10.0)
    shape = (20, 20)
    crs = "EPSG:32652"

    # Простой полигон AOI, содержащий растр
    minx, miny = transform * (0, shape[0])
    maxx, maxy = transform * (shape[1], 0)
    geom = shapely.geometry.box(minx, miny, maxx, maxy)
    gdf = gpd.GeoDataFrame({"aoi_id": ["aoi"]}, geometry=[geom], crs=crs)
    gdf_4326 = gdf.to_crs("EPSG:4326")
    gdf_4326.to_file(data_dir / "vectors" / "aoi.geojson", driver="GeoJSON")

    # AUX: 6 полос [slope, hand, occurrence, seasonality, max_extent, builtup]
    aux = np.zeros((6, shape[0], shape[1]), dtype=np.float32)
    aux[1] = 5.0  # hand
    aux[2] = 90.0  # occurrence -> постоянная вода
    aux[4] = 1.0  # max_extent
    aux[5, :10, :] = 1.0  # builtup - верхняя половина
    with rasterio.open(
        rasters_dir / "AUX_terrain_gsw.tif",
        "w",
        driver="GTiff",
        height=shape[0],
        width=shape[1],
        count=6,
        dtype=np.float32,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(aux)

    # Пашня: правая половина
    cropland = np.zeros(shape, dtype=np.uint8)
    cropland[:, 10:] = 1
    with rasterio.open(
        rasters_dir / "CROPLAND_worldcover.tif",
        "w",
        driver="GTiff",
        height=shape[0],
        width=shape[1],
        count=1,
        dtype=np.uint8,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(cropland, 1)

    # Растр паводка: затоплен весь AOI -> 20*20 px, каждый 0.01 ha
    preds = tmp_path / "predictions"
    preds.mkdir(parents=True, exist_ok=True)
    flood = np.ones(shape, dtype=np.uint8)
    with rasterio.open(
        preds / f"{pair_id}_flood.tif",
        "w",
        driver="GTiff",
        height=shape[0],
        width=shape[1],
        count=1,
        dtype=np.uint8,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(flood, 1)

    # pairs.csv + submission.csv
    (data_dir / "pairs.csv").write_text(
        "pair_id,aoi_id,aoi_name,event_id,event_name,event_kind,year,sensor_sar,sensor_optical,"
        "date_pre_sar,date_peak_sar,date_pre_opt,date_peak_opt,orbit_pass,relative_orbit,aoi_km2,"
        "rasters_dir,reference_mask\n"
        f"{pair_id},aoi,AOI,ev,Event,flood,2021,sentinel1,,2021-05-14,2021-07-01,,,DESCENDING,105.0,"
        "4.0,rasters/ev/aoi,reference_masks/reference.tif\n",
        encoding="utf-8",
    )
    sub = tmp_path / "submission.csv"
    sub.write_text(f"pair_id,flood_ha,water_pre_ha,water_peak_ha\n{pair_id},4.0,1.0,5.0\n", encoding="utf-8")

    return data_dir, preds, sub, shape


def test_cropland_is_separated_from_natural_vegetation(tmp_path):
    from src.service.data_loader import DataLoader

    pair_id = "test_pair"
    data_dir, preds, sub, shape = _make_pair_workspace(tmp_path, pair_id)
    loader = DataLoader(
        data_dir=data_dir,
        predictions_dir=preds,
        submission_csv=sub,
        cache_dir=tmp_path / "cache",
    )
    report = loader.get_report(pair_id)
    assert report is not None
    lc = report["landcover"]

    # Всего 400 px, каждый 0.01 ha. Builtup = верхняя половина (200 px = 2.0 ha).
    # Пашня = правая половина (200 px), но builtup выигрывает там, где они пересекаются.
    assert lc["builtup_ha"] == 2.0
    assert lc["cropland_ha"] == 1.0  # правая половина ниже верха -> 100 px
    assert lc["natural_vegetation_ha"] == 1.0  # оставшаяся левая нижняя четверть
    assert abs(lc["builtup_ha"] + lc["cropland_ha"] + lc["natural_vegetation_ha"] - 4.0) < 1e-6


def test_cropland_missing_is_graceful(tmp_path):
    from src.service.data_loader import DataLoader

    pair_id = "test_pair"
    data_dir, preds, sub, shape = _make_pair_workspace(tmp_path, pair_id)
    # Удаление маски пашни -> пашня должна стать 0, а остаток поглощается естественной растительностью
    (data_dir / "rasters" / "ev" / "aoi" / "CROPLAND_worldcover.tif").unlink()

    loader = DataLoader(
        data_dir=data_dir,
        predictions_dir=preds,
        submission_csv=sub,
        cache_dir=tmp_path / "cache",
    )
    lc = loader.get_report(pair_id)["landcover"]
    assert lc["cropland_ha"] == 0.0
    assert lc["natural_vegetation_ha"] == 2.0


def test_dashboard_assets_are_vendored_offline():
    """index.html не должен ссылаться на внешние CDN; встроенные файлы должны существовать."""
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    for cdn in ("unpkg.com", "cdn.jsdelivr.net", "cdnjs.cloudflare.com", "fonts.googleapis.com", "fonts.gstatic.com"):
        assert cdn not in html, f"index.html still references external CDN: {cdn}"

    for asset in (
        "vendor/leaflet/leaflet.js",
        "vendor/leaflet/leaflet.css",
        "vendor/chart.umd.js",
        "vendor/fontawesome/css/all.min.css",
        "vendor/fontawesome/webfonts/fa-solid-900.woff2",
        "vendor/fonts/fonts.css",
    ):
        assert (STATIC_DIR / asset).exists(), f"missing vendored asset: {asset}"

    # Встроенный CSS шрифтов не должен обращаться обратно к gstatic
    fonts_css = (STATIC_DIR / "vendor/fonts/fonts.css").read_text(encoding="utf-8")
    assert "gstatic" not in fonts_css


def test_static_vendor_is_served():
    resp = client.get("/static/vendor/leaflet/leaflet.js")
    assert resp.status_code == 200
    assert "Leaflet" in resp.text
