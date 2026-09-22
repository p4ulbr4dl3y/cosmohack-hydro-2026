"""Модуль мультимодальной сегментации воды для HydroWatch Amur.

Объединяет SAR Sentinel-1 VV/VH, оптику Sentinel-2 MNDWI, NDVI, AWEIsh
и топографические и гидрологические априорные данные: HAND, уклон, застройка, occurrence GSW
с фильтрацией по минимальной единице картирования MMU.

Ограничение данных AUX:
    Исходные многополосные растры AUX содержат только band 1 (slope Copernicus DEM),
    band 2 (MERIT Hydro HAND), band 3 (GSW occurrence) и band 6 (WSF builtup).
    Канал абсолютной высоты Copernicus DEM GLO-30 в AUX отсутствует. Поэтому
    экспозиция рельефа вычисляется по вектору наискорейшего спуска HAND
    как прокси для азимута дренажной сети и применяется в radar_shadow_mask().
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.warp import Resampling

from src.config import HydroConfig
from src.filters import apply_hydrological_connectivity as _filters_apply_hydrological_connectivity
from src.filters import apply_mmu as _filters_apply_mmu
from src.filters import apply_morphological_closing as _filters_apply_morphological_closing
from src.filters import apply_planar_hand_filter as _filters_apply_planar_hand_filter
from src.filters import refined_lee_filter as _filters_refined_lee_filter
from src.filters import speckle_filter as _filters_speckle_filter
from src.geo_utils import clip_by_aoi, read_raster_with_meta, resample_to_target
from src.indices import segment_optical as _indices_segment_optical

logger = logging.getLogger(__name__)

__all__ = [
    "HydroConfig",
    "load_config",
    "refined_lee_filter",
    "speckle_filter",
    "compute_otsu_threshold",
    "load_aux_priors",
    "radar_shadow_mask",
    "segment_optical",
    "apply_mmu",
    "apply_morphological_closing",
    "apply_hydrological_connectivity",
    "apply_planar_hand_filter",
    "detect_flooded_vegetation",
    "segment_water",
    "read_raster_with_meta",
    "resample_to_target",
    "clip_by_aoi",
]


# Кэш конфигурации по умолчанию
_CONFIG_CACHE: dict[str, Any] | None = None


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Загружает словарь конфигурации из config.yaml или HydroConfig."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None and config_path is None:
        return _CONFIG_CACHE

    cfg_obj = HydroConfig.from_yaml(config_path)
    cfg = cfg_obj.to_dict()

    defaults = {
        "otsu_min_db": -22.0,
        "otsu_max_db": -12.0,
        "otsu_bins": 64,
        "otsu_valid_min_db": -30.0,
        "otsu_valid_max_db": -12.0,
        "otsu_min_valid_pixels": 50,
        "otsu_fallback_db": -16.5,
        "sar_nodata_max_db": -100.0,
        "builtup_max_fraction": 0.5,
        "sar_flood_drop_db": 3.0,
        "vh_threshold_db": -16.5,
        "double_bounce_delta_vh_db": 2.0,
        "double_bounce_hand_max_m": 3.0,
        "slope_max_deg": 5.0,
        "hand_max_m": 25.0,
        "sar_nominal_incidence_deg": 38.0,
        "radar_shadow_min_incidence_deg": 90.0,
        "gsw_occurrence_min_pct": 80.0,
        "optical_mndwi_min": 0.1,
        "optical_aweish_min": 0.0,
        "optical_ndvi_max": 0.3,
        "mmu_min_pixels": 25,
    }
    for k, v in defaults.items():
        cfg.setdefault(k, v)

    _CONFIG_CACHE = cfg
    return cfg


def refined_lee_filter(
    data: np.ndarray,
    size: int = 7,
    n_looks: float = 4.4,
) -> np.ndarray:
    """Применяет спекл-фильтр Lee MMSE (квадратное окно 7x7, n_looks=4.4).

    Это классический фильтр Lee с минимумом среднеквадратичной ошибки и квадратным
    окном. Направленный вариант "Refined Lee" с выравниванием по краям НЕ реализован.
    """
    return _filters_refined_lee_filter(data=data, size=size, n_looks=n_looks)


def speckle_filter(
    data: np.ndarray | None,
    method: str = "lee",
    size: int = 7,
) -> np.ndarray | None:
    """Применяет подавление спекла к данным обратного рассеяния радара."""
    return _filters_speckle_filter(data=data, method=method, size=size)


def compute_otsu_threshold(
    vv_data: np.ndarray,
    mask: np.ndarray | None = None,
    min_db: float | None = None,
    max_db: float | None = None,
    bins: int | None = None,
    valid_min_db: float | None = None,
    valid_max_db: float | None = None,
    min_valid_pixels: int | None = None,
    fallback_db: float | None = None,
) -> float:
    """Вычисляет порог Otsu по обратному рассеянию радара VV с ограничением [min_db, max_db].

    Гистограмма строится по *полному* окну валидности
    [valid_min_db, valid_max_db], так что представлены и мода воды (~ -20 дБ), и мода
    суши (~ -8 дБ); Otsu по урезанному одномодальному хвосту
    бессмыслен. Полученный порог затем ограничивается физически
    допустимым коридором [min_db, max_db] (ТЗ: [-22, -12] дБ).

    Пиксели вне [valid_min_db, valid_max_db] считаются nodata и исключаются
    из гистограммы; если остаётся меньше min_valid_pixels, возвращается fallback_db.
    """
    cfg = load_config()
    min_val = min_db if min_db is not None else float(cfg["otsu_min_db"])
    max_val = max_db if max_db is not None else float(cfg["otsu_max_db"])
    num_bins = bins if bins is not None else int(cfg["otsu_bins"])
    valid_min = valid_min_db if valid_min_db is not None else float(cfg["otsu_valid_min_db"])
    valid_max = valid_max_db if valid_max_db is not None else float(cfg["otsu_valid_max_db"])
    min_pixels = min_valid_pixels if min_valid_pixels is not None else int(cfg["otsu_min_valid_pixels"])
    fallback = fallback_db if fallback_db is not None else float(cfg["otsu_fallback_db"])

    valid = np.isfinite(vv_data) & (vv_data > valid_min) & (vv_data < valid_max)
    if mask is not None:
        valid = valid & mask

    valid_vals = vv_data[valid]
    if len(valid_vals) < min_pixels:
        return fallback

    # Гистограмма охватывает полное окно валидности (обе моды), порог ограничивается после этого.
    counts, bin_edges = np.histogram(valid_vals, bins=num_bins, range=(valid_min, valid_max))
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0

    weight1 = np.cumsum(counts)
    weight2 = np.cumsum(counts[::-1])[::-1]

    mean1 = np.cumsum(counts * bin_centers) / np.maximum(weight1, 1)
    mean2 = (np.cumsum((counts * bin_centers)[::-1]) / np.maximum(weight2[::-1], 1))[::-1]

    variance = weight1[:-1] * weight2[1:] * (mean1[:-1] - mean2[1:]) ** 2
    # Межклассовая дисперсия постоянна на пустом промежутке между двумя модами.
    # Берём центр максимального плато, а не первый бин, который
    # иначе смещает порог в сторону моды воды (тёмной).
    best = float(variance.max())
    plateau_idx = np.flatnonzero(variance >= best * (1.0 - 1e-9))
    best_idx = int(plateau_idx[len(plateau_idx) // 2])
    threshold = float(bin_centers[best_idx])

    if not np.isfinite(threshold):
        return fallback

    return float(np.clip(threshold, min_val, max_val))


def load_aux_priors(
    aux_path: str | Path,
    target_shape: tuple[int, int],
    target_transform: rasterio.Affine,
    target_crs: Any,
) -> dict[str, np.ndarray]:
    """Загружает и перепроецирует слои рельефа AUX и GSW в целевую сетку.

    Ограничение данных AUX:
    Исходные многополосные растры AUX датасета содержат только 4 канала:
      - полоса 1: уклон Copernicus DEM GLO-30 slope, в градусах;
      - полоса 2: HAND, высота над ближайшим дренажем MERIT Hydro, в метрах;
      - полоса 3: частота воды GSW occurrence, %;
      - полоса 6: слой застройки WSF builtup fraction.
    Канал абсолютной высоты Copernicus DEM GLO-30 elevation в предоставленных AUX-растрах
    отсутствует. Поэтому истинная экспозиция DEM не может быть вычислена напрямую.
    Вместо этого слой экспозиции рельефа ``aspect`` вычисляется из поля HAND: поскольку HAND
    монотонно возрастает вверх по склону от дренажной сети, вектор наискорейшего спуска
    (-grad HAND) служит физическим прокси для азимута стока к русловой сети.

    Этот прокси используется исключительно защитой от радиолокационной тени с учётом орбиты
    (:func:`radar_shadow_mask`) и действует строго на гранях, достаточно крутых для геометрического
    затенения (> 52 град при номинальном угле падения ~38 град). На плоском рельефе (planar flats,
    dy=0 и dx=0) градиент равен нулю, аспект принимается равным нейтральным 0.0 град, а критерий
    крутизны (slope > 52 град) гарантирует отсутствие ложного затенения.
    """
    cfg = load_config()
    slope_max = float(cfg["slope_max_deg"])
    hand_max = float(cfg["hand_max_m"])
    gsw_min = float(cfg["gsw_occurrence_min_pct"])

    slope = resample_to_target(
        source_path=aux_path,
        band=1,
        target_shape=target_shape,
        target_transform=target_transform,
        target_crs=target_crs,
        resampling=Resampling.bilinear,
    )
    hand = resample_to_target(
        source_path=aux_path,
        band=2,
        target_shape=target_shape,
        target_transform=target_transform,
        target_crs=target_crs,
        resampling=Resampling.bilinear,
    )
    occurrence = resample_to_target(
        source_path=aux_path,
        band=3,
        target_shape=target_shape,
        target_transform=target_transform,
        target_crs=target_crs,
        resampling=Resampling.nearest,
    )
    builtup = resample_to_target(
        source_path=aux_path,
        band=6,
        target_shape=target_shape,
        target_transform=target_transform,
        target_crs=target_crs,
        resampling=Resampling.nearest,
    )

    # Очистка невалидных или повреждённых значений nodata (например, -inf в Свободном 2021-08)
    valid_slope = np.isfinite(slope) & (slope >= 0.0)
    valid_hand = np.isfinite(hand) & (hand >= 0.0)
    topo_mask = valid_slope & valid_hand & (slope <= slope_max) & (hand <= hand_max)
    permanent_mask = (occurrence >= gsw_min) & np.isfinite(occurrence)

    # Экспозиция рельефа (азимут вниз по склону, градусы по часовой стрелке от севера):
    # В отсутствие полосы высоты DEM в AUX аспект аппроксимируется вектором наискорейшего спуска HAND.
    # Санитизируем HAND перед градиентом, чтобы повреждённые пиксели nodata (-inf/nan) не загрязняли соседей.
    hand_clean = np.where(valid_hand, hand, 0.0)
    dy = np.gradient(hand_clean, axis=0)  # d(HAND)/d(row); строки растут в южном направлении
    dx = np.gradient(hand_clean, axis=1)  # d(HAND)/d(col); столбцы растут в восточном направлении
    grad_mag = np.hypot(dx, dy)
    # На плоских участках (planar flats, dy=0 и dx=0) градиент равен нулю, спуск не определен.
    # Явно задаем нейтральный азимут 0.0 во избежание артефактов знаковых нулей (-0.0 в IEEE 754 дает 180 град)
    is_flat = (grad_mag < 1e-7) | ~valid_hand
    # Вектор вниз по склону в системе (north, east) = (dy, -dx), азимут = atan2(east, north)
    raw_aspect = np.degrees(np.arctan2(-dx, dy)) % 360.0
    aspect = np.where(is_flat, 0.0, raw_aspect)
    aspect = np.where(valid_hand & np.isfinite(aspect), aspect, 0.0).astype(np.float32)

    return {
        "slope": slope,
        "hand": hand,
        "aspect": aspect,
        "occurrence": occurrence,
        "builtup": builtup,
        "topo_mask": topo_mask,
        "permanent_mask": permanent_mask,
    }


def segment_optical(
    s2_path: str | Path | None,
    target_shape: tuple[int, int],
) -> tuple[np.ndarray | None, np.ndarray]:
    """Сегментирует воду по индексам Sentinel-2 MSI там, где они доступны."""
    cfg = load_config()
    mndwi_min = float(cfg["optical_mndwi_min"])
    aweish_min = float(cfg["optical_aweish_min"])
    ndvi_max = float(cfg["optical_ndvi_max"])
    return _indices_segment_optical(
        s2_path=s2_path,
        target_shape=target_shape,
        mndwi_min=mndwi_min,
        aweish_min=aweish_min,
        ndvi_max=ndvi_max,
    )


def apply_mmu(
    mask: np.ndarray,
    min_size: int | None = None,
) -> np.ndarray:
    """Удаляет изолированные кластеры шума меньше min_size пикселей (обёртка с учётом конфигурации)."""
    if min_size is None:
        cfg = load_config()
        min_size = int(cfg["mmu_min_pixels"])
    return _filters_apply_mmu(mask, min_size=min_size)


def apply_hydrological_connectivity(
    flood_mask: np.ndarray,
    seed_mask: np.ndarray,
) -> np.ndarray:
    """Фильтрует кластеры затопления по гидрологической связности с постоянной опорной сетью."""
    return _filters_apply_hydrological_connectivity(flood_mask=flood_mask, seed_mask=seed_mask)


def apply_morphological_closing(
    mask: np.ndarray,
    kernel_size: int = 5,
) -> np.ndarray:
    """Закрывает мелкие спекл-провалы и разрывы от волн внутри водных объектов."""
    return _filters_apply_morphological_closing(mask=mask, kernel_size=kernel_size)


def apply_planar_hand_filter(
    flood_mask: np.ndarray,
    seed_mask: np.ndarray,
    hand: np.ndarray | None,
    percentile: float = 90.0,
    tolerance_m: float = 1.5,
) -> np.ndarray:
    """Filter flood water elevation exceeding river boundary HAND + tolerance."""
    return _filters_apply_planar_hand_filter(
        flood_mask=flood_mask,
        seed_mask=seed_mask,
        hand=hand,
        percentile=percentile,
        tolerance_m=tolerance_m,
    )


def detect_flooded_vegetation(
    vv: np.ndarray,
    vh: np.ndarray | None,
    vv_ref: np.ndarray | None,
    vh_ref: np.ndarray | None,
    hand: np.ndarray | None = None,
    slope: np.ndarray | None = None,
    builtup: np.ndarray | None = None,
    filter_method: str = "lee",
    filter_size: int = 7,
) -> np.ndarray:
    """Обнаруживает затопленную растительность под пологом по механизму двойного отражения.

    Двойное отражение = открытая вода + вертикальный стебель. Физически пиксель на дату *pre* это
    сухая растительность (яркий VV, например ~ -8 дБ), и на пике он затопляется, поэтому VH
    растёт. Пиксель, который уже был открытой водой на дату pre, не может дать
    двойное отражение, поэтому VV на дату pre должен быть >= ``double_bounce_vv_pre_min_db``.

    Согласно разделу 5 ТЗ затопленная растительность это отдельный слой продукта и
    НЕ входит в зеркало открытой воды, поэтому маска возвращается отдельно и
    никогда не объединяется с :func:`segment_water`.
    """
    if vh is None or vh_ref is None or vv_ref is None:
        return np.zeros(vv.shape, dtype=bool)

    cfg = load_config()
    db_delta = float(cfg["double_bounce_delta_vh_db"])
    db_hand_max = float(cfg["double_bounce_hand_max_m"])
    db_slope_max = float(cfg.get("double_bounce_slope_max_deg", 3.0))
    db_vv_pre_min = float(cfg.get("double_bounce_vv_pre_min_db", -14.0))
    nodata_max_db = float(cfg.get("sar_nodata_max_db", -100.0))
    builtup_max = float(cfg.get("builtup_max_fraction", 0.5))

    sar_valid = np.isfinite(vv) & (vv > nodata_max_db)
    vv_ref_filt = speckle_filter(vv_ref, method=filter_method, size=filter_size)
    vh_filt = speckle_filter(vh, method=filter_method, size=filter_size)
    vh_ref_filt = speckle_filter(vh_ref, method=filter_method, size=filter_size)
    delta_vh = vh_filt - vh_ref_filt

    builtup_clean = (builtup < builtup_max) if builtup is not None else True
    cond = (delta_vh >= db_delta) & (vv_ref_filt >= db_vv_pre_min) & builtup_clean & sar_valid
    if hand is not None:
        cond = cond & (hand <= db_hand_max)
    if slope is not None:
        cond = cond & (slope <= db_slope_max)

    return cond


def radar_shadow_mask(
    slope: np.ndarray | None,
    aspect: np.ndarray | None,
    orbit_pass: str | None,
    nominal_incidence_deg: float | None = None,
    shadow_min_incidence_deg: float | None = None,
) -> np.ndarray | None:
    """Отмечает грани рельефа, геометрически находящиеся в радиолокационной тени Sentinel-1.

    Геометрия
    --------
    Sentinel-1 это *правосторонний* радиолокатор бокового обзора, поэтому освещаемая им сторона
    зависит от направления полёта:

      - нисходящий виток (спутник летит с севера на юг) смотрит на **запад**, азимут сенсора ~270 град;
      - восходящий виток (спутник летит с юга на север) смотрит на **восток**, азимут сенсора ~90 град.

    Грань с уклоном ``s``, наискорейший спуск которой направлен по азимуту ``A``, освещается
    под *локальным* углом падения, который отличается от угла падения на плоском рельефе (номинального)
    ``theta_0`` на проекцию уклона по дальности на плоскость сенсор-цель. Где
    ``L`` это азимут от цели к сенсору (единичный вектор вверх по склону равен ``-(downslope)``),

        cos(theta_local) = cos(s) * cos(theta_0) + sin(s) * sin(theta_0) * cos(A - L)

    Когда грань спускается *к* сенсору (``A -> L``), локальный угол падения уменьшается
    (сокращение, ближний по дальности склон всё ещё отображается), и ``theta_local`` стремится к
    ``|s - theta_0|``. Когда она спускается *от* сенсора (``A -> L + 180 град``),
    локальный угол падения растёт, ``theta_local -> s + theta_0``, и как только ``theta_local >= 90 град``,
    нормаль поверхности уходит от линии визирования: луч скользит по гребню и
    никогда не достигает этой грани. Обратное рассеяние падает до системного шума (sigma0 < -24 дБ),
    и наивный классификатор Otsu считает это открытой водой - систематическое ложное срабатывание.

    Именно поэтому восходящий виток не равен нисходящему: затенённая экспозиция меняется на 180 град
    между витками, так что один и тот же склон в тени на одной орбите и полностью отображается на
    другой. Поэтому направление орбиты это физически значимый вход, а не метка.

    Допущения (намеренно консервативные):
    - в датасете нет попиксельного канала углов падения, поэтому номинальный угол падения
      середины полосы (``SAR_NOMINAL_INCIDENCE_DEG``, ~38 град для S1 IW) используется как ``theta_0``;
    - ограничение данных AUX: растры AUX содержат только band 1 (slope), band 2 (hand),
      band 3 (occurrence) и band 6 (builtup); канал абсолютной высоты Copernicus DEM GLO-30
      в AUX не включён. Поэтому входной ``aspect`` вычисляется по вектору наискорейшего спуска
      HAND (MERIT Hydro) как прокси для азимута дренажной сети (см. :func:`load_aux_priors`);
    - критерий уклона: для возникновения геометрической тени необходимо, чтобы
      локальный угол падения достиг скользящего предела (``theta_local >= shadow_min`` ~ 90 град).
      Поскольку максимальный локальный угол падения равен ``slope + theta_0`` (при экспозиции строго
      в противоположную сторону от радара), тень физически невозможна при
      ``slope < shadow_min - theta_0`` (при theta_0 ~38 град это уклон < 52 град).
      Поэтому плоский рельеф (slope ~ 0 град) и пологие поймы гарантированно отсекаются
      критерием уклона и никогда не помечаются как тень, независимо от значений аспекта
      или неопределенностей на плоских участках (planar flats, dy=0, dx=0);
    - применяется только строгий критерий самозатенения (``theta_local`` на уровне
      ``RADAR_SHADOW_MIN_INCIDENCE_DEG`` и выше, то есть уклон круче ``90 - theta_0`` ~ 52 град
      при направлении строго в сторону). Отбрасываемая и собственная тень от соседних хребтов требует
      профиля DEM вдоль направления дальности и намеренно здесь не моделируется. Сокращённые
      склоны ближней зоны дальности никогда не подавляются.

    Возвращает:
        Булев массив затенённых пикселей или ``None``, когда защиту нельзя оценить
        (отсутствуют слои уклона и экспозиции или нераспознан ``orbit_pass``). ``None`` означает
        "без подавления", поэтому вызывающий код может считать это пустой операцией.
    """
    if slope is None or aspect is None or orbit_pass is None:
        return None

    pass_norm = str(orbit_pass).strip().upper()
    if pass_norm.startswith("D"):
        look_azimuth_deg = 270.0  # нисходящий, правосторонний - освещает с запада
    elif pass_norm.startswith("A"):
        look_azimuth_deg = 90.0  # восходящий, правосторонний - освещает с востока
    else:
        return None

    cfg = load_config()
    theta0 = (
        nominal_incidence_deg
        if nominal_incidence_deg is not None
        else float(cfg.get("sar_nominal_incidence_deg", 38.0))
    )
    shadow_min = (
        shadow_min_incidence_deg
        if shadow_min_incidence_deg is not None
        else float(cfg.get("radar_shadow_min_incidence_deg", 90.0))
    )

    slope_arr = np.asarray(slope, dtype=np.float64)
    aspect_arr = np.asarray(aspect, dtype=np.float64)
    # Некоторые AOI содержат NaN/inf или отрицательные nodata в каналах уклона и экспозиции;
    # исключаем их из расчёта (неконечные и некорректные пиксели остаются незатенёнными).
    finite = np.isfinite(slope_arr) & (slope_arr >= 0.0) & np.isfinite(aspect_arr)

    # Критерий уклона: уклон должен быть не менее (shadow_min - theta0) ~ 52 град,
    # иначе даже при наихудшей ориентации theta_local не достигнет shadow_min.
    min_shadow_slope = max(0.0, shadow_min - theta0)
    steep_enough = slope_arr >= min_shadow_slope

    # Выполняем тригонометрию только на валидных и достаточно крутых пикселях
    valid_candidates = finite & steep_enough
    theta0_rad = np.radians(theta0)
    slope_rad = np.radians(np.where(valid_candidates, slope_arr, 0.0))
    psi = np.radians(look_azimuth_deg - np.where(valid_candidates, aspect_arr, look_azimuth_deg))
    # cos(theta_local) = cos(theta0)cos(s) + sin(theta0)sin(s)cos(L - A):
    # азимут вниз по склону A равен азимуту визирования L - сокращённый склон ближней зоны (theta_local
    # уменьшается); A равен L + 180 - обратный склон (theta_local растёт к s + theta0).
    cos_incidence = np.cos(slope_rad) * np.cos(theta0_rad) + np.sin(slope_rad) * np.sin(theta0_rad) * np.cos(psi)
    local_incidence_deg = np.degrees(np.arccos(np.clip(cos_incidence, -1.0, 1.0)))

    return valid_candidates & (local_incidence_deg >= shadow_min)


def segment_water(
    vv: np.ndarray,
    vh: np.ndarray | None = None,
    vv_ref: np.ndarray | None = None,
    vh_ref: np.ndarray | None = None,
    optical_water: np.ndarray | None = None,
    optical_valid: np.ndarray | None = None,
    topo_mask: np.ndarray | None = None,
    permanent_mask: np.ndarray | None = None,
    hand: np.ndarray | None = None,
    slope: np.ndarray | None = None,
    builtup: np.ndarray | None = None,
    occurrence: np.ndarray | None = None,
    aspect: np.ndarray | None = None,
    orbit_pass: str | None = None,
    is_peak: bool = False,
    use_topo: bool = True,
    use_optical: bool = True,
    use_mmu: bool = True,
    use_permanent: bool = True,
    filter_method: str = "lee",
    filter_size: int = 7,
    mmu_min_size: int | None = None,
) -> np.ndarray:
    """Сквозная сегментация воды для одной даты съёмки (pre или peak).

    Необязательные аргументы ``aspect`` (азимут вниз по склону, градусы от севера) и ``orbit_pass``
    включают защиту от радиолокационной тени с учётом орбиты: грани круче локального
    предела угла падения *и* направленные в сторону от направления визирования сенсора подавляются
    до применения топографических априорных данных, поскольку они не несут радиолокационного сигнала и иначе
    были бы неверно прочитаны как открытая вода. Защита неактивна (пустая операция), когда любой
    из аргументов равен ``None``, поэтому существующий вызывающий код сохраняет прежнее поведение. См.
    :func:`radar_shadow_mask` для геометрии и её описанных допущений.
    """
    cfg = load_config()
    drop_thresh = float(cfg["sar_flood_drop_db"])
    vh_thresh = float(cfg["vh_threshold_db"])
    sar_drop_vv_max = float(cfg.get("sar_drop_vv_max_db", -14.0))
    sar_drop_vh_min = float(cfg.get("sar_drop_vh_min_db", 1.5))
    sar_drop_vh_max = float(cfg.get("sar_drop_vh_max_db", -17.0))
    mmu_pixels = mmu_min_size if mmu_min_size is not None else int(cfg["mmu_min_pixels"])
    nodata_max_db = float(cfg.get("sar_nodata_max_db", -100.0))
    builtup_max = float(cfg.get("builtup_max_fraction", 0.5))
    sar_valid_frac_min = float(cfg.get("sar_valid_frac_min", 0.1))
    fb_hand_max = float(cfg.get("fallback_hand_max_m", 1.0))
    fb_occ_min = float(cfg.get("fallback_occurrence_min_pct", 5.0))

    sar_valid = np.isfinite(vv) & (vv > nodata_max_db)

    # 1. Подавление спекла (Lee MMSE, по умолчанию квадратное окно 7x7;
    #    направленный вариант "Refined Lee" с выравниванием по краям НЕ реализован)
    vv_filt = speckle_filter(vv, method=filter_method, size=filter_size)
    vh_filt = speckle_filter(vh, method=filter_method, size=filter_size) if vh is not None else None

    use_dual_pol = bool(cfg.get("sar_use_dual_pol", True))
    vv_w = float(cfg.get("sar_dual_pol_vv_weight", 0.7))
    vh_w = float(cfg.get("sar_dual_pol_vh_weight", 0.3))

    # 2. Порог Otsu по SAR в пределах поймы
    mask_for_otsu = topo_mask if (use_topo and topo_mask is not None) else None
    if use_dual_pol and vh_filt is not None:
        sar_feature = vv_w * vv_filt + vh_w * vh_filt
        th_feature = compute_otsu_threshold(sar_feature, mask=mask_for_otsu)
        builtup_clean = (builtup < builtup_max) if builtup is not None else True
        otsu_water = (sar_feature < th_feature) & sar_valid & builtup_clean & (vh_filt < vh_thresh)
    else:
        th_vv = compute_otsu_threshold(vv_filt, mask=mask_for_otsu)
        builtup_clean = (builtup < builtup_max) if builtup is not None else True
        otsu_water = (vv_filt < th_vv) & sar_valid & builtup_clean
        if vh_filt is not None:
            otsu_water = otsu_water & (vh_filt < vh_thresh)

    sar_water = otsu_water

    # 3. Обнаружение изменений на пике паводка и двойное отражение
    if is_peak and vv_ref is not None:
        vv_ref_filt = speckle_filter(vv_ref, method=filter_method, size=filter_size)
        drop = vv_ref_filt - vv_filt
        drop_cond = (drop >= drop_thresh) & (vv_filt < sar_drop_vv_max)
        if vh_filt is not None and vh_ref is not None:
            vh_ref_filt = speckle_filter(vh_ref, method=filter_method, size=filter_size)
            drop_vh = vh_ref_filt - vh_filt
            drop_cond = drop_cond & (drop_vh >= sar_drop_vh_min) & (vh_filt < sar_drop_vh_max)

        # Вода на пике объединяет провал >= 3 дБ и ограниченную воду Otsu.
        # Затопленная растительность под пологом (двойное отражение) намеренно НЕ объединяется
        # с зеркалом открытой воды (раздел 5 ТЗ); см. detect_flooded_vegetation().
        sar_water = (sar_water | drop_cond) & sar_valid

    # 3b. Защита от радиолокационной тени с учётом орбиты. Грани в геометрической тени (крутой склон,
    #     направленный от направления визирования) возвращают только тепловой шум, который путь
    #     Otsu выше неверно читает как открытую воду. Подавляем их только на маске, полученной из SAR, чтобы
    #     независимые свидетельства (оптическая вода, априорная постоянная вода GSW) сохранялись.
    shadow = radar_shadow_mask(slope, aspect, orbit_pass)
    if shadow is not None:
        sar_water = sar_water & ~shadow

    # Аккуратная обработка частичного SAR и nodata (например, границы треков Поярково).
    # Явная эвристика из конфигурации: когда покрытие SAR слишком разрежено, чтобы ему
    # доверять (< sar_valid_frac_min от AOI), откат к постоянной воде GSW
    # плюс консервативное расширение поймы по низкому HAND вместо SAR Otsu.
    if sar_valid.mean() < sar_valid_frac_min and permanent_mask is not None:
        if is_peak and topo_mask is not None and hand is not None and occurrence is not None:
            flood_expansion = topo_mask & (hand <= fb_hand_max) & (occurrence >= fb_occ_min) & (~permanent_mask)
            sar_water = permanent_mask | flood_expansion
        else:
            sar_water = permanent_mask.copy()

    # 4. Объединение с оптикой там, где она доступна
    if use_optical and optical_water is not None and optical_valid is not None and np.any(optical_valid):
        water = np.where(optical_valid, optical_water | sar_water, sar_water)
    else:
        water = sar_water

    # 5. Топографические априорные данные
    if use_topo and topo_mask is not None:
        water = water & topo_mask

    # 6. Априорная постоянная вода GSW
    if use_permanent and permanent_mask is not None:
        water = water | permanent_mask

    # 7. Фильтрация MMU
    if use_mmu:
        water = apply_mmu(water, min_size=mmu_pixels)

    return water.astype(np.uint8)
