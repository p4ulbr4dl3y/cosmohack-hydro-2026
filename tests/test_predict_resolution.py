"""Tests for the temporal + polygon aware /api/v1/predict resolution.

Covers audit finding 1.7: a bbox query with dates matching an existing pair
(Blagoveshchensk has three pairs with identical bounds) must resolve to the
date-matching pair instead of always returning the earliest baseline.
"""

import shapely.geometry
from fastapi.testclient import TestClient

from src.service.app import app

client = TestClient(app)

BLAGOVESHCHENSK_BOUNDS = [127.218519, 50.120525, 127.857226, 50.459458]
BLAGOVESHCHENSK_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [127.30, 50.20],
            [127.60, 50.20],
            [127.60, 50.40],
            [127.30, 50.40],
            [127.30, 50.20],
        ]
    ],
}


def test_predict_bounds_resolves_pair_by_dates():
    """Dates that match the 2021 event must select the 2021 pair, not baseline_2018."""
    resp = client.post(
        "/api/v1/predict",
        json={"bounds": BLAGOVESHCHENSK_BOUNDS, "date_pre": "2021-05-14", "date_peak": "2021-07-01"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pair_id"] == "flood_2021_06_amur__blagoveshchensk"
    assert data["scene_dates"] == {"date_pre": "2021-05-14", "date_peak": "2021-07-01"}


def test_predict_bounds_resolves_pair_by_2019_dates():
    resp = client.post(
        "/api/v1/predict",
        json={"bounds": BLAGOVESHCHENSK_BOUNDS, "date_pre": "2019-06-13", "date_peak": "2019-07-25"},
    )
    assert resp.status_code == 200
    assert resp.json()["pair_id"] == "flood_2019_07_amur__blagoveshchensk"


def test_predict_bounds_without_dates_uses_spatial_overlap():
    resp = client.post("/api/v1/predict", json={"bounds": BLAGOVESHCHENSK_BOUNDS})
    assert resp.status_code == 200
    assert resp.json()["pair_id"] == "baseline_2018_09_low__blagoveshchensk"


def test_predict_polygon_is_accepted_and_clipped():
    resp = client.post("/api/v1/predict", json={"polygon": BLAGOVESHCHENSK_POLYGON})
    assert resp.status_code == 200
    data = resp.json()
    assert data["pair_id"] == "baseline_2018_09_low__blagoveshchensk"
    assert data["query_polygon"] == BLAGOVESHCHENSK_POLYGON
    assert "flood_clipped" in data["geojson"]["name"]


def test_predict_polygon_dates_resolve_pair():
    resp = client.post(
        "/api/v1/predict",
        json={"polygon": BLAGOVESHCHENSK_POLYGON, "date_pre": "2021-05-14", "date_peak": "2021-07-01"},
    )
    assert resp.status_code == 200
    assert resp.json()["pair_id"] == "flood_2021_06_amur__blagoveshchensk"


def test_predict_polygon_area_uses_metric_projection():
    """area_ha of clipped contours must be computed in UTM, not degrees.

    A clipped Blagoveshchensk flood contour must total a physically plausible
    value (the old degree formula inflated areas by ~1/cos(lat) ~= 1.55x).
    """
    resp = client.post(
        "/api/v1/predict",
        json={"polygon": BLAGOVESHCHENSK_POLYGON, "pair_id": "flood_2021_06_amur__blagoveshchensk"},
    )
    assert resp.status_code == 200
    feats = resp.json()["geojson"]["features"]
    assert feats, "expected clipped flood contours inside the query polygon"

    total = sum(f["properties"]["area_ha"] for f in feats)
    # UTM area of the ~0.30 deg x 0.20 deg clip box near 50 degN is ~ 500-900 ha;
    # the degree approximation would overstate it by ~1.55x (> 1300 ha).
    assert 100.0 < total < 1000.0

    # Compare against a direct metric computation of the query polygon area.
    from src.service.data_loader import data_loader

    poly_area_ha = data_loader._metric_area_ha(
        shapely.geometry.shape(BLAGOVESHCHENSK_POLYGON), "flood_2021_06_amur__blagoveshchensk"
    )
    # The clipped flood can never exceed the query polygon area by much
    assert total <= poly_area_ha * 1.05


def test_predict_invalid_polygon_returns_400():
    resp = client.post("/api/v1/predict", json={"polygon": {"type": "Nonsense", "coordinates": []}})
    assert resp.status_code == 400
    assert "polygon" in resp.json()["detail"].lower()
