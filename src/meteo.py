"""Модуль гидрометеорологического анализа данных ERA5 для HydroWatch Amur.

Выполняет чтение суточных временных рядов ERA5 (осадки, температура, снеготаяние),
расчет гидрометеорологических прекурсоров паводка (аккумулированные осадки за 3/7/14 дней,
междусъемочные суммы, аномалии) и верификацию гидрологического триггера паводка.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MeteoPrecursorSummary:
    """Сводные гидрометеорологические показатели ERA5 по паре."""

    pair_id: str
    has_meteo_data: bool
    data_points_count: int
    date_start: str
    date_end: str
    # Аккумулированные осадки
    precip_interval_mm: float  # Осадки между датой pre и peak
    precip_3d_before_peak_mm: float  # Осадки за 3 дня до пика (ударный гидрограф)
    precip_7d_before_peak_mm: float  # Осадки за 7 дней до пика
    precip_14d_before_peak_mm: float  # Осадки за 14 дней до пика
    max_daily_precip_mm: float  # Суточный максимум осадков в интервале
    max_daily_precip_date: str
    heavy_rain_days_count: int  # Дни с осадками > 15 мм
    # Температурный режим и таяние
    mean_temp_c: float
    min_temp_c: float
    max_temp_c: float
    snowmelt_interval_mm: float
    # Гидрологическая интерпретация
    flood_meteo_trigger: str  # 'extreme_rainfall', 'moderate_rainfall', 'low_rainfall_snowmelt', 'low_precip'
    meteo_confirmation: bool  # Подтверждается ли паводок метеорологически (>25 мм суммарно или >15 мм/сут)
    description: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_era5_timeseries(file_path: Path | str) -> pd.DataFrame:
    """Загружает CSV суточных рядов ERA5 с валидацией колонок и типов."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Файл ERA5 не найден: {path}")

    df = pd.read_csv(path)
    required_cols = {"date", "precip_mm", "temp_c", "snowmelt_mm"}
    if not required_cols.issubset(df.columns):
        missing = required_cols - set(df.columns)
        raise ValueError(f"В файле ERA5 {path} отсутствуют колонки: {missing}")

    df["date"] = pd.to_datetime(df["date"])
    df["precip_mm"] = pd.to_numeric(df["precip_mm"], errors="coerce").fillna(0.0).clip(lower=0.0)
    df["temp_c"] = pd.to_numeric(df["temp_c"], errors="coerce").fillna(0.0)
    df["snowmelt_mm"] = pd.to_numeric(df["snowmelt_mm"], errors="coerce").fillna(0.0).clip(lower=0.0)
    df = df.sort_values("date").reset_index(drop=True)
    return df


def find_era5_file(data_dir: Path | str, rasters_dir: str | Path, pair_id: str) -> Path | None:
    """Находит файл ERA5 для пары в каталоге растров."""
    base_dir = Path(data_dir) / Path(rasters_dir)
    if not base_dir.exists():
        return None

    # Прямой поиск по стандартному имени ERA5_daily_{pair_id}.csv
    exact = base_dir / f"ERA5_daily_{pair_id}.csv"
    if exact.exists():
        return exact

    # Поиск любого файла ERA5 в папке
    candidates = list(base_dir.glob("ERA5*.csv"))
    if candidates:
        return candidates[0]

    return None


