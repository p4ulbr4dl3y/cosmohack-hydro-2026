"""Тесты основных алгоритмических модулей: config, filters, indices, geo_utils."""

import numpy as np
import rasterio
from rasterio.transform import from_origin

from src.config import (
    LEE_LOOKS,
    LEE_SIZE,
    MMU_MIN_PIXELS,
    OTSU_MAX_DB,
    OTSU_MIN_DB,
    PIXEL_SIZE_HA,
    PIXEL_SIZE_M,
    HydroConfig,
)
from src.filters import apply_mmu, refined_lee_filter, speckle_filter
from src.geo_utils import clip_by_aoi, read_raster_with_meta, resample_to_target
from src.indices import calculate_optical_indices, segment_optical


def test_hydro_config_defaults():
    cfg = HydroConfig()
    assert cfg.lee_looks == LEE_LOOKS
    assert cfg.lee_size == LEE_SIZE
    assert cfg.mmu_min_pixels == MMU_MIN_PIXELS
    assert cfg.otsu_min_db == OTSU_MIN_DB
    assert cfg.otsu_max_db == OTSU_MAX_DB
    assert cfg.pixel_size_m == PIXEL_SIZE_M
    assert cfg.pixel_size_ha == PIXEL_SIZE_HA

    d = cfg.to_dict()
    assert d["mmu_min_pixels"] == 25
    assert d["otsu_min_db"] == -22.0


def test_hydro_config_from_yaml(tmp_path):
    # Несуществующий yaml
    cfg = HydroConfig.from_yaml(tmp_path / "non_existent.yaml")
    assert cfg.mmu_min_pixels == 25

    # Путь к yaml по умолчанию (None)
    cfg_default = HydroConfig.from_yaml(None)
    assert cfg_default.mmu_min_pixels == 25

    # Пользовательский yaml с дополнительными полями
    custom_yaml = tmp_path / "custom.yaml"
    custom_yaml.write_text("mmu_min_pixels: 50\ncustom_field: 123\n", encoding="utf-8")
    cfg_custom = HydroConfig.from_yaml(custom_yaml)
    assert cfg_custom.mmu_min_pixels == 50
    assert cfg_custom.extra["custom_field"] == 123
    assert cfg_custom.to_dict()["custom_field"] == 123


def test_filters_refined_lee_and_speckle():
    data = np.full((15, 15), -15.0, dtype=np.float32)
    filtered = refined_lee_filter(data, size=5, n_looks=4.4)
    assert np.allclose(filtered, -15.0, atol=0.1)

    # speckle_filter с None
    assert speckle_filter(None) is None

    # Некорректный вход speckle_filter
    inv = np.full((5, 5), -999.0, dtype=np.float32)
    assert np.array_equal(speckle_filter(inv), inv)

    # Методы speckle_filter
    res_lee = speckle_filter(data, method="lee", size=5)
    assert res_lee.shape == data.shape
    res_med = speckle_filter(data, method="median", size=5)
    assert res_med.shape == data.shape
    res_uni = speckle_filter(data, method="uniform", size=5)
    assert res_uni.shape == data.shape


def test_filters_apply_mmu():
    # Пустая маска
    empty = np.zeros((10, 10), dtype=bool)
    assert np.array_equal(apply_mmu(empty, min_size=5), empty)

    # Малый кластер
    mask = np.zeros((20, 20), dtype=bool)
    mask[2:4, 2:4] = True  # 4 пикселя
    mask[10:15, 10:15] = True  # 25 пикселей
    cleaned = apply_mmu(mask, min_size=10)
    assert not np.any(cleaned[2:4, 2:4])
    assert np.all(cleaned[10:15, 10:15])

    # min_size равный None использует значение по умолчанию MMU_MIN_PIXELS
    cleaned_def = apply_mmu(mask, min_size=None)
    assert not np.any(cleaned_def[2:4, 2:4])


def test_filters_apply_mmu_zero_features(monkeypatch):
    mask = np.zeros((10, 10), dtype=bool)
    mask[2:5, 2:5] = True
    monkeypatch.setattr("src.filters.label", lambda m, structure=None: (np.zeros_like(m), 0))
    res = apply_mmu(mask, min_size=10)
    assert np.array_equal(res, mask)


