"""Модульные и интеграционные тесты диспетчеризации МЧС и экспорта ESRI Shapefile."""

from __future__ import annotations

import io
import tempfile
import zipfile

import geopandas as gpd
from fastapi.testclient import TestClient

from src.service.app import app
from src.service.mchs_report import AOI_MUNICIPALITIES, build_mchs_dispatch, render_mchs_html

client = TestClient(app)

FLOOD_PAIR = "flood_2019_07_amur__blagoveshchensk"
BASELINE_PAIR = "baseline_2018_09_low__blagoveshchensk"


def test_mchs_dispatch_json_default() -> None:
    """Запрос по умолчанию возвращает структурированный JSON, соответствующий стандартным полевым донесениям МЧС."""
    resp = client.get(f"/api/v1/report/{FLOOD_PAIR}/mchs-dispatch")
    assert resp.status_code == 200
    data = resp.json()

    # Основные обязательные поля согласно спецификации
    assert "event_type" in data
    assert "affected_municipalities" in data
    assert "flooded_builtup_area_ha" in data
    assert "flooded_cropland_area_ha" in data
    assert "estimated_cutoff_transport_segments" in data
    assert "depth_risk_breakdown" in data

    # Проверки типов и содержимого
    assert isinstance(data["event_type"], str) and len(data["event_type"]) > 0
    assert isinstance(data["affected_municipalities"], list)
    assert len(data["affected_municipalities"]) > 0
    assert any("Благовещенск" in m for m in data["affected_municipalities"])

    assert isinstance(data["flooded_builtup_area_ha"], (int, float))
    assert data["flooded_builtup_area_ha"] >= 0.0
    assert isinstance(data["flooded_cropland_area_ha"], (int, float))
    assert data["flooded_cropland_area_ha"] >= 0.0

    assert isinstance(data["estimated_cutoff_transport_segments"], int)
    assert data["estimated_cutoff_transport_segments"] >= 1

    # Детализация транспортной инфраструктуры
    trans = data["transport_infrastructure"]
    assert trans["cutoff_segments_count"] == data["estimated_cutoff_transport_segments"]
    assert trans["estimated_cutoff_km"] > 0
    assert trans["risk_level"] in ("критический", "высокий", "умеренный", "штатный")

    # Разбивка по риску глубины
    depth = data["depth_risk_breakdown"]
    for tier in ("high_risk", "moderate_risk", "low_risk"):
        assert tier in depth
        item = depth[tier]
        assert "depth_range" in item
        assert "area_ha" in item
        assert "share_pct" in item
        assert "description" in item
        assert item["area_ha"] >= 0.0

    # Оперативная сводка и действия
    assert len(data["operational_summary"]) > 0
    assert isinstance(data["recommended_actions"], list)
    assert len(data["recommended_actions"]) >= 3


def test_mchs_dispatch_format_param_json() -> None:
    """Явный ?format=json возвращает корректный JSON."""
    resp = client.get(f"/api/v1/report/{FLOOD_PAIR}/mchs-dispatch?format=json")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    data = resp.json()
    assert data["pair_id"] == FLOOD_PAIR


def test_mchs_dispatch_html_view() -> None:
    """?format=html возвращает оперативную HTML-сводку для печати."""
    resp = client.get(f"/api/v1/report/{FLOOD_PAIR}/mchs-dispatch?format=html")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    html_text = resp.text

    assert "<!DOCTYPE html>" in html_text
    assert "МЧС РОССИИ" in html_text or "Министерство Российской Федерации" in html_text
    assert "ОПЕРАТИВНОЕ ДОНЕСЕНИЕ" in html_text
    assert FLOOD_PAIR in html_text
    assert "Затронутые муниципальные образования" in html_text
    assert "Depth Risk Breakdown" in html_text
    assert "window.print()" in html_text


def test_mchs_dispatch_baseline_pair() -> None:
    """Базовая пара сообщает о штатной обстановке с 0 отрезанных участков."""
    resp = client.get(f"/api/v1/report/{BASELINE_PAIR}/mchs-dispatch")
    assert resp.status_code == 200
    data = resp.json()

    assert data["estimated_cutoff_transport_segments"] == 0
    assert data["flooded_builtup_area_ha"] <= 1.0
    assert "межен" in data["event_type"].lower() or "Штатн" in data["status"]
    assert data["transport_infrastructure"]["cutoff_segments_count"] == 0


