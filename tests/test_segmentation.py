"""Тесты мультимодальной сегментации воды и спекл-фильтрации."""

import warnings

import numpy as np
import rasterio
from rasterio.transform import from_origin

from src.segmentation import (
    apply_mmu,
    compute_otsu_threshold,
    detect_flooded_vegetation,
    load_aux_priors,
    load_config,
    radar_shadow_mask,
    refined_lee_filter,
    segment_optical,
    segment_water,
    speckle_filter,
)


def test_load_config_defaults(tmp_path):
    # Проверка load_config: при отсутствующем файле используются значения по умолчанию
    cfg = load_config(tmp_path / "non_existent.yaml")
    assert "otsu_min_db" in cfg
    assert cfg["otsu_min_db"] == -22.0
    assert cfg["mmu_min_pixels"] == 25

    # Проверка load_config с пользовательским файлом
    custom_yaml = tmp_path / "custom.yaml"
    custom_yaml.write_text("otsu_min_db: -25.0\nmmu_min_pixels: 50\n", encoding="utf-8")
    cfg_custom = load_config(custom_yaml)
    assert cfg_custom["otsu_min_db"] == -25.0
    assert cfg_custom["mmu_min_pixels"] == 50
    assert cfg_custom["slope_max_deg"] == 3.0  # значение по умолчанию подставлено

    # Сброс кэша, чтобы другие тесты использовали значения проекта по умолчанию
    import src.segmentation as seg

    seg._CONFIG_CACHE = None


def test_refined_lee_filter_basic():
    # Постоянные данные: отфильтрованное изображение должно совпадать с исходным
    data = np.full((20, 20), -15.0, dtype=np.float32)
    filtered = refined_lee_filter(data, size=5)
    assert filtered.shape == (20, 20)
    assert np.allclose(filtered, -15.0, atol=0.1)

    # Граничный случай: все значения некорректны (например, nodata -999.0)
    invalid = np.full((10, 10), -999.0, dtype=np.float32)
    filtered_inv = refined_lee_filter(invalid)
    assert np.array_equal(filtered_inv, invalid)

    # Частично некорректные данные
    data[0, 0] = -999.0
    filtered_part = refined_lee_filter(data, size=5)
    assert filtered_part[0, 0] == -999.0


def test_speckle_filter_methods():
    arr = np.random.uniform(-25.0, -10.0, (15, 15)).astype(np.float32)
    arr[0, 0] = np.nan

    assert speckle_filter(None) is None

    # Lee
    res_lee = speckle_filter(arr, method="lee", size=5)
    assert res_lee.shape == arr.shape

    # Median
    res_med = speckle_filter(arr, method="median", size=5)
    assert res_med.shape == arr.shape

    # Uniform
    res_uni = speckle_filter(arr, method="uniform", size=5)
    assert res_uni.shape == arr.shape

    # Все значения некорректны
    all_nan = np.full((5, 5), np.nan, dtype=np.float32)
    res_nan = speckle_filter(all_nan, method="uniform")
    assert np.all(np.isnan(res_nan))


def test_compute_otsu_threshold():
    # Бимодальное распределение: вода около -20 dB, суша около -14 dB
    rng = np.random.default_rng(42)
    water_vals = rng.normal(-20.0, 0.5, 500)
    land_vals = rng.normal(-14.5, 0.5, 500)
    data = np.concatenate([water_vals, land_vals]).reshape((20, 50)).astype(np.float32)

    th = compute_otsu_threshold(data)
    assert -21.0 < th < -15.0

    # С маской
    mask = np.zeros(data.shape, dtype=bool)
    mask[:, :25] = True
    th_masked = compute_otsu_threshold(data, mask=mask)
    assert -22.0 <= th_masked <= -14.0

    # Малый массив (< 50 корректных пикселей) -> резервное значение -16.5
    tiny = np.full((5, 5), -18.0, dtype=np.float32)
    assert compute_otsu_threshold(tiny) == -16.5


