"""Unit tests for newly ported REST API endpoints in HydroWatch service."""

from __future__ import annotations

from starlette.testclient import TestClient

from src.service.app import app

client = TestClient(app)
SAMPLE_PAIR = "flood_2019_07_amur__blagoveshchensk"


def test_api_audit_endpoint():
    res = client.get(f"/api/v1/audit/{SAMPLE_PAIR}")
    assert res.status_code == 200
    data = res.json()

    assert data["pair_id"] == SAMPLE_PAIR
    assert data["status"] == "VERIFIED"
    assert len(data["merkle_root"]) == 64
    assert len(data["signature_hash"]) == 64
    assert "leaves" in data
    assert len(data["leaves"]) >= 3
    assert data["merkle_root_sha256"] == data["merkle_root"]
    assert len(data["inputs_hash_sha256"]) == 64
    assert len(data["parameters_hash_sha256"]) == 64
    assert len(data["results_hash_sha256"]) == 64
    assert data["verified"] is True


def test_api_audit_404():
    res = client.get("/api/v1/audit/non_existent_pair_123")
    assert res.status_code == 404


def test_api_uncertainty_endpoint():
    res = client.get(f"/api/v1/uncertainty/{SAMPLE_PAIR}?confidence_level=0.95&spatial_correlation=0.20")
    assert res.status_code == 200
    data = res.json()

    assert data["pair_id"] == SAMPLE_PAIR
    assert data["area_ha"] > 0.0
    assert data["confidence_level"] == 0.95
    assert data["lower_bound_ha"] < data["area_ha"] < data["upper_bound_ha"]
    assert data["margin_ha"] > 0.0
    assert data["relative_uncertainty_pct"] > 0.0
    assert data["spatial_correlation"] == 0.20


def test_api_uncertainty_404():
    res = client.get("/api/v1/uncertainty/non_existent_pair_123")
    assert res.status_code == 404


def test_api_sar_analytics_endpoint():
    res = client.get(f"/api/v1/sar-analytics/{SAMPLE_PAIR}")
    assert res.status_code == 200
    data = res.json()

    assert data["pair_id"] == SAMPLE_PAIR
    assert "water_fraction" in data
    assert "water_area_ha" in data
    assert data["cloud_penetration_verified"] is True
    assert data["mean_vv_db"] < 0.0
    assert data["mean_vh_db"] < 0.0


def test_api_sar_analytics_404():
    res = client.get("/api/v1/sar-analytics/non_existent_pair_123")
    assert res.status_code == 404


def test_api_overlay_meta_and_png():
    # 1. Metadata endpoint
    res_meta = client.get(f"/api/v1/overlay/{SAMPLE_PAIR}/meta?layer=flood")
    assert res_meta.status_code == 200
    meta = res_meta.json()

    assert meta["pair_id"] == SAMPLE_PAIR
    assert meta["layer"] == "flood"
    assert "bounds" in meta
    assert len(meta["bounds"]) == 2
    assert "overlay_url" in meta

    # 2. Direct PNG render endpoint (default gradient)
    res_png = client.get(f"/api/v1/overlay/{SAMPLE_PAIR}?layer=flood")
    assert res_png.status_code == 200
    assert res_png.headers["content-type"] == "image/png"
    assert res_png.content.startswith(b"\x89PNG\r\n\x1a\n")

    # 3. Direct PNG render endpoint with gradient=false
    res_png_flat = client.get(f"/api/v1/overlay/{SAMPLE_PAIR}?layer=flood&gradient=false")
    assert res_png_flat.status_code == 200
    assert res_png_flat.headers["content-type"] == "image/png"
    assert res_png_flat.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_api_overlay_invalid_layer():
    res = client.get(f"/api/v1/overlay/{SAMPLE_PAIR}?layer=invalid_layer_name")
    assert res.status_code == 400


def test_api_official_metrics_endpoint():
    res = client.get("/api/v1/metrics/official")
    assert res.status_code == 200
    data = res.json()

    assert "score" in data
    assert "q_flood" in data
    assert "q_water_peak" in data
    assert "q_water_pre" in data
    assert "spec_base" in data
    assert data["num_events"] == 8
    assert data["num_baselines"] == 3
    assert len(data["details"]) == 11
    assert data["technical_points"] >= 0.0


def test_api_validate_submission_endpoint():
    res = client.get("/api/v1/metrics/validate-submission")
    assert res.status_code == 200
    data = res.json()

    assert "is_valid" in data
    assert data["is_valid"] is True
    assert data["num_pairs"] == 11
    assert len(data["passed_checks"]) >= 3
    assert len(data["errors"]) == 0


def test_api_carbon_metrics_endpoint():
    res = client.get(f"/api/v1/carbon-metrics/{SAMPLE_PAIR}")
    assert res.status_code == 200
    data = res.json()

    assert data["pair_id"] == SAMPLE_PAIR
    assert "flood_ha" in data
    assert "carbon_loss_tC" in data
    assert "emissions_equivalent_tCO2e" in data
    assert "credit_potential" in data
    assert "Q_credits" in data["credit_potential"]


def test_api_carbon_metrics_404():
    res = client.get("/api/v1/carbon-metrics/non_existent_pair_123")
    assert res.status_code == 404

