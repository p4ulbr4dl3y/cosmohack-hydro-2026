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

    # Некорректные параметры (aoi <= 0, NaN)
    assert calculate_baseline_spec(10.0, 20.0, 0.0) == 0.0
    assert calculate_baseline_spec(10.0, 20.0, -100.0) == 0.0
    assert calculate_baseline_spec(float("nan"), 20.0, aoi_ha) == 0.0
    assert calculate_baseline_spec(10.0, float("nan"), aoi_ha) == 0.0


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


def test_official_score_missing_pairs_csv(tmp_path):
    import pytest

    fake_pairs = tmp_path / "non_existent_pairs.csv"
    sub_df = pd.DataFrame({"pair_id": ["p1"]})
    with pytest.raises(FileNotFoundError, match="pairs.csv не найден"):
        compute_live_official_score(sub_df, fake_pairs, tmp_path)


def test_official_score_missing_ref_json_and_no_baselines(tmp_path):
    pairs_csv = tmp_path / "pairs.csv"
    pairs_df = pd.DataFrame(
        [
            {"pair_id": "pair_missing", "reference_mask": "missing.tif", "event_kind": "rain_flood"},
            {"pair_id": "pair_exist", "reference_mask": "exist.tif", "event_kind": "rain_flood"},
        ]
    )
    pairs_df.to_csv(pairs_csv, index=False)

    # Создаем только exist.json, missing.json оставляем отсутствующим
    import json

    exist_json = tmp_path / "exist.json"
    exist_json.write_text(
        json.dumps(
            {
                "stats": {
                    "aoi_ha": 50000.0,
                    "flood_ha": 100.0,
                    "water_pre_ha": 50.0,
                    "water_peak_ha": 150.0,
                }
            }
        ),
        encoding="utf-8",
    )

    sub_df = pd.DataFrame(
        [
            {"pair_id": "pair_exist", "flood_ha": 100.0, "water_pre_ha": 50.0, "water_peak_ha": 150.0},
        ]
    )

    # predictions_dir с растром, где sub_flood == 0 и raster_ha > 0, либо ошибка чтения
    preds_dir = tmp_path / "preds"
    preds_dir.mkdir()
    corrupt_tif = preds_dir / "pair_exist_flood.tif"
    corrupt_tif.write_text("not a valid tiff file")

    res = compute_live_official_score(
        submission_df=sub_df,
        pairs_csv_path=pairs_csv,
        data_dir=tmp_path,
        predictions_dir=preds_dir,
    )

    assert res.num_baselines == 0
    assert res.spec_base == 1.0  # Ветка строки 251: базовых пар нет -> spec_base_mean = 1.0
    assert len(res.details) == 1


def test_official_score_raster_zero_sub_flood(tmp_path):
    import json

    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    pairs_csv = tmp_path / "pairs.csv"
    pd.DataFrame(
        [
            {"pair_id": "p0", "reference_mask": "p0.tif", "event_kind": "rain_flood"},
        ]
    ).to_csv(pairs_csv, index=False)

    (tmp_path / "p0.json").write_text(
        json.dumps({"stats": {"aoi_ha": 10000.0, "flood_ha": 0.0, "water_pre_ha": 10.0, "water_peak_ha": 10.0}}),
        encoding="utf-8",
    )

    sub_df = pd.DataFrame(
        [
            {"pair_id": "p0", "flood_ha": 0.0, "water_pre_ha": 10.0, "water_peak_ha": 10.0},
        ]
    )

    preds_dir = tmp_path / "preds"
    preds_dir.mkdir()
    tif_path = preds_dir / "p0_flood.tif"
    transform = from_origin(100.0, 50.0, 10.0, 10.0)
    data = np.zeros((1, 10, 10), dtype=np.uint8)
    data[0, 2:5, 2:5] = 1  # 9 pixels = 0.09 ha > 0
    with rasterio.open(
        tif_path,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype=np.uint8,
        crs="EPSG:32652",
        transform=transform,
    ) as dst:
        dst.write(data)

    res = compute_live_official_score(
        submission_df=sub_df,
        pairs_csv_path=pairs_csv,
        data_dir=tmp_path,
        predictions_dir=preds_dir,
    )
    # Строки 212: raster_ha > 0 при sub_flood == 0 -> disc_pct = 100.0
    assert res.details[0]["raster_csv_discrepancy_pct"] == 100.0


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
    assert any("соответствуют официальному реестру пар" in c for c in val.passed_checks)

    # Проверка повреждённого submission (отсутствующая пара, flood > peak)
    bad_csv = tmp_path / "bad_submission.csv"
    bad_df = pd.DataFrame(
        [{"pair_id": "flood_2019_07_amur__belogorsk", "flood_ha": 999.0, "water_pre_ha": 10.0, "water_peak_ha": 50.0}]
    )
    bad_df.to_csv(bad_csv, index=False)

    bad_val = validate_submission_file(bad_csv, pairs_path, None)
    assert bad_val.is_valid is False
    assert any("Отсутствуют обязательные пары" in e for e in bad_val.errors)
    assert any("превышает water_peak_ha" in e for e in bad_val.errors)


