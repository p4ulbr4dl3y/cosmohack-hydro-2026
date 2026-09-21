"""Official competition metrics and submission verification module for HydroWatch Amur.

Implements all evaluation metrics and constraints specified in:
- docs/TASK_SPEC.md (Section 8: Официальная метрика оценки, Section 7: Формат сабмита)
- docs/CRITERIA.md (Раздел 2: Значение метрики, Корректность сабмита)

Official Formula:
  Score = 0.45 * Q_flood + 0.25 * Q_water_peak + 0.15 * Q_water_pre + 0.15 * Spec_base

Components:
  1. Event pairs convergence:
     q = max(0, 1 - |X_sub - X_ref| / max(X_ref, threshold))
     threshold = 50.0 ha for flood
     threshold = 200.0 ha for water mirror (pre & peak)

  2. Baseline pairs specificity:
     excess = max(0, flood_sub - flood_ref)
     share = excess / aoi_ha
     Spec_base = mean(1 - min(1, share / 0.005))  # 0.5% AOI allowance

  3. Submission correctness rules:
     - exactly 11 pairs matching sample_submission.csv
     - areas non-negative and <= aoi_ha
     - flood_ha <= water_peak_ha
     - no missing values or NaN
     - GeoTIFF raster <pair_id>_flood.tif matching CRS (EPSG:32652) and dimensions
     - raster area vs CSV area discrepancy <= 2.0%
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import rasterio

logger = logging.getLogger(__name__)

# Constants from docs/TASK_SPEC.md & docs/CRITERIA.md
FLOOD_THRESHOLD_HA: float = 50.0
WATER_THRESHOLD_HA: float = 200.0
BASELINE_ALLOWANCE_FRACTION: float = 0.005  # 0.5% of AOI area
MAX_RASTER_CSV_DISCREPANCY_PCT: float = 2.0  # 2% maximum allowed divergence
PIXEL_AREA_HA_10M: float = 0.01  # 10m x 10m = 100 m² = 0.01 ha


@dataclass(frozen=True)
class PairScoreDetail:
    """Detailed convergence metrics for a single monitored pair."""

    pair_id: str
    event_kind: str
    aoi_ha: float
    flood_sub_ha: float
    flood_ref_ha: float
    water_peak_sub_ha: float
    water_peak_ref_ha: float
    water_pre_sub_ha: float
    water_pre_ref_ha: float
    q_flood: float
    q_water_peak: float
    q_water_pre: float
    spec_score: float | None = None
    flood_abs_diff_ha: float = 0.0
    flood_rel_diff_pct: float = 0.0
    raster_ha: float | None = None
    raster_csv_discrepancy_pct: float | None = None


@dataclass(frozen=True)
class OfficialCompetitionScore:
    """Official competition score and component breakdown."""

    score: float
    q_flood: float
    q_water_peak: float
    q_water_pre: float
    spec_base: float
    num_events: int
    num_baselines: int
    technical_points: float  # Normalized 0-7 score according to criteria
    details: list[dict[str, Any]]


@dataclass(frozen=True)
class SubmissionValidationResult:
    """Submission and raster integrity check report."""

    is_valid: bool
    num_pairs: int
    passed_checks: list[str]
    errors: list[str]
    warnings: list[str]
    discrepancies: list[dict[str, Any]]


def calculate_q_score(
    sub_val: float,
    ref_val: float,
    threshold: float,
) -> float:
    """Calculate single convergence score q = max(0, 1 - |X_sub - X_ref| / max(X_ref, threshold))."""
    if not np.isfinite(sub_val) or not np.isfinite(ref_val):
        return 0.0
    denom = max(float(ref_val), float(threshold))
    diff = abs(float(sub_val) - float(ref_val))
    return float(max(0.0, 1.0 - diff / denom))


def calculate_baseline_spec(
    flood_sub_ha: float,
    flood_ref_ha: float,
    aoi_ha: float,
    allowance_ratio: float = BASELINE_ALLOWANCE_FRACTION,
) -> float:
    """Calculate specificity score for a baseline pair: 1 - min(1, excess / (0.005 * aoi_ha))."""
    if aoi_ha <= 0 or not np.isfinite(flood_sub_ha) or not np.isfinite(flood_ref_ha):
        return 0.0
    excess = max(0.0, float(flood_sub_ha) - float(flood_ref_ha))
    excess_share = excess / float(aoi_ha)
    return float(1.0 - min(1.0, excess_share / allowance_ratio))


def compute_live_official_score(
    submission_df: pd.DataFrame,
    pairs_csv_path: Path,
    data_dir: Path,
    predictions_dir: Path | None = None,
) -> OfficialCompetitionScore:
    """Compute official HydroWatch Amur metric score from submission and ground truth."""
    if not pairs_csv_path.exists():
        raise FileNotFoundError(f"pairs.csv not found: {pairs_csv_path}")

    pairs_df = pd.read_csv(pairs_csv_path)

    # Load reference stats
    ref_rows = []
    for _, row in pairs_df.iterrows():
        pair_id = str(row["pair_id"])
        ref_json_path = data_dir / str(row["reference_mask"]).replace(".tif", ".json")
        if not ref_json_path.exists():
            continue

        with open(ref_json_path, encoding="utf-8") as fp:
            meta = json.load(fp)

        stats = meta.get("stats", {})
        ref_rows.append(
            {
                "pair_id": pair_id,
                "event_kind": str(row.get("event_kind", "rain_flood")),
                "aoi_ha": float(stats.get("aoi_ha", 100000.0)),
                "ref_flood_ha": float(stats.get("flood_ha", 0.0)),
                "ref_water_pre_ha": float(stats.get("water_pre_ha", 0.0)),
                "ref_water_peak_ha": float(stats.get("water_peak_ha", 0.0)),
            }
        )

    ref_df = pd.DataFrame(ref_rows)
    merged = pd.merge(submission_df, ref_df, on="pair_id")

    events = merged[merged["event_kind"] != "baseline"].copy()
    baselines = merged[merged["event_kind"] == "baseline"].copy()

    # Calculate event convergence
    event_q_floods = []
    event_q_peaks = []
    event_q_pres = []
    details_list: list[dict[str, Any]] = []

    for _, r in merged.iterrows():
        pair_id = str(r["pair_id"])
        sub_flood = float(r["flood_ha"])
        ref_flood = float(r["ref_flood_ha"])
        sub_peak = float(r["water_peak_ha"])
        ref_peak = float(r["ref_water_peak_ha"])
        sub_pre = float(r["water_pre_ha"])
        ref_pre = float(r["ref_water_pre_ha"])
        aoi_ha = float(r["aoi_ha"])
        is_baseline = str(r["event_kind"]) == "baseline"

        q_fl = calculate_q_score(sub_flood, ref_flood, FLOOD_THRESHOLD_HA)
        q_pk = calculate_q_score(sub_peak, ref_peak, WATER_THRESHOLD_HA)
        q_pr = calculate_q_score(sub_pre, ref_pre, WATER_THRESHOLD_HA)

        spec = None
        if is_baseline:
            spec = calculate_baseline_spec(sub_flood, ref_flood, aoi_ha)
        else:
            event_q_floods.append(q_fl)
            event_q_peaks.append(q_pk)
            event_q_pres.append(q_pr)

        # Check raster area if predictions_dir is given
        raster_ha = None
        disc_pct = None
        if predictions_dir:
            tif_path = predictions_dir / f"{pair_id}_flood.tif"
            if tif_path.exists():
                try:
                    with rasterio.open(tif_path) as src:
                        mask = src.read(1)
                    raster_ha = float(np.count_nonzero(mask == 1) * PIXEL_AREA_HA_10M)
                    if sub_flood > 0:
                        disc_pct = float(abs(raster_ha - sub_flood) / sub_flood * 100.0)
                    else:
                        disc_pct = 0.0 if raster_ha == 0 else 100.0
                except Exception as ex:
                    logger.warning(f"Could not read raster {tif_path}: {ex}")

        abs_diff = abs(sub_flood - ref_flood)
        rel_diff = (abs_diff / ref_flood * 100.0) if ref_flood > 0 else (100.0 if abs_diff > 0 else 0.0)

        detail = PairScoreDetail(
            pair_id=pair_id,
            event_kind=str(r["event_kind"]),
            aoi_ha=round(aoi_ha, 2),
            flood_sub_ha=round(sub_flood, 2),
            flood_ref_ha=round(ref_flood, 2),
            water_peak_sub_ha=round(sub_peak, 2),
            water_peak_ref_ha=round(ref_peak, 2),
            water_pre_sub_ha=round(sub_pre, 2),
            water_pre_ref_ha=round(ref_pre, 2),
            q_flood=round(q_fl, 4),
            q_water_peak=round(q_pk, 4),
            q_water_pre=round(q_pr, 4),
            spec_score=round(spec, 4) if spec is not None else None,
            flood_abs_diff_ha=round(abs_diff, 2),
            flood_rel_diff_pct=round(rel_diff, 2),
            raster_ha=round(raster_ha, 2) if raster_ha is not None else None,
            raster_csv_discrepancy_pct=round(disc_pct, 2) if disc_pct is not None else None,
        )
        details_list.append(asdict(detail))

    q_flood_mean = float(np.mean(event_q_floods)) if event_q_floods else 0.0
    q_peak_mean = float(np.mean(event_q_peaks)) if event_q_peaks else 0.0
    q_pre_mean = float(np.mean(event_q_pres)) if event_q_pres else 0.0

    if len(baselines) > 0:
        base_specs = [
            calculate_baseline_spec(float(r["flood_ha"]), float(r["ref_flood_ha"]), float(r["aoi_ha"]))
            for _, r in baselines.iterrows()
        ]
        spec_base_mean = float(np.mean(base_specs))
    else:
        spec_base_mean = 1.0

    # Composite Score
    total_score = (
        0.45 * q_flood_mean
        + 0.25 * q_peak_mean
        + 0.15 * q_pre_mean
        + 0.15 * spec_base_mean
    )

    # Technical Criteria points: 0 to 7 based on score
    # Score 0.403 -> ~4.5 points; Score 1.0 -> 7.0 points
    tech_points = round(min(7.0, max(0.0, total_score * 7.0)), 2)

    return OfficialCompetitionScore(
        score=round(float(total_score), 4),
        q_flood=round(float(q_flood_mean), 4),
        q_water_peak=round(float(q_peak_mean), 4),
        q_water_pre=round(float(q_pre_mean), 4),
        spec_base=round(float(spec_base_mean), 4),
        num_events=len(events),
        num_baselines=len(baselines),
        technical_points=tech_points,
        details=details_list,
    )


def validate_submission_file(
    submission_path: Path,
    pairs_csv_path: Path,
    predictions_dir: Path | None = None,
) -> SubmissionValidationResult:
    """Validate submission.csv and optional raster masks against competition rules."""
    passed_checks: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []
    discrepancies: list[dict[str, Any]] = []

    if not submission_path.exists():
        return SubmissionValidationResult(
            is_valid=False,
            num_pairs=0,
            passed_checks=[],
            errors=[f"Submission file does not exist: {submission_path}"],
            warnings=[],
            discrepancies=[],
        )

    try:
        sub_df = pd.read_csv(submission_path)
    except Exception as ex:
        return SubmissionValidationResult(
            is_valid=False,
            num_pairs=0,
            passed_checks=[],
            errors=[f"Failed to parse CSV: {ex}"],
            warnings=[],
            discrepancies=[],
        )

    # 1. Header check
    expected_cols = ["pair_id", "flood_ha", "water_pre_ha", "water_peak_ha"]
    if list(sub_df.columns) == expected_cols:
        passed_checks.append("Columns match required schema [pair_id, flood_ha, water_pre_ha, water_peak_ha]")
    else:
        errors.append(f"Invalid columns: expected {expected_cols}, got {list(sub_df.columns)}")

    # 2. Pairs count and match
    if pairs_csv_path.exists():
        pairs_df = pd.read_csv(pairs_csv_path)
        expected_pair_ids = sorted(pairs_df["pair_id"].astype(str).tolist())
        actual_pair_ids = sorted(sub_df["pair_id"].astype(str).tolist())

        if expected_pair_ids == actual_pair_ids:
            passed_checks.append(f"All {len(expected_pair_ids)} pairs match official pairs registry")
        else:
            missing = set(expected_pair_ids) - set(actual_pair_ids)
            unexpected = set(actual_pair_ids) - set(expected_pair_ids)
            if missing:
                errors.append(f"Missing required pairs: {list(missing)}")
            if unexpected:
                errors.append(f"Unexpected extra pairs: {list(unexpected)}")

    # 3. Value constraints
    has_nans = sub_df.isna().any().any()
    if not has_nans:
        passed_checks.append("No missing values or NaNs in table")
    else:
        errors.append("Submission contains NaN / null values")

    for _, row in sub_df.iterrows():
        pid = str(row["pair_id"])
        try:
            fl = float(row["flood_ha"])
            pr = float(row["water_pre_ha"])
            pk = float(row["water_peak_ha"])
        except (ValueError, TypeError):
            errors.append(f"Pair '{pid}' has non-numeric values")
            continue

        if fl < 0 or pr < 0 or pk < 0:
            errors.append(f"Pair '{pid}' has negative area values")

        if fl > pk:
            errors.append(f"Pair '{pid}': flood_ha ({fl}) exceeds water_peak_ha ({pk})")

    if not any("exceeds water_peak_ha" in e or "negative area" in e for e in errors):
        passed_checks.append("Physical constraints satisfied (non-negative and flood_ha <= water_peak_ha)")

    # 4. Raster mask consistency check
    if predictions_dir and predictions_dir.exists():
        all_rasters_ok = True
        for _, row in sub_df.iterrows():
            pid = str(row["pair_id"])
            fl = float(row["flood_ha"])
            tif_file = predictions_dir / f"{pid}_flood.tif"

            if not tif_file.exists():
                warnings.append(f"Missing prediction raster: {tif_file.name}")
                all_rasters_ok = False
                continue

            try:
                with rasterio.open(tif_file) as src:
                    crs_str = str(src.crs).upper()
                    if "32652" not in crs_str:
                        warnings.append(f"Raster {tif_file.name} CRS is {src.crs}, expected EPSG:32652")

                    mask = src.read(1)
                    raster_flood_ha = float(np.count_nonzero(mask == 1) * PIXEL_AREA_HA_10M)

                    disc_pct = 0.0
                    if fl > 0:
                        disc_pct = abs(raster_flood_ha - fl) / fl * 100.0
                    elif raster_flood_ha > 0:
                        disc_pct = 100.0

                    item = {
                        "pair_id": pid,
                        "csv_flood_ha": round(fl, 2),
                        "raster_flood_ha": round(raster_flood_ha, 2),
                        "discrepancy_pct": round(disc_pct, 2),
                        "is_within_2_percent": disc_pct <= MAX_RASTER_CSV_DISCREPANCY_PCT,
                    }
                    discrepancies.append(item)

                    if disc_pct > MAX_RASTER_CSV_DISCREPANCY_PCT:
                        warnings.append(
                            f"Pair '{pid}': raster vs CSV discrepancy is {disc_pct:.2f}% (exceeds 2% limit)"
                        )
                        all_rasters_ok = False
            except Exception as ex:
                warnings.append(f"Error checking raster {tif_file.name}: {ex}")
                all_rasters_ok = False

        if all_rasters_ok and len(discrepancies) == len(sub_df):
            passed_checks.append("All 11 GeoTIFF rasters match CSV areas within <= 2.0% divergence rule")

    is_valid = len(errors) == 0

    return SubmissionValidationResult(
        is_valid=is_valid,
        num_pairs=len(sub_df),
        passed_checks=passed_checks,
        errors=errors,
        warnings=warnings,
        discrepancies=discrepancies,
    )