def test_compute_otsu_threshold_configurable_gates():
    """Пороги допустимости, минимальное число выборок и резервное значение настраиваются вызывающим кодом."""
    rng = np.random.default_rng(7)
    data = (
        np.concatenate([rng.normal(-20.0, 0.4, 200), rng.normal(-14.5, 0.4, 200)]).reshape((20, 20)).astype(np.float32)
    )

    # Сужение окна допустимости убирает популяцию "суши" и при требовании к минимальному
    # числу выборок выше оставшейся популяции вынуждает использовать резервное значение
    th_narrow = compute_otsu_threshold(
        data,
        valid_min_db=-100.0,
        valid_max_db=-17.0,
        min_valid_pixels=1000,
        fallback_db=-19.0,
    )
    assert th_narrow == -19.0

    # Те же данные, широкое окно -> реальный порог Otsu внутри физического коридора
    th_wide = compute_otsu_threshold(data, valid_min_db=-30.0, valid_max_db=-12.0)
    assert -22.0 <= th_wide <= -14.0

    # min_valid_pixels ниже размера популяции сохраняет реальный порог
    th_min_px = compute_otsu_threshold(data, min_valid_pixels=10)
    assert -22.0 <= th_min_px <= -14.0

    # min_valid_pixels выше размера популяции вынуждает использовать резервное значение
    th_need_more = compute_otsu_threshold(data, min_valid_pixels=10**6, fallback_db=-13.0)
    assert th_need_more == -13.0


def test_otsu_gates_come_from_yaml():
    """Load-config предоставляет порог допустимости Otsu как данные, а не как литералы в коде."""
    import src.segmentation as seg

    cfg = seg.load_config()
    assert cfg["otsu_valid_min_db"] == -30.0
    assert cfg["otsu_valid_max_db"] == -12.0
    assert cfg["otsu_min_valid_pixels"] == 50
    assert cfg["otsu_fallback_db"] == -16.5
    assert cfg["sar_nodata_max_db"] == -100.0


def test_otsu_histogram_spans_full_validity_window():
    """Регрессия: гистограмма должна охватывать всё окно допустимости, а не только
    коридор [-22, -14], чтобы мода сухой суши могла разделить два класса."""
    rng = np.random.default_rng(11)
    # Мода воды ~ -20 dB, мода сухой суши ~ -13 dB. Обе находятся внутри заданного
    # окна допустимости, но мода сухой суши ВЫШЕ прежнего коридора -14 dB.
    data = (
        np.concatenate([rng.normal(-20.0, 0.3, 400), rng.normal(-13.0, 0.3, 400)]).reshape((20, 40)).astype(np.float32)
    )

    th = compute_otsu_threshold(data, valid_min_db=-30.0, valid_max_db=-8.0, min_db=-22.0, max_db=-8.0)
    # Порог должен разделять две моды. При прежнем усечённом диапазоне (-22, -14)
    # мода сухой суши выходила за пределы диапазона np.histogram и молча
    # отбрасывалась, порождая смещение в сторону моды воды.
    assert -19.5 < th < -13.5

    # Проверка здравости: усечённый диапазон гистограммы полностью теряет яркую моду,
    # поэтому результирующий порог смещается на сторону воды (тёмную).
    th_truncated = compute_otsu_threshold(data, valid_min_db=-30.0, valid_max_db=-8.0, min_db=-22.0, max_db=-14.0)
    assert th_truncated <= -14.0


def test_otsu_contracts_corridor_but_keeps_full_histogram():
    """Порог ограничивается диапазоном [_min_db, _max_db], тогда как гистограмма остаётся полной."""
    rng = np.random.default_rng(3)
    data = (
        np.concatenate([rng.normal(-19.0, 0.3, 300), rng.normal(-8.0, 0.3, 300)]).reshape((20, 30)).astype(np.float32)
    )
    # -8 dB лежит вне окна допустимости и полностью исключается
    th = compute_otsu_threshold(data, valid_min_db=-30.0, valid_max_db=-12.0, min_db=-22.0, max_db=-12.0)
    assert -22.0 <= th <= -12.0