def analyze_meteo_precursors(
    df: pd.DataFrame,
    pair_id: str,
    date_pre: str | None = None,
    date_peak: str | None = None,
) -> MeteoPrecursorSummary:
    """Анализирует метеорологические прекурсоры паводка по ряду ERA5."""
    if df.empty:
        return MeteoPrecursorSummary(
            pair_id=pair_id,
            has_meteo_data=False,
            data_points_count=0,
            date_start="",
            date_end="",
            precip_interval_mm=0.0,
            precip_3d_before_peak_mm=0.0,
            precip_7d_before_peak_mm=0.0,
            precip_14d_before_peak_mm=0.0,
            max_daily_precip_mm=0.0,
            max_daily_precip_date="",
            heavy_rain_days_count=0,
            mean_temp_c=0.0,
            min_temp_c=0.0,
            max_temp_c=0.0,
            snowmelt_interval_mm=0.0,
            flood_meteo_trigger="no_data",
            meteo_confirmation=False,
            description="Данные ERA5 отсутствуют",
        )

    t_start = pd.to_datetime(date_pre) if date_pre else df["date"].min()
    t_peak = pd.to_datetime(date_peak) if date_peak else df["date"].max()

    # Срез между датой до события и пиком
    mask_interval = (df["date"] >= t_start) & (df["date"] <= t_peak)
    df_interval = df[mask_interval]
    if df_interval.empty:
        df_interval = df

    precip_interval = float(df_interval["precip_mm"].sum())
    snowmelt_interval = float(df_interval["snowmelt_mm"].sum())
    mean_temp = float(df_interval["temp_c"].mean())
    min_temp = float(df_interval["temp_c"].min())
    max_temp = float(df_interval["temp_c"].max())

    # Максимум осадков за день в интервале
    max_row = df_interval.loc[df_interval["precip_mm"].idxmax()]
    max_daily_precip = float(max_row["precip_mm"])
    max_daily_date = max_row["date"].strftime("%Y-%m-%d")

    # Дни с сильным дождем (> 15 мм)
    heavy_rain_days = int((df_interval["precip_mm"] >= 15.0).sum())

    # Прекурсоры за 3, 7, 14 дней до пика
    mask_3d = (df["date"] >= (t_peak - pd.Timedelta(days=3))) & (df["date"] <= t_peak)
    mask_7d = (df["date"] >= (t_peak - pd.Timedelta(days=7))) & (df["date"] <= t_peak)
    mask_14d = (df["date"] >= (t_peak - pd.Timedelta(days=14))) & (df["date"] <= t_peak)

    p_3d = float(df.loc[mask_3d, "precip_mm"].sum()) if mask_3d.any() else 0.0
    p_7d = float(df.loc[mask_7d, "precip_mm"].sum()) if mask_7d.any() else 0.0
    p_14d = float(df.loc[mask_14d, "precip_mm"].sum()) if mask_14d.any() else 0.0

    # Оценка триггера паводка
    meteo_confirmation = False
    if precip_interval >= 80.0 or p_7d >= 40.0 or max_daily_precip >= 30.0:
        trigger = "extreme_rainfall"
        meteo_confirmation = True
        desc = (
            f"Экстремальные дождевые осадки ({precip_interval:.1f} мм за интервал, суточный максимум "
            f"{max_daily_precip:.1f} мм {max_daily_date}). Сформирован мощный дождевой паводок."
        )
    elif precip_interval >= 30.0 or p_7d >= 20.0 or max_daily_precip >= 15.0:
        trigger = "moderate_rainfall"
        meteo_confirmation = True
        desc = (
            f"Умеренные дождевые осадки ({precip_interval:.1f} мм, суточный максимум "
            f"{max_daily_precip:.1f} мм). Дождевое подпитывание речной сети."
        )
    elif snowmelt_interval > 10.0:
        trigger = "snowmelt_dominant"
        meteo_confirmation = True
        desc = (
            f"Преобладание весенне-летнего снеготаяния ({snowmelt_interval:.1f} мм воды от таяния) "
            f"при умеренных осадках ({precip_interval:.1f} мм)."
        )
    else:
        trigger = "low_precip"
        meteo_confirmation = False
        desc = (
            f"Низкая сумма осадков ({precip_interval:.1f} мм за интервал). "
            f"Характерно для устойчивой межени или транзитного руслового притока с верхнего бьефа."
        )

    return MeteoPrecursorSummary(
        pair_id=pair_id,
        has_meteo_data=True,
        data_points_count=len(df),
        date_start=df["date"].min().strftime("%Y-%m-%d"),
        date_end=df["date"].max().strftime("%Y-%m-%d"),
        precip_interval_mm=round(precip_interval, 1),
        precip_3d_before_peak_mm=round(p_3d, 1),
        precip_7d_before_peak_mm=round(p_7d, 1),
        precip_14d_before_peak_mm=round(p_14d, 1),
        max_daily_precip_mm=round(max_daily_precip, 1),
        max_daily_precip_date=max_daily_date,
        heavy_rain_days_count=heavy_rain_days,
        mean_temp_c=round(mean_temp, 1),
        min_temp_c=round(min_temp, 1),
        max_temp_c=round(max_temp, 1),
        snowmelt_interval_mm=round(snowmelt_interval, 1),
        flood_meteo_trigger=trigger,
        meteo_confirmation=meteo_confirmation,
        description=desc,
    )
