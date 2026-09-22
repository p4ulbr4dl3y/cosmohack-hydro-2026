import numpy as np
import pytest
import rasterio

from src.service.data_loader import DataLoader


def test_data_loader_fresh_cache_report(tmp_path):
    # Инициализация DataLoader с чистым временным каталогом кэша
    loader = DataLoader(cache_dir=tmp_path / "cache")

    pair_id = "flood_2019_07_amur__blagoveshchensk"
    # Расчёт отчёта напрямую по растрам прогноза и AUX
    rep = loader.get_report(pair_id)
    assert rep is not None
    assert rep["pair_id"] == pair_id
    assert rep["flood_ha"] > 0
    assert "landcover" in rep
    assert rep["landcover"]["natural_vegetation_ha"] > 0
    assert rep["landcover"]["builtup_pct"] >= 0

    # Проверка, что файл кэша был записан
    cache_file = tmp_path / "cache" / f"report_{pair_id}.json"
    assert cache_file.exists()

    # Второй вызов использует кэш в памяти/на диске
    rep2 = loader.get_report(pair_id)
    assert rep2 == rep


def test_data_loader_report_exposes_sensor_and_generation_metadata(tmp_path):
    loader = DataLoader(cache_dir=tmp_path / "cache")
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    rep = loader.get_report(pair_id)

    assert rep["sensor_sar"] == "sentinel1"
    assert rep["sensor_optical"] == ""
    # Отметка времени UTC ISO-8601, формируемая во время сборки отчёта
    assert rep["generated_at"].endswith("+00:00")


def test_data_loader_backfills_legacy_cached_report(tmp_path):
    """Отчёты, закэшированные до появления полей sensor/generated_at, обновляются при чтении."""
    import json

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    pair_id = "flood_2019_07_amur__blagoveshchensk"

    # Имитация устаревшей записи кэша, записанной более старой версией схемы
    stale = {
        "pair_id": pair_id,
        "aoi_id": "blagoveshchensk",
        "flood_ha": 996.37,
        "landcover": {},
    }
    stale_file = cache_dir / f"report_{pair_id}.json"
    stale_file.write_text(json.dumps(stale), encoding="utf-8")

    rep = DataLoader(cache_dir=cache_dir).get_report(pair_id)

    assert rep["sensor_sar"] == "sentinel1"
    assert rep["generated_at"].endswith("+00:00")
    # Исходные метрики сохранены
    assert rep["flood_ha"] == 996.37


def test_data_loader_fresh_cache_geojson(tmp_path):
    loader = DataLoader(cache_dir=tmp_path / "cache")
    pair_id = "flood_2019_07_amur__blagoveshchensk"

    for layer in ["flood", "water_pre", "water_peak"]:
        gj = loader.get_geojson(pair_id, layer=layer)
        assert gj is not None
        assert gj["type"] == "FeatureCollection"
        assert len(gj["features"]) > 0

    assert loader.get_geojson(pair_id, layer="invalid_layer") is None


def test_data_loader_predict_spatial_temporal(tmp_path):
    loader = DataLoader(cache_dir=tmp_path / "cache")
    pair_id = "flood_2019_07_amur__blagoveshchensk"

    # 1. По pair_id
    res1 = loader.predict_spatial_temporal(pair_id=pair_id)
    assert res1["status"] == "success"
    assert res1["pair_id"] == pair_id
    assert "summary" in res1

    # 2. По перекрывающимся границам без pair_id
    bounds = [127.21, 50.12, 127.85, 50.45]
    res2 = loader.predict_spatial_temporal(bounds=bounds)
    assert res2["status"] == "success"
    assert "blagoveshchensk" in res2["pair_id"]

    # 3. Неизвестный pair_id вызывает ValueError
    with pytest.raises(ValueError):
        loader.predict_spatial_temporal(pair_id="non_existent_pair")


def test_data_loader_unknown_pair_returns_none(tmp_path):
    loader = DataLoader(cache_dir=tmp_path / "cache")
    assert loader.get_pair_meta("invalid_id") is None
    assert loader.get_report("invalid_id") is None
    assert loader.get_geojson("invalid_id") is None
    assert loader.get_shapefile_zip("invalid_id") is None


