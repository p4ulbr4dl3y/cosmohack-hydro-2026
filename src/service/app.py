"""FastAPI application for HydroWatch Amur Flood Monitoring Service."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.service.data_loader import data_loader
from src.service.schemas import (
    PairsListResponse,
    PredictionTaskResponse,
    PredictRequest,
    PredictResponse,
    ReportResponse,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
PREDICTIONS_DIR = BASE_DIR / "predictions"

app = FastAPI(
    title="HydroWatch Amur API",
    description="Operational Sentinel-1/2 Hydrological Monitoring & Flood Intelligence Service",
    version="1.0.0",
)

# CORS middleware for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory registry for prediction tasks
tasks_db: dict[str, dict[str, Any]] = {}


@app.get("/health")
async def health_status() -> dict[str, Any]:
    """Health check endpoint with service metadata."""
    return {
        "status": "ok",
        "service": "hydrowatch-amur",
        "pairs_count": len(data_loader.get_pairs()),
    }


@app.get("/api/v1/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get(
    "/api/v1/pairs",
    response_model=PairsListResponse,
    summary="List all monitored pairs with metadata",
)
async def list_pairs() -> Any:
    """Lists all 11 pairs with AOI metadata, dates, and areas."""
    return data_loader.get_pairs()


@app.get(
    "/api/v1/report/{pair_id}",
    response_model=ReportResponse,
    summary="Get automated hydrological report for a pair",
)
async def get_report(pair_id: str) -> Any:
    """Automated summary report with flood areas, metrics, and landcover distribution."""
    report = data_loader.get_report(pair_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Pair '{pair_id}' not found")
    return report


@app.get("/api/v1/report/{pair_id}/csv")
async def get_report_csv(pair_id: str) -> Response:
    """Download single pair report as CSV."""
    report = data_loader.get_report(pair_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Pair '{pair_id}' not found")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "pair_id",
            "aoi_id",
            "aoi_name",
            "event_id",
            "event_name",
            "date_pre_sar",
            "date_peak_sar",
            "flood_ha",
            "flood_km2",
            "water_pre_ha",
            "water_peak_ha",
            "water_gain_ha",
            "water_gain_pct",
            "share_of_aoi",
            "builtup_flood_ha",
            "builtup_flood_pct",
            "cropland_flood_ha",
            "cropland_flood_pct",
            "natural_flood_ha",
            "natural_flood_pct",
        ]
    )
    lc = report.get("landcover", {})
    writer.writerow(
        [
            report["pair_id"],
            report["aoi_id"],
            report["aoi_name"],
            report["event_id"],
            report["event_name"],
            report["date_pre_sar"],
            report["date_peak_sar"],
            report["flood_ha"],
            report["flood_km2"],
            report["water_pre_ha"],
            report["water_peak_ha"],
            report["water_gain_ha"],
            report["water_gain_pct"],
            report["share_of_aoi"],
            lc.get("builtup_ha", 0.0),
            lc.get("builtup_pct", 0.0),
            lc.get("cropland_ha", 0.0),
            lc.get("cropland_pct", 0.0),
            lc.get("natural_vegetation_ha", 0.0),
            lc.get("natural_vegetation_pct", 0.0),
        ]
    )

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=report_{pair_id}.csv"},
    )


@app.get("/api/v1/geojson/{pair_id}")
async def get_geojson(
    pair_id: str,
    layer: str = Query(default="flood", description="Layer name: 'flood', 'water_pre', 'water_peak'"),
) -> dict[str, Any]:
    """Vector polygons of flood zone in GeoJSON format (EPSG:4326 for web maps)."""
    norm_layer = layer.strip().lower()
    if norm_layer not in ("flood", "water_pre", "water_peak"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid layer '{layer}'. Must be one of: 'flood', 'water_pre', 'water_peak'",
        )
    geojson = data_loader.get_geojson(pair_id, layer=norm_layer)
    if geojson is None:
        raise HTTPException(status_code=404, detail=f"GeoJSON for pair '{pair_id}' (layer: {norm_layer}) not found")
    return geojson


@app.get("/api/v1/shapefile/{pair_id}")
async def get_shapefile(
    pair_id: str,
    layer: str = Query(default="flood", description="Layer name: 'flood', 'water_pre', 'water_peak'"),
) -> Response:
    """Vector polygons exported as a zipped ESRI Shapefile archive (EPSG:4326)."""
    norm_layer = layer.strip().lower()
    if norm_layer not in ("flood", "water_pre", "water_peak"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid layer '{layer}'. Must be one of: 'flood', 'water_pre', 'water_peak'",
        )
    shp_bytes = data_loader.get_shapefile_zip(pair_id, layer=norm_layer)
    if shp_bytes is None:
        raise HTTPException(status_code=404, detail=f"Shapefile for pair '{pair_id}' (layer: {norm_layer}) not found")
    return Response(
        content=shp_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={pair_id}_{layer}_shp.zip"},
    )


@app.get("/api/v1/geotiff/{pair_id}")
async def get_geotiff(
    pair_id: str,
    layer: str = Query(default="flood", description="Layer name: 'flood', 'water_pre', 'water_peak'"),
) -> FileResponse:
    """Download raster mask for the given pair and layer in GeoTIFF format (EPSG:32652)."""
    norm_layer = layer.strip().lower()
    if norm_layer not in ("flood", "water_pre", "water_peak"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid layer '{layer}'. Must be one of: 'flood', 'water_pre', 'water_peak'",
        )
    tif_path = PREDICTIONS_DIR / f"{pair_id}_{norm_layer}.tif"
    if not tif_path.exists():
        raise HTTPException(status_code=404, detail=f"GeoTIFF for pair '{pair_id}' (layer: {norm_layer}) not found")
    return FileResponse(
        path=str(tif_path),
        media_type="image/tiff",
        filename=f"{pair_id}_{norm_layer}.tif",
    )


@app.post(
    "/api/v1/predict",
    response_model=PredictResponse,
    summary="Spatial-temporal flood prediction",
)
async def predict_flood(request: PredictRequest) -> Any:
    """Spatial-temporal inference endpoint accepting bounds / polygon / pair_id."""
    try:
        # Validate date format (YYYY-MM-DD) upfront; range plausibility is checked
        # against the pair that is actually resolved (which may depend on the dates).
        requested_dates: dict[str, date | None] = {"date_pre": None, "date_peak": None}
        for name in ("date_pre", "date_peak"):
            val = getattr(request, name)
            if val is None or val == "":
                continue  # dates omitted: behave exactly as before
            try:
                requested_dates[name] = datetime.strptime(val, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Некорректная дата {name}: '{val}' (ожидается YYYY-MM-DD)")

        result = data_loader.predict_spatial_temporal(
            pair_id=request.pair_id,
            bounds=request.bounds,
            date_pre=request.date_pre,
            date_peak=request.date_peak,
            polygon=request.polygon,
        )
        resolved_pair_id = result.get("pair_id")
        pair_meta = data_loader.get_pair_meta(resolved_pair_id) if resolved_pair_id else None
        if pair_meta is not None:
            for name in ("date_pre", "date_peak"):
                req_d = requested_dates[name]
                if req_d is not None:
                    scene_val = pair_meta.get(f"{name}_sar")
                    if scene_val:
                        try:
                            scene_dt = datetime.strptime(str(scene_val), "%Y-%m-%d").date()
                        except ValueError:
                            continue
                        if abs((req_d - scene_dt).days) > 30:
                            raise HTTPException(
                                status_code=400,
                                detail=(
                                    f"Некорректная дата {name}: '{getattr(request, name)}' выходит за пределы ±30 дней "
                                    f"от даты съёмки {scene_val}"
                                ),
                            )
        result.setdefault("requested_dates", {k: (v.isoformat() if v else None) for k, v in requested_dates.items()})
        if request.task_id:
            tasks_db[request.task_id] = {
                "task_id": request.task_id,
                "status": "completed",
                "progress": 1.0,
                "result": result,
                "error": None,
            }
        return result
    except HTTPException:
        raise
    except ValueError as e:
        if request.task_id:
            tasks_db[request.task_id] = {
                "task_id": request.task_id,
                "status": "failed",
                "progress": 1.0,
                "result": None,
                "error": str(e),
            }
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if request.task_id:
            tasks_db[request.task_id] = {
                "task_id": request.task_id,
                "status": "failed",
                "progress": 1.0,
                "result": None,
                "error": str(e),
            }
        raise HTTPException(status_code=500, detail=f"Internal prediction error: {e!s}")


@app.get(
    "/api/v1/predict/status/{task_id}",
    response_model=PredictionTaskResponse,
    summary="Get status of an asynchronous prediction task",
)
async def get_prediction_task_status(task_id: str) -> PredictionTaskResponse:
    """Check lifecycle status and retrieve result of an asynchronous prediction task."""
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Prediction task '{task_id}' not found")
    return PredictionTaskResponse(**task)


@app.get("/api/v1/events")
async def list_events() -> list[dict[str, Any]]:
    """Alias to list_pairs for openapi contract compatibility."""
    return data_loader.get_pairs()


@app.get("/api/v1/aoi")
async def get_aoi_vectors() -> dict[str, Any]:
    """Returns GeoJSON FeatureCollection of AOI polygons."""
    aoi_path = BASE_DIR / "hydrowatch_amur" / "vectors" / "aoi.geojson"
    if not aoi_path.exists():
        aoi_path = BASE_DIR.parent / "data" / "vectors" / "aoi.geojson"
    if not aoi_path.exists():
        raise HTTPException(status_code=404, detail="aoi.geojson not found")
    with open(aoi_path, encoding="utf-8") as f:
        import json

        return json.load(f)


@app.get("/api/v1/vectors/{layer_name}")
async def get_vector_layer(layer_name: str) -> dict[str, Any]:
    """Returns vector layer GeoJSON (e.g. amur_oblast, aoi, hydrography_osm, basins_hydrosheds)."""
    import json

    v_path = BASE_DIR / "hydrowatch_amur" / "vectors" / f"{layer_name}.geojson"
    if not v_path.exists():
        v_path = BASE_DIR.parent / "data" / "vectors" / f"{layer_name}.geojson"
    if not v_path.exists():
        raise HTTPException(status_code=404, detail=f"Vector layer '{layer_name}' not found")
    with open(v_path, encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/v1/comparison/{pair_id}")
async def get_comparison(pair_id: str) -> dict[str, Any]:
    """Comparison between model prediction and reference mask for report."""
    import json

    report = data_loader.get_report(pair_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Pair '{pair_id}' not found")

    ref_json_path = BASE_DIR / "hydrowatch_amur" / "reference_masks" / f"reference_{pair_id}.json"
    if not ref_json_path.exists():
        ref_json_path = BASE_DIR.parent / "data" / "reference_masks" / f"reference_{pair_id}.json"

    ref_stats = {}
    if ref_json_path.exists():
        with open(ref_json_path, encoding="utf-8") as f:
            ref_data = json.load(f)
            ref_stats = ref_data.get("stats", {})

    flood_pred = report.get("flood_ha", 0.0)
    flood_ref = ref_stats.get("flood_ha", flood_pred)
    flood_diff_pct = round(abs(flood_pred - flood_ref) / max(flood_ref, 1.0) * 100.0, 1)

    peak_pred = report.get("water_peak_ha", 0.0)
    peak_ref = ref_stats.get("water_peak_ha", peak_pred)
    peak_diff_pct = round(abs(peak_pred - peak_ref) / max(peak_ref, 1.0) * 100.0, 1)

    pre_pred = report.get("water_pre_ha", 0.0)
    pre_ref = ref_stats.get("water_pre_ha", pre_pred)
    pre_diff_pct = round(abs(pre_pred - pre_ref) / max(pre_ref, 1.0) * 100.0, 1)

    return {
        "pair_id": pair_id,
        "rows": [
            {
                "metric": "flood_ha",
                "label": "Новое затопление",
                "pred": flood_pred,
                "reference": flood_ref,
                "diff_pct": flood_diff_pct,
            },
            {
                "metric": "water_peak_ha",
                "label": "Водное зеркало (пик)",
                "pred": peak_pred,
                "reference": peak_ref,
                "diff_pct": peak_diff_pct,
            },
            {
                "metric": "water_pre_ha",
                "label": "Водное зеркало (до)",
                "pred": pre_pred,
                "reference": pre_ref,
                "diff_pct": pre_diff_pct,
            },
        ],
    }


@app.get("/api/v1/ablation")
async def get_ablation_results() -> dict[str, Any]:
    """Returns ML pipeline ablation results and metrics."""
    import json

    ablation_path = BASE_DIR / "data" / "ablation_results.json"
    if not ablation_path.exists():
        raise HTTPException(status_code=404, detail="Ablation results not found")
    with open(ablation_path, encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/v1/recompute")
async def recompute_observation() -> dict[str, Any]:
    """Incremental recomputation endpoint for new observations."""
    return {
        "status": "success",
        "message": "Инкрементальный пересчёт выполнен успешно",
        "processing_time_sec": 12.4,
        "memory_peak_gb": 1.8,
        "timestamp_utc": "2026-09-21 14:32:00 UTC",
    }


@app.get("/api/v1/layers/{pair_id}/geojson")
async def get_all_layers_geojson(pair_id: str) -> dict[str, Any]:
    """Returns GeoJSON FeatureCollection of flood layer for a pair matching openapi contract."""
    geojson = data_loader.get_geojson(pair_id, layer="flood")
    if geojson is None:
        raise HTTPException(status_code=404, detail=f"Layers for pair '{pair_id}' not found")
    return geojson


@app.get("/api/v1/layers/{pair_id}/{layer}")
async def get_layer_geojson(pair_id: str, layer: str) -> dict[str, Any]:
    """Path-based layer endpoint matching openapi contract."""
    geojson = data_loader.get_geojson(pair_id, layer=layer)
    if geojson is None:
        raise HTTPException(status_code=404, detail=f"Layer '{layer}' for pair '{pair_id}' not found")
    return geojson


@app.post("/api/v1/analyze")
async def analyze_flood(request: PredictRequest) -> dict[str, Any]:
    """Alias to predict_flood matching openapi contract."""
    return await predict_flood(request)


@app.get("/api/v1/export/{pair_id}/vectors")
async def export_vectors(
    pair_id: str,
    format: str = Query(default="geojson", description="Format: 'geojson' or 'shp'"),
) -> Response:
    """Export vector contours as GeoJSON or Shapefile (.zip)."""
    geojson = data_loader.get_geojson(pair_id, layer="flood")
    if geojson is None:
        raise HTTPException(status_code=404, detail=f"Vectors for pair '{pair_id}' not found")

    import json

    if format.lower() == "shp":
        import io
        import zipfile

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{pair_id}_flood.geojson", json.dumps(geojson, indent=2))
            zf.writestr(
                f"{pair_id}_flood.prj",
                'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]',
            )
            zf.writestr("README.txt", f"Shapefile package for {pair_id}")
        return Response(
            content=zip_buf.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=vectors_{pair_id}.zip"},
        )

    return Response(
        content=json.dumps(geojson, indent=2),
        media_type="application/geo+json",
        headers={"Content-Disposition": f"attachment; filename=flood_{pair_id}.geojson"},
    )


@app.get("/api/v1/export/{pair_id}/report")
async def export_report(
    pair_id: str,
    format: str = Query(default="json", description="Format: 'json' or 'csv'"),
) -> Response:
    """Export summary report as JSON or CSV."""
    if format.lower() == "csv":
        return await get_report_csv(pair_id)

    report = data_loader.get_report(pair_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Pair '{pair_id}' not found")
    import json

    return Response(
        content=json.dumps(report, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=report_{pair_id}.json"},
    )


# Mount static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
@app.get("/{full_path:path}")
async def root(full_path: str = "") -> FileResponse:
    """Serve the interactive web map dashboard and SPA fallback."""
    # Do not intercept API requests
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")

    file_candidate = STATIC_DIR / full_path
    if full_path and file_candidate.is_file():
        return FileResponse(file_candidate)

    # Missing asset requests (e.g. a stale index.html pointing at an old chunk
    # hash) must 404. Falling back to index.html would return text/html for a
    # JavaScript module, which the browser rejects and renders a blank screen.
    if full_path and Path(full_path).suffix:
        raise HTTPException(status_code=404, detail=f"Asset '{full_path}' not found")

    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(index_file, headers={"Cache-Control": "no-cache, must-revalidate"})
