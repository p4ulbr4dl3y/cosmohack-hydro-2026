"""Tests for official competition evaluation and ablation analysis."""

import json
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin

from src.evaluate import (
    compute_official_score,
    compute_raster_metrics,
    load_reference_stats,
    run_ablation_study,
)
from src.evaluate import (
    main as eval_main,
)


def test_compute_official_score_perfect():
    submission_df = pd.DataFrame(
        [
            {"pair_id": "event_1", "flood_ha": 100.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0},
            {"pair_id": "base_1", "flood_ha": 0.0, "water_pre_ha": 500.0, "water_peak_ha": 500.0},
        ]
    )
    ref_df = pd.DataFrame(
        [
            {
                "pair_id": "event_1",
                "event_kind": "flood_summer",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 100.0,
                "ref_water_pre_ha": 500.0,
                "ref_water_peak_ha": 600.0,
            },
            {
                "pair_id": "base_1",
                "event_kind": "baseline",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 0.0,
                "ref_water_pre_ha": 500.0,
                "ref_water_peak_ha": 500.0,
            },
        ]
    )
    score_data = compute_official_score(submission_df, ref_df)
    assert score_data["score"] == 1.0
    assert score_data["Q_flood"] == 1.0
    assert score_data["Q_water_peak"] == 1.0
    assert score_data["Q_water_pre"] == 1.0
    assert score_data["Spec_base"] == 1.0


def test_compute_official_score_baseline_penalty():
    submission_df = pd.DataFrame(
        [
            {"pair_id": "base_1", "flood_ha": 100.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0},
        ]
    )
    # AOI 10,000 ha -> 0.5% is 50 ha. Excess is 100 ha -> excess_share = 0.01 -> min(1, 0.01/0.005) = 1.0 -> Spec = 0.0
    ref_df = pd.DataFrame(
        [
            {
                "pair_id": "base_1",
                "event_kind": "baseline",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 0.0,
                "ref_water_pre_ha": 500.0,
                "ref_water_peak_ha": 500.0,
            }
        ]
    )
    score_data = compute_official_score(submission_df, ref_df)
    assert score_data["Spec_base"] == 0.0
    assert score_data["Q_flood"] == 0.0


def test_missing_baseline_pair_scores_zero():
    """A reference baseline pair absent from the submission is a missed specificity.

    Missing a baseline pair must LOWER ``Spec_base`` versus submitting that same
    pair with its correct (zero false-alarm) value: an absent pair scores 0 for
    its own objective, it does **not** inherit ``spec = 1.0``.
    """
    ref_df = pd.DataFrame(
        [
            {
                "pair_id": "base_1",
                "event_kind": "baseline",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 0.0,
                "ref_water_pre_ha": 500.0,
                "ref_water_peak_ha": 500.0,
            },
            {
                "pair_id": "base_2",
                "event_kind": "baseline",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 0.0,
                "ref_water_pre_ha": 500.0,
                "ref_water_peak_ha": 500.0,
            },
        ]
    )
    # base_1 false alarm: excess 100 ha / 10,000 ha = 0.01 -> min(1, 0.01 / 0.005) = 1 -> spec 0.
    sub_missing_base_2 = pd.DataFrame(
        [{"pair_id": "base_1", "flood_ha": 100.0, "water_pre_ha": 500.0, "water_peak_ha": 500.0}]
    )
    # Same submission but base_2 present with its correct value (spec 1.0).
    sub_with_base_2 = pd.DataFrame(
        [
            {"pair_id": "base_1", "flood_ha": 100.0, "water_pre_ha": 500.0, "water_peak_ha": 500.0},
            {"pair_id": "base_2", "flood_ha": 0.0, "water_pre_ha": 500.0, "water_peak_ha": 500.0},
        ]
    )

    missing_score = compute_official_score(sub_missing_base_2, ref_df)
    present_score = compute_official_score(sub_with_base_2, ref_df)

    # base_2 missing -> spec 0; base_1 present false alarm -> spec 0 => Spec_base = 0.0.
    assert missing_score["Spec_base"] == 0.0
    # base_2 present & correct -> spec 1; base_1 spec 0 => Spec_base = 0.5.
    assert present_score["Spec_base"] == 0.5
    # Missing the baseline pair strictly lowers Spec_base (no exploit).
    assert missing_score["Spec_base"] < present_score["Spec_base"]
    assert missing_score["num_baselines"] == 2


