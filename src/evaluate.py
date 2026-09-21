"""Evaluation and ablation analysis module for HydroWatch Amur.

Computes the official competition metric:
  Score = 0.45*Q_flood + 0.25*Q_water_peak + 0.15*Q_water_pre + 0.15*Spec_base
Thresholds: 50 ha for flood, 200 ha for water mirror.
Spec_base penalizes baseline pairs when false flood > 0.5% AOI.

Runs ablations across 4 configurations:
  1: Naive SAR Otsu alone.
  2: SAR Otsu + HAND/Slope filter.
  3: SAR + MSI fusion (where available).
  4: Full pipeline (+ MMU 25px + GSW permanent).
Saves results to data/ablation_results.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure repository root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any

import numpy as np
import pandas as pd
import rasterio

from src.predict import run_prediction

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_reference_stats(pairs_df: pd.DataFrame, data_dir: Path) -> pd.DataFrame:
    """Load reference statistics from reference_*.json metadata files."""
    rows = []
    for _, row in pairs_df.iterrows():
        pair_id = str(row["pair_id"])
        ref_json_path = data_dir / str(row["reference_mask"]).replace(".tif", ".json")
        if not ref_json_path.exists():
            raise FileNotFoundError(f"Reference JSON not found: {ref_json_path}")

        with open(ref_json_path, encoding="utf-8") as fp:
            meta = json.load(fp)

        stats = meta["stats"]
        rows.append({
            "pair_id": pair_id,
            "event_kind": str(row["event_kind"]),
            "aoi_ha": float(stats["aoi_ha"]),
            "ref_flood_ha": float(stats["flood_ha"]),
            "ref_water_pre_ha": float(stats["water_pre_ha"]),
            "ref_water_peak_ha": float(stats["water_peak_ha"]),
            "ref_permanent_ha": float(stats.get("permanent_ha", 0.0)),
        })

    return pd.DataFrame(rows)


def compute_official_score(
    submission_df: pd.DataFrame,
    ref_df: pd.DataFrame,
) -> dict[str, Any]:
    """Compute official HydroWatch Amur metric score.

    Formula:
      Score = 0.45*Q_flood + 0.25*Q_water_peak + 0.15*Q_water_pre + 0.15*Spec_base
      q = max(0, 1 - |X_sub - X_ref| / max(X_ref, threshold))
      threshold: flood=50 ha, water=200 ha

      Spec_base = mean(1 - min(1, excess / 0.005))
      excess = max(0, flood_sub - flood_ref) / aoi_ha
    """
    merged = pd.merge(submission_df, ref_df, on="pair_id")

    # Split into event pairs and baseline pairs
    events = merged[merged["event_kind"] != "baseline"].copy()
    baselines = merged[merged["event_kind"] == "baseline"].copy()

    # 1. Event pairs convergence
    events["q_flood"] = np.maximum(
        0.0,
        1.0 - np.abs(events["flood_ha"] - events["ref_flood_ha"]) /
        np.maximum(events["ref_flood_ha"], 50.0),
    )
    events["q_water_peak"] = np.maximum(
        0.0,
        1.0 - np.abs(events["water_peak_ha"] - events["ref_water_peak_ha"]) /
        np.maximum(events["ref_water_peak_ha"], 200.0),
    )
    events["q_water_pre"] = np.maximum(
        0.0,
        1.0 - np.abs(events["water_pre_ha"] - events["ref_water_pre_ha"]) /
        np.maximum(events["ref_water_pre_ha"], 200.0),
    )

    q_flood = float(events["q_flood"].mean()) if len(events) > 0 else 0.0
    q_water_peak = float(events["q_water_peak"].mean()) if len(events) > 0 else 0.0
    q_water_pre = float(events["q_water_pre"].mean()) if len(events) > 0 else 0.0

    # 2. Baseline pairs specificity (false alarm penalty)
    if len(baselines) > 0:
        excess = np.maximum(0.0, baselines["flood_ha"] - baselines["ref_flood_ha"])
        excess_share = excess / baselines["aoi_ha"]
        baselines["spec"] = 1.0 - np.minimum(1.0, excess_share / 0.005)
        spec_base = float(baselines["spec"].mean())
    else:
        spec_base = 1.0

    # 3. Overall official composite score
    total_score = (
        0.45 * q_flood +
        0.25 * q_water_peak +
        0.15 * q_water_pre +
        0.15 * spec_base
    )

    per_pair_details = []
    for _, r in merged.iterrows():
        per_pair_details.append({
            "pair_id": r["pair_id"],
            "event_kind": r["event_kind"],
            "flood_sub_ha": float(r["flood_ha"]),
            "flood_ref_ha": float(r["ref_flood_ha"]),
            "water_peak_sub_ha": float(r["water_peak_ha"]),
            "water_peak_ref_ha": float(r["ref_water_peak_ha"]),
            "water_pre_sub_ha": float(r["water_pre_ha"]),
            "water_pre_ref_ha": float(r["ref_water_pre_ha"]),
        })

    return {
        "score": round(float(total_score), 4),
        "Q_flood": round(float(q_flood), 4),
        "Q_water_peak": round(float(q_water_peak), 4),
        "Q_water_pre": round(float(q_water_pre), 4),
        "Spec_base": round(float(spec_base), 4),
        "num_events": len(events),
        "num_baselines": len(baselines),
        "details": per_pair_details,
    }


def compute_raster_metrics(
    predictions_dir: Path,
    pairs_df: pd.DataFrame,
    data_dir: Path,
) -> dict[str, float]:
    """Compute pixel-level IoU, Precision, Recall, F1 against reference masks."""
    ious, precisions, recalls, f1s = [], [], [], []

    for _, row in pairs_df.iterrows():
        pair_id = str(row["pair_id"])
        pred_tif = predictions_dir / f"{pair_id}_flood.tif"
        ref_tif = data_dir / str(row["reference_mask"])

        if not pred_tif.exists() or not ref_tif.exists():
            continue

        with rasterio.open(pred_tif) as p_src, rasterio.open(ref_tif) as r_src:
            pred_mask = p_src.read(1) == 1
            ref_flood = r_src.read(1) == 1

        tp = int(np.sum(pred_mask & ref_flood))
        fp = int(np.sum(pred_mask & (~ref_flood)))
        fn = int(np.sum((~pred_mask) & ref_flood))

        iou = tp / max(tp + fp + fn, 1)
        prec = tp / max(tp + fp, 1)
        rec = tp / max(tp + fn, 1)
        f1 = 2 * prec * rec / max(prec + rec, 1e-6)

        ious.append(iou)
        precisions.append(prec)
        recalls.append(rec)
        f1s.append(f1)

    return {
        "mean_iou": round(float(np.mean(ious)), 4) if ious else 0.0,
        "mean_precision": round(float(np.mean(precisions)), 4) if precisions else 0.0,
        "mean_recall": round(float(np.mean(recalls)), 4) if recalls else 0.0,
        "mean_f1": round(float(np.mean(f1s)), 4) if f1s else 0.0,
    }


def run_ablation_study(
    pairs_csv_path: Path = Path("hydrowatch_amur/pairs.csv"),
    data_dir: Path = Path("hydrowatch_amur"),
    output_json_path: Path = Path("data/ablation_results.json"),
) -> dict[str, Any]:
    """Execute ablation experiments across 4 pipeline configurations."""
    pairs_df = pd.read_csv(pairs_csv_path)
    ref_df = load_reference_stats(pairs_df, data_dir)

    ablation_descriptions = {
        1: "Ablation 1: Naive SAR Otsu alone",
        2: "Ablation 2: SAR Otsu + HAND/Slope filter",
        3: "Ablation 3: SAR + MSI fusion (where available)",
        4: "Ablation 4: Full pipeline (+ MMU 25px + GSW permanent)",
    }

    ablation_results = {}
    tmp_pred_base = Path("predictions_ablation")

    for mode in [1, 2, 3, 4]:
        name = ablation_descriptions[mode]
        logger.info(f"\n{'='*60}\nRunning {name}\n{'='*60}")
        pred_dir = tmp_pred_base / f"mode_{mode}"
        sub_csv = tmp_pred_base / f"sub_mode_{mode}.csv"

        sub_df = run_prediction(
            pairs_csv_path=pairs_csv_path,
            data_dir=data_dir,
            output_csv_path=sub_csv,
            predictions_dir=pred_dir,
            ablation_mode=mode,
        )

        score_res = compute_official_score(sub_df, ref_df)
        raster_res = compute_raster_metrics(pred_dir, pairs_df, data_dir)

        combined_res = {
            "mode": mode,
            "description": name,
            "official_metrics": score_res,
            "raster_metrics": raster_res,
        }
        ablation_results[f"ablation_{mode}"] = combined_res

        logger.info(
            f"Result for {name}: Score={score_res['score']} "
            f"(Q_flood={score_res['Q_flood']}, Q_peak={score_res['Q_water_peak']}, "
            f"Q_pre={score_res['Q_water_pre']}, Spec_base={score_res['Spec_base']}) | "
            f"Mean IoU={raster_res['mean_iou']}, F1={raster_res['mean_f1']}"
        )

    # Save to json
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as fp:
        json.dump(ablation_results, fp, indent=2, ensure_ascii=False)

    logger.info(f"Ablation study saved to {output_json_path}")
    return ablation_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate submissions and run ablations")
    parser.add_argument("--submission", type=Path, default=Path("submission.csv"))
    parser.add_argument("--pairs", type=Path, default=Path("hydrowatch_amur/pairs.csv"))
    parser.add_argument("--data_dir", type=Path, default=Path("hydrowatch_amur"))
    parser.add_argument("--predictions_dir", type=Path, default=Path("predictions"))
    parser.add_argument("--run_ablations", action="store_true", help="Run full 4-stage ablation study")
    parser.add_argument("--output_json", type=Path, default=Path("data/ablation_results.json"))
    args = parser.parse_args()

    pairs_df = pd.read_csv(args.pairs)
    ref_df = load_reference_stats(pairs_df, args.data_dir)

    if args.run_ablations:
        run_ablation_study(
            pairs_csv_path=args.pairs,
            data_dir=args.data_dir,
            output_json_path=args.output_json,
        )
    elif args.submission.exists():
        sub_df = pd.read_csv(args.submission)
        score_res = compute_official_score(sub_df, ref_df)
        raster_res = compute_raster_metrics(args.predictions_dir, pairs_df, args.data_dir)

        print("\n" + "=" * 50)
        print("HYDRO-MONITORING EVALUATION RESULTS")
        print("=" * 50)
        print(f"Composite Score: {score_res['score']:.4f}")
        print(f"  Q_flood (weight 0.45):       {score_res['Q_flood']:.4f}")
        print(f"  Q_water_peak (weight 0.25):  {score_res['Q_water_peak']:.4f}")
        print(f"  Q_water_pre (weight 0.15):   {score_res['Q_water_pre']:.4f}")
        print(f"  Spec_base (weight 0.15):     {score_res['Spec_base']:.4f}")
        print("-" * 50)
        print(f"Raster Mean IoU:               {raster_res['mean_iou']:.4f}")
        print(f"Raster Mean F1:                {raster_res['mean_f1']:.4f}")
        print("=" * 50 + "\n")
    else:
        logger.error(f"Submission file not found: {args.submission}. Run predict.py first.")


if __name__ == "__main__":
    main()
