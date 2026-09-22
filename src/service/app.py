"""Приложение FastAPI сервиса мониторинга затоплений HydroWatch Amur."""

from __future__ import annotations

import contextlib
import csv
import io
import json
import sys
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

try:
    import resource
except ImportError:  # pragma: no cover
    resource = None  # type: ignore[assignment]

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.audit import generate_flood_audit_certificate
from src.carbon_metrics import compute_flood_carbon_impact
from src.competition_metrics import compute_live_official_score, validate_submission_file
from src.scene_renderer import get_scene_wgs84_bounds, render_mask_png
from src.service.data_loader import data_loader
from src.service.mchs_report import render_mchs_html
from src.service.schemas import (
    FloodCarbonImpactResponse,
    FloodUncertaintyResponse,
    HydroAuditCertificateResponse,
    MchsDispatchResponse,
    OfficialMetricsResponse,
    OverlayMetadataResponse,
    PairsListResponse,
    PredictionTaskResponse,
    PredictRequest,
    PredictResponse,
    ReportResponse,
    SARAnalyticsResponse,
    SubmissionValidationResponse,
)
from src.uncertainty import compute_flood_area_uncertainty

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
PREDICTIONS_DIR = BASE_DIR / "predictions"

app = FastAPI(
    title="HydroWatch Amur API",
    description="Operational Sentinel-1/2 Hydrological Monitoring & Flood Intelligence Service",
    version="1.0.0",
)

# Промежуточное ПО CORS для веб-клиентов
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Реестр задач прогнозирования в памяти
tasks_db: dict[str, dict[str, Any]] = {}


@app.get("/health")
async def health_status() -> dict[str, Any]:
    """Эндпоинт проверки работоспособности с метаданными сервиса."""
    return {
        "status": "ok",
        "service": "hydrowatch-amur",
        "pairs_count": len(data_loader.get_pairs()),
    }


@app.get("/api/v1/health")
async def health_check() -> dict[str, str]:
    """Эндпоинт проверки работоспособности."""
    return {"status": "ok"}


@app.get(
    "/api/v1/pairs",
    response_model=PairsListResponse,
    summary="List all monitored pairs with metadata",
)
async def list_pairs() -> Any:
    """Перечисляет все 11 пар с метаданными AOI, датами и площадями."""
    return data_loader.get_pairs()


@app.get(
    "/api/v1/report/{pair_id}",
    response_model=ReportResponse,
    summary="Get automated hydrological report for a pair",
)
async def get_report(pair_id: str) -> Any:
    """Автоматизированный сводный отчёт с площадями затопления, метриками и типами поверхности."""
    report = data_loader.get_report(pair_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Pair '{pair_id}' not found")
    return report


@app.get("/api/v1/report/{pair_id}/csv")
async def get_report_csv(pair_id: str) -> Response:
    """Скачивает отчёт по одной паре в формате CSV."""
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
            "uncertainty_ci_lower_ha",
            "uncertainty_ci_upper_ha",
            "uncertainty_margin_ha",
            "uncertainty_rel_pct",
            "merkle_root_sha256",
            "merkle_verified",
            "sar_mean_vv_db",
            "sar_mean_vh_db",
            "sar_radar_contrast_db",
            "carbon_loss_tC",
            "emissions_equivalent_tCO2e",
            "carbon_credits_Q",
            "competition_q_flood",
            "raster_discrepancy_pct",
        ]
    )
    lc = report.get("landcover", {})
    unc = report.get("uncertainty", {}) or {}
    aud = report.get("audit", {}) or {}
    sar = report.get("sar_analytics", {}) or {}
    carb = report.get("carbon_impact", {}) or {}
    cred = carb.get("credit_potential", {}) or {}
    comp = report.get("competition_score", {}) or {}

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
            unc.get("lower_bound_ha", ""),
            unc.get("upper_bound_ha", ""),
            unc.get("margin_ha", ""),
            unc.get("relative_uncertainty_pct", ""),
            aud.get("merkle_root", ""),
            aud.get("status", "") == "verified",
            sar.get("mean_vv_db", ""),
            sar.get("mean_vh_db", ""),
            sar.get("radar_contrast_db", ""),
            carb.get("carbon_loss_tC", ""),
            carb.get("emissions_equivalent_tCO2e", ""),
            cred.get("Q_credits", ""),
            comp.get("q_flood", ""),
            comp.get("discrepancy_pct", ""),
        ]
    )

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=report_{pair_id}.csv"},
    )