def test_missing_event_pair_drops_q_proportionally():
    """An event pair absent from the submission contributes q = 0, not a vanished mean."""
    ref_df = pd.DataFrame(
        [
            {
                "pair_id": "event_1",
                "event_kind": "flood_summer",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 100.0,
                "ref_water_pre_ha": 500.0,
                "ref_water_peak_ha": 600.0,
            },
            {
                "pair_id": "event_2",
                "event_kind": "flood_summer",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 200.0,
                "ref_water_pre_ha": 700.0,
                "ref_water_peak_ha": 800.0,
            },
        ]
    )
    full_sub = pd.DataFrame(
        [
            {"pair_id": "event_1", "flood_ha": 100.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0},
            {"pair_id": "event_2", "flood_ha": 200.0, "water_pre_ha": 700.0, "water_peak_ha": 800.0},
        ]
    )
    missing_sub = pd.DataFrame(
        [{"pair_id": "event_1", "flood_ha": 100.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0}]
    )

    full_score = compute_official_score(full_sub, ref_df)
    missing_score = compute_official_score(missing_sub, ref_df)

    assert full_score["Q_flood"] == 1.0
    assert missing_score["Q_flood"] == 0.5
    assert missing_score["Q_water_peak"] == 0.5
    assert missing_score["Q_water_pre"] == 0.5
    assert missing_score["Q_flood"] < full_score["Q_flood"]
    assert missing_score["num_events"] == 2


def test_removing_baseline_rows_does_not_raise_score():
    """Regression: dropping baseline rows must not inflate the score (auditor scenario).

    The submission contains a *false alarm* on ``base_1`` (which caps Spec_base
    below 1.0). Deleting the baseline rows would previously delete the false-alarm
    penalty and raise the score. With the correct semantics a deleted baseline pair
    scores ``spec = 0`` (missed specificity), so the damaged score is STRICTLY LESS
    than the full score.
    """
    ref_df = pd.DataFrame(
        [
            {
                "pair_id": "event_1",
                "event_kind": "flood_summer",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 100.0,
                "ref_water_pre_ha": 500.0,
                "ref_water_peak_ha": 600.0,
            },
            {
                "pair_id": "base_1",
                "event_kind": "baseline",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 0.0,
                "ref_water_pre_ha": 500.0,
                "ref_water_peak_ha": 500.0,
            },
            {
                "pair_id": "base_2",
                "event_kind": "baseline",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 0.0,
                "ref_water_pre_ha": 500.0,
                "ref_water_peak_ha": 500.0,
            },
            {
                "pair_id": "base_3",
                "event_kind": "baseline",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 0.0,
                "ref_water_pre_ha": 500.0,
                "ref_water_peak_ha": 500.0,
            },
        ]
    )
    # base_1 carries a false alarm: excess 100 ha / 10,000 ha = 0.01 -> spec 0.
    full_sub = pd.DataFrame(
        [
            {"pair_id": "event_1", "flood_ha": 100.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0},
            {"pair_id": "base_1", "flood_ha": 100.0, "water_pre_ha": 500.0, "water_peak_ha": 500.0},
            {"pair_id": "base_2", "flood_ha": 0.0, "water_pre_ha": 500.0, "water_peak_ha": 500.0},
            {"pair_id": "base_3", "flood_ha": 0.0, "water_pre_ha": 500.0, "water_peak_ha": 500.0},
        ]
    )
    # Auditor scenario: delete the baseline rows, hoping the score goes up.
    damaged_sub = full_sub[~full_sub["pair_id"].str.startswith("base_")].reset_index(drop=True)

    full_score = compute_official_score(full_sub, ref_df)
    damaged_score = compute_official_score(damaged_sub, ref_df)

    # Full submission: Spec_base = (0 + 1 + 1) / 3 = 0.6667, events perfect.
    assert full_score["Spec_base"] == 0.6667
    assert full_score["Q_flood"] == 1.0
    # Damaged: all baseline pairs absent -> Spec_base = 0.0 -> score strictly lower.
    assert damaged_score["Spec_base"] == 0.0
    assert damaged_score["score"] < full_score["score"]
    assert damaged_score["num_baselines"] == 3


