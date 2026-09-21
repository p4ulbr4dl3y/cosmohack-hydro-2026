"""Integration tests for HydroWatch Amur FastAPI service."""

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
    assert data["flood_ha"] == 1614.38
    assert data["water_pre_ha"] == 8413.79
    assert data["water_peak_ha"] == 9672.04

    # Verify landcover structure
    assert "landcover" in data
    lc = data["landcover"]
    assert "builtup_ha" in lc
    assert "builtup_pct" in lc
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
    # Bounds outside coverage - should still return 200 with best matching pair or empty features
    bounds = [10.0, 10.0, 11.0, 11.0]
    resp = client.post("/api/v1/predict", json={"bounds": bounds})
    assert resp.status_code == 200
    res = resp.json()
    assert res["status"] == "success"


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
