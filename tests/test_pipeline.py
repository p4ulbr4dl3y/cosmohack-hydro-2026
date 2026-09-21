import os

import numpy as np

from src.segmentation import apply_mmu
from src.temporal import compute_receded_ha, compute_temporal_dynamics


def test_compute_receded_ha():
    # pre has 10 px water, peak has 6 px water overlapping -> 4 receded px
    water_pre = np.zeros((10, 10), dtype=np.uint8)
    water_peak = np.zeros((10, 10), dtype=np.uint8)
    water_pre[0, :6] = 1  # 6 px overlap region
    water_pre[0, 6:10] = 1  # 4 px receded (water on pre, gone by peak)
    water_peak[0, :6] = 1

    # px_ha for 10 m resolution: 10*10 / 10000 = 0.01 ha/px
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
    # Shape 10x10
    water_pre = np.zeros((10, 10), dtype=np.uint8)
    water_peak = np.zeros((10, 10), dtype=np.uint8)
    permanent = np.zeros((10, 10), dtype=np.uint8)

    # Pixel (2, 2): flood
    water_peak[2, 2] = 1

    # Pixel (4, 4): permanent water (both pre and peak)
    water_pre[4, 4] = 1
    water_peak[4, 4] = 1
    permanent[4, 4] = 1

    # Pixel (6, 6): receded
    water_pre[6, 6] = 1

    res = compute_temporal_dynamics(water_pre, water_peak, permanent)
    flood, receded = res["flood"], res["receded"]

    assert flood[2, 2] == 1
    assert flood[4, 4] == 0  # permanent excluded from flood
    assert flood[6, 6] == 0

    assert receded[6, 6] == 1
    assert receded[2, 2] == 0
    assert receded[4, 4] == 0


def test_mmu_filter():
    # Single isolated pixel < min_size=25 should be zeroed
    mask = np.zeros((20, 20), dtype=np.uint8)
    mask[2, 2] = 1  # 1 pixel component

    # 5x5 block = 25 pixels -> should be preserved
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
    # No NaNs, non-negative
    assert not df.isna().any().any()
    assert (df["flood_ha"] >= 0).all()
    assert (df["water_peak_ha"] >= df["flood_ha"]).all()