def test_removing_small_event_pair_lowers_score():
    """Small-event exploit: an absent event pair with ref < 50 ha must score q = 0.

    With the old semantics a missing pair with ``ref_flood_ha = 20`` (< 50 ha
    threshold) still got ``q = 1 - |0 - 20| / max(20, 50) = 0.6``, so *skipping*
    the pair raised the total score. It must now strictly DECREASE.
    """
    ref_df = pd.DataFrame(
        [
            {
                "pair_id": "event_big",
                "event_kind": "flood_summer",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 100.0,
                "ref_water_pre_ha": 500.0,
                "ref_water_peak_ha": 600.0,
            },
            {
                "pair_id": "event_small",
                "event_kind": "flood_summer",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 20.0,
                "ref_water_pre_ha": 100.0,
                "ref_water_peak_ha": 120.0,
            },
        ]
    )
    # Imperfect big event: flood overshoots -> q_flood < 1; small event perfect.
    full_sub = pd.DataFrame(
        [
            {"pair_id": "event_big", "flood_ha": 200.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0},
            {"pair_id": "event_small", "flood_ha": 20.0, "water_pre_ha": 100.0, "water_peak_ha": 120.0},
        ]
    )
    damaged_sub = full_sub[full_sub["pair_id"] != "event_small"].reset_index(drop=True)

    full_score = compute_official_score(full_sub, ref_df)
    damaged_score = compute_official_score(damaged_sub, ref_df)

    # event_big q_flood = 1 - 100/100 = 0.0; event_small q_flood = 1.0 -> mean 0.5.
    assert full_score["Q_flood"] == 0.5
    # event_small absent -> q_flood = 0.0; event_big q_flood = 0.0 -> mean 0.0.
    assert damaged_score["Q_flood"] == 0.0
    assert damaged_score["score"] < full_score["score"]
    assert damaged_score["num_events"] == 2


def test_dropping_any_single_pair_never_raises_score():
    """Monotonicity guard: for a non-perfect submission, dropping any single pair
    must never increase the total score."""
    ref_df = pd.DataFrame(
        [
            {
                "pair_id": "event_1",
                "event_kind": "flood_summer",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 100.0,
                "ref_water_pre_ha": 500.0,
                "ref_water_peak_ha": 600.0,
            },
            {
                "pair_id": "event_2",
                "event_kind": "flood_summer",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 20.0,
                "ref_water_pre_ha": 100.0,
                "ref_water_peak_ha": 120.0,
            },
            {
                "pair_id": "base_1",
                "event_kind": "baseline",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 0.0,
                "ref_water_pre_ha": 500.0,
                "ref_water_peak_ha": 500.0,
            },
            {
                "pair_id": "base_2",
                "event_kind": "baseline",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 0.0,
                "ref_water_pre_ha": 500.0,
                "ref_water_peak_ha": 500.0,
            },
            {
                "pair_id": "base_3",
                "event_kind": "baseline",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 0.0,
                "ref_water_pre_ha": 500.0,
                "ref_water_peak_ha": 500.0,
            },
        ]
    )
    # Non-perfect submission: event_1 overshoots, base_1 has a false alarm.
    full_sub = pd.DataFrame(
        [
            {"pair_id": "event_1", "flood_ha": 250.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0},
            {"pair_id": "event_2", "flood_ha": 20.0, "water_pre_ha": 100.0, "water_peak_ha": 120.0},
            {"pair_id": "base_1", "flood_ha": 100.0, "water_pre_ha": 500.0, "water_peak_ha": 500.0},
            {"pair_id": "base_2", "flood_ha": 0.0, "water_pre_ha": 500.0, "water_peak_ha": 500.0},
            {"pair_id": "base_3", "flood_ha": 0.0, "water_pre_ha": 500.0, "water_peak_ha": 500.0},
        ]
    )
    full_score = compute_official_score(full_sub, ref_df)["score"]

    for pair_id in full_sub["pair_id"]:
        dropped = full_sub[full_sub["pair_id"] != pair_id].reset_index(drop=True)
        dropped_score = compute_official_score(dropped, ref_df)["score"]
        assert dropped_score <= full_score, f"dropping {pair_id} raised the score ({dropped_score} > {full_score})"