def test_mchs_dispatch_404_on_invalid_pair() -> None:
    """Некорректная пара возвращает HTTP 404."""
    resp = client.get("/api/v1/report/unknown_pair_xyz/mchs-dispatch")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_export_shapefile_endpoint_flood() -> None:
    """Эндпоинт ESRI Shapefile возвращает zip-архив с .shp, .shx, .dbf, .prj и стандартными атрибутами."""
    resp = client.get(f"/api/v1/export/{FLOOD_PAIR}/shapefile?layer=flood")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert f"{FLOOD_PAIR}_flood_shp.zip" in resp.headers["content-disposition"]

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()

    # Проверка наличия всех обязательных компонентов ESRI Shapefile
    assert any(n.endswith(".shp") for n in names), f"Missing .shp in {names}"
    assert any(n.endswith(".shx") for n in names), f"Missing .shx in {names}"
    assert any(n.endswith(".dbf") for n in names), f"Missing .dbf in {names}"
    assert any(n.endswith(".prj") for n in names), f"Missing .prj in {names}"

    with tempfile.TemporaryDirectory() as tmpdir:
        zf.extractall(tmpdir)
        gdf = gpd.read_file(tmpdir)

        # Проверка атрибутов согласно требованиям задания: (feature_id, class, area_ha, date_peak, crs)
        for attr in ("feature_id", "class", "area_ha", "date_peak", "crs"):
            assert attr in gdf.columns, f"Missing required attribute '{attr}' in Shapefile attributes {gdf.columns}"

        assert gdf["class"].iloc[0] == "flood"
        assert gdf["crs"].iloc[0] == "EPSG:4326"
        assert str(gdf.crs).lower() == "epsg:4326"
        assert len(gdf) > 0


def test_export_shapefile_layers() -> None:
    """Экспорт Shapefile работает для различных типов слоёв."""
    for layer in ("water_pre", "water_peak"):
        resp = client.get(f"/api/v1/export/{FLOOD_PAIR}/shapefile?layer={layer}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        names = zf.namelist()
        assert any(n.endswith(".shp") for n in names)
        assert any(n.endswith(".prj") for n in names)


def test_export_shapefile_invalid_layer() -> None:
    """Некорректный слой возвращает HTTP 400."""
    resp = client.get(f"/api/v1/export/{FLOOD_PAIR}/shapefile?layer=invalid_foo")
    assert resp.status_code == 400
    assert "Invalid layer" in resp.json()["detail"]


def test_export_shapefile_invalid_pair() -> None:
    """Некорректная пара возвращает HTTP 404."""
    resp = client.get("/api/v1/export/unknown_pair_xyz/shapefile")
    assert resp.status_code == 404


def test_export_shapefile_empty_baseline() -> None:
    """Пустой слой базовой линии экспортируется в корректный Shapefile со стандартными атрибутами без ошибок."""
    resp = client.get(f"/api/v1/export/{BASELINE_PAIR}/shapefile?layer=flood")
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert any(n.endswith(".shp") for n in names)
    assert any(n.endswith(".shx") for n in names)
    assert any(n.endswith(".dbf") for n in names)
    assert any(n.endswith(".prj") for n in names)

    with tempfile.TemporaryDirectory() as tmpdir:
        zf.extractall(tmpdir)
        gdf = gpd.read_file(tmpdir)
        for attr in ("feature_id", "class", "area_ha", "date_peak", "crs"):
            assert attr in gdf.columns
        assert str(gdf.crs).lower() == "epsg:4326"


def test_mchs_report_unit_helpers() -> None:
    """Модульный тест функций модуля mchs_report."""
    mock_report = {
        "pair_id": "test_pair",
        "aoi_id": "blagoveshchensk",
        "aoi_name": "Благовещенск — слияние Амура и Зеи",
        "event_id": "test_event",
        "event_name": "Тестовый паводок",
        "event_kind": "flood",
        "date_peak_sar": "2021-06-26",
        "date_pre_sar": "2021-05-15",
        "flood_ha": 500.0,
        "flood_km2": 5.0,
        "landcover": {
            "builtup_ha": 15.0,
            "cropland_ha": 120.0,
            "natural_vegetation_ha": 365.0,
            "mean_hand_m": 1.2,
        },
    }

    dispatch = build_mchs_dispatch(mock_report)
    assert dispatch["flooded_builtup_area_ha"] == 15.0
    assert dispatch["flooded_cropland_area_ha"] == 120.0
    assert dispatch["estimated_cutoff_transport_segments"] >= 1
    assert "Благовещенск" in AOI_MUNICIPALITIES["blagoveshchensk"][0]

    html_out = render_mchs_html(dispatch)
    assert "ОПЕРАТИВНОЕ ДОНЕСЕНИЕ" in html_out
    assert "500.00" in html_out