def test_load_aux_priors(tmp_path):
    aux_path = tmp_path / "test_aux.tif"
    transform = from_origin(127.0, 50.0, 10.0, 10.0)
    crs = "EPSG:32652"

    # Создание фиктивного 6-полосного GeoTIFF
    # полоса 1: slope, полоса 2: hand, полоса 3: occurrence, полоса 6: builtup
    data = np.zeros((6, 20, 20), dtype=np.float32)
    data[0, :, :] = 2.0  # slope 2 deg <= 5
    data[1, :, :] = 10.0  # hand 10m <= 25
    data[2, :, :] = 90.0  # occurrence 90% >= 80% (постоянная вода)
    data[5, :, :] = 0.0  # builtup 0 < 0.5

    with rasterio.open(
        aux_path,
        "w",
        driver="GTiff",
        height=20,
        width=20,
        count=6,
        dtype=np.float32,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(data)

    res = load_aux_priors(aux_path, target_shape=(20, 20), target_transform=transform, target_crs=crs)
    assert "topo_mask" in res
    assert "permanent_mask" in res
    assert res["topo_mask"].all()
    assert res["permanent_mask"].all()


def test_segment_optical(tmp_path):
    # Несуществующий путь
    w, v = segment_optical(tmp_path / "absent.tif", (10, 10))
    assert w is None
    assert not np.any(v)

    # Файл с числом полос меньше 8
    short_tif = tmp_path / "short.tif"
    transform = from_origin(127.0, 50.0, 10.0, 10.0)
    with rasterio.open(
        short_tif,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=4,
        dtype=np.float32,
        crs="EPSG:32652",
        transform=transform,
    ) as dst:
        dst.write(np.zeros((4, 10, 10), dtype=np.float32))

    w, v = segment_optical(short_tif, (10, 10))
    assert w is None
    assert not np.any(v)

    # Корректный 8-полосный растр
    opt_tif = tmp_path / "valid_s2.tif"
    s2_data = np.full((8, 10, 10), -999.0, dtype=np.float32)
    # Полоса 6 (индекс 5): MNDWI, Полоса 7 (индекс 6): NDVI, Полоса 8 (индекс 7): AWEIsh
    # Пиксель (2, 2) - чистая вода: MNDWI=0.3 (>0.1), NDVI=0.1 (<=0.3), AWEIsh=0.2 (>0.0)
    s2_data[5, 2, 2] = 0.3
    s2_data[6, 2, 2] = 0.1
    s2_data[7, 2, 2] = 0.2

    # Пиксель (4, 4) - растительность: MNDWI=-0.2, NDVI=0.8, AWEIsh=-0.5
    s2_data[5, 4, 4] = -0.2
    s2_data[6, 4, 4] = 0.8
    s2_data[7, 4, 4] = -0.5

    with rasterio.open(
        opt_tif,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=8,
        dtype=np.float32,
        crs="EPSG:32652",
        transform=transform,
    ) as dst:
        dst.write(s2_data)

    water_mask, valid_mask = segment_optical(opt_tif, (10, 10))
    assert valid_mask[2, 2]
    assert valid_mask[4, 4]
    assert not valid_mask[0, 0]  # nodata
    assert water_mask[2, 2]
    assert not water_mask[4, 4]


def test_segment_water_comprehensive():
    shape = (30, 30)
    # Фон SAR: суша на -12 dB, водный участок на -22 dB
    vv = np.full(shape, -12.0, dtype=np.float32)
    vv[10:20, 10:20] = -22.0
    vh = vv - 6.0

    # 1. Сегментация даты pre с Otsu
    water_pre = segment_water(
        vv=vv,
        vh=vh,
        is_peak=False,
        use_topo=False,
        use_optical=False,
        use_mmu=False,
        use_permanent=False,
    )
    assert water_pre[15, 15] == 1
    assert water_pre[0, 0] == 0

    # 2. Дата peak с обнаружением падения сигнала
    vv_peak = np.full(shape, -12.0, dtype=np.float32)
    vv_peak[10:20, 10:20] = -22.0  # вода до паводка
    vv_peak[22:28, 22:28] = -18.0  # затоплено: было -12 в ref, стало -18 -> падение = 6 dB >= 3 dB
    vh_peak = vv_peak - 6.0

    water_peak = segment_water(
        vv=vv_peak,
        vh=vh_peak,
        vv_ref=vv,
        vh_ref=vh,
        is_peak=True,
        use_topo=False,
        use_optical=False,
        use_mmu=False,
        use_permanent=False,
    )
    assert water_peak[25, 25] == 1

    # 3. Двойное отражение (затопленная растительность) - отдельный слой, а НЕ открытая вода.
    #    VV на дату pre сухая/яркая (-16 dB >= -14? нет -> делаем ярче) и VH растёт.
    vv_db = np.full(shape, -8.0, dtype=np.float32)  # сухая растительность до/на момент пика
    vh_ref = np.full(shape, -22.0, dtype=np.float32)
    vh_db = np.full(shape, -18.0, dtype=np.float32)  # delta_vh = +4 dB >= 2.0 dB
    hand = np.full(shape, 1.0, dtype=np.float32)
    slope = np.full(shape, 1.0, dtype=np.float32)
    builtup = np.zeros(shape, dtype=np.float32)

    water_db = segment_water(
        vv=vv_db,
        vh=vh_db,
        vv_ref=vv_db,
        vh_ref=vh_ref,
        hand=hand,
        slope=slope,
        builtup=builtup,
        is_peak=True,
        use_topo=False,
        use_optical=False,
        use_mmu=False,
        use_permanent=False,
    )
    # Зеркало открытой воды не должно содержать пиксель тройного отражения от затопленной растительности
    assert water_db[5, 5] == 0

    fv = detect_flooded_vegetation(
        vv=vv_db,
        vh=vh_db,
        vv_ref=vv_db,
        vh_ref=vh_ref,
        hand=hand,
        slope=slope,
        builtup=builtup,
    )
    assert fv[5, 5]

    # Пиксель, который уже был водой до пика, не может дать двойное отражение
    fv_already_water = detect_flooded_vegetation(
        vv=vv_db,
        vh=vh_db,
        vv_ref=np.full(shape, -22.0, dtype=np.float32),
        vh_ref=vh_ref,
        hand=hand,
        slope=slope,
        builtup=builtup,
    )
    assert not fv_already_water[5, 5]

    # 4. Резервный путь для частичных данных или nodata SAR
    sar_nodata = np.full(shape, -999.0, dtype=np.float32)
    permanent_mask = np.zeros(shape, dtype=bool)
    permanent_mask[5:8, 5:8] = True
    topo_mask = np.ones(shape, dtype=bool)
    occ = np.full(shape, 10.0, dtype=np.float32)

    water_fallback = segment_water(
        vv=sar_nodata,
        permanent_mask=permanent_mask,
        topo_mask=topo_mask,
        hand=hand,
        occurrence=occ,
        is_peak=True,
        use_permanent=True,
        use_mmu=False,
    )
    assert np.all(water_fallback[5:8, 5:8] == 1)

    # 5. Оптическое объединение
    opt_water = np.zeros(shape, dtype=bool)
    opt_water[2, 2] = True
    opt_valid = np.zeros(shape, dtype=bool)
    opt_valid[2, 2] = True

    fused = segment_water(
        vv=vv,
        optical_water=opt_water,
        optical_valid=opt_valid,
        use_optical=True,
        use_topo=False,
        use_mmu=False,
    )
    assert fused[2, 2] == 1


def test_radar_shadow_mask_flat_and_facing_slopes_are_not_shadowed():
    """Плоский рельеф и склон, обращённый к радару, никогда не помечаются как радиолокационная тень."""
    shape = (20, 20)
    flat_slope = np.zeros(shape, dtype=np.float32)
    # Даже сильно изменчивый аспект не может создать тень на плоской поверхности
    noise_aspect = np.linspace(0.0, 359.0, shape[0] * shape[1]).reshape(shape).astype(np.float32)

    assert not np.any(radar_shadow_mask(flat_slope, noise_aspect, orbit_pass="DESCENDING"))
    assert not np.any(radar_shadow_mask(flat_slope, noise_aspect, orbit_pass="ASCENDING"))

    # Крутой склон, но обращённый к радару, остаётся освещённым: нисходящий проход смотрит
    # на запад (~270 deg), поэтому поверхность с западным уклоном (азимут склона 270 deg) освещена.
    steep_slope = np.full(shape, 70.0, dtype=np.float32)
    facing_az = np.full(shape, 270.0, dtype=np.float32)
    assert not np.any(radar_shadow_mask(steep_slope, facing_az, orbit_pass="DESCENDING"))

    # Отсутствие метаданных (orbit_pass/slope/aspect) полностью отключает защиту
    assert radar_shadow_mask(steep_slope, None, orbit_pass="DESCENDING") is None
    assert radar_shadow_mask(None, facing_az, orbit_pass="DESCENDING") is None
    assert radar_shadow_mask(steep_slope, facing_az, orbit_pass=None) is None


def test_radar_shadow_mask_follows_orbit_pass():
    """Крутой склон, обращённый в сторону от направления обзора, затенён; восходящий проход меняет это.

    Sentinel-1 с правосторонним обзором: нисходящий проход смотрит на запад (~270 deg),
    восходящий - на восток (~90 deg), поэтому крутая поверхность с восточным уклоном
    (азимут склона 90 deg) затенена на нисходящем проходе и полностью освещена на восходящем.
    """
    shape = (10, 10)
    steep = np.full(shape, 70.0, dtype=np.float32)  # круче, чем 90 - 38 = 52 deg
    east_facing = np.full(shape, 90.0, dtype=np.float32)

    desc = radar_shadow_mask(steep, east_facing, orbit_pass="DESCENDING")
    assert desc is not None and np.all(desc)

    asc = radar_shadow_mask(steep, east_facing, orbit_pass="ASCENDING")
    assert asc is not None and not np.any(asc)

    # Порог соблюдается: углы падения ниже скользящего не отклоняются
    gentle = np.full(shape, 30.0, dtype=np.float32)
    assert not np.any(radar_shadow_mask(gentle, east_facing, orbit_pass="DESCENDING"))

    # Плоские поверхности никогда не затеняются, что бы ни говорил аспект
    assert not np.any(radar_shadow_mask(np.zeros(shape, dtype=np.float32), east_facing, orbit_pass="DESCENDING"))


def test_radar_shadow_mask_non_finite_bands_are_not_shadowed():
    """Пиксели с slope или aspect NaN/inf остаются незатенёнными и не порождают предупреждение numpy.

    Реальные AOI (например, flood_2021_08_zeya__svobodny) содержат неконечные значения в полосе
    slope, из-за чего тригонометрия угла падения ранее вызывала RuntimeWarning, хотя пиксель уже
    был исключён проверкой конечности.
    """
    shape = (8, 8)
    steep = np.full(shape, 70.0, dtype=np.float32)  # затенял бы поверхность с восточным уклоном
    east_facing = np.full(shape, 90.0, dtype=np.float32)
    steep[0, 0] = np.nan
    steep[0, 1] = np.inf
    east_facing[1, 0] = np.nan
    east_facing[1, 1] = np.inf

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        mask = radar_shadow_mask(steep, east_facing, orbit_pass="DESCENDING")

    assert mask is not None
    # Неконечные пиксели никогда не помечаются как тень ...
    assert not mask[0, 0] and not mask[0, 1]
    assert not mask[1, 0] and not mask[1, 1]
    # ... тогда как остальные конечные поверхности, обращённые в сторону, всё равно затеняются.
    assert mask[2:, :].all()


def test_segment_water_radar_shadow_guard_is_orbit_aware():
    """Защита от радиолокационной тени: без метаданных без эффекта, подавляет только обратный склон."""
    shape = (40, 40)
    vv = np.full(shape, -12.0, dtype=np.float32)
    vv[10:30, 10:30] = -26.0  # тёмное обратное рассеяние, Otsu посчитал бы это открытой водой
    vh = vv - 6.0

    slope = np.zeros(shape, dtype=np.float32)
    aspect = np.full(shape, 90.0, dtype=np.float32)  # восточный уклон: от обзора нисходящего прохода (~270 deg)

    # 1. Без orbit_pass -> защита без эффекта, тёмный участок сегментируется как вода
    baseline = segment_water(
        vv=vv,
        vh=vh,
        slope=slope,
        aspect=aspect,
        use_topo=False,
        use_optical=False,
        use_mmu=False,
        use_permanent=False,
    )
    assert baseline[20, 20] == 1

    # 2. Плоский рельеф + orbit_pass -> по-прежнему без подавления (slope ниже предела тени)
    flat_orbit = segment_water(
        vv=vv,
        vh=vh,
        slope=slope,
        aspect=aspect,
        orbit_pass="DESCENDING",
        use_topo=False,
        use_optical=False,
        use_mmu=False,
        use_permanent=False,
    )
    assert np.array_equal(flat_orbit, baseline)

    # 3. Крутой склон, обращённый в тень + orbit_pass -> подавление
    steep_slope = np.zeros(shape, dtype=np.float32)
    steep_slope[10:30, 10:30] = 70.0
    steep_aspect = np.zeros(shape, dtype=np.float32)
    steep_aspect[10:30, 10:30] = 90.0

    shadowed = segment_water(
        vv=vv,
        vh=vh,
        slope=steep_slope,
        aspect=steep_aspect,
        orbit_pass="DESCENDING",
        use_topo=False,
        use_optical=False,
        use_mmu=False,
        use_permanent=False,
    )
    assert shadowed[20, 20] == 0
    assert shadowed[0, 0] == baseline[0, 0]  # пиксели вне участка не затронуты

    # 4. Та же геометрия при восходящем проходе -> обратный склон освещён
    ascended = segment_water(
        vv=vv,
        vh=vh,
        slope=steep_slope,
        aspect=steep_aspect,
        orbit_pass="ASCENDING",
        use_topo=False,
        use_optical=False,
        use_mmu=False,
        use_permanent=False,
    )
    assert np.array_equal(ascended, baseline)


def test_segment_water_radar_shadow_guard_keeps_near_range_slope():
    """Ближний к радару склон, обращённый к нему, никогда не подавляется, даже будучи крутым."""
    shape = (40, 40)
    vv = np.full(shape, -12.0, dtype=np.float32)
    vv[10:30, 10:30] = -26.0
    vh = vv - 6.0

    slope = np.zeros(shape, dtype=np.float32)
    slope[10:30, 10:30] = 70.0
    aspect = np.zeros(shape, dtype=np.float32)
    aspect[10:30, 10:30] = 270.0  # обращён к направлению обзора нисходящего прохода (запад)

    water = segment_water(
        vv=vv,
        vh=vh,
        slope=slope,
        aspect=aspect,
        orbit_pass="DESCENDING",
        use_topo=False,
        use_optical=False,
        use_mmu=False,
        use_permanent=False,
    )
    assert water[20, 20] == 1


def test_load_aux_priors_provides_aspect(tmp_path):
    """AUX-приоры предоставляют слой аспекта рельефа для защиты от тени с учётом орбиты."""
    aux_path = tmp_path / "aux_aspect.tif"
    transform = from_origin(127.0, 50.0, 10.0, 10.0)
    data = np.zeros((6, 20, 20), dtype=np.float32)
    # HAND растёт к югу (индекс строки увеличивается к югу), поэтому наискорейший спуск
    # направлен на север -> азимут склона = 0 deg.
    data[1, :, :] = np.arange(20, dtype=np.float32)[:, None]
    data[0, :, :] = 2.0

    with rasterio.open(
        aux_path,
        "w",
        driver="GTiff",
        height=20,
        width=20,
        count=6,
        dtype=np.float32,
        crs="EPSG:32652",
        transform=transform,
    ) as dst:
        dst.write(data)

    res = load_aux_priors(aux_path, target_shape=(20, 20), target_transform=transform, target_crs="EPSG:32652")
    assert "aspect" in res
    aspect = res["aspect"]
    assert aspect.shape == (20, 20)
    # HAND растёт к югу, поэтому наискорейший спуск направлен на север (0 deg)
    assert np.allclose(aspect, 0.0, atol=1.0)
    assert np.all(np.isfinite(aspect))


def test_segment_optical_no_valid(tmp_path):
    """Все некорректные пиксели в оптических полосах возвращают None и нулевую маску valid (строка 289)."""
    shape = (10, 10)
    opt_tif = tmp_path / "all_invalid_s2.tif"
    s2_data = np.full((8, 10, 10), -999.0, dtype=np.float32)
    transform = from_origin(127.0, 50.0, 10.0, 10.0)

    with rasterio.open(
        opt_tif,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=8,
        dtype=np.float32,
        crs="EPSG:32652",
        transform=transform,
    ) as dst:
        dst.write(s2_data)

    opt_water, valid_mask = segment_optical(opt_tif, shape)
    assert opt_water is None
    assert valid_mask.shape == shape
    assert not np.any(valid_mask)


def test_apply_mmu_config_fallback_and_zero_features(monkeypatch):
    """apply_mmu загружает конфигурацию при min_size=None (строки 303-304) и обрабатывает 0 объектов (строка 312)."""
    # 0. Ранний возврат при пустой маске (строка 307)
    empty = np.zeros((5, 5), dtype=bool)
    assert np.array_equal(apply_mmu(empty), empty)

    mask = np.zeros((10, 10), dtype=bool)
    mask[2:5, 2:5] = True

    # 1. min_size равен None -> вызов load_config()
    cleaned = apply_mmu(mask, min_size=None)
    assert cleaned.shape == mask.shape

    # 2. Резервный путь при num_features == 0
    monkeypatch.setattr("src.filters.label", lambda m, structure=None: (np.zeros_like(m), 0))
    res = apply_mmu(mask, min_size=10)
    assert np.array_equal(res, mask)


def test_segment_water_sar_nodata_non_peak():
    """Когда SAR равен nodata и есть permanent_mask, но is_peak=False, возвращается копия permanent_mask (строка 407)."""
    shape = (20, 20)
    vv_nodata = np.full(shape, -999.0, dtype=np.float32)
    perm_mask = np.zeros(shape, dtype=bool)
    perm_mask[5:11, 5:11] = True  # 36 пикселей > порога mmu 25

    water = segment_water(
        vv=vv_nodata,
        permanent_mask=perm_mask,
        is_peak=False,
        use_permanent=True,
        use_mmu=True,
    )
    assert np.array_equal(water, perm_mask.astype(np.uint8))


def test_segment_water_partial_sar_fallback_is_config_driven():
    """Расширение резервного пути при разреженном SAR должно следовать порогам конфигурации, а не литералам в коде.

    Ветвь в стиле Пояркова (доля sar_valid ниже порога) расширяет маску воды
    по ``topo_mask & (hand <= fallback_hand_max_m) & (occurrence >= fallback_occurrence_min_pct)``.
    """
    import src.segmentation as seg

    shape = (20, 20)
    # Лишь 1% пикселей содержат корректный SAR -> ниже порога покрытия 10%
    vv = np.full(shape, -999.0, dtype=np.float32)
    vv[0, 0] = -15.0

    perm_mask = np.zeros(shape, dtype=bool)
    perm_mask[2:5, 2:5] = True

    topo_mask = np.ones(shape, dtype=bool)
    hand = np.full(shape, 0.5, dtype=np.float32)  # <= 1.0 m -> внутри оболочки резервного пути
    occurrence = np.full(shape, 10.0, dtype=np.float32)  # >= 5% -> внутри оболочки резервного пути

    original = seg.load_config()
    try:
        # Базовая конфигурация: HAND 0.5 <= 1.0 и occurrence 10 >= 5 -> расширение активно
        seg._CONFIG_CACHE = None
        water = segment_water(
            vv=vv,
            permanent_mask=perm_mask,
            topo_mask=topo_mask,
            hand=hand,
            occurrence=occurrence,
            is_peak=True,
            use_permanent=True,
            use_mmu=False,
        )
        assert water.sum() > perm_mask.sum(), "expansion should add floodplain pixels"
        assert water[10, 10] == 1

        # Ужесточение настраиваемых порогов делает оболочку расширения пустой
        tightened = dict(original)
        tightened["fallback_hand_max_m"] = 0.1
        seg._CONFIG_CACHE = tightened
        water_tight = segment_water(
            vv=vv,
            permanent_mask=perm_mask,
            topo_mask=topo_mask,
            hand=hand,
            occurrence=occurrence,
            is_peak=True,
            use_permanent=True,
            use_mmu=False,
        )
        assert np.array_equal(water_tight, perm_mask.astype(np.uint8))

        # Поднятие порога покрытия выше фактической доли корректных данных всё равно сохраняет резервный путь
        loosened = dict(original)
        loosened["sar_valid_frac_min"] = 0.0
        seg._CONFIG_CACHE = loosened
        water_no_fallback = segment_water(
            vv=vv,
            permanent_mask=perm_mask,
            topo_mask=topo_mask,
            hand=hand,
            occurrence=occurrence,
            is_peak=True,
            use_permanent=True,
            use_mmu=False,
        )
        assert not np.array_equal(water_no_fallback, water), "disabling the fallback changes the mask"
    finally:
        seg._CONFIG_CACHE = None


def test_apply_planar_hand_filter():
    from src.segmentation import apply_planar_hand_filter

    # Seed is a 3x3 block in the center (rows 4..6, cols 4..6)
    seed = np.zeros((10, 10), dtype=bool)
    seed[4:7, 4:7] = True

    # HAND: seed has 0.0, boundary has 1.0, distant points have varying HAND
    hand = np.full((10, 10), 5.0, dtype=np.float32)
    hand[4:7, 4:7] = 0.0
    hand[3:8, 3:8] = 1.0  # boundary has HAND = 1.0
    hand[4:7, 4:7] = 0.0

    # Flood candidate: entire 10x10 array
    flood = np.ones((10, 10), dtype=np.uint8)

    # With p90 on boundary = 1.0 and tolerance = 1.5 -> limit = 2.5m
    # Pixels with hand = 1.0 stay (<= 2.5m), pixels with hand = 5.0 are filtered out (> 2.5m)
    filtered = apply_planar_hand_filter(flood, seed, hand, percentile=90.0, tolerance_m=1.5)

    assert np.all(filtered[3:8, 3:8] == 1)
    assert np.all(filtered[0, :] == 0)
    assert np.all(filtered[:, 0] == 0)