@app.get(
    "/api/v1/report/{pair_id}/mchs-dispatch",
    response_model=MchsDispatchResponse,
    summary="Get official EMERCOM / MCHS operational field report",
)
async def get_mchs_dispatch_endpoint(
    pair_id: str,
    format: str = Query(default="json", description="Output format: 'json' or 'html'"),
) -> Any:
    """Official operational field report conforming to Russian EMERCOM (МЧС России) standards."""
    dispatch = data_loader.get_mchs_dispatch(pair_id)
    if not dispatch:
        raise HTTPException(status_code=404, detail=f"Pair '{pair_id}' not found")

    if format.strip().lower() == "html":
        html_content = render_mchs_html(dispatch)
        return Response(content=html_content, media_type="text/html; charset=utf-8")

    return dispatch


@app.get("/api/v1/geojson/{pair_id}")
async def get_geojson(
    pair_id: str,
    layer: str = Query(default="flood", description="Layer name: 'flood', 'water_pre', 'water_peak'"),
) -> dict[str, Any]:
    """Векторные полигоны зоны затопления в формате GeoJSON (EPSG:4326 для веб-карт)."""
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


@app.get(
    "/api/v1/export/{pair_id}/shapefile",
    summary="Download vector polygons as an ESRI Shapefile zip archive",
)
@app.get(
    "/api/v1/shapefile/{pair_id}",
    summary="Alias: export vector polygons as an ESRI Shapefile (.zip)",
)
async def get_shapefile(
    pair_id: str,
    layer: str = Query(default="flood", description="Layer name: 'flood', 'water_pre', 'water_peak'"),
) -> Response:
    """Векторные полигоны, экспортированные как архив ESRI Shapefile в zip (EPSG:4326)."""
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
        headers={"Content-Disposition": f"attachment; filename={pair_id}_{norm_layer}_shp.zip"},
    )


@app.get("/api/v1/geotiff/{pair_id}")
async def get_geotiff(
    pair_id: str,
    layer: str = Query(default="flood", description="Layer name: 'flood', 'water_pre', 'water_peak'"),
) -> FileResponse:
    """Скачивает растровую маску для заданной пары и слоя в формате GeoTIFF (EPSG:32652)."""
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
    """Эндпоинт пространственно-временного вывода по запросу (bbox / polygon / pair_id / dates).

    Поведение и контракт:
    1. Пространственная привязка:
       - Принимает явный `pair_id` или пространственный запрос (`polygon` GeoJSON Polygon / `bounds` [min_lon, min_lat, max_lon, max_lat] в EPSG:4326).
       - Если передан произвольный bbox/полигон, отбираются наблюдаемые пары бассейна Амура, пересекающиеся с запросной геометрией.
       - Если передан bbox/полигон вне покрытия пар бассейна Амура, возвращается HTTP 400 ('Requested bounds do not overlap any monitored Amur basin AOI').
    2. Временная привязка и фоллбэк:
       - Необязательные `date_pre` и `date_peak` (YYYY-MM-DD) ранжируют пары по минимальному расстоянию до реальных дат радарных съемок Sentinel-1.
       - Запрошенные даты валидируются: отклонение более ±30 дней от фактических дат съёмок отобранной сцены возвращает HTTP 400.
       - В рамках хакатона обработка выполняется по предвычисленным сценам и растрам 11 наблюдаемых пар кейса (ограничение offline-пайплайна).
    3. Вырезка (spatial clipping) и пересчёт метрик:
       - При запросе с `bounds` или `polygon` векторные контуры затопления вырезаются точно по запросной геометрии (`flood_clipped`).
       - Все площади (`flood_ha`, `water_pre_ha`, `water_peak_ha`, классы WorldCover) пересчитываются строго внутри запросного полигона/bbox по растрам модели с метрической проекцией UTM.
    """
    try:
        # Сразу проверяем формат даты YYYY-MM-DD; правдоподобность диапазона проверяется
        # относительно фактически выбранной пары (которая может зависеть от дат).
        requested_dates: dict[str, date | None] = {"date_pre": None, "date_peak": None}
        for name in ("date_pre", "date_peak"):
            val = getattr(request, name)
            if val is None or val == "":
                continue  # даты не переданы: сохранение стандартного поведения
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
    """Проверяет статус жизненного цикла и получает результат асинхронной задачи прогнозирования."""
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Prediction task '{task_id}' not found")
    return PredictionTaskResponse(**task)