def test_data_loader_missing_pairs_csv(tmp_path):
    with pytest.raises(FileNotFoundError, match="pairs.csv не найден"):
        DataLoader(data_dir=tmp_path / "nonexistent", cache_dir=tmp_path / "cache")


def test_data_loader_report_no_submission_csv(tmp_path):
    loader = DataLoader(
        submission_csv=tmp_path / "missing_sub.csv",
        cache_dir=tmp_path / "cache",
    )
    rep = loader.get_report("flood_2019_07_amur__blagoveshchensk")
    assert rep is not None
    # Площади берутся из растров, поэтому они присутствуют даже без submission.csv
    assert rep["flood_ha"] > 0
    assert rep["water_pre_ha"] > 0
    assert rep["water_peak_ha"] > 0


def test_data_loader_report_ignores_wrong_submission_csv(tmp_path):
    """Отдаваемые площади берутся из растров, а не из submission.csv (аудит D10)."""
    import json

    import rasterio

    pair_id = "flood_2019_07_amur__blagoveshchensk"
    wrong_sub = tmp_path / "wrong_submission.csv"
    wrong_sub.write_text(
        f"pair_id,flood_ha,water_pre_ha,water_peak_ha\n{pair_id},1.0,2.0,3.0\n",
        encoding="utf-8",
    )
    cache_dir = tmp_path / "cache"
    loader = DataLoader(submission_csv=wrong_sub, cache_dir=cache_dir)

    rep = loader.get_report(pair_id)
    assert rep is not None

    def raster_ha(layer: str) -> float:
        with rasterio.open(loader.predictions_dir / f"{pair_id}_{layer}.tif") as src:
            px_ha = (abs(src.res[0]) * abs(src.res[1])) / 10000.0
            return round(float((src.read(1) == 1).sum()) * px_ha, 2)

    assert rep["flood_ha"] == raster_ha("flood")
    assert rep["water_pre_ha"] == raster_ha("water_pre")
    assert rep["water_peak_ha"] == raster_ha("water_peak")
    # Намеренно неверные значения CSV никогда не отдаются
    assert rep["flood_ha"] != 1.0
    assert rep["water_pre_ha"] != 2.0

    # Кэшированный отчёт по всему AOI также содержит измеренные по растру значения
    cache_file = cache_dir / f"report_{pair_id}.json"
    assert cache_file.exists()
    cached = json.loads(cache_file.read_text(encoding="utf-8"))
    assert cached["flood_ha"] == raster_ha("flood")
    assert cached["water_peak_ha"] == raster_ha("water_peak")


def test_data_loader_get_pairs(tmp_path):
    loader = DataLoader(cache_dir=tmp_path / "cache")
    pairs = loader.get_pairs()
    assert isinstance(pairs, list)
    assert len(pairs) > 0


def test_data_loader_report_disk_cache_hit(tmp_path):
    loader1 = DataLoader(cache_dir=tmp_path / "cache")
    rep1 = loader1.get_report("flood_2019_07_amur__blagoveshchensk")
    assert rep1 is not None

    # Создание нового DataLoader с тем же cache_dir для попадания в дисковый кэш
    loader2 = DataLoader(cache_dir=tmp_path / "cache")
    rep2 = loader2.get_report("flood_2019_07_amur__blagoveshchensk")
    assert rep2 == rep1


def test_data_loader_shapefile_with_features(tmp_path):
    loader = DataLoader(cache_dir=tmp_path / "cache")
    shp_bytes = loader.get_shapefile_zip("flood_2019_07_amur__blagoveshchensk", layer="flood")
    assert shp_bytes is not None
    assert len(shp_bytes) > 0


