"""Интеграционные тесты сервиса HydroWatch Amur на FastAPI."""

from pathlib import Path

import pandas as pd
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.service.app import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_pairs_endpoint():
    resp = client.get("/api/v1/pairs")
    assert resp.status_code == 200
    pairs = resp.json()
    assert isinstance(pairs, list)
    assert len(pairs) == 11

    # Проверка полей первой пары
    first = pairs[0]
    required_keys = [
        "pair_id",
        "aoi_id",
        "aoi_name",
        "event_id",
        "event_name",
        "date_pre_sar",
        "date_peak_sar",
        "aoi_km2",
        "aoi_ha",
        "bounds_4326",
        "center_4326",
    ]
    for key in required_keys:
        assert key in first, f"Missing key '{key}' in pair metadata"


def test_report_endpoint():
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    resp = client.get(f"/api/v1/report/{pair_id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["pair_id"] == pair_id
    assert "flood_ha" in data
    assert "flood_km2" in data
    assert "water_pre_ha" in data
    assert "water_peak_ha" in data
    assert "receded_ha" in data
    assert "water_gain_ha" in data
    assert "water_gain_pct" in data
    assert "share_of_aoi" in data

    # Проверка, что значения совпадают с прогнозами из submission.csv
    sub = pd.read_csv(Path("submission.csv"))
    row = sub[sub["pair_id"] == "flood_2019_07_amur__blagoveshchensk"].iloc[0]
    assert data["flood_ha"] == float(row["flood_ha"])
    assert data["water_pre_ha"] == float(row["water_pre_ha"])
    assert data["water_peak_ha"] == float(row["water_peak_ha"])

    # Проверка структуры землепользования
    assert "landcover" in data
    lc = data["landcover"]
    assert "builtup_ha" in lc
    assert "builtup_pct" in lc
    assert "cropland_ha" in lc
    assert "cropland_pct" in lc
    assert "natural_vegetation_ha" in lc
    assert "natural_vegetation_pct" in lc
    assert "mean_hand_m" in lc

    # Проверка структуры depth_statistics
    assert "depth_statistics" in data
    ds = data["depth_statistics"]
    assert "low_risk_ha" in ds
    assert "medium_risk_ha" in ds
    assert "high_risk_ha" in ds
    assert "low_risk_pct" in ds
    assert "medium_risk_pct" in ds
    assert "high_risk_pct" in ds
    assert "mchs_traversability" in ds

    # Проверка структуры gauge_status
    assert "gauge_status" in data
    assert data["gauge_status"] is not None
    gs = data["gauge_status"]
    assert gs["station_name"] == "Благовещенск"
    assert gs["npu_cm"] == 600
    assert gs["oya_cm"] == 800
    assert gs["observed_level_cm"] == 745
    assert gs["exceeds_npu"] is True
    assert gs["exceeds_oya"] is False
    assert gs["stage_risk"] == "warning_nya"


def test_report_csv_endpoint():
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    resp = client.get(f"/api/v1/report/{pair_id}/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    text = resp.text
    assert "pair_id,aoi_id,aoi_name" in text
    assert pair_id in text


def test_geojson_endpoint():
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    for layer in ["flood", "water_pre", "water_peak"]:
        resp = client.get(f"/api/v1/geojson/{pair_id}?layer={layer}")
        assert resp.status_code == 200
        gj = resp.json()
        assert gj.get("type") == "FeatureCollection"
        assert "features" in gj

    # Проверка свойств GeoJSON для слоя паводка из прогнозов
    flood_resp = client.get(f"/api/v1/geojson/{pair_id}?layer=flood")
    flood_gj = flood_resp.json()
    assert len(flood_gj["features"]) > 0
    props = flood_gj["features"][0]["properties"]
    for required_prop in ["area_ha", "pair_id", "layer", "aoi_name", "event_name"]:
        assert required_prop in props, f"Missing {required_prop} in GeoJSON properties"
    assert props["pair_id"] == pair_id
    assert props["layer"] == "flood"
    assert props["area_ha"] > 0


def test_predict_endpoint_by_pair_id():
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    resp = client.post("/api/v1/predict", json={"pair_id": pair_id})
    assert resp.status_code == 200
    res = resp.json()
    assert res["status"] == "success"
    assert res["pair_id"] == pair_id
    assert "summary" in res
    assert "geojson" in res
    assert res["summary"]["flood_ha"] > 0


def test_predict_endpoint_by_bounds():
    # Границы вблизи Благовещенска
    bounds = [127.21, 50.12, 127.85, 50.45]
    resp = client.post("/api/v1/predict", json={"bounds": bounds})
    assert resp.status_code == 200
    res = resp.json()
    assert res["status"] == "success"
    assert "summary" in res
    assert "geojson" in res


def test_predict_endpoint_invalid_date_format():
    # Валидация выполняется до обращения к кэшу, поэтому растровые данные не требуются
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    resp = client.post("/api/v1/predict", json={"pair_id": pair_id, "date_pre": "2019/06/13"})
    assert resp.status_code == 400
    assert "Некорректная дата" in resp.json()["detail"]


def test_predict_endpoint_date_out_of_range():
    # 2019-06-13 + более 30 дней -> отклоняется относительно даты снимка
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    resp = client.post("/api/v1/predict", json={"pair_id": pair_id, "date_pre": "2019-01-01"})
    assert resp.status_code == 400
    assert "Некорректная дата" in resp.json()["detail"]


def test_predict_endpoint_valid_dates_echoed():
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    resp = client.post(
        "/api/v1/predict",
        json={"pair_id": pair_id, "date_pre": "2019-06-13", "date_peak": "2019-07-25"},
    )
    assert resp.status_code == 200
    res = resp.json()
    assert res["status"] == "success"
    assert res["scene_dates"] == {"date_pre": "2019-06-13", "date_peak": "2019-07-25"}
    assert res["requested_dates"] == {"date_pre": "2019-06-13", "date_peak": "2019-07-25"}


def test_predict_endpoint_arbitrary_bounds():
    # Границы вне зоны покрытия (например, Гвинейский залив) корректно отклоняются с кодом 400
    bounds_outside = [10.0, 10.0, 11.0, 11.0]
    resp_outside = client.post("/api/v1/predict", json={"bounds": bounds_outside})
    assert resp_outside.status_code == 400
    assert "не пересекают" in resp_outside.json()["detail"]

    # Корректные перекрывающиеся границы внутри AOI Благовещенска
    bounds_inside = [127.3, 50.2, 127.6, 50.4]
    resp_inside = client.post("/api/v1/predict", json={"bounds": bounds_inside})
    assert resp_inside.status_code == 200
    res = resp_inside.json()
    assert res["status"] == "success"
    assert "flood_clipped" in res["geojson"]["name"]


def test_static_index_html():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "HydroWatch" in resp.text
    assert "Leaflet" in resp.text or "leaflet.js" in resp.text


def test_404_not_found_endpoints():
    assert client.get("/api/v1/report/non_existent_pair").status_code == 404
    assert client.get("/api/v1/report/non_existent_pair/csv").status_code == 404
    assert client.get("/api/v1/geojson/non_existent_pair").status_code == 404


def test_predict_endpoint_errors(monkeypatch):
    # Проверка обработки ValueError (400)
    resp = client.post("/api/v1/predict", json={"pair_id": "non_existent_pair"})
    assert resp.status_code == 400

    # Проверка обработки необработанного Exception (500)
    def mock_predict(*args, **kwargs):
        raise RuntimeError("Mock failure")

    monkeypatch.setattr("src.service.app.data_loader.predict_spatial_temporal", mock_predict)
    resp500 = client.post("/api/v1/predict", json={"pair_id": "flood_2019_07_amur__blagoveshchensk"})
    assert resp500.status_code == 500


def test_shapefile_endpoint():
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    resp = client.get(f"/api/v1/shapefile/{pair_id}?layer=flood")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert len(resp.content) > 0
    assert client.get("/api/v1/shapefile/non_existent_pair").status_code == 404


def test_geojson_invalid_layer():
    resp = client.get("/api/v1/geojson/flood_2019_07_amur__blagoveshchensk?layer=invalid_layer")
    assert resp.status_code == 400
    assert "Некорректный слой" in resp.json()["detail"]


def test_shapefile_invalid_layer():
    resp = client.get("/api/v1/shapefile/flood_2019_07_amur__blagoveshchensk?layer=invalid_layer")
    assert resp.status_code == 400
    assert "Некорректный слой" in resp.json()["detail"]


def test_geotiff_endpoint():
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    # Успешный случай
    resp = client.get(f"/api/v1/geotiff/{pair_id}?layer=flood")
    assert resp.status_code == 200
    assert "image/tiff" in resp.headers["content-type"]
    assert len(resp.content) > 0

    # Некорректный слой
    resp_inv = client.get(f"/api/v1/geotiff/{pair_id}?layer=invalid_layer")
    assert resp_inv.status_code == 400
    assert "Некорректный слой" in resp_inv.json()["detail"]

    # 404 не найдено
    resp_404 = client.get("/api/v1/geotiff/non_existent_pair?layer=flood")
    assert resp_404.status_code == 404
    assert "не найден" in resp_404.json()["detail"]


def test_predict_endpoint_unparseable_scene_date(monkeypatch):
    from src.service.app import data_loader

    orig_meta = data_loader.get_pair_meta("flood_2019_07_amur__blagoveshchensk")
    assert orig_meta is not None
    tampered_meta = dict(orig_meta)
    tampered_meta["date_pre_sar"] = "invalid-scene-date"

    monkeypatch.setattr(
        data_loader,
        "get_pair_meta",
        lambda pid: tampered_meta if pid == "flood_2019_07_amur__blagoveshchensk" else orig_meta,
    )
    resp = client.post(
        "/api/v1/predict",
        json={"pair_id": "flood_2019_07_amur__blagoveshchensk", "date_pre": "2019-06-13"},
    )
    assert resp.status_code == 200


def test_missing_asset_returns_404_not_index_html():
    # Устаревший index.html может ссылаться на старый хешированный чанк. Отдача оболочки SPA
    # с типом text/html на запрос .js нарушает импорт модуля и приводит к пустой странице,
    # поэтому отсутствующие ресурсы должны возвращать 404.
    for path in (
        "/assets/index-BVnVLfPl.js",
        "/assets/does-not-exist.css",
        "/icons/missing.png",
    ):
        resp = client.get(path)
        assert resp.status_code == 404, path
        assert "text/html" not in resp.headers["content-type"], path


def test_spa_fallback_serves_index_without_cache():
    for path in ("/dashboard", "/report/some-pair", "/deeply/nested/route"):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert "text/html" in resp.headers["content-type"], path
        assert "HydroWatch" in resp.text, path
    assert "no-cache" in client.get("/").headers["cache-control"]


def test_static_index_html_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr("src.service.app.STATIC_DIR", tmp_path / "nonexistent_static")
    resp = client.get("/")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "index.html не найден"


def test_prediction_task_status_lifecycle(monkeypatch):
    from src.service.app import tasks_db

    # 404 для несуществующей задачи
    resp = client.get("/api/v1/predict/status/nonexistent_task_123")
    assert resp.status_code == 404
    assert "не найдена" in resp.json()["detail"]

    # Отправка задачи с task_id
    task_id = "test_task_success_456"
    resp = client.post(
        "/api/v1/predict",
        json={"pair_id": "flood_2019_07_amur__blagoveshchensk", "task_id": task_id},
    )
    assert resp.status_code == 200
    assert task_id in tasks_db

    # Запрос статуса
    status_resp = client.get(f"/api/v1/predict/status/{task_id}")
    assert status_resp.status_code == 200
    task_data = status_resp.json()
    assert task_data["task_id"] == task_id
    assert task_data["status"] == "completed"
    assert task_data["progress"] == 1.0
    assert task_data["result"] is not None
    assert task_data["error"] is None

    # Проверка сбоя по ValueError
    fail_task_id = "test_task_fail_val_error"
    fail_resp = client.post(
        "/api/v1/predict",
        json={"pair_id": "non_existent_pair", "task_id": fail_task_id},
    )
    assert fail_resp.status_code == 400
    fail_status = client.get(f"/api/v1/predict/status/{fail_task_id}")
    assert fail_status.status_code == 200
    assert fail_status.json()["status"] == "failed"
    assert fail_status.json()["error"] is not None

    # Проверка сбоя с ошибкой времени выполнения 500
    def mock_predict(*args, **kwargs):
        raise RuntimeError("Async crash")

    monkeypatch.setattr("src.service.app.data_loader.predict_spatial_temporal", mock_predict)
    crash_task_id = "test_task_fail_crash"
    crash_resp = client.post(
        "/api/v1/predict",
        json={"pair_id": "flood_2019_07_amur__blagoveshchensk", "task_id": crash_task_id},
    )
    assert crash_resp.status_code == 500
    crash_status = client.get(f"/api/v1/predict/status/{crash_task_id}")
    assert crash_status.status_code == 200
    assert crash_status.json()["status"] == "failed"
    assert "Async crash" in crash_status.json()["error"]


def test_schemas_direct():
    from src.service.schemas import (
        LandcoverDistribution,
        PairInfo,
        PairsListResponse,
        PredictionTaskResponse,
        PredictMetadata,
        PredictRequest,
        PredictResponse,
        PredictSummary,
        ReportResponse,
    )

    lc = LandcoverDistribution(builtup_ha=10.0, builtup_pct=5.0)
    assert lc.builtup_ha == 10.0

    pair = PairInfo(
        pair_id="p1",
        aoi_id="a1",
        aoi_name="AOI 1",
        event_id="e1",
        event_name="Event 1",
        event_kind="flood",
        year=2021,
        aoi_km2=100.0,
        aoi_ha=10000.0,
        bounds_4326=[120.0, 50.0, 121.0, 51.0],
        center_4326=[50.5, 120.5],
    )
    pairs_list = PairsListResponse([pair])
    assert len(pairs_list.root) == 1

    report = ReportResponse(
        pair_id="p1",
        aoi_id="a1",
        aoi_name="AOI 1",
        event_id="e1",
        event_name="Event 1",
        event_kind="flood",
        year=2021,
        bounds_4326=[120.0, 50.0, 121.0, 51.0],
        center_4326=[50.5, 120.5],
        aoi_ha=10000.0,
        aoi_km2=100.0,
        flood_ha=50.0,
        flood_km2=0.5,
        water_pre_ha=200.0,
        water_pre_km2=2.0,
        water_peak_ha=250.0,
        water_peak_km2=2.5,
        permanent_ha=150.0,
        receded_ha=0.0,
        water_gain_ha=50.0,
        water_gain_pct=25.0,
        share_of_aoi=0.005,
        flood_share_pct=0.5,
        landcover=lc,
    )
    assert report.flood_ha == 50.0

    pred_res = PredictResponse(
        pair_id="p1",
        summary=PredictSummary(
            flood_ha=50.0,
            flood_km2=0.5,
            water_pre_ha=200.0,
            water_peak_ha=250.0,
            water_gain_ha=50.0,
            water_gain_pct=25.0,
        ),
        metadata=PredictMetadata(
            aoi_id="a1",
            aoi_name="AOI 1",
            event_id="e1",
            event_name="Event 1",
            event_kind="flood",
            year=2021,
            bounds_4326=[120.0, 50.0, 121.0, 51.0],
            center_4326=[50.5, 120.5],
        ),
    )
    task = PredictionTaskResponse(task_id="t1", status="completed", progress=1.0, result=pred_res)
    assert task.status == "completed"

    req = PredictRequest(pair_id="p1", task_id="t1")
    assert req.task_id == "t1"


def test_data_loader_cache_resolution(tmp_path, monkeypatch):

    from src.service.data_loader import DataLoader

    # Проверка конфигурации через переменную окружения
    custom_cache = tmp_path / "env_cache"
    monkeypatch.setenv("HYDROWATCH_CACHE_DIR", str(custom_cache))
    loader = DataLoader(cache_dir=None)
    assert loader.cache_dir == custom_cache
    assert custom_cache.exists()

    # Явное переопределение cache_dir имеет приоритет над переменной окружения
    override_cache = tmp_path / "explicit_cache"
    loader_override = DataLoader(cache_dir=override_cache)
    assert loader_override.cache_dir == override_cache
    assert override_cache.exists()


def test_openapi_events_and_aoi():
    resp = client.get("/api/v1/events")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

    aoi_resp = client.get("/api/v1/aoi")
    assert aoi_resp.status_code == 200
    assert aoi_resp.json().get("type") == "FeatureCollection"


def test_openapi_analyze_and_layers():
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    analyze_resp = client.post("/api/v1/analyze", json={"pair_id": pair_id})
    assert analyze_resp.status_code == 200
    assert analyze_resp.json()["status"] == "success"

    layer_resp = client.get(f"/api/v1/layers/{pair_id}/geojson")
    assert layer_resp.status_code == 200
    assert layer_resp.json().get("type") == "FeatureCollection"


def test_openapi_export_endpoints():
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    vec_resp = client.get(f"/api/v1/export/{pair_id}/vectors?format=geojson")
    assert vec_resp.status_code == 200

    vec_shp = client.get(f"/api/v1/export/{pair_id}/vectors?format=shp")
    assert vec_shp.status_code == 200
    assert vec_shp.headers["content-type"] == "application/zip"

    rep_json = client.get(f"/api/v1/export/{pair_id}/report?format=json")
    assert rep_json.status_code == 200

    rep_csv = client.get(f"/api/v1/export/{pair_id}/report?format=csv")
    assert rep_csv.status_code == 200
    assert "text/csv" in rep_csv.headers["content-type"]


def test_openapi_ablation_and_recompute():
    ablation_resp = client.get("/api/v1/ablation")
    assert ablation_resp.status_code == 200

    recompute_resp = client.post("/api/v1/recompute")
    assert recompute_resp.status_code == 200
    body = recompute_resp.json()
    assert body["status"] == "success"
    assert len(body["pairs"]) == 11
    assert body["processing_time_sec"] > 0.0
    assert body["memory_peak_gb"] >= 0.0
    assert body["timestamp_utc"].endswith(" UTC")


def test_recompute_single_pair_measures_real_time_and_invalidates_cache():
    from src.service.app import data_loader

    pair_id = "flood_2019_07_amur__belogorsk"
    first = client.post("/api/v1/recompute", json={"pair_id": pair_id})
    second = client.post("/api/v1/recompute", json={"pair_id": pair_id})
    assert first.status_code == 200
    assert second.status_code == 200

    first_body = first.json()
    second_body = second.json()
    assert first_body["pairs"] == [pair_id]
    assert second_body["pairs"] == [pair_id]

    # Время измеряется, а не задаётся жёстко, и различается между идентичными вызовами
    assert first_body["processing_time_sec"] != 12.4
    assert second_body["processing_time_sec"] != 12.4
    assert first_body["processing_time_sec"] > 0.0
    assert second_body["processing_time_sec"] > 0.0
    assert first_body["timestamp_utc"] != "2026-09-21 14:32:00 UTC"

    # Пересобранный отчёт снова отдаётся и совпадает с прогнозом на диске
    report = client.get(f"/api/v1/report/{pair_id}")
    assert report.status_code == 200
    sub = pd.read_csv(Path("submission.csv"))
    row = sub[sub["pair_id"] == pair_id].iloc[0]
    assert report.json()["flood_ha"] == float(row["flood_ha"])

    # Кэши были инвалидированы и пересобраны на диске
    assert (data_loader.cache_dir / f"report_{pair_id}.json").exists()
    assert pair_id in data_loader._reports_cache


def test_recompute_removes_stale_disk_caches(monkeypatch):
    from src.service.app import data_loader

    pair_id = "flood_2019_07_amur__belogorsk"
    stale_report = data_loader.cache_dir / f"report_{pair_id}.json"
    stale_layer = data_loader.cache_dir / f"{pair_id}_flood.geojson"
    stale_report.parent.mkdir(parents=True, exist_ok=True)
    stale_report.write_text('{"flood_ha": -1}', encoding="utf-8")
    stale_layer.write_text('{"type": "FeatureCollection", "stale": true}', encoding="utf-8")
    data_loader._reports_cache[pair_id] = {"flood_ha": -1}

    resp = client.post("/api/v1/recompute", json={"pair_id": pair_id})
    assert resp.status_code == 200

    assert not stale_layer.exists()
    assert data_loader._reports_cache[pair_id]["flood_ha"] != -1


def test_recompute_unknown_pair_returns_404():
    resp = client.post("/api/v1/recompute", json={"pair_id": "does_not_exist"})
    assert resp.status_code == 404
    assert "does_not_exist" in resp.json()["detail"]


def test_recompute_missing_data_returns_real_500(monkeypatch):
    from src.service.app import data_loader

    def mock_get_report(pair_id, query_geom=None):
        raise RuntimeError("raster missing on disk")

    monkeypatch.setattr(data_loader, "get_report", mock_get_report)
    resp = client.post("/api/v1/recompute", json={"pair_id": "flood_2019_07_amur__belogorsk"})
    assert resp.status_code == 500
    assert "raster missing on disk" in resp.json()["detail"]


def test_dynamic_sar_analytics_not_hardcoded(synthetic_s1_scene):
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    resp = client.get(f"/api/v1/sar-analytics/{pair_id}")
    assert resp.status_code == 200
    sar = resp.json()

    # Проверяем, что константы больше не зашиты в код
    assert sar["mean_vv_db"] != -16.2
    assert sar["mean_vh_db"] != -22.8
    assert sar["radar_contrast_db"] != 9.4
    assert sar["double_bounce_fraction"] != 0.038

    # Проверяем физическую корректность
    assert -30.0 < sar["mean_vv_db"] < 0.0
    assert -40.0 < sar["mean_vh_db"] < 0.0
    assert sar["water_fraction"] > 0.0
    assert sar["water_area_ha"] > 0.0
    assert sar["cloud_penetration_verified"] is True

    # Проверяем, что отчет также содержит динамическую аналитику SAR
    rep_resp = client.get(f"/api/v1/report/{pair_id}")
    assert rep_resp.status_code == 200
    rep_sar = rep_resp.json().get("sar_analytics")
    assert rep_sar is not None
    assert rep_sar["mean_vv_db"] == sar["mean_vv_db"]
    assert rep_sar["mean_vh_db"] == sar["mean_vh_db"]


def test_sar_analytics_missing_raster_fallback(caplog):
    from src.service.app import data_loader

    with caplog.at_level("WARNING"):
        res = data_loader.compute_sar_analytics(
            pair_id="missing_pair_test",
            aoi_ha=500.0,
            water_ha=25.0,
            force_recompute=True,
        )
    assert res["mean_vv_db"] == 0.0
    assert res["mean_vh_db"] == 0.0
    assert res["mean_vh_vv_ratio"] == 0.0
    assert res["radar_contrast_db"] == 0.0
    assert res["double_bounce_fraction"] == 0.0
    assert res["water_fraction"] == 0.05
    assert res["water_area_ha"] == 25.0
    assert res["cloud_penetration_verified"] is True
    assert any("Растр S1 отсутствует" in record.message for record in caplog.records)


def test_root_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "hydrowatch-amur"
    assert data["pairs_count"] == 11


def test_mchs_dispatch_endpoints():
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    # JSON
    resp_json = client.get(f"/api/v1/report/{pair_id}/mchs-dispatch")
    assert resp_json.status_code == 200
    data = resp_json.json()
    assert data["pair_id"] == pair_id
    assert "station_name" in data or "flooded_total_ha" in data

    # HTML
    resp_html = client.get(f"/api/v1/report/{pair_id}/mchs-dispatch?format=html")
    assert resp_html.status_code == 200
    assert "text/html" in resp_html.headers["content-type"]
    assert "Благовещенск" in resp_html.text or "html" in resp_html.text.lower()

    # 404
    resp_404 = client.get("/api/v1/report/nonexistent_pair_999/mchs-dispatch")
    assert resp_404.status_code == 404


def test_aoi_endpoint():
    resp = client.get("/api/v1/aoi")
    assert resp.status_code == 200
    assert resp.json().get("type") == "FeatureCollection"


def test_aoi_endpoint_fallback_and_404(monkeypatch, tmp_path):
    import src.service.app as app_mod

    fake_base = tmp_path / "app_dir"
    fake_base.mkdir()
    fake_data_vectors = tmp_path / "data" / "vectors"
    fake_data_vectors.mkdir(parents=True)
    fake_aoi = fake_data_vectors / "aoi.geojson"
    fake_aoi.write_text('{"type": "FeatureCollection", "features": []}', encoding="utf-8")

    monkeypatch.setattr(app_mod, "BASE_DIR", fake_base)

    # Строка 424: запасной вариант
    resp = client.get("/api/v1/aoi")
    assert resp.status_code == 200
    assert resp.json()["type"] == "FeatureCollection"

    # Строка 426: 404
    fake_aoi.unlink()
    resp = client.get("/api/v1/aoi")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "aoi.geojson не найден"


def test_vector_layer_endpoint():
    resp = client.get("/api/v1/vectors/amur_oblast")
    assert resp.status_code == 200
    assert "features" in resp.json() or "type" in resp.json()

    resp_404 = client.get("/api/v1/vectors/nonexistent_layer")
    assert resp_404.status_code == 404
    assert "Векторный слой 'nonexistent_layer' не найден" in resp_404.json()["detail"]


def test_vector_layer_fallback(monkeypatch, tmp_path):
    import src.service.app as app_mod

    fake_base = tmp_path / "app_dir"
    fake_base.mkdir()
    fake_data_vectors = tmp_path / "data" / "vectors"
    fake_data_vectors.mkdir(parents=True)
    fake_layer = fake_data_vectors / "custom_layer.geojson"
    fake_layer.write_text('{"type": "FeatureCollection", "features": []}', encoding="utf-8")

    monkeypatch.setattr(app_mod, "BASE_DIR", fake_base)

    resp = client.get("/api/v1/vectors/custom_layer")
    assert resp.status_code == 200
    assert resp.json()["type"] == "FeatureCollection"


def test_comparison_endpoint():
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    resp = client.get(f"/api/v1/comparison/{pair_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pair_id"] == pair_id
    assert "rows" in data
    assert len(data["rows"]) == 3

    resp_404 = client.get("/api/v1/comparison/non_existent_pair_999")
    assert resp_404.status_code == 404


def test_comparison_without_reference_file(monkeypatch, tmp_path):
    import src.service.app as app_mod

    fake_base = tmp_path / "empty_base"
    fake_base.mkdir()
    monkeypatch.setattr(app_mod, "BASE_DIR", fake_base)

    pair_id = "flood_2019_07_amur__blagoveshchensk"
    resp = client.get(f"/api/v1/comparison/{pair_id}")
    assert resp.status_code == 200
    data = resp.json()
    for row in data["rows"]:
        assert row["diff_pct"] == 0.0


def test_comparison_konstantinovka_anomaly():
    pair_id = "flood_2021_06_amur__konstantinovka"
    resp = client.get(f"/api/v1/comparison/{pair_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pair_id"] == pair_id
    assert "anomaly_analysis" in data
    anomaly = data["anomaly_analysis"]
    assert "FP 8572" in anomaly["title"]
    assert anomaly["radar_flood_ha"] > 8000.0
    assert anomaly["permanent_water_ha"] > 5000.0
    assert "МЧС" in anomaly["mchs_operational_safety"]
    assert "IoU" in anomaly["topological_boundary_metrics"]


def test_ablation_not_found(monkeypatch, tmp_path):
    import src.service.app as app_mod

    fake_base = tmp_path / "empty_base"
    fake_base.mkdir()
    monkeypatch.setattr(app_mod, "BASE_DIR", fake_base)

    resp = client.get("/api/v1/ablation")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Результаты аблаций не найдены"


def test_peak_rss_gb_linux(monkeypatch):
    from src.service.app import _peak_rss_gb

    monkeypatch.setattr("sys.platform", "linux")
    rss = _peak_rss_gb()
    assert rss >= 0.0


def test_recompute_report_rebuild_failure_and_http_exception(monkeypatch):
    import src.service.app as app_mod
    from src.service.app import data_loader

    monkeypatch.setattr(data_loader, "get_report", lambda *args, **kwargs: None)
    resp = client.post("/api/v1/recompute", json={"pair_id": "flood_2019_07_amur__blagoveshchensk"})
    assert resp.status_code == 500
    assert "Не удалось перестроить отчет" in resp.json()["detail"]

    def mock_invalidate(*args, **kwargs):
        raise HTTPException(status_code=418, detail="Teapot failure")

    monkeypatch.setattr(app_mod, "_invalidate_pair_caches", mock_invalidate)
    resp = client.post("/api/v1/recompute", json={"pair_id": "flood_2019_07_amur__blagoveshchensk"})
    assert resp.status_code == 418
    assert resp.json()["detail"] == "Teapot failure"


def test_layers_geojson_endpoints():
    pair_id = "flood_2019_07_amur__blagoveshchensk"

    # Строка 588
    resp_404_all = client.get("/api/v1/layers/nonexistent_pair_999/geojson")
    assert resp_404_all.status_code == 404
    assert "Слои для пары 'nonexistent_pair_999' не найдены" in resp_404_all.json()["detail"]

    # Строки 595-598
    resp_layer = client.get(f"/api/v1/layers/{pair_id}/water_peak")
    assert resp_layer.status_code == 200
    assert resp_layer.json().get("type") == "FeatureCollection"

    resp_layer_bad = client.get(f"/api/v1/layers/{pair_id}/invalid_layer")
    assert resp_layer_bad.status_code == 404

    resp_layer_bad_pair = client.get("/api/v1/layers/invalid_pair_999/water_peak")
    assert resp_layer_bad_pair.status_code == 404


def test_derived_layers_available_over_http():
    """Чекбоксы «Постоянная вода» и «Убыль воды» теперь опираются на реальные слои, а не на 400."""
    pair_id = "flood_2019_07_amur__blagoveshchensk"

    for layer in ("permanent", "receded"):
        resp = client.get(f"/api/v1/layers/{pair_id}/{layer}")
        assert resp.status_code == 200, f"Слой {layer} должен отдаваться как GeoJSON"
        body = resp.json()
        assert body["type"] == "FeatureCollection"
        assert body["features"], f"Слой {layer} не должен быть пустым"
        assert body["features"][0]["properties"]["layer"] == layer

    # Растровых GeoTIFF для производных масок нет: ручка честно отказывает
    assert client.get(f"/api/v1/geotiff/{pair_id}?layer=permanent").status_code == 400


def test_scene_png_and_metadata_endpoints():
    """Подложка карты отдаётся реальной сценой Sentinel, а не чужими тайлами."""
    pair_id = "flood_2019_07_amur__blagoveshchensk"

    resp = client.get(f"/api/v1/scene/{pair_id}/sar_vv?window=peak")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert len(resp.content) > 10_000

    meta = client.get(f"/api/v1/scene/{pair_id}/sar_vv/meta?window=peak")
    assert meta.status_code == 200
    body = meta.json()
    assert body["mode"] == "sar_vv"
    assert body["window"] == "peak"
    assert body["source"].startswith("S1_peak_")
    assert len(body["bounds"]) == 2
    # Границы сцены совпадают с границами растра модели той же пары
    assert body["crs"] == "EPSG:32652"

    pre_meta = client.get(f"/api/v1/scene/{pair_id}/sar_vv/meta?window=pre").json()
    assert body["source"] != pre_meta["source"]
    assert pre_meta["source"].startswith("S1_pre_")

    # Оптические сцены пары пусты (только nodata): 404 вместо пустой картинки
    assert client.get(f"/api/v1/scene/{pair_id}/msi_true").status_code == 404
    # Неизвестный режим и окно отвергаются
    assert client.get(f"/api/v1/scene/{pair_id}/invalid_mode").status_code == 400
    assert client.get(f"/api/v1/scene/{pair_id}/sar_vv?window=nope").status_code == 400


def test_scene_endpoints_missing_pair():
    assert client.get("/api/v1/scene/invalid_pair_999/sar_vv").status_code == 404
    assert client.get("/api/v1/scene/invalid_pair_999/sar_vv/meta").status_code == 404


def test_export_vectors_and_report_errors():
    # Строка 616
    resp_shp_404 = client.get("/api/v1/export/invalid_pair_999/vectors?format=shp")
    assert resp_shp_404.status_code == 404

    # Строка 625
    resp_geo_404 = client.get("/api/v1/export/invalid_pair_999/vectors?format=geojson")
    assert resp_geo_404.status_code == 404

    # Строка 645
    resp_rep_404 = client.get("/api/v1/export/invalid_pair_999/report?format=json")
    assert resp_rep_404.status_code == 404


def test_uncertainty_without_prediction_raster(monkeypatch, tmp_path):
    import src.service.app as app_mod

    monkeypatch.setattr(app_mod, "PREDICTIONS_DIR", tmp_path / "no_preds")
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    resp = client.get(f"/api/v1/uncertainty/{pair_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["area_ha"] > 0.0

    orig_get_report = app_mod.data_loader.get_report

    def mock_report_zero_flood(p_id):
        rep = orig_get_report(p_id)
        if rep:
            rep = dict(rep)
            rep["flood_ha"] = 0.0
        return rep

    monkeypatch.setattr(app_mod.data_loader, "get_report", mock_report_zero_flood)
    resp_zero = client.get(f"/api/v1/uncertainty/{pair_id}")
    assert resp_zero.status_code == 200
    assert resp_zero.json()["area_ha"] == 0.0


def test_sar_analytics_hardcoded_or_missing_triggers_recompute(monkeypatch):
    from src.service.app import data_loader

    orig_get_report = data_loader.get_report
    pair_id = "flood_2019_07_amur__blagoveshchensk"

    def mock_get_report_hardcoded(p_id):
        rep = dict(orig_get_report(p_id))
        rep["sar_analytics"] = {"mean_vv_db": -16.2, "mean_vh_db": -22.8}
        return rep

    monkeypatch.setattr(data_loader, "get_report", mock_get_report_hardcoded)
    resp = client.get(f"/api/v1/sar-analytics/{pair_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mean_vv_db"] != -16.2


def test_raster_overlay_fallback_and_errors(monkeypatch, tmp_path):
    import src.service.app as app_mod

    # Строка 830
    resp_meta_404 = client.get("/api/v1/overlay/invalid_pair_999/meta")
    assert resp_meta_404.status_code == 404

    # Строки 808-809: запасной вариант при пустой маске
    monkeypatch.setattr(app_mod, "PREDICTIONS_DIR", tmp_path / "no_preds")
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    resp_png = client.get(f"/api/v1/overlay/{pair_id}?layer=flood")
    assert resp_png.status_code == 200
    assert resp_png.headers["content-type"] == "image/png"

    # Строки 842-844: запасные границы и размеры
    resp_meta = client.get(f"/api/v1/overlay/{pair_id}/meta")
    assert resp_meta.status_code == 200
    meta = resp_meta.json()
    assert meta["width"] == 1000
    assert meta["height"] == 1000
    assert meta["crs"] == "EPSG:4326"


def test_official_metrics_missing_submission(monkeypatch, tmp_path):
    import src.service.app as app_mod

    fake_base = tmp_path / "empty_base"
    fake_base.mkdir()
    monkeypatch.setattr(app_mod, "BASE_DIR", fake_base)

    resp = client.get("/api/v1/metrics/official")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "submission.csv не найден"


def test_root_fallback_and_static_serving(monkeypatch, tmp_path):
    import src.service.app as app_mod

    # Строка 929: префикс api/ возвращает 404
    resp_api = client.get("/api/nonexistent_subroute")
    assert resp_api.status_code == 404
    assert resp_api.json()["detail"] == "Точка входа API не найдена"

    # Строка 933: статический файл
    resp_static = client.get("/icons/logo.png")
    assert resp_static.status_code == 200

    # Строка 939: отсутствующий ресурс с расширением
    resp_asset = client.get("/assets/nonexistent_script.js")
    assert resp_asset.status_code == 404
    assert "Ресурс 'assets/nonexistent_script.js' не найден" in resp_asset.json()["detail"]

    # Строка 943: отсутствует index.html
    monkeypatch.setattr(app_mod, "STATIC_DIR", tmp_path / "empty_static")
    resp_no_index = client.get("/")
    assert resp_no_index.status_code == 404
    assert resp_no_index.json()["detail"] == "index.html не найден"


def test_eda_endpoint(monkeypatch, tmp_path):
    import src.service.app as app_mod

    resp = client.get("/eda")
    assert resp.status_code in [200, 404]

    # Проверка отката при отсутствии файла
    monkeypatch.setattr(app_mod, "BASE_DIR", tmp_path)
    resp_404 = client.get("/eda")
    assert resp_404.status_code == 404
    assert resp_404.json()["detail"] == "Отчет EDA не скомпилирован"


# --- Регрессия производительности: сжатие, кэширование и дедупликация расчётов ---


def test_gzip_middleware_compresses_large_json():
    """Крупные JSON/CSV-ответы сжимаются, когда клиент запрашивает gzip."""
    resp = client.get("/api/v1/pairs", headers={"Accept-Encoding": "gzip"})
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") == "gzip"
    # httpx прозрачно распаковывает тело, поэтому Content-Length (байты в сети)
    # строго меньше распакованного JSON.
    assert int(resp.headers["content-length"]) < len(resp.content)
    assert "accept-encoding" in resp.headers.get("vary", "").lower()


def test_gzip_not_applied_without_accept_encoding():
    """Без Accept-Encoding: gzip тело отдаётся как есть (identity)."""
    resp = client.get("/api/v1/pairs", headers={"Accept-Encoding": "identity"})
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") is None
    assert int(resp.headers["content-length"]) == len(resp.content)


def test_gzip_not_applied_to_excluded_content_types():
    """PNG-оверлеи исключены из сжатия самим Starlette (плохо сжимаемый формат)."""
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    resp = client.get(f"/api/v1/overlay/{pair_id}?layer=flood", headers={"Accept-Encoding": "gzip"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.headers.get("content-encoding") != "gzip"


def test_artifact_cache_headers_present():
    """Неизменяемые артефакты (GeoJSON, GeoTIFF) отдаются с Cache-Control."""
    pair_id = "flood_2019_07_amur__blagoveshchensk"

    gj = client.get(f"/api/v1/geojson/{pair_id}?layer=flood")
    assert gj.status_code == 200
    assert gj.headers.get("cache-control") == "public, max-age=86400"

    tif = client.get(f"/api/v1/geotiff/{pair_id}?layer=flood")
    assert tif.status_code == 200
    assert tif.headers.get("cache-control") == "public, max-age=86400"


def test_artifact_cache_header_absent_on_errors():
    """404 не должен кэшироваться как неизменяемый артефакт."""
    resp = client.get("/api/v1/geojson/non_existent_pair?layer=flood")
    assert resp.status_code == 404
    assert resp.headers.get("cache-control") != "public, max-age=86400"


def test_meteo_endpoint():
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    resp = client.get(f"/api/v1/meteo/{pair_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pair_id"] == pair_id
    assert "summary" in data
    assert "timeseries" in data
    assert data["summary"]["has_meteo_data"] is True
    assert len(data["timeseries"]) > 0

    # 404 для несуществующей пары
    resp_404 = client.get("/api/v1/meteo/non_existent_pair")
    assert resp_404.status_code == 404


def test_webhook_scene_ingest():
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    payload = {
        "pair_id": pair_id,
        "source": "copernicus-dataspace",
        "scene_id": "S1A_IW_GRDH_1SDV_20190725T212629_028278_0331A4_E180",
        "sensor": "sentinel1",
    }
    resp = client.post("/api/v1/webhook/scene-ingest", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"
    assert "recompute_result" in data
    assert data["recompute_result"]["status"] == "success"
