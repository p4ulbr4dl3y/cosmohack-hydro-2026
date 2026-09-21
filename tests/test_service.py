"""Integration tests for HydroWatch Amur FastAPI service."""

from pathlib import Path

import pandas as pd
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

    # Check fields of first pair
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

    # Verify values match submission.csv predictions
    sub = pd.read_csv(Path("submission.csv"))
    row = sub[sub["pair_id"] == "flood_2019_07_amur__blagoveshchensk"].iloc[0]
    assert data["flood_ha"] == float(row["flood_ha"])
    assert data["water_pre_ha"] == float(row["water_pre_ha"])
    assert data["water_peak_ha"] == float(row["water_peak_ha"])

    # Verify landcover structure
    assert "landcover" in data
    lc = data["landcover"]
    assert "builtup_ha" in lc
    assert "builtup_pct" in lc
    assert "cropland_ha" in lc
    assert "cropland_pct" in lc
    assert "natural_vegetation_ha" in lc
    assert "natural_vegetation_pct" in lc
    assert "mean_hand_m" in lc


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

    # Verify GeoJSON properties on flood layer from predictions
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
    # Bounds near Blagoveshchensk
    bounds = [127.21, 50.12, 127.85, 50.45]
    resp = client.post("/api/v1/predict", json={"bounds": bounds})
    assert resp.status_code == 200
    res = resp.json()
    assert res["status"] == "success"
    assert "summary" in res
    assert "geojson" in res


def test_predict_endpoint_invalid_date_format():
    # Validation runs before cache lookup, so no raster data is needed
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    resp = client.post("/api/v1/predict", json={"pair_id": pair_id, "date_pre": "2019/06/13"})
    assert resp.status_code == 400
    assert "Некорректная дата" in resp.json()["detail"]


def test_predict_endpoint_date_out_of_range():
    # 2019-06-13 + more than 30 days -> rejected against scene date
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
    # Bounds outside coverage (e.g. Gulf of Guinea) correctly rejected with 400
    bounds_outside = [10.0, 10.0, 11.0, 11.0]
    resp_outside = client.post("/api/v1/predict", json={"bounds": bounds_outside})
    assert resp_outside.status_code == 400
    assert "do not overlap" in resp_outside.json()["detail"]

    # Valid overlapping bounds within Blagoveshchensk AOI
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
    # Test ValueError handling (400)
    resp = client.post("/api/v1/predict", json={"pair_id": "non_existent_pair"})
    assert resp.status_code == 400

    # Test unhandled Exception handling (500)
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
    assert "Invalid layer" in resp.json()["detail"]


def test_shapefile_invalid_layer():
    resp = client.get("/api/v1/shapefile/flood_2019_07_amur__blagoveshchensk?layer=invalid_layer")
    assert resp.status_code == 400
    assert "Invalid layer" in resp.json()["detail"]


def test_geotiff_endpoint():
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    # Success
    resp = client.get(f"/api/v1/geotiff/{pair_id}?layer=flood")
    assert resp.status_code == 200
    assert "image/tiff" in resp.headers["content-type"]
    assert len(resp.content) > 0

    # Invalid layer
    resp_inv = client.get(f"/api/v1/geotiff/{pair_id}?layer=invalid_layer")
    assert resp_inv.status_code == 400
    assert "Invalid layer" in resp_inv.json()["detail"]

    # 404 not found
    resp_404 = client.get("/api/v1/geotiff/non_existent_pair?layer=flood")
    assert resp_404.status_code == 404
    assert "not found" in resp_404.json()["detail"]


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
    # A stale index.html can reference an old hashed chunk. Serving the SPA
    # shell as text/html for a .js request makes the module import fail and the
    # page render blank, so missing assets must 404 instead.
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
    assert resp.json()["detail"] == "index.html not found"


def test_prediction_task_status_lifecycle(monkeypatch):
    from src.service.app import tasks_db

    # 404 on nonexistent task
    resp = client.get("/api/v1/predict/status/nonexistent_task_123")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]

    # Submit task with task_id
    task_id = "test_task_success_456"
    resp = client.post(
        "/api/v1/predict",
        json={"pair_id": "flood_2019_07_amur__blagoveshchensk", "task_id": task_id},
    )
    assert resp.status_code == 200
    assert task_id in tasks_db

    # Query status
    status_resp = client.get(f"/api/v1/predict/status/{task_id}")
    assert status_resp.status_code == 200
    task_data = status_resp.json()
    assert task_data["task_id"] == task_id
    assert task_data["status"] == "completed"
    assert task_data["progress"] == 1.0
    assert task_data["result"] is not None
    assert task_data["error"] is None

    # Test failure on ValueError
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

    # Test failure on 500 runtime error
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

    # Test env var config
    custom_cache = tmp_path / "env_cache"
    monkeypatch.setenv("HYDROWATCH_CACHE_DIR", str(custom_cache))
    loader = DataLoader(cache_dir=None)
    assert loader.cache_dir == custom_cache
    assert custom_cache.exists()

    # Test fallback to legacy cache
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    (legacy_dir / "report_mock.json").write_text('{"mock": true}', encoding="utf-8")

    loader_fallback = DataLoader(cache_dir=tmp_path / "new_cache", legacy_cache_dir=legacy_dir)
    resolved = loader_fallback._resolve_cache_path("report_mock.json")
    assert resolved == legacy_dir / "report_mock.json"

    # If primary exists, primary takes priority
    primary_file = tmp_path / "new_cache" / "report_mock.json"
    primary_file.write_text('{"primary": true}', encoding="utf-8")
    assert loader_fallback._resolve_cache_path("report_mock.json") == primary_file

    # When neither primary nor legacy exists, return primary
    assert loader_fallback._resolve_cache_path("missing_file.json") == tmp_path / "new_cache" / "missing_file.json"


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
    assert recompute_resp.json()["status"] == "success"
