"""Тесты официальной оценки конкурса и анализа абляций."""

import json
from pathlib import Path
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
    run_holdout_study,
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
    # AOI 10,000 ha -> 0.5% составляет 50 ha. Превышение 100 ha -> excess_share = 0.01 -> min(1, 0.01/0.005) = 1.0 -> Spec = 0.0
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
    """Отсутствующая в submission референсная базовая пара - это пропущенная специфичность.

    Пропуск базовой пары должен ПОНИЖАТЬ ``Spec_base`` относительно подачи той же
    пары с её корректным (без ложной тревоги) значением: отсутствующая пара
    получает 0 по собственной цели и НЕ наследует ``spec = 1.0``.
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
    # Ложная тревога на base_1: превышение 100 ha / 10,000 ha = 0.01 -> min(1, 0.01 / 0.005) = 1 -> spec 0.
    sub_missing_base_2 = pd.DataFrame(
        [{"pair_id": "base_1", "flood_ha": 100.0, "water_pre_ha": 500.0, "water_peak_ha": 500.0}]
    )
    # Тот же submission, но base_2 присутствует с корректным значением (spec 1.0).
    sub_with_base_2 = pd.DataFrame(
        [
            {"pair_id": "base_1", "flood_ha": 100.0, "water_pre_ha": 500.0, "water_peak_ha": 500.0},
            {"pair_id": "base_2", "flood_ha": 0.0, "water_pre_ha": 500.0, "water_peak_ha": 500.0},
        ]
    )

    missing_score = compute_official_score(sub_missing_base_2, ref_df)
    present_score = compute_official_score(sub_with_base_2, ref_df)

    # base_2 отсутствует -> spec 0; base_1 присутствует с ложной тревогой -> spec 0 => Spec_base = 0.0.
    assert missing_score["Spec_base"] == 0.0
    # base_2 присутствует и корректна -> spec 1; base_1 spec 0 => Spec_base = 0.5.
    assert present_score["Spec_base"] == 0.5
    # Пропуск базовой пары строго понижает Spec_base (без эксплойта).
    assert missing_score["Spec_base"] < present_score["Spec_base"]
    assert missing_score["num_baselines"] == 2


def test_missing_event_pair_drops_q_proportionally():
    """Отсутствующая в submission событийная пара вносит q = 0, а не исчезнувшее среднее."""
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
    """Регрессия: удаление строк базовых линий не должно завышать балл (сценарий аудитора).

    Submission содержит *ложную тревогу* на ``base_1`` (что ограничивает Spec_base
    ниже 1.0). Удаление строк базовых линий ранее удаляло штраф за ложную тревогу
    и повышало балл. При корректной семантике удалённая базовая пара получает
    ``spec = 0`` (пропущенная специфичность), поэтому испорченный балл СТРОГО МЕНЬШЕ
    полного балла.
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
    # base_1 несёт ложную тревогу: превышение 100 ha / 10,000 ha = 0.01 -> spec 0.
    full_sub = pd.DataFrame(
        [
            {"pair_id": "event_1", "flood_ha": 100.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0},
            {"pair_id": "base_1", "flood_ha": 100.0, "water_pre_ha": 500.0, "water_peak_ha": 500.0},
            {"pair_id": "base_2", "flood_ha": 0.0, "water_pre_ha": 500.0, "water_peak_ha": 500.0},
            {"pair_id": "base_3", "flood_ha": 0.0, "water_pre_ha": 500.0, "water_peak_ha": 500.0},
        ]
    )
    # Сценарий аудитора: удалить строки базовых линий в надежде повысить балл.
    damaged_sub = full_sub[~full_sub["pair_id"].str.startswith("base_")].reset_index(drop=True)

    full_score = compute_official_score(full_sub, ref_df)
    damaged_score = compute_official_score(damaged_sub, ref_df)

    # Полный submission: Spec_base = (0 + 1 + 1) / 3 = 0.6667, события идеальны.
    assert full_score["Spec_base"] == 0.6667
    assert full_score["Q_flood"] == 1.0
    # Испорченный: все базовые пары отсутствуют -> Spec_base = 0.0 -> балл строго ниже.
    assert damaged_score["Spec_base"] == 0.0
    assert damaged_score["score"] < full_score["score"]
    assert damaged_score["num_baselines"] == 3