def test_indices_calculations(tmp_path):
    # calculate_optical_indices
    green = np.array([[0.2, 0.3], [0.1, 0.4]], dtype=np.float32)
    nir = np.array([[0.1, 0.1], [0.2, 0.2]], dtype=np.float32)
    swir1 = np.array([[0.05, 0.1], [0.1, 0.1]], dtype=np.float32)
    swir2 = np.array([[0.05, 0.05], [0.05, 0.05]], dtype=np.float32)
    indices = calculate_optical_indices(green, nir, swir1, swir2)
    assert "ndwi" in indices
    assert "mndwi" in indices
    assert indices["ndwi"].shape == (2, 2)
    # NDVI/AWEIsh требуют собственных полос и не должны молча подделываться
    assert "ndvi" not in indices
    assert "aweish" not in indices

    # Несуществующий вход segment_optical
    w, v = segment_optical(tmp_path / "non_existent.tif", (10, 10))
    assert w is None
    assert not np.any(v)

    # segment_optical < 8 полос
    short_tif = tmp_path / "short.tif"
    transform = from_origin(127.0, 50.0, 10.0, 10.0)
    with rasterio.open(
        short_tif,
        "w",
        driver="GTiff",
        height=5,
        width=5,
        count=3,
        dtype=np.float32,
        crs="EPSG:32652",
        transform=transform,
    ) as dst:
        dst.write(np.zeros((3, 5, 5), dtype=np.float32))
    w, v = segment_optical(short_tif, (5, 5))
    assert w is None
    assert not np.any(v)


def test_indices_optional_bands_enable_ndvi_and_aweish():
    """NDVI и AWEIsh формируются только при предоставлении полос red/blue."""
    green = np.array([[0.20, 0.30]], dtype=np.float32)
    nir = np.array([[0.10, 0.40]], dtype=np.float32)
    swir1 = np.array([[0.05, 0.10]], dtype=np.float32)
    swir2 = np.array([[0.02, 0.05]], dtype=np.float32)
    red = np.array([[0.15, 0.20]], dtype=np.float32)
    blue = np.array([[0.08, 0.09]], dtype=np.float32)

    with_red = calculate_optical_indices(green, nir, swir1, swir2, red=red)
    assert "ndvi" in with_red
    assert "aweish" not in with_red
    expected_ndvi = (nir - red) / (nir + red)
    assert np.allclose(with_red["ndvi"], expected_ndvi)

    with_blue = calculate_optical_indices(green, nir, swir1, swir2, blue=blue)
    assert "aweish" in with_blue
    assert "ndvi" not in with_blue
    expected_aweish = blue + 2.5 * green - 1.5 * (nir + swir1) - 0.25 * swir2
    assert np.allclose(with_blue["aweish"], expected_aweish)

    both = calculate_optical_indices(green, nir, swir1, swir2, blue=blue, red=red)
    assert set(both) == {"ndwi", "mndwi", "ndvi", "aweish"}


def test_geo_utils_read_raster_with_meta(tmp_path):
    tif_path = tmp_path / "test_meta.tif"
    transform = from_origin(100.0, 50.0, 10.0, 10.0)
    data = np.ones((2, 10, 10), dtype=np.float32)
    data[1] = 2.0

    with rasterio.open(
        tif_path,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=2,
        dtype=np.float32,
        crs="EPSG:32652",
        transform=transform,
    ) as dst:
        dst.write(data)

    # Чтение всех полос
    arr_all, meta = read_raster_with_meta(tif_path)
    assert arr_all.shape == (2, 10, 10)
    assert meta["count"] == 2

    # Чтение одной полосы
    arr_b1, _ = read_raster_with_meta(tif_path, band=1)
    assert arr_b1.shape == (10, 10)
    assert arr_b1[0, 0] == 1.0

    # Чтение списка полос
    arr_list, _ = read_raster_with_meta(tif_path, band=[1, 2])
    assert arr_list.shape == (2, 10, 10)


def test_geo_utils_resample_to_target(tmp_path):
    src_path = tmp_path / "src.tif"
    transform = from_origin(100.0, 50.0, 10.0, 10.0)
    data = np.ones((1, 10, 10), dtype=np.float32) * 5.0

    with rasterio.open(
        src_path,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype=np.float32,
        crs="EPSG:32652",
        transform=transform,
    ) as dst:
        dst.write(data)

    target_shape = (20, 20)
    target_transform = from_origin(100.0, 50.0, 5.0, 5.0)
    res = resample_to_target(
        source_path=src_path,
        band=1,
        target_shape=target_shape,
        target_transform=target_transform,
        target_crs="EPSG:32652",
    )
    assert res.shape == (20, 20)
    assert np.allclose(res, 5.0)


def test_geo_utils_clip_by_aoi():
    from shapely.geometry import box

    mask = np.ones((10, 10), dtype=np.uint8)
    transform = from_origin(0.0, 100.0, 10.0, 10.0)

    # Полигон, покрывающий левую половину (от 0 до 50 по X, от 0 до 100 по Y)
    geom = box(0.0, 0.0, 50.0, 100.0)
    clipped = clip_by_aoi(mask, geom, transform)
    assert clipped.shape == (10, 10)
    # Левые столбцы (от 0 до 4) должны быть 1, правые столбцы (от 5 до 9) должны быть 0
    assert np.all(clipped[:, :5] == 1)
    assert np.all(clipped[:, 5:] == 0)
