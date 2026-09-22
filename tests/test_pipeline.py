import os

import numpy as np

from src.segmentation import apply_mmu
from src.temporal import compute_receded_ha, compute_temporal_dynamics


def test_compute_receded_ha():
    # pre содержит 10 px воды, peak содержит 6 px воды с перекрытием -> 4 px отступившей воды
    water_pre = np.zeros((10, 10), dtype=np.uint8)
    water_peak = np.zeros((10, 10), dtype=np.uint8)
    water_pre[0, :6] = 1  # область перекрытия 6 px
    water_pre[0, 6:10] = 1  # 4 px отступившей воды (вода на pre, исчезнувшая к peak)
    water_peak[0, :6] = 1

    # px_ha для разрешения 10 м: 10*10 / 10000 = 0.01 ha/px
    receded_ha = compute_receded_ha(water_pre, water_peak, px_ha=0.01)
    assert receded_ha == 4 * 0.01
    assert receded_ha == 0.04


def test_compute_receded_ha_zero():
    water_pre = np.full((5, 5), 1, dtype=np.uint8)
    water_peak = np.full((5, 5), 1, dtype=np.uint8)
    assert compute_receded_ha(water_pre, water_peak, px_ha=0.01) == 0.0

    empty = np.zeros((5, 5), dtype=np.uint8)
    assert compute_receded_ha(empty, empty, px_ha=0.01) == 0.0


def test_temporal_dynamics_logic():
    # Размер 10x10
    water_pre = np.zeros((10, 10), dtype=np.uint8)
    water_peak = np.zeros((10, 10), dtype=np.uint8)
    permanent = np.zeros((10, 10), dtype=np.uint8)

    # Пиксель (2, 2): паводок
    water_peak[2, 2] = 1

    # Пиксель (4, 4): постоянная вода (и на pre, и на peak)
    water_pre[4, 4] = 1
    water_peak[4, 4] = 1
    permanent[4, 4] = 1

    # Пиксель (6, 6): отступившая вода
    water_pre[6, 6] = 1

    res = compute_temporal_dynamics(water_pre, water_peak, permanent)
    flood, receded = res["flood"], res["receded"]

    assert flood[2, 2] == 1
    assert flood[4, 4] == 0  # постоянная вода исключена из паводка
    assert flood[6, 6] == 0

    assert receded[6, 6] == 1
    assert receded[2, 2] == 0
    assert receded[4, 4] == 0


def test_mmu_filter():
    # Одиночный изолированный пиксель < min_size=25 должен обнуляться
    mask = np.zeros((20, 20), dtype=np.uint8)
    mask[2, 2] = 1  # компонента из 1 пикселя

    # Блок 5x5 = 25 пикселей -> должен сохраниться
    mask[5:10, 5:10] = 1

    cleaned = apply_mmu(mask, min_size=25)
    assert cleaned[2, 2] == 0
    assert np.sum(cleaned[5:10, 5:10]) == 25


def test_submission_exists_and_valid():
    assert os.path.exists("submission.csv")
    import pandas as pd

    df = pd.read_csv("submission.csv")
    assert len(df) == 11
    assert list(df.columns) == ["pair_id", "flood_ha", "water_pre_ha", "water_peak_ha"]
    # Нет NaN, значения неотрицательны
    assert not df.isna().any().any()
    assert (df["flood_ha"] >= 0).all()
    assert (df["water_peak_ha"] >= df["flood_ha"]).all()


def test_refined_lee_filter_noise_reduction():
    from src.segmentation import refined_lee_filter

    rng = np.random.default_rng(42)
    clean = np.full((30, 30), -18.0, dtype=np.float32)
    noise = rng.normal(0.0, 3.0, (30, 30)).astype(np.float32)
    noisy = clean + noise

    filtered = refined_lee_filter(noisy, size=7, n_looks=4.4)
    # Дисперсия отфильтрованного изображения в однородной области должна быть существенно ниже, чем у зашумлённого
    assert np.var(filtered) < np.var(noisy)


def test_compute_otsu_threshold_synthetic():
    from src.segmentation import compute_otsu_threshold

    rng = np.random.default_rng(100)
    water = rng.normal(-21.0, 0.4, 600)
    land = rng.normal(-15.0, 0.4, 600)
    synthetic_vv = np.concatenate([water, land]).reshape((30, 40)).astype(np.float32)

    th = compute_otsu_threshold(synthetic_vv, min_db=-22.0, max_db=-14.5)
    assert -21.0 < th < -14.5