def test_removing_small_event_pair_lowers_score():
    """Эксплойт малого события: отсутствующая событийная пара с ref < 50 ha должна давать q = 0.

    При старой семантике отсутствующая пара с ``ref_flood_ha = 20`` (< порога 50 ha)
    всё равно получала ``q = 1 - |0 - 20| / max(20, 50) = 0.6``, поэтому *пропуск*
    пары повышал итоговый балл. Теперь он должен строго УМЕНЬШАТЬСЯ.
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
    # Неидеальное большое событие: паводок завышен -> q_flood < 1; малое событие идеально.
    full_sub = pd.DataFrame(
        [
            {"pair_id": "event_big", "flood_ha": 200.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0},
            {"pair_id": "event_small", "flood_ha": 20.0, "water_pre_ha": 100.0, "water_peak_ha": 120.0},
        ]
    )
    damaged_sub = full_sub[full_sub["pair_id"] != "event_small"].reset_index(drop=True)

    full_score = compute_official_score(full_sub, ref_df)
    damaged_score = compute_official_score(damaged_sub, ref_df)

    # event_big q_flood = 1 - 100/100 = 0.0; event_small q_flood = 1.0 -> среднее 0.5.
    assert full_score["Q_flood"] == 0.5
    # event_small отсутствует -> q_flood = 0.0; event_big q_flood = 0.0 -> среднее 0.0.
    assert damaged_score["Q_flood"] == 0.0
    assert damaged_score["score"] < full_score["score"]
    assert damaged_score["num_events"] == 2


def test_dropping_any_single_pair_never_raises_score():
    """Защита монотонности: для неидеального submission удаление любой отдельной пары
    никогда не должно повышать итоговый балл."""
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
    # Неидеальный submission: event_1 завышен, base_1 содержит ложную тревогу.
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
    """Строки submission, чей pair_id отсутствует в ref_df, никогда не должны оцениваться."""
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
    # Отсутствующий json
    with pytest.raises(FileNotFoundError):
        load_reference_stats(pairs_df, tmp_path)

    # Корректный json
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
    # Размер 10x10
    pred_arr = np.zeros((10, 10), dtype=np.uint8)
    ref_arr = np.zeros((10, 10), dtype=np.uint8)
    # 4 пикселя TP, 1 пиксель FP, 1 пиксель FN
    pred_arr[0, :5] = 1  # 5 положительных
    ref_arr[0, 1:6] = 1  # 5 положительных, перекрытие - столбцы 1..4 (4 пикселя)

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


def _write_holdout_fixture(tmp_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Запись фикстуры из 5 пар / 3 AOI и возврат (pairs_df, ref_df)."""
    rows = [
        ("base_alpha", "alpha", "baseline", 0.0),
        ("ev_alpha", "alpha", "flood_summer", 50.0),
        ("base_beta", "beta", "baseline", 0.0),
        ("ev_beta", "beta", "flood_summer", 120.0),
        ("ev_gamma", "gamma", "flood_summer", 80.0),
    ]
    csv_lines = ["pair_id,aoi_id,event_kind,reference_mask"]
    for pair_id, aoi_id, event_kind, ref_flood in rows:
        csv_lines.append(f"{pair_id},{aoi_id},{event_kind},{pair_id}.tif")
        (tmp_path / f"{pair_id}.json").write_text(
            json.dumps(
                {
                    "stats": {
                        "aoi_ha": 10000.0,
                        "flood_ha": ref_flood,
                        "water_pre_ha": 500.0,
                        "water_peak_ha": 600.0,
                        "permanent_ha": 400.0,
                    }
                }
            ),
            encoding="utf-8",
        )
    pairs_csv = tmp_path / "pairs.csv"
    pairs_csv.write_text("\n".join(csv_lines) + "\n", encoding="utf-8")

    pairs_df = pd.read_csv(pairs_csv)
    ref_df = load_reference_stats(pairs_df, tmp_path)
    return pairs_df, ref_df


def test_run_holdout_study_folds_match_aois_and_schema(tmp_path):
    """Один фолд на AOI и машиночитаемый артефакт с ожидаемой схемой."""
    pairs_df, ref_df = _write_holdout_fixture(tmp_path)
    sub_df = pd.DataFrame(
        [
            {"pair_id": "base_alpha", "flood_ha": 0.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0},
            {"pair_id": "ev_alpha", "flood_ha": 50.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0},
            {"pair_id": "base_beta", "flood_ha": 0.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0},
            {"pair_id": "ev_beta", "flood_ha": 120.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0},
            {"pair_id": "ev_gamma", "flood_ha": 80.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0},
        ]
    )

    out_json = tmp_path / "holdout.json"
    res = run_holdout_study(sub_df, pairs_df, ref_df, output_json_path=out_json)

    expected_aois = sorted(pairs_df["aoi_id"].unique())
    assert res["num_folds"] == len(expected_aois) == 3
    assert res["aois"] == expected_aois
    assert sorted(res["folds"].keys()) == expected_aois
    assert res["num_pairs"] == len(pairs_df)

    # Схема сохраняемого артефакта.
    assert out_json.exists()
    with open(out_json, encoding="utf-8") as fp:
        stored = json.load(fp)
    assert stored == res
    assert stored["method"] == "spatial leave-one-AOI-out (LOAO)"
    assert "official_pooled_metrics" in stored
    assert set(stored["fold_summary"]) == {"mean_score", "std_score", "min_score", "max_score"}

    for aoi, fold in stored["folds"].items():
        assert fold["held_out_aoi"] == aoi
        assert fold["num_pairs"] == len(fold["pair_ids"])
        assert set(fold["official_metrics"]) >= {"score", "Q_flood", "Q_water_peak", "Q_water_pre", "Spec_base"}
        assert set(fold["in_sample_metrics"]) >= {"score", "Q_flood", "Q_water_peak", "Q_water_pre", "Spec_base"}