def test_data_loader_report_missing_rasters(tmp_path):
    import shutil

    from src.service.data_loader import DATA_DIR

    fake_data = tmp_path / "data"
    fake_data.mkdir()
    shutil.copy(DATA_DIR / "pairs.csv", fake_data / "pairs.csv")

    # При наличии submission.csv: строка 235 с корректными числами
    loader = DataLoader(
        data_dir=fake_data,
        predictions_dir=tmp_path / "empty_preds",
        cache_dir=tmp_path / "cache1",
    )
    rep = loader.get_report("flood_2019_07_amur__blagoveshchensk")
    assert rep is not None
    assert rep["permanent_ha"] >= 0.0

    # Без submission.csv: резервный путь строки 235 и строки 238, 240, 242
    loader_no_sub = DataLoader(
        data_dir=fake_data,
        predictions_dir=tmp_path / "empty_preds",
        submission_csv=tmp_path / "no_sub.csv",
        cache_dir=tmp_path / "cache2",
    )
    rep_no_sub = loader_no_sub.get_report("flood_2019_07_amur__blagoveshchensk")
    assert rep_no_sub is not None
    assert rep_no_sub["flood_ha"] == 0.0
    assert rep_no_sub["water_pre_ha"] == 0.0


def test_data_loader_receded_ha_exception(tmp_path, monkeypatch):
    loader = DataLoader(cache_dir=tmp_path / "cache")

    def mock_compute(*args, **kwargs):
        raise RuntimeError("Test receded error")

    monkeypatch.setattr("src.service.data_loader.compute_receded_ha", mock_compute)
    rep = loader.get_report("flood_2019_07_amur__blagoveshchensk")
    assert rep["receded_ha"] == 0.0


def test_data_loader_geojson_missing_rasters(tmp_path):
    loader = DataLoader(
        predictions_dir=tmp_path / "empty_preds",
        cache_dir=tmp_path / "cache",
    )
    assert loader.get_geojson("flood_2019_07_amur__blagoveshchensk", layer="flood") is None


def test_geojson_total_area_matches_raster(tmp_path):
    """Экспортированные контуры не должны молча усекать картированную площадь паводка.

    Конфигурация по умолчанию отключает ограничение числа контуров, поэтому суммарная
    площадь полигонов должна оставаться в пределах малого допуска от площади пикселей растра.
    """
    import rasterio

    pair_id = "flood_2019_07_amur__blagoveshchensk"
    loader = DataLoader(cache_dir=tmp_path / "cache")
    geojson = loader.get_geojson(pair_id, layer="flood")
    assert geojson is not None

    with rasterio.open(loader.predictions_dir / f"{pair_id}_flood.tif") as src:
        raster_ha = float((src.read(1) == 1).sum()) * 0.01

    contour_ha = sum(f["properties"]["area_ha"] for f in geojson["features"])
    assert contour_ha <= raster_ha * 1.02
    # Оба ограничения в принципе приводят к потерям: крошечные кластеры (<500 m²) и упрощение
    # полигонов. Совокупные потери должны оставаться малыми (< 5% картированной площади).
    assert contour_ha >= raster_ha * 0.95


def test_geojson_contour_cap_is_config_driven(tmp_path, monkeypatch):
    """Ненулевое значение geojson_max_contours ограничивает экспорт; 0 сохраняет все контуры."""
    from src.config import HydroConfig

    pair_id = "flood_2019_07_amur__blagoveshchensk"

    real_from_yaml = HydroConfig.from_yaml

    # Конфигурация по умолчанию: без ограничения -> экспортируются все контуры
    uncapped = DataLoader(cache_dir=tmp_path / "cache_uncapped").get_geojson(pair_id, layer="flood")
    assert uncapped is not None
    assert len(uncapped["features"]) > 5

    def capped_from_yaml(cls, path=None):
        cfg = real_from_yaml(path)
        cfg.extra["geojson_max_contours"] = 5
        return cfg

    monkeypatch.setattr(HydroConfig, "from_yaml", classmethod(capped_from_yaml))
    capped = DataLoader(cache_dir=tmp_path / "cache_capped").get_geojson(pair_id, layer="flood")
    assert capped is not None
    assert len(capped["features"]) == 5


def test_data_loader_predict_non_overlapping_bounds(tmp_path):
    loader = DataLoader(cache_dir=tmp_path / "cache")
    with pytest.raises(ValueError, match="не пересекают"):
        loader.predict_spatial_temporal(bounds=[0.0, 0.0, 1.0, 1.0])