def test_extra_unknown_pair_ids_are_ignored():
    """Submission rows whose pair_id is not in ref_df must never be scored."""
    ref_df = pd.DataFrame(
        [
            {
                "pair_id": "event_1",
                "event_kind": "flood_summer",
                "aoi_ha": 10000.0,
                "ref_flood_ha": 100.0,
                "ref_water_pre_ha": 500.0,
                "ref_water_peak_ha": 600.0,
            }
        ]
    )
    known_sub = pd.DataFrame([{"pair_id": "event_1", "flood_ha": 100.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0}])
    with_unknown_sub = pd.concat(
        [
            known_sub,
            pd.DataFrame(
                [
                    {"pair_id": "ghost_1", "flood_ha": 9999.0, "water_pre_ha": 0.0, "water_peak_ha": 0.0},
                    {"pair_id": "ghost_2", "flood_ha": 0.0, "water_pre_ha": 9999.0, "water_peak_ha": 9999.0},
                ]
            ),
        ],
        ignore_index=True,
    )

    known_score = compute_official_score(known_sub, ref_df)
    unknown_score = compute_official_score(with_unknown_sub, ref_df)

    assert unknown_score == known_score
    assert unknown_score["num_events"] == 1
    assert {detail["pair_id"] for detail in unknown_score["details"]} == {"event_1"}


def test_load_reference_stats(tmp_path):
    pairs_df = pd.DataFrame([{"pair_id": "p1", "event_kind": "flood", "reference_mask": "ref.tif"}])
    # Missing json
    with pytest.raises(FileNotFoundError):
        load_reference_stats(pairs_df, tmp_path)

    # Valid json
    ref_json = tmp_path / "ref.json"
    ref_json.write_text(
        json.dumps(
            {
                "stats": {
                    "aoi_ha": 1000.0,
                    "flood_ha": 50.0,
                    "water_pre_ha": 200.0,
                    "water_peak_ha": 250.0,
                    "permanent_ha": 180.0,
                }
            }
        ),
        encoding="utf-8",
    )
    res_df = load_reference_stats(pairs_df, tmp_path)
    assert len(res_df) == 1
    assert res_df.iloc[0]["ref_flood_ha"] == 50.0
    assert res_df.iloc[0]["ref_permanent_ha"] == 180.0


def test_compute_raster_metrics(tmp_path):
    pred_dir = tmp_path / "pred"
    data_dir = tmp_path / "data"
    pred_dir.mkdir()
    data_dir.mkdir()

    transform = from_origin(127.0, 50.0, 10.0, 10.0)
    # Shape 10x10
    pred_arr = np.zeros((10, 10), dtype=np.uint8)
    ref_arr = np.zeros((10, 10), dtype=np.uint8)
    # 4 pixels TP, 1 pixel FP, 1 pixel FN
    pred_arr[0, :5] = 1  # 5 positive
    ref_arr[0, 1:6] = 1  # 5 positive, overlap is cols 1..4 (4 pixels)

    pred_tif = pred_dir / "p1_flood.tif"
    ref_tif = data_dir / "ref_p1.tif"

    for path, arr in [(pred_tif, pred_arr), (ref_tif, ref_arr)]:
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=10,
            width=10,
            count=1,
            dtype=np.uint8,
            crs="EPSG:32652",
            transform=transform,
        ) as dst:
            dst.write(arr, 1)

    pairs_df = pd.DataFrame([{"pair_id": "p1", "reference_mask": "ref_p1.tif"}])
    metrics = compute_raster_metrics(pred_dir, pairs_df, data_dir)

    # TP=4, FP=1, FN=1 -> IoU = 4/6 = 0.6667
    assert 0.66 < metrics["mean_iou"] < 0.67
    assert metrics["mean_precision"] == 0.8
    assert metrics["mean_recall"] == 0.8