def test_run_holdout_study_reuses_official_metric(tmp_path):
    """Каждый фолд оценивается ТОЙ ЖЕ ``compute_official_score`` на удержанном AOI."""
    pairs_df, ref_df = _write_holdout_fixture(tmp_path)
    sub_df = pd.DataFrame(
        [
            {"pair_id": "base_alpha", "flood_ha": 0.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0},
            {"pair_id": "ev_alpha", "flood_ha": 50.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0},
            {"pair_id": "base_beta", "flood_ha": 10.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0},
            {"pair_id": "ev_beta", "flood_ha": 120.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0},
            {"pair_id": "ev_gamma", "flood_ha": 0.0, "water_pre_ha": 500.0, "water_peak_ha": 600.0},
        ]
    )

    res = run_holdout_study(sub_df, pairs_df, ref_df, output_json_path=tmp_path / "h.json")

    ref = ref_df.copy()
    ref["pair_id"] = ref["pair_id"].astype(str)
    ref["aoi_id"] = pairs_df.set_index("pair_id")["aoi_id"].reindex(ref["pair_id"]).values

    for aoi in res["aois"]:
        manual = compute_official_score(sub_df, ref[ref["aoi_id"] == aoi].drop(columns=["aoi_id"]))
        assert res["folds"][aoi]["official_metrics"] == manual

    # Сводные метрики - это неизменённая официальная метрика по всем парам.
    assert res["official_pooled_metrics"] == compute_official_score(sub_df, ref_df)
    # Среднее по удержанным фолдам - реальная диагностика разброса фолдов.
    assert res["fold_summary"]["min_score"] <= res["fold_summary"]["mean_score"] <= res["fold_summary"]["max_score"]


def test_holdout_main_cli_prints_table_and_writes_json(tmp_path, monkeypatch, capsys):
    pairs_df, _ = _write_holdout_fixture(tmp_path)
    sub_csv = tmp_path / "submission.csv"
    sub_csv.write_text(
        "pair_id,flood_ha,water_pre_ha,water_peak_ha\n"
        "base_alpha,0.0,500.0,600.0\n"
        "ev_alpha,50.0,500.0,600.0\n"
        "base_beta,0.0,500.0,600.0\n"
        "ev_beta,120.0,500.0,600.0\n"
        "ev_gamma,80.0,500.0,600.0\n",
        encoding="utf-8",
    )
    out_json = tmp_path / "holdout_results.json"

    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate.py",
            "--submission",
            str(sub_csv),
            "--pairs",
            str(tmp_path / "pairs.csv"),
            "--data_dir",
            str(tmp_path),
            "--holdout",
            "--holdout_json",
            str(out_json),
        ],
    )
    eval_main()
    out = capsys.readouterr().out
    assert "SPATIAL HOLD-OUT (LEAVE-ONE-AOI-OUT)" in out
    assert "ADDITIONAL DIAGNOSTIC" in out
    assert "Official pooled Score" in out
    assert out_json.exists()
    with open(out_json, encoding="utf-8") as fp:
        stored = json.load(fp)
    assert stored["num_folds"] == len(pairs_df["aoi_id"].unique())
    # Официальное сводное число сообщается и никогда не подменяется.
    assert "official_pooled_metrics" in stored


def test_default_evaluate_path_unchanged_no_holdout(tmp_path, monkeypatch, capsys):
    """Вывод evaluate по умолчанию (без флага) должен оставаться только сводным: без раздела hold-out."""
    dummy_pairs = tmp_path / "pairs.csv"
    dummy_pairs.write_text("pair_id,event_kind,reference_mask\np1,flood,ref.tif\n", encoding="utf-8")
    (tmp_path / "ref.json").write_text(
        json.dumps({"stats": {"aoi_ha": 1000.0, "flood_ha": 50.0, "water_pre_ha": 100.0, "water_peak_ha": 150.0}}),
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
    assert "Composite Score: 1.0000" in out
    assert "SPATIAL HOLD-OUT" not in out


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
