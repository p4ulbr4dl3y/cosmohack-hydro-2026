"""Общие фикстуры тестов HydroWatch Amur."""

from __future__ import annotations

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

SAMPLE_PAIR_ID = "flood_2019_07_amur__blagoveshchensk"


@pytest.fixture
def synthetic_s1_scene(tmp_path, monkeypatch):
    """Подменяет каталоги данных и кэша синтетической сценой Sentinel-1.

    Тяжелые сцены S1 (~170 МБ на пару) не хранятся в репозитории, поэтому в окружении
    без них (CI) аналитика SAR считалась бы по аварийному пути с нулевым обратным
    рассеянием. Фикстура создаёт компактный растр с физически правдоподобными
    значениями VV/VH и изолирует дисковый кэш отчётов, чтобы аналитика пересчитывалась
    по этой сцене, а не подхватывалась из ранее закэшированного отчёта.
    """
    from src.service import data_loader as dl_module

    loader = dl_module.data_loader
    meta = loader.get_pair_meta(SAMPLE_PAIR_ID)
    assert meta is not None

    data_dir = tmp_path / "hydrowatch_amur"
    rasters_dir = data_dir / str(meta["rasters_dir"])
    rasters_dir.mkdir(parents=True, exist_ok=True)

    # VV/VH в дБ: гладкая вода даёт провал обратного рассеяния (30% площади сцены)
    shape = (100, 100)
    vv = np.full(shape, -9.0, dtype=np.float32)
    vh = np.full(shape, -14.0, dtype=np.float32)
    vv[:30, :] = -22.0
    vh[:30, :] = -28.0

    s1_tif = rasters_dir / "S1_peak_synthetic.tif"
    s1_pre_tif = rasters_dir / "S1_pre_synthetic.tif"
    for target in (s1_tif, s1_pre_tif):
        with rasterio.open(
            target,
            "w",
            driver="GTiff",
            height=shape[0],
            width=shape[1],
            count=2,
            dtype=np.float32,
            crs="EPSG:32652",
            transform=from_origin(127.0, 50.0, 10.0, 10.0),
        ) as dst:
            dst.write(vv, 1)
            dst.write(vh, 2)

    monkeypatch.setattr(loader, "data_dir", data_dir)
    monkeypatch.setattr(loader, "cache_dir", tmp_path / "cache")
    loader.cache_dir.mkdir(parents=True, exist_ok=True)
    loader._reports_cache.pop(SAMPLE_PAIR_ID, None)
    loader._sar_analytics_cache.pop(SAMPLE_PAIR_ID, None)

    yield loader

    loader._reports_cache.pop(SAMPLE_PAIR_ID, None)
    loader._sar_analytics_cache.pop(SAMPLE_PAIR_ID, None)
