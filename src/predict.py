"""Сквозной конвейер предсказания и инференса для HydroWatch Amur.

Обрабатывает все 11 пар в hydrowatch_amur/pairs.csv, формирует:
  - submission.csv со столбцами [pair_id, flood_ha, water_pre_ha, water_peak_ha]
  - predictions/<pair_id>_flood.tif (GeoTIFF, uint8, 0/1, EPSG:32652)
Проверяет, что площади в CSV совпадают с числом растровых пикселей в пределах 2%.
"""

from __future__ import annotations

import argparse
import gc
import glob
import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

# Гарантируем наличие корня репозитория в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window

from src.config import FLOOD_MMU_MIN_PIXELS, MMU_MIN_PIXELS, PIXEL_SIZE_HA, PIXEL_SIZE_M, SAR_READ_BLOCK_ROWS
from src.filters import (
    apply_hydrological_connectivity,
    apply_mmu,
    apply_morphological_closing,
    apply_planar_hand_filter,
)
from src.geo_utils import clip_by_aoi
from src.indices import segment_optical
from src.segmentation import (
    detect_flooded_vegetation,
    load_aux_priors,
    load_config,
    segment_water,
)
from src.temporal import compute_temporal_dynamics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def read_sar_bands(
    path: str | Path,
    block_rows: int = SAR_READ_BLOCK_ROWS,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Читает VV (канал 1) и VH (канал 2) из сцены Sentinel-1 блоками строк.

    Полные сцены S1 в этом кейсе имеют размер ~3700x4500 float32; чтение их целиком
    (``src.read(1)`` / ``src.read(2)``) делает пиковый RSS пропорциональным размеру сцены. Здесь
    канал читается потоком через ``rasterio.windows.Window`` полосами высотой ``block_rows`` и
    пишется в целевой массив, поэтому дополнительный рабочий набор ограничен одним блоком
    (``block_rows * width`` пикселей) вместо всей сцены.

    Целевой массив выделяется с собственным dtype растра, и каждый блок копируется
    дословно, поэтому результат побитово идентичен чтению всего массива.

    Аргументы:
        path: путь к растру S1 (канал 1 = VV, канал 2 = VH при наличии).
        block_rows: число строк на окно (по умолчанию из ``SAR_READ_BLOCK_ROWS``).

    Возвращает:
        (vv, vh): ``vh`` равен ``None``, когда в растре меньше 2 каналов.
    """
    rows_per_block = max(int(block_rows), 1)
    with rasterio.open(path) as src:
        height, width = src.shape
        vv = np.empty((height, width), dtype=src.dtypes[0])
        vh = np.empty((height, width), dtype=src.dtypes[1]) if src.count >= 2 else None
        for row0 in range(0, height, rows_per_block):
            block = min(rows_per_block, height - row0)
            window = Window(col_off=0, row_off=row0, width=width, height=block)
            rows = slice(row0, row0 + block)
            vv[rows] = src.read(1, window=window)
            if vh is not None:
                vh[rows] = src.read(2, window=window)
    return vv, vh


def resolve_orbit_pass(row: pd.Series) -> str | None:
    """Возвращает метку направления орбиты SAR ("ASCENDING"/"DESCENDING") из строки pairs.

    Метка управляет защитой от радиолокационной тени с учётом орбиты в :func:`segment_water`:
    правосторонняя Sentinel-1 освещает с запада на нисходящих витках и с
    востока на восходящих витках, поэтому затенённая экспозиция рельефа меняется на 180 град. Возвращает
    ``None``, когда столбец отсутствует или пуст, что отключает защиту.
    """
    value = row.get("orbit_pass") if hasattr(row, "get") else None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _process_pair_worker(task_args: tuple[int, int, pd.Series, Path, Path, int]) -> dict[str, float | str]:
    """Вспомогательная функция верхнего уровня для запуска в пуле многопроцессной обработки."""
    idx, total, row, data_dir, predictions_dir, ablation_mode = task_args
    logger.info(f"Processing [{idx + 1}/{total}]: {row['pair_id']}")
    return process_pair(
        row=row,
        data_dir=data_dir,
        predictions_dir=predictions_dir,
        ablation_mode=ablation_mode,
    )


def process_pair(
    row: pd.Series,
    data_dir: Path,
    predictions_dir: Path,
    ablation_mode: int = 4,
) -> dict[str, float | str]:
    """Обрабатывает одну пару AOI через конвейер сегментации.

    Режимы аблации:
      1: только наивный SAR Otsu (без априорных данных, оптики, MMU и постоянной воды).
      2: SAR Otsu + фильтр по HAND и уклону.
      3: объединение SAR и оптики MSI (где доступно) + фильтр по HAND и уклону.
      4: полный конвейер (+ MMU 25 пикс. + постоянная вода GSW).
    """
    pair_id = str(row["pair_id"])
    rasters_dir = data_dir / str(row["rasters_dir"])

    # 1. Сначала находим растры Sentinel-1, чтобы обеспечить автономный откат по геометрии
    s1_pre_files = sorted(glob.glob(str(rasters_dir / "S1_pre_*.tif")))
    s1_peak_files = sorted(glob.glob(str(rasters_dir / "S1_peak_*.tif")))

    if not s1_pre_files or not s1_peak_files:
        raise FileNotFoundError(f"Missing S1 pre/peak rasters in {rasters_dir}")

    # Целевая геометрия: берётся из сетки сцены Sentinel-1 (нативная сетка сенсора).
    # Эталонный растр используется только как запасной вариант, когда метаданные S1 недоступны.
    with rasterio.open(s1_pre_files[0]) as s1_src:
        target_shape = s1_src.shape
        target_transform = s1_src.transform
        target_crs = s1_src.crs

    height, width = target_shape

    # Оконное чтение (блоками строк): пиковый RSS пути чтения SAR ограничен
    # SAR_READ_BLOCK_ROWS, а не полным размером сцены. Побитово идентично src.read().
    vv_pre, vh_pre = read_sar_bands(s1_pre_files[0], block_rows=SAR_READ_BLOCK_ROWS)
    vv_peak, vh_peak = read_sar_bands(s1_peak_files[0], block_rows=SAR_READ_BLOCK_ROWS)

    # 2. Загрузка топографических и гидрологических априорных данных из AUX
    aux_file = rasters_dir / "AUX_terrain_gsw.tif"
    if aux_file.exists() and ablation_mode >= 2:
        aux_data = load_aux_priors(aux_file, target_shape, target_transform, target_crs)
        topo_mask = aux_data["topo_mask"]
        perm_mask = aux_data["permanent_mask"] if ablation_mode == 4 else None
        hand_arr = aux_data["hand"]
        slope_arr = aux_data["slope"]
        aspect_arr = aux_data["aspect"]
        builtup_arr = aux_data["builtup"]
        occ_arr = aux_data["occurrence"]
    else:
        topo_mask = None
        perm_mask = None
        hand_arr = None
        slope_arr = None
        aspect_arr = None
        builtup_arr = None
        occ_arr = None

    tree_arr = None
    tree_file = rasters_dir / "TREE_worldcover.tif"
    if tree_file.exists() and ablation_mode >= 2:
        try:
            with rasterio.open(tree_file) as t_src:
                if t_src.shape == target_shape:
                    tree_arr = t_src.read(1) == 1
        except Exception as e:
            logger.warning(f"[{pair_id}] Failed to load TREE_worldcover: {e}")

    # 3. Загрузка оптических данных Sentinel-2 там, где они доступны
    opt_pre_w, opt_pre_v = None, None
    opt_peak_w, opt_peak_v = None, None
    if ablation_mode >= 3:
        s2_pre_files = sorted(glob.glob(str(rasters_dir / "SENTINEL2_pre_*.tif")))
        s2_peak_files = sorted(glob.glob(str(rasters_dir / "SENTINEL2_peak_*.tif")))
        if s2_pre_files:
            opt_pre_w, opt_pre_v = segment_optical(s2_pre_files[0], target_shape)
        if s2_peak_files:
            opt_peak_w, opt_peak_v = segment_optical(s2_peak_files[0], target_shape)

    use_topo = ablation_mode >= 2
    use_optical = ablation_mode >= 3
    use_mmu = ablation_mode == 4
    use_permanent = ablation_mode == 4

    # Геометрия орбиты из строки pairs управляет защитой от радиолокационной тени с учётом орбиты
    # (нисходящий виток смотрит на запад, восходящий на восток, поэтому затенённая экспозиция меняется).
    orbit_pass = resolve_orbit_pass(row)

    # 4. Сегментация воды до паводка
    water_pre = segment_water(
        vv=vv_pre,
        vh=vh_pre,
        optical_water=opt_pre_w,
        optical_valid=opt_pre_v,
        topo_mask=topo_mask,
        permanent_mask=perm_mask,
        hand=hand_arr,
        slope=slope_arr,
        builtup=builtup_arr,
        occurrence=occ_arr,
        aspect=aspect_arr,
        orbit_pass=orbit_pass,
        is_peak=False,
        use_topo=use_topo,
        use_optical=use_optical,
        use_mmu=use_mmu,
        use_permanent=use_permanent,
    )

    # 5. Сегментация воды пика паводка
    water_peak = segment_water(
        vv=vv_peak,
        vh=vh_peak,
        vv_ref=vv_pre,
        vh_ref=vh_pre,
        optical_water=opt_peak_w,
        optical_valid=opt_peak_v,
        topo_mask=topo_mask,
        permanent_mask=perm_mask,
        hand=hand_arr,
        slope=slope_arr,
        builtup=builtup_arr,
        occurrence=occ_arr,
        aspect=aspect_arr,
        orbit_pass=orbit_pass,
        is_peak=True,
        use_topo=use_topo,
        use_optical=use_optical,
        use_mmu=use_mmu,
        use_permanent=use_permanent,
    )

    # 5c. Морфологическое закрытие водных зеркал (заполняет внутренние спекл-провалы и разрывы от волн)
    if ablation_mode >= 2:
        water_pre = apply_morphological_closing(water_pre, kernel_size=5)
        water_peak = apply_morphological_closing(water_peak, kernel_size=5)

    # 6. Расчёт временной динамики
    temporal = compute_temporal_dynamics(
        water_pre=water_pre,
        water_peak=water_peak,
        permanent=perm_mask,
        pixel_size_m=PIXEL_SIZE_M,
    )

    flood_mask = temporal["flood"]
    water_pre_mask = temporal["water_pre"]
    water_peak_mask = temporal["water_peak"]

    # 5b. Затопленная растительность под пологом (двойное отражение) как отдельный слой продукта.
    # Не входит в зеркало открытой воды (раздел 5 ТЗ); только справочно.
    flooded_vegetation_mask = np.zeros(water_peak_mask.shape, dtype=np.uint8)
    if ablation_mode >= 2:
        fv = detect_flooded_vegetation(
            vv=vv_peak,
            vh=vh_peak,
            vv_ref=vv_pre,
            vh_ref=vh_pre,
            hand=hand_arr,
            slope=slope_arr,
            builtup=builtup_arr,
        )
        flooded_vegetation_mask = fv.astype(np.uint8)
        if ablation_mode >= 2 and tree_arr is not None and hand_arr is not None and occ_arr is not None:
            riparian_corridor = (hand_arr <= 2.0) & (occ_arr >= 5.0)
            riparian_flooded_forest = (flooded_vegetation_mask == 1) & tree_arr & riparian_corridor
            flood_mask = flood_mask | riparian_flooded_forest.astype(np.uint8)
            water_peak_mask = water_peak_mask | riparian_flooded_forest.astype(np.uint8)

    # 6b. Обрезка по границе полигона AOI (устраняет предсказания за пределами границ)
    aoi_geojson_path = data_dir / "vectors" / "aoi.geojson"
    if aoi_geojson_path.exists():
        try:
            aoi_gdf = gpd.read_file(aoi_geojson_path)
            aoi_id = str(row.get("aoi_id", ""))
            matched = aoi_gdf[aoi_gdf["aoi_id"] == aoi_id]
            if not matched.empty:
                geom = matched.to_crs(target_crs).geometry.values[0]
                flood_mask = clip_by_aoi(flood_mask, geom, target_transform, target_crs)
                water_pre_mask = clip_by_aoi(water_pre_mask, geom, target_transform, target_crs)
                water_peak_mask = clip_by_aoi(water_peak_mask, geom, target_transform, target_crs)
                flooded_vegetation_mask = clip_by_aoi(flooded_vegetation_mask, geom, target_transform, target_crs)
        except Exception as e:
            logger.warning(f"[{pair_id}] Failed to clip to AOI boundary: {e}")

    # 6c. Фильтр гидрологической связности с несколькими опорами и MMU в режиме полного конвейера (режим 4)
    if ablation_mode == 4:
        cfg = load_config()
        # Опорная сеть: постоянная речная вода (GSW >= 80%) плюс сезонные русла (GSW occurrence >= 70%)
        seed_mask = None
        if perm_mask is not None and np.any(perm_mask):
            seed_mask = perm_mask.copy()
            if occ_arr is not None:
                seed_mask = seed_mask | ((occ_arr >= 70.0) & np.isfinite(occ_arr))
        elif occ_arr is not None:
            seed_mask = (occ_arr >= 70.0) & np.isfinite(occ_arr)

        if seed_mask is not None and np.any(seed_mask):
            flood_mask = apply_hydrological_connectivity(flood_mask, seed_mask)
            if hand_arr is not None and bool(cfg.get("planar_hand_filter_enabled", True)):
                flood_mask = apply_planar_hand_filter(
                    flood_mask=flood_mask,
                    seed_mask=seed_mask,
                    hand=hand_arr,
                    percentile=float(cfg.get("planar_hand_percentile", 90.0)),
                    tolerance_m=float(cfg.get("planar_hand_tolerance_m", 1.8)),
                )
                flood_mask = apply_hydrological_connectivity(flood_mask, seed_mask)
        flood_mmu = int(cfg.get("flood_mmu_min_pixels", FLOOD_MMU_MIN_PIXELS))
        flood_mask = apply_mmu(flood_mask, min_size=flood_mmu).astype(np.uint8)
        flooded_vegetation_mask = apply_mmu(flooded_vegetation_mask, min_size=MMU_MIN_PIXELS).astype(np.uint8)

    # Пересчёт площадей в гектарах после обрезки, связности и MMU
    flood_ha = round(float(np.sum(flood_mask == 1) * PIXEL_SIZE_HA), 2)
    water_pre_ha = round(float(np.sum(water_pre_mask == 1) * PIXEL_SIZE_HA), 2)
    water_peak_ha = round(float(np.sum(water_peak_mask == 1) * PIXEL_SIZE_HA), 2)

    # 7. Запись предсказания GeoTIFF
    predictions_dir.mkdir(parents=True, exist_ok=True)
    out_tif = predictions_dir / f"{pair_id}_flood.tif"
    with rasterio.open(
        out_tif,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype=np.uint8,
        crs=target_crs,
        transform=target_transform,
        compress="deflate",
        nodata=0,
    ) as dst:
        dst.write(flood_mask, 1)

    # 7b. Запись собственных водных масок GeoTIFF (отдаются сервисом FastAPI)
    water_masks_map = {
        "water_pre": water_pre_mask,
        "water_peak": water_peak_mask,
        "flooded_vegetation": flooded_vegetation_mask,
    }
    for water_layer in ("water_pre", "water_peak", "flooded_vegetation"):
        out_tif = predictions_dir / f"{pair_id}_{water_layer}.tif"
        with rasterio.open(
            out_tif,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype=np.uint8,
            crs=target_crs,
            transform=target_transform,
            compress="deflate",
            nodata=0,
        ) as dst:
            dst.write(water_masks_map[water_layer], 1)

    # 8. Строгая проверка площадей (< 2% расхождения между CSV и растровой маской)
    raster_flood_px = int(np.sum(flood_mask == 1))
    raster_flood_ha = round(raster_flood_px * PIXEL_SIZE_HA, 2)
    diff = abs(flood_ha - raster_flood_ha)
    denom = max(raster_flood_ha, 1.0)
    diff_pct = (diff / denom) * 100.0
    if diff_pct >= 2.0:
        logger.warning(f"[{pair_id}] Area mismatch: CSV={flood_ha} ha, Raster={raster_flood_ha} ha ({diff_pct:.2f}%)")
    assert diff_pct < 2.0, f"Area verification failed for {pair_id}: {diff_pct:.2f}% >= 2.0%"

    logger.info(
        f"[{pair_id}] Done -> flood: {flood_ha} ha, pre: {water_pre_ha} ha, peak: {water_peak_ha} ha (diff={diff_pct:.4f}%)"
    )

    res = {
        "pair_id": pair_id,
        "flood_ha": flood_ha,
        "water_pre_ha": water_pre_ha,
        "water_peak_ha": water_peak_ha,
    }

    # Освобождение временной памяти и запуск сборки мусора
    del vv_pre, vh_pre, vv_peak, vh_peak
    if "aux_data" in locals():
        del aux_data
    del hand_arr, slope_arr, builtup_arr, occ_arr, topo_mask, perm_mask
    del opt_pre_w, opt_pre_v, opt_peak_w, opt_peak_v
    del water_pre, water_peak, temporal
    del flood_mask, water_pre_mask, water_peak_mask, flooded_vegetation_mask, water_masks_map
    gc.collect()

    return res


def run_prediction(
    pairs_csv_path: Path = Path("hydrowatch_amur/pairs.csv"),
    data_dir: Path = Path("hydrowatch_amur"),
    output_csv_path: Path = Path("submission.csv"),
    predictions_dir: Path = Path("predictions"),
    ablation_mode: int = 4,
    workers: int | None = None,
) -> pd.DataFrame:
    """Запускает инференс по всем парам в pairs.csv и формирует submission.csv."""
    pairs_df = pd.read_csv(pairs_csv_path)
    total_pairs = len(pairs_df)
    logger.info(f"Loaded {total_pairs} pairs from {pairs_csv_path}")

    if total_pairs == 0:
        sub_df = pd.DataFrame(columns=["pair_id", "flood_ha", "water_pre_ha", "water_peak_ha"])
        sub_df.to_csv(output_csv_path, index=False)
        return sub_df

    if workers is None:
        cpu_cores = os.cpu_count() or 1
        effective_workers = min(cpu_cores, total_pairs)
    elif workers <= 1:
        effective_workers = 1
    else:
        effective_workers = min(workers, total_pairs)

    records: list[dict[str, Any]] = []
    if effective_workers > 1:
        logger.info(f"Running parallel inference across {effective_workers} worker processes")
        tasks = [(idx, total_pairs, row, data_dir, predictions_dir, ablation_mode) for idx, row in pairs_df.iterrows()]
        with ProcessPoolExecutor(max_workers=effective_workers) as executor:
            records = list(executor.map(_process_pair_worker, tasks))
    else:
        logger.info("Running sequential inference (1 worker)")
        for idx, row in pairs_df.iterrows():
            logger.info(f"Processing [{idx + 1}/{total_pairs}]: {row['pair_id']}")
            rec = process_pair(
                row=row,
                data_dir=data_dir,
                predictions_dir=predictions_dir,
                ablation_mode=ablation_mode,
            )
            records.append(rec)

    sub_df = pd.DataFrame(records)
    sub_df.to_csv(output_csv_path, index=False)
    logger.info(f"Successfully wrote {len(sub_df)} rows to {output_csv_path}")
    return sub_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate flood predictions and submission.csv")
    parser.add_argument("--pairs", type=Path, default=Path("hydrowatch_amur/pairs.csv"))
    parser.add_argument("--data_dir", type=Path, default=Path("hydrowatch_amur"))
    parser.add_argument("--output_csv", type=Path, default=Path("submission.csv"))
    parser.add_argument("--predictions_dir", type=Path, default=Path("predictions"))
    parser.add_argument("--ablation_mode", type=int, default=4, choices=[1, 2, 3, 4])
    parser.add_argument(
        "--workers",
        "--jobs",
        dest="workers",
        type=int,
        default=None,
        help="Number of worker processes for parallel batch inference (default: auto)",
    )
    args = parser.parse_args()

    run_prediction(
        pairs_csv_path=args.pairs,
        data_dir=args.data_dir,
        output_csv_path=args.output_csv,
        predictions_dir=args.predictions_dir,
        ablation_mode=args.ablation_mode,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
