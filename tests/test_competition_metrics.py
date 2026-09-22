"""Модульные тесты метрик конкурса и валидатора submission (TASK_SPEC.md и CRITERIA.md)."""

import math
from pathlib import Path

import pandas as pd

from src.competition_metrics import (
    FLOOD_THRESHOLD_HA,
    calculate_baseline_spec,
    calculate_q_score,
    compute_live_official_score,
    validate_submission_file,
)


def test_q_score_thresholds():
    """Проверка формулы сходимости q = max(0, 1 - |X_sub - X_ref| / max(X_ref, threshold))."""
    # 1. Точное совпадение -> q = 1.0
    assert calculate_q_score(100.0, 100.0, FLOOD_THRESHOLD_HA) == 1.0

    # 2. X_ref < порога (например, ref = 20 ha < порога 50 ha)
    # diff = 10 ha -> q = 1 - 10 / 50 = 0.8
    assert math.isclose(calculate_q_score(30.0, 20.0, 50.0), 0.8, rel_tol=1e-5)

    # 3. X_ref > порога (например, ref = 1000 ha > порога 200 ha)
    # diff = 100 ha -> q = 1 - 100 / 1000 = 0.9
    assert math.isclose(calculate_q_score(900.0, 1000.0, 200.0), 0.9, rel_tol=1e-5)

    # 4. Большая ошибка, превышающая знаменатель -> q = 0.0
    assert calculate_q_score(200.0, 20.0, 50.0) == 0.0

    # 5. Обработка некорректных значений и NaN
    assert calculate_q_score(float("nan"), 100.0, 50.0) == 0.0


def test_baseline_specificity():
    """Проверка формулы специфичности базовой линии Spec_base = 1 - min(1, excess / (0.005 * aoi_ha))."""
    aoi_ha = 10000.0  # допуск 0.5% составляет 50 ha

    # Без превышения (sub <= ref) -> Spec = 1.0
    assert calculate_baseline_spec(10.0, 20.0, aoi_ha) == 1.0

    # Превышение = 25 ha (половина допуска) -> Spec = 1 - 25/50 = 0.5
    assert math.isclose(calculate_baseline_spec(35.0, 10.0, aoi_ha), 0.5, rel_tol=1e-5)

    # Превышение = 50 ha (ровно допуск) -> Spec = 0.0
    assert calculate_baseline_spec(60.0, 10.0, aoi_ha) == 0.0

    # Превышение > 50 ha -> ограничивается значением 0.0
    assert calculate_baseline_spec(100.0, 10.0, aoi_ha) == 0.0


def test_official_score_live_computation():
    """Проверка онлайн-расчёта официального балла на существующем submission.csv."""
    repo_root = Path(__file__).resolve().parent.parent
    sub_path = repo_root / "submission.csv"
    pairs_path = repo_root / "hydrowatch_amur" / "pairs.csv"
    data_dir = repo_root / "hydrowatch_amur"
    preds_dir = repo_root / "predictions"

    assert sub_path.exists(), "submission.csv should exist"
    sub_df = pd.read_csv(sub_path)

    res = compute_live_official_score(
        submission_df=sub_df,
        pairs_csv_path=pairs_path,
        data_dir=data_dir,
        predictions_dir=preds_dir if preds_dir.exists() else None,
    )

    assert res.score > 0.35
    assert res.num_events == 8
    assert res.num_baselines == 3
    assert len(res.details) == 11

    # Проверка компонентов официальной формулы
    expected_score = 0.45 * res.q_flood + 0.25 * res.q_water_peak + 0.15 * res.q_water_pre + 0.15 * res.spec_base
    assert math.isclose(res.score, expected_score, abs_tol=1e-3)


def test_submission_validation(tmp_path):
    """Тест валидатора файла submission."""
    repo_root = Path(__file__).resolve().parent.parent
    pairs_path = repo_root / "hydrowatch_amur" / "pairs.csv"
    preds_dir = repo_root / "predictions"

    # Проверка реального submission.csv
    real_sub = repo_root / "submission.csv"
    val = validate_submission_file(real_sub, pairs_path, preds_dir)
    assert val.is_valid is True
    assert val.num_pairs == 11
    assert any("match official pairs" in c for c in val.passed_checks)

    # Проверка повреждённого submission (отсутствующая пара, flood > peak)
    bad_csv = tmp_path / "bad_submission.csv"
    bad_df = pd.DataFrame(
        [{"pair_id": "flood_2019_07_amur__belogorsk", "flood_ha": 999.0, "water_pre_ha": 10.0, "water_peak_ha": 50.0}]
    )
    bad_df.to_csv(bad_csv, index=False)

    bad_val = validate_submission_file(bad_csv, pairs_path, None)
    assert bad_val.is_valid is False
    assert any("Missing required pairs" in e for e in bad_val.errors)
    assert any("exceeds water_peak_ha" in e for e in bad_val.errors)