def test_run_ablation_study_mocked(tmp_path):
    out_json = tmp_path / "ablation.json"
    dummy_pairs = tmp_path / "pairs.csv"
    dummy_pairs.write_text(
        "pair_id,event_kind,reference_mask,rasters_dir\np1,baseline,ref.tif,r1\n",
        encoding="utf-8",
    )
    ref_json = tmp_path / "ref.json"
    ref_json.write_text(
        json.dumps(
            {
                "stats": {
                    "aoi_ha": 1000.0,
                    "flood_ha": 0.0,
                    "water_pre_ha": 100.0,
                    "water_peak_ha": 100.0,
                }
            }
        ),
        encoding="utf-8",
    )

    fake_sub = pd.DataFrame([{"pair_id": "p1", "flood_ha": 0.0, "water_pre_ha": 100.0, "water_peak_ha": 100.0}])

    with patch("src.evaluate.run_prediction", return_value=fake_sub):
        res = run_ablation_study(
            pairs_csv_path=dummy_pairs,
            data_dir=tmp_path,
            output_json_path=out_json,
        )
        assert "ablation_1" in res
        assert "ablation_4" in res
        assert out_json.exists()


def test_evaluate_main_cli(tmp_path, monkeypatch, capsys):
    dummy_pairs = tmp_path / "pairs.csv"
    dummy_pairs.write_text(
        "pair_id,event_kind,reference_mask,rasters_dir\np1,flood,ref.tif,r1\n",
        encoding="utf-8",
    )
    ref_json = tmp_path / "ref.json"
    ref_json.write_text(
        json.dumps(
            {
                "stats": {
                    "aoi_ha": 1000.0,
                    "flood_ha": 50.0,
                    "water_pre_ha": 100.0,
                    "water_peak_ha": 150.0,
                }
            }
        ),
        encoding="utf-8",
    )
    sub_csv = tmp_path / "submission.csv"
    sub_csv.write_text("pair_id,flood_ha,water_pre_ha,water_peak_ha\np1,50.0,100.0,150.0\n", encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate.py",
            "--submission",
            str(sub_csv),
            "--pairs",
            str(dummy_pairs),
            "--data_dir",
            str(tmp_path),
            "--predictions_dir",
            str(tmp_path),
        ],
    )
    eval_main()
    out = capsys.readouterr().out
    assert "HYDRO-MONITORING EVALUATION RESULTS" in out
    assert "Composite Score: 1.0000" in out


def test_evaluate_main_run_ablations(tmp_path, monkeypatch):
    dummy_pairs = tmp_path / "pairs.csv"
    dummy_pairs.write_text("pair_id,event_kind,reference_mask,rasters_dir\np1,flood,ref.tif,r1\n", encoding="utf-8")
    ref_json = tmp_path / "ref.json"
    ref_json.write_text(
        json.dumps(
            {
                "stats": {
                    "aoi_ha": 1000.0,
                    "flood_ha": 50.0,
                    "water_pre_ha": 100.0,
                    "water_peak_ha": 150.0,
                }
            }
        ),
        encoding="utf-8",
    )

    called = {}
    monkeypatch.setattr("src.evaluate.run_ablation_study", lambda **kwargs: called.setdefault("ablations", True))
    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate.py",
            "--pairs",
            str(dummy_pairs),
            "--data_dir",
            str(tmp_path),
            "--run_ablations",
            "--output_json",
            str(tmp_path / "out.json"),
        ],
    )
    eval_main()
    assert called.get("ablations")


def test_evaluate_main_submission_not_found(tmp_path, monkeypatch):
    dummy_pairs = tmp_path / "pairs.csv"
    dummy_pairs.write_text("pair_id,event_kind,reference_mask,rasters_dir\np1,flood,ref.tif,r1\n", encoding="utf-8")
    ref_json = tmp_path / "ref.json"
    ref_json.write_text(
        json.dumps(
            {
                "stats": {
                    "aoi_ha": 1000.0,
                    "flood_ha": 50.0,
                    "water_pre_ha": 100.0,
                    "water_peak_ha": 150.0,
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate.py",
            "--pairs",
            str(dummy_pairs),
            "--data_dir",
            str(tmp_path),
            "--submission",
            str(tmp_path / "nonexistent_sub.csv"),
        ],
    )
    eval_main()


def test_evaluate_main_module_execution(monkeypatch):
    import runpy

    with pytest.raises(SystemExit) as exc:
        monkeypatch.setattr("sys.argv", ["evaluate.py", "--help"])
        runpy.run_module("src.evaluate", run_name="__main__")
    assert exc.value.code == 0