def test_submission_validation_edge_cases(tmp_path):
    # 1. Несуществующий файл посылки (строка 285)
    non_existent = tmp_path / "does_not_exist.csv"
    res_none = validate_submission_file(non_existent, tmp_path / "pairs.csv")
    assert res_none.is_valid is False
    assert any("не существует" in e for e in res_none.errors)

    # 2. Неразбираемый CSV (строки 296-297)
    corrupt_csv = tmp_path / "corrupt.csv"
    # Пишем некорректный поток байтов, на котором падает pandas, либо некорректный синтаксис
    corrupt_csv.write_bytes(b"\x00\x00\x00\xff\xfe\xff\xfe")
    res_corrupt = validate_submission_file(corrupt_csv, tmp_path / "pairs.csv")
    assert res_corrupt.is_valid is False
    assert any("Не удалось разобрать CSV" in e for e in res_corrupt.errors)

    # 3. Некорректные столбцы (строка 311)
    bad_cols_csv = tmp_path / "bad_cols.csv"
    pd.DataFrame(
        {
            "pair_id": ["pair1"],
            "wrong_col": [1],
            "water_pre_ha": [5.0],
            "water_peak_ha": [15.0],
        }
    ).to_csv(bad_cols_csv, index=False)
    res_cols = validate_submission_file(bad_cols_csv, tmp_path / "non_existent_pairs.csv")
    assert res_cols.is_valid is False
    assert any("Некорректные столбцы" in e for e in res_cols.errors)

    # 4. Лишние неожиданные пары (строка 327)
    pairs_csv = tmp_path / "pairs.csv"
    pd.DataFrame({"pair_id": ["pair1"]}).to_csv(pairs_csv, index=False)
    extra_pairs_csv = tmp_path / "extra_pairs.csv"
    pd.DataFrame(
        {
            "pair_id": ["pair1", "unexpected_pair"],
            "flood_ha": [10.0, 20.0],
            "water_pre_ha": [5.0, 5.0],
            "water_peak_ha": [15.0, 25.0],
        }
    ).to_csv(extra_pairs_csv, index=False)
    res_extra = validate_submission_file(extra_pairs_csv, pairs_csv)
    assert res_extra.is_valid is False
    assert any("Неожиданные лишние пары" in e for e in res_extra.errors)

    # 5. Значения NaN (строка 334)
    nan_csv = tmp_path / "nan.csv"
    pd.DataFrame(
        {
            "pair_id": ["pair1"],
            "flood_ha": [float("nan")],
            "water_pre_ha": [5.0],
            "water_peak_ha": [15.0],
        }
    ).to_csv(nan_csv, index=False)
    res_nan = validate_submission_file(nan_csv, pairs_csv)
    assert res_nan.is_valid is False
    assert any("содержит значения NaN" in e for e in res_nan.errors)

    # 6. Нечисловые значения (строки 342-344) и отрицательная площадь (строка 347)
    non_num_csv = tmp_path / "non_num.csv"
    pd.DataFrame(
        {
            "pair_id": ["pair1", "pair2"],
            "flood_ha": ["invalid_text", -5.0],
            "water_pre_ha": [5.0, -2.0],
            "water_peak_ha": [15.0, -1.0],
        }
    ).to_csv(non_num_csv, index=False)
    res_non_num = validate_submission_file(non_num_csv, pairs_csv)
    assert res_non_num.is_valid is False
    assert any("нечисловые значения" in e for e in res_non_num.errors)
    assert any("отрицательные значения площади" in e for e in res_non_num.errors)


def test_submission_validation_raster_checks(tmp_path):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    pairs_csv = tmp_path / "pairs.csv"
    pd.DataFrame({"pair_id": ["p1", "p2", "p3", "p4"]}).to_csv(pairs_csv, index=False)

    sub_csv = tmp_path / "sub.csv"
    pd.DataFrame(
        {
            "pair_id": ["p1", "p2", "p3", "p4"],
            "flood_ha": [0.0, 100.0, 100.0, 50.0],
            "water_pre_ha": [5.0, 5.0, 5.0, 5.0],
            "water_peak_ha": [10.0, 120.0, 120.0, 60.0],
        }
    ).to_csv(sub_csv, index=False)

    preds_dir = tmp_path / "preds"
    preds_dir.mkdir()

    transform = from_origin(100.0, 50.0, 10.0, 10.0)

    # p1: fl == 0, в растре 10 пикселей (0.1 га) -> срабатывают строки 380-381 (disc_pct = 100.0, превышает лимит 2%)
    with rasterio.open(
        preds_dir / "p1_flood.tif",
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype=np.uint8,
        crs="EPSG:4326",  # Строка 372: предупреждение о CRS, отличном от 32652
        transform=transform,
    ) as dst:
        d = np.zeros((1, 10, 10), dtype=np.uint8)
        d[0, 0, :5] = 1
        dst.write(d)

    # p2: отсутствующий растр -> срабатывают строки 364-366

    # p3: расхождение растра и CSV превышает 2% -> срабатывают строки 393-396
    with rasterio.open(
        preds_dir / "p3_flood.tif",
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype=np.uint8,
        crs="EPSG:32652",
        transform=transform,
    ) as dst:
        # 1000 пикселей = 10.0 га != 100.0 га -> disc_pct = 90%
        d = np.zeros((1, 10, 10), dtype=np.uint8)
        dst.write(d)

    # p4: исключение при чтении растра -> срабатывают строки 397-399
    (preds_dir / "p4_flood.tif").write_text("corrupted content")

    val = validate_submission_file(sub_csv, pairs_csv, preds_dir)
    assert any("ожидался EPSG:32652" in w for w in val.warnings)
    assert any("Отсутствует растровый прогноз: p2_flood.tif" in w for w in val.warnings)
    assert any("превышает лимит 2%" in w for w in val.warnings)
    assert any("Ошибка проверки растра p4_flood.tif" in w for w in val.warnings)