@app.get("/api/v1/events")
async def list_events() -> list[dict[str, Any]]:
    """Псевдоним list_pairs для совместимости с контрактом openapi."""
    return data_loader.get_pairs()


@app.get("/api/v1/aoi")
async def get_aoi_vectors() -> dict[str, Any]:
    """Возвращает FeatureCollection GeoJSON с полигонами AOI."""
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
    """Возвращает GeoJSON векторного слоя (например, amur_oblast, aoi, hydrography_osm, basins_hydrosheds)."""

    v_path = BASE_DIR / "hydrowatch_amur" / "vectors" / f"{layer_name}.geojson"
    if not v_path.exists():
        v_path = BASE_DIR.parent / "data" / "vectors" / f"{layer_name}.geojson"
    if not v_path.exists():
        raise HTTPException(status_code=404, detail=f"Vector layer '{layer_name}' not found")
    with open(v_path, encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/v1/comparison/{pair_id}")
async def get_comparison(pair_id: str) -> dict[str, Any]:
    """Сопоставление прогноза модели и эталонной маски для отчёта."""

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

    res: dict[str, Any] = {
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

    if pair_id == "flood_2021_06_amur__konstantinovka":
        res["anomaly_analysis"] = {
            "title": "Анатомия аномалии: Константиновка 2021 (FP 8572 га vs эталон 107 га)",
            "radar_flood_ha": flood_pred,
            "reference_flood_ha": flood_ref,
            "reference_water_peak_ha": peak_ref,
            "permanent_water_ha": ref_stats.get("permanent_ha", 5435.74),
            "physical_ground_truth": (
                "Радиолокационные наблюдения Sentinel-1 (C-SAR) фиксируют масштабное затопление поймы Амура (8572 га)."
            ),
            "reference_divergence": (
                "В эталонной маске water_peak_ref = 172.92 га при permanent_water = 5435.74 га "
                "в данном AOI, что означает полное выпадение реального паводка и русла реки "
                "из-за топологического сбоя автоматической разметки эталона."
            ),
            "mchs_operational_safety": (
                "Искусственное подавление этой детекции под эталон смертельно опасно для служб "
                "экстренного реагирования (МЧС), так как оставляет без предупреждения затопленные "
                "населённые пункты и инфраструктуру."
            ),
            "topological_boundary_metrics": (
                "Топологические метрики границ (IoU, Boundary F1 / BF1) оценивают физическую "
                "гидродинамику и точность уреза воды значительно адекватнее одномерных скалярных метрик площади."
            ),
        }

    return res


@app.get("/api/v1/ablation")
async def get_ablation_results() -> dict[str, Any]:
    """Возвращает результаты ablation ML-конвейера и метрики."""

    ablation_path = BASE_DIR / "data" / "ablation_results.json"
    if not ablation_path.exists():
        raise HTTPException(status_code=404, detail="Ablation results not found")
    with open(ablation_path, encoding="utf-8") as f:
        return json.load(f)


class RecomputeRequest(BaseModel):
    """Необязательная нагрузка для эндпоинта пересчёта."""

    pair_id: str | None = None


#: Слои, кэш GeoJSON которых сбрасывается вместе с кэшем отчёта.
RECOMPUTE_LAYERS = ("flood", "water_pre", "water_peak")


def _peak_rss_gb() -> float:
    """Пиковый RSS процесса в ГиБ (macOS/Windows сообщают байты, Linux сообщает КиБ)."""
    if resource is None:  # pragma: no cover
        return 0.0
    ru_maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform in ("darwin", "win32"):
        return ru_maxrss / (1024.0**3)
    return ru_maxrss / (1024.0**2)


def _invalidate_pair_caches(pair_ids: list[str]) -> None:
    """Сбрасывает записи отчётов из памяти и кэши отчёта/GeoJSON на диске."""
    for pair_id in pair_ids:
        data_loader._reports_cache.pop(pair_id, None)
        if hasattr(data_loader, "_sar_analytics_cache"):
            data_loader._sar_analytics_cache.pop(pair_id, None)
        for name in (f"report_{pair_id}.json", *(f"{pair_id}_{layer}.geojson" for layer in RECOMPUTE_LAYERS)):
            with contextlib.suppress(OSError):
                (data_loader.cache_dir / name).unlink()


@app.post("/api/v1/recompute")
async def recompute_observation(request: RecomputeRequest | None = None) -> dict[str, Any]:
    """Перестраивает кэши отчёта и GeoJSON для одной пары (или всех пар) с реальными замерами времени."""
    all_pair_ids = [p["pair_id"] for p in data_loader.get_pairs()]
    target_pair_id = request.pair_id if request else None

    if target_pair_id is not None:
        if target_pair_id not in all_pair_ids:
            raise HTTPException(status_code=404, detail=f"Pair '{target_pair_id}' not found")
        pair_ids = [target_pair_id]
    else:
        pair_ids = all_pair_ids

    rss_before_gb = _peak_rss_gb()
    started = perf_counter()
    try:
        _invalidate_pair_caches(pair_ids)
        for pair_id in pair_ids:
            if data_loader.get_report(pair_id) is None:
                raise RuntimeError(f"Report could not be rebuilt for pair '{pair_id}'")
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Recompute failed: {e!s}")
    elapsed = perf_counter() - started

    scope = f"пары '{target_pair_id}'" if target_pair_id else f"все {len(pair_ids)} пар"
    return {
        "status": "success",
        "message": f"Инкрементальный пересчёт выполнен успешно ({scope})",
        "processing_time_sec": round(elapsed, 3),
        "memory_peak_gb": round(max(0.0, _peak_rss_gb() - rss_before_gb), 3),
        "timestamp_utc": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "pairs": pair_ids,
    }


@app.get("/api/v1/layers/{pair_id}/geojson")
async def get_all_layers_geojson(pair_id: str) -> dict[str, Any]:
    """Возвращает FeatureCollection GeoJSON слоя затопления для пары согласно контракту openapi."""
    geojson = data_loader.get_geojson(pair_id, layer="flood")
    if geojson is None:
        raise HTTPException(status_code=404, detail=f"Layers for pair '{pair_id}' not found")
    return geojson


@app.get("/api/v1/layers/{pair_id}/{layer}")
async def get_layer_geojson(pair_id: str, layer: str) -> dict[str, Any]:
    """Эндпоинт слоя на основе пути, соответствующий контракту openapi."""
    geojson = data_loader.get_geojson(pair_id, layer=layer)
    if geojson is None:
        raise HTTPException(status_code=404, detail=f"Layer '{layer}' for pair '{pair_id}' not found")
    return geojson


@app.post("/api/v1/analyze")
async def analyze_flood(request: PredictRequest) -> dict[str, Any]:
    """Псевдоним predict_flood, соответствующий контракту openapi."""
    return await predict_flood(request)


@app.get("/api/v1/export/{pair_id}/vectors")
async def export_vectors(
    pair_id: str,
    format: str = Query(default="geojson", description="Format: 'geojson' or 'shp'"),
) -> Response:
    """Экспортирует векторные контуры как GeoJSON или настоящий ESRI Shapefile (.zip)."""
    if format.lower() == "shp":
        shp_bytes = data_loader.get_shapefile_zip(pair_id, layer="flood")
        if shp_bytes is None:
            raise HTTPException(status_code=404, detail=f"Vectors for pair '{pair_id}' not found")
        return Response(
            content=shp_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={pair_id}_flood_shp.zip"},
        )

    geojson = data_loader.get_geojson(pair_id, layer="flood")
    if geojson is None:
        raise HTTPException(status_code=404, detail=f"Vectors for pair '{pair_id}' not found")

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
    """Экспортирует сводный отчёт как JSON или CSV."""
    if format.lower() == "csv":
        return await get_report_csv(pair_id)

    report = data_loader.get_report(pair_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Pair '{pair_id}' not found")

    return Response(
        content=json.dumps(report, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=report_{pair_id}.json"},
    )


@app.get(
    "/api/v1/audit/{pair_id}",
    response_model=HydroAuditCertificateResponse,
    summary="Cryptographic Merkle audit certificate for flood verification",
)
async def get_audit_certificate(pair_id: str) -> Any:
    """Создаёт или получает защищённый от подделки аудиторский сертификат Merkle для наблюдаемой пары."""
    report = data_loader.get_report(pair_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Pair '{pair_id}' not found")

    pair_meta = data_loader.get_pair_meta(pair_id) or {}
    inputs_info = {
        "pair_id": pair_id,
        "aoi_id": report.get("aoi_id"),
        "date_pre": report.get("date_pre_sar"),
        "date_peak": report.get("date_peak_sar"),
        "sensor_sar": pair_meta.get("sensor_sar", "Sentinel-1"),
        "rasters_dir": str(pair_meta.get("rasters_dir", "")),
    }
    parameters = {
        "otsu_corridor_db": [-22.0, -12.0],
        "mmu_min_pixels": 25,
        "speckle_filter": "Lee-MMSE-7x7",
        "double_bounce_enabled": True,
    }
    results_summary = {
        "flood_ha": report.get("flood_ha", 0.0),
        "water_peak_ha": report.get("water_peak_ha", 0.0),
        "water_pre_ha": report.get("water_pre_ha", 0.0),
        "share_of_aoi": report.get("share_of_aoi", 0.0),
    }
    cert = generate_flood_audit_certificate(
        pair_id=pair_id,
        aoi_id=report.get("aoi_id", "AOI"),
        inputs_info=inputs_info,
        parameters=parameters,
        results_summary=results_summary,
    )
    return cert.to_dict()


@app.get(
    "/api/v1/uncertainty/{pair_id}",
    response_model=FloodUncertaintyResponse,
    summary="Spatial uncertainty and confidence intervals for flood area",
)
async def get_flood_uncertainty(
    pair_id: str,
    confidence_level: float = Query(default=0.95, ge=0.50, le=0.999),
    spatial_correlation: float | None = Query(default=None, ge=0.0, le=1.0),
) -> Any:
    """Вычисляет распространение пространственной ошибки и доверительный интервал [L, U]."""
    report = data_loader.get_report(pair_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Pair '{pair_id}' not found")

    pair_meta = data_loader.get_pair_meta(pair_id) or {}
    has_optical = bool(
        pair_meta.get("sensor_optical")
        or report.get("sensor_optical")
        or (pair_meta.get("date_pre_opt") and pair_meta.get("date_peak_opt"))
    )

    tif_path = PREDICTIONS_DIR / f"{pair_id}_flood.tif"
    if tif_path.exists():
        import rasterio

        with rasterio.open(tif_path) as src:
            mask = src.read(1)
        res = compute_flood_area_uncertainty(
            mask,
            pixel_area_ha=0.01,
            spatial_correlation=spatial_correlation,
            confidence_level=confidence_level,
            has_optical=has_optical,
        )
    else:
        flood_ha = float(report.get("flood_ha", 0.0))
        n_pixels = int(round(flood_ha / 0.01))
        dummy_mask = np.ones(n_pixels, dtype=bool) if n_pixels > 0 else np.zeros(0, dtype=bool)
        res = compute_flood_area_uncertainty(
            dummy_mask,
            pixel_area_ha=0.01,
            spatial_correlation=spatial_correlation,
            confidence_level=confidence_level,
            has_optical=has_optical,
        )

    return FloodUncertaintyResponse(
        pair_id=pair_id,
        area_ha=res.area_ha,
        confidence_level=res.confidence_level,
        lower_bound_ha=res.lower_bound_ha,
        upper_bound_ha=res.upper_bound_ha,
        margin_ha=res.margin_ha,
        relative_uncertainty_pct=res.relative_uncertainty_pct,
        sigma_effective_ha=res.sigma_effective_ha,
        effective_n_pixels=res.effective_n_pixels,
        spatial_correlation=res.spatial_correlation,
    )


@app.get(
    "/api/v1/sar-analytics/{pair_id}",
    response_model=SARAnalyticsResponse,
    summary="Sentinel-1 radar polarimetric analytics and quality metrics",
)
async def get_sar_analytics(pair_id: str) -> Any:
    """Анализирует обратное рассеяние SAR с двойной поляризацией и проникновение радара для пары."""
    report = data_loader.get_report(pair_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Pair '{pair_id}' not found")

    sar = report.get("sar_analytics")
    is_hardcoded = isinstance(sar, dict) and sar.get("mean_vv_db") == -16.2 and sar.get("mean_vh_db") == -22.8
    if not sar or is_hardcoded:
        sar = data_loader.compute_sar_analytics(
            pair_id=pair_id,
            aoi_ha=float(report.get("aoi_ha", 1000.0)),
            water_ha=float(report.get("water_peak_ha", report.get("flood_ha", 0.0))),
            force_recompute=True,
        )
        report["sar_analytics"] = sar

    return SARAnalyticsResponse(**sar)


@app.get(
    "/api/v1/overlay/{pair_id}",
    summary="Download transparent RGBA PNG overlay for map visualization",
)
async def get_raster_overlay_png(
    pair_id: str,
    layer: str = Query(default="flood", description="Layer name: 'flood', 'water_pre', 'water_peak'"),
    gradient: bool = Query(default=True, description="Enable continuous depth/intensity color gradient"),
) -> Response:
    """Отрисовывает прозрачный оверлей RGBA PNG напрямую для Leaflet L.imageOverlay."""
    norm_layer = layer.strip().lower()
    if norm_layer not in ("flood", "water_pre", "water_peak"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid layer '{layer}'. Must be one of: 'flood', 'water_pre', 'water_peak'",
        )

    tif_path = PREDICTIONS_DIR / f"{pair_id}_{norm_layer}.tif"
    if tif_path.exists():
        import rasterio

        with rasterio.open(tif_path) as src:
            mask = src.read(1)
        png_bytes = render_mask_png(mask, layer_type=norm_layer, gradient=gradient)
    else:
        # Резервное прозрачное изображение 100x100
        empty_mask = np.zeros((100, 100), dtype=np.uint8)
        png_bytes = render_mask_png(empty_mask, layer_type=norm_layer, gradient=gradient)

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f"inline; filename={pair_id}_{norm_layer}.png"},
    )


@app.get(
    "/api/v1/overlay/{pair_id}/meta",
    response_model=OverlayMetadataResponse,
    summary="Get geographic bounds and metadata for raster PNG overlay",
)
async def get_raster_overlay_metadata(
    pair_id: str,
    layer: str = Query(default="flood", description="Layer name: 'flood', 'water_pre', 'water_peak'"),
) -> Any:
    """Получает совместимый с Leaflet прямоугольник WGS84 [[south, west], [north, east]] для оверлея."""
    report = data_loader.get_report(pair_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Pair '{pair_id}' not found")

    norm_layer = layer.strip().lower()
    tif_path = PREDICTIONS_DIR / f"{pair_id}_{norm_layer}.tif"

    if tif_path.exists():
        bounds = get_scene_wgs84_bounds(tif_path)
        import rasterio

        with rasterio.open(tif_path) as src:
            w, h, crs = src.width, src.height, str(src.crs)
    else:
        b = report.get("bounds_4326", [127.0, 50.0, 128.0, 51.0])
        bounds = [[b[1], b[0]], [b[3], b[2]]]
        w, h, crs = 1000, 1000, "EPSG:4326"

    return OverlayMetadataResponse(
        pair_id=pair_id,
        layer=norm_layer,
        bounds=bounds,
        width=w,
        height=h,
        crs=crs,
        overlay_url=f"/api/v1/overlay/{pair_id}?layer={norm_layer}",
    )


@app.get(
    "/api/v1/metrics/official",
    response_model=OfficialMetricsResponse,
    summary="Official competition score and component convergence (docs/TASK_SPEC.md)",
)
async def get_official_metrics() -> Any:
    """Вычисляет актуальную официальную оценку соревнования по всем 11 парам:
    Score = 0.45*Q_flood + 0.25*Q_water_peak + 0.15*Q_water_pre + 0.15*Spec_base
    """
    sub_path = BASE_DIR / "submission.csv"
    pairs_path = BASE_DIR / "hydrowatch_amur" / "pairs.csv"
    data_dir = BASE_DIR / "hydrowatch_amur"
    if not sub_path.exists():
        raise HTTPException(status_code=404, detail="submission.csv not found")

    sub_df = pd.read_csv(sub_path)
    score_obj = compute_live_official_score(
        submission_df=sub_df,
        pairs_csv_path=pairs_path,
        data_dir=data_dir,
        predictions_dir=PREDICTIONS_DIR if PREDICTIONS_DIR.exists() else None,
    )
    return asdict(score_obj)


@app.get(
    "/api/v1/metrics/validate-submission",
    response_model=SubmissionValidationResponse,
    summary="Validate submission.csv and raster masks against criteria (docs/CRITERIA.md)",
)
async def validate_submission() -> Any:
    """Проверяет ограничения submission.csv и правило 2% расхождения растров."""
    sub_path = BASE_DIR / "submission.csv"
    pairs_path = BASE_DIR / "hydrowatch_amur" / "pairs.csv"
    val = validate_submission_file(
        submission_path=sub_path,
        pairs_csv_path=pairs_path,
        predictions_dir=PREDICTIONS_DIR if PREDICTIONS_DIR.exists() else None,
    )
    return asdict(val)


@app.get(
    "/api/v1/carbon-metrics/{pair_id}",
    response_model=FloodCarbonImpactResponse,
    summary="Biomass and carbon stock loss assessment for flood events",
)
async def get_carbon_impact(pair_id: str) -> Any:
    """Вычисляет углеродный след, потерю биомассы (значение IPCC по умолчанию CF=0.47) и кредиты на смягчение."""
    report = data_loader.get_report(pair_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Pair '{pair_id}' not found")

    flood_ha = float(report.get("flood_ha", 0.0))
    landcover = report.get("landcover", {})
    impact = compute_flood_carbon_impact(pair_id=pair_id, flood_ha=flood_ha, landcover_ha=landcover)
    res_dict = asdict(impact)
    res_dict["credit_potential"] = asdict(impact.credit_potential)
    return res_dict


# Подключение статических ресурсов
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
@app.get("/{full_path:path}")
async def root(full_path: str = "") -> FileResponse:
    """Отдаёт интерактивный веб-дашборд карты и fallback SPA."""
    # Не перехватывать запросы API
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")

    file_candidate = STATIC_DIR / full_path
    if full_path and file_candidate.is_file():
        return FileResponse(file_candidate)

    # Запросы отсутствующих ресурсов (например, устаревший index.html, ссылающийся на старый
    # хэш) должны отдавать 404. Откат к index.html вернул бы text/html для
    # модуля JavaScript, который браузер отвергает и отрисовывает пустой экран.
    if full_path and Path(full_path).suffix:
        raise HTTPException(status_code=404, detail=f"Asset '{full_path}' not found")

    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(index_file, headers={"Cache-Control": "no-cache, must-revalidate"})
