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
    """Spatial-temporal inference endpoint accepting bounds / pair_id."""
    try:
        # Validate optional requested dates (YYYY-MM-DD) and plausibility (±30 days
        # around the pair's scene dates) before any cache lookup
        requested_dates: dict[str, date | None] = {"date_pre": None, "date_peak": None}
        pair_meta = data_loader.get_pair_meta(request.pair_id) if request.pair_id else None
        for name in ("date_pre", "date_peak"):
            val = getattr(request, name)
            if val is None or val == "":
                continue  # dates omitted: behave exactly as before
            try:
                requested_date = datetime.strptime(val, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Некорректная дата {name}: '{val}' (ожидается YYYY-MM-DD)")
            requested_dates[name] = requested_date
        result = data_loader.predict_spatial_temporal(
            pair_id=request.pair_id,
            bounds=request.bounds,
            date_pre=request.date_pre,
            date_peak=request.date_peak,
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


# Mount static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root() -> FileResponse:
    """Serve the interactive web map dashboard."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(index_file)