def test_data_loader_empty_raster_geojson_and_shapefile(tmp_path):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    preds_dir = tmp_path / "preds"
    preds_dir.mkdir(parents=True, exist_ok=True)
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    tif_path = preds_dir / f"{pair_id}_flood.tif"

    transform = from_origin(127.5, 50.5, 0.0001, 0.0001)
    with rasterio.open(
        tif_path,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype=rasterio.uint8,
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(np.zeros((10, 10), dtype=np.uint8), 1)

    loader = DataLoader(
        predictions_dir=preds_dir,
        cache_dir=tmp_path / "cache",
    )
    gj = loader.get_geojson(pair_id, layer="flood")
    assert gj is not None
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) == 0

    shp_zip = loader.get_shapefile_zip(pair_id, layer="flood")
    assert shp_zip is not None
    assert len(shp_zip) > 0


def test_data_loader_predict_default_first_pair(tmp_path):
    loader = DataLoader(cache_dir=tmp_path / "cache")
    res = loader.predict_spatial_temporal()
    assert res["status"] == "success"
    assert res["pair_id"] == loader._pairs_cache[0]["pair_id"]


def test_data_loader_morphological_micro_island_filtering(tmp_path):
    """Микроострова (одиночные пиксели и кластеры ниже порога) отфильтровываются перед shapes()."""
    from rasterio.transform import from_origin

    pair_id = "flood_2019_07_amur__blagoveshchensk"
    preds_dir = tmp_path / "preds"
    preds_dir.mkdir(parents=True)
    flood_tif = preds_dir / f"{pair_id}_flood.tif"

    arr = np.zeros((50, 50), dtype=np.uint8)
    # Реальный крупный объект паводка (10x10 = 100 пикселей = 10,000 sqm)
    arr[10:20, 10:20] = 1
    # Изолированные микроострова размером в один пиксель (спекл-шум)
    arr[2, 2] = 1
    arr[2, 40] = 1
    arr[40, 2] = 1
    arr[45, 45] = 1

    transform = from_origin(127.0, 50.0, 10.0, 10.0)
    with rasterio.open(
        flood_tif,
        "w",
        driver="GTiff",
        height=50,
        width=50,
        count=1,
        dtype=np.uint8,
        crs="EPSG:32652",
        transform=transform,
    ) as dst:
        dst.write(arr, 1)

    loader = DataLoader(
        predictions_dir=preds_dir,
        cache_dir=tmp_path / "cache",
    )
    gj = loader.get_geojson(pair_id, layer="flood")
    assert gj is not None
    # Только 1 объект (крупное пятно 10x10), микроострова были отфильтрованы!
    assert len(gj["features"]) == 1
    assert gj["features"][0]["properties"]["area_ha"] == 1.0  # 100 пикс * 0.01 га/пикс


def test_get_report_dedupes_concurrent_cold_build(tmp_path, monkeypatch):
    """Параллельные запросы к одной холодной паре выполняют тяжёлый расчёт один раз.

    Синхронные эндпоинты FastAPI работают в threadpool, поэтому без блокировки
    per-pair ``N`` одновременных запросов повторяли бы репроекцию растров ``N`` раз.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor

    pair_id = "flood_2019_07_amur__blagoveshchensk"
    loader = DataLoader(cache_dir=tmp_path / "cache")
    loader._reports_cache.pop(pair_id, None)

    real_build = loader._build_report
    calls: list[str] = []
    calls_lock = threading.Lock()

    def counting_build(pid, query_geom=None):
        with calls_lock:
            calls.append(pid)
        # Задержка расширяет окно гонки, в котором параллельные потоки должны ждать.
        import time

        time.sleep(0.05)
        return real_build(pid, query_geom)

    monkeypatch.setattr(loader, "_build_report", counting_build)

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda _: loader.get_report(pair_id), range(8)))

    # Тяжёлый расчёт выполнен ровно один раз, все потоки получили один отчёт
    assert len(calls) == 1
    assert all(r is not None and r["pair_id"] == pair_id for r in results)
    assert len({id(r) for r in results}) == 1
