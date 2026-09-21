"""FastAPI application for HydroWatch Amur Flood Monitoring Service."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.service.data_loader import data_loader

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"

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


class PredictRequest(BaseModel):
    pair_id: Optional[str] = Field(default=None, description="Pair identifier, e.g. flood_2019_07_amur__blagoveshchensk")
    bounds: Optional[List[float]] = Field(default=None, description="[min_lon, min_lat, max_lon, max_lat] in EPSG:4326")
    date_pre: Optional[str] = Field(default=None, description="Pre-flood reference date (YYYY-MM-DD)")
    date_peak: Optional[str] = Field(default=None, description="Peak flood date (YYYY-MM-DD)")


@app.get("/api/v1/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/api/v1/pairs")
async def list_pairs() -> List[Dict[str, Any]]:
    """Lists all 11 pairs with AOI metadata, dates, and areas."""
    return data_loader.get_pairs()


@app.get("/api/v1/report/{pair_id}")
async def get_report(pair_id: str) -> Dict[str, Any]:
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
    writer.writerow([
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
    ])
    lc = report.get("landcover", {})
    writer.writerow([
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
    ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=report_{pair_id}.csv"},
    )


@app.get("/api/v1/geojson/{pair_id}")
async def get_geojson(
    pair_id: str,
    layer: str = Query(default="flood", description="Layer name: 'flood', 'water_pre', 'water_peak'"),
) -> Dict[str, Any]:
    """Vector polygons of flood zone in GeoJSON format (EPSG:4326 for web maps)."""
    geojson = data_loader.get_geojson(pair_id, layer=layer)
    if geojson is None:
        raise HTTPException(status_code=404, detail=f"GeoJSON for pair '{pair_id}' (layer: {layer}) not found")
    return geojson


@app.post("/api/v1/predict")
async def predict_flood(request: PredictRequest) -> Dict[str, Any]:
    """Spatial-temporal inference endpoint accepting bounds / pair_id."""
    try:
        result = data_loader.predict_spatial_temporal(
            pair_id=request.pair_id,
            bounds=request.bounds,
            date_pre=request.date_pre,
            date_peak=request.date_peak,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal prediction error: {str(e)}")


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
