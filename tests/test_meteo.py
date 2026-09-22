"""Тесты для модуля гидрометеорологического анализа ERA5."""

from pathlib import Path

import pandas as pd
import pytest

from src.meteo import (
    analyze_meteo_precursors,
    load_era5_timeseries,
)
from src.service.data_loader import DataLoader


def test_load_era5_timeseries_valid(tmp_path: Path):
    csv_file = tmp_path / "ERA5_daily_test.csv"
    csv_file.write_text(
        "date,precip_mm,temp_c,snowmelt_mm\n"
        "2019-06-01,10.5,15.2,0.0\n"
        "2019-06-02,25.0,14.8,0.5\n"
        "2019-06-03,0.0,18.1,0.0\n"
    )
    df = load_era5_timeseries(csv_file)
    assert len(df) == 3
    assert df["precip_mm"].iloc[1] == 25.0
    assert df["temp_c"].iloc[0] == 15.2
    assert df["snowmelt_mm"].iloc[1] == 0.5


def test_load_era5_timeseries_missing_file():
    with pytest.raises(FileNotFoundError):
        load_era5_timeseries("non_existent_file.csv")


def test_load_era5_timeseries_missing_columns(tmp_path: Path):
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("date,val\n2019-01-01,1\n")
    with pytest.raises(ValueError, match="отсутствуют колонки"):
        load_era5_timeseries(bad_csv)


def test_analyze_meteo_precursors_extreme(tmp_path: Path):
    dates = pd.date_range("2019-06-01", periods=15, freq="D")
    precip = [0.0] * 10 + [20.0, 35.0, 15.0, 5.0, 0.0]
    temp = [18.0] * 15
    snowmelt = [0.0] * 15

    df = pd.DataFrame(
        {
            "date": dates,
            "precip_mm": precip,
            "temp_c": temp,
            "snowmelt_mm": snowmelt,
        }
    )

    summary = analyze_meteo_precursors(
        df,
        pair_id="test_pair",
        date_pre="2019-06-01",
        date_peak="2019-06-15",
    )

    assert summary.has_meteo_data is True
    assert summary.data_points_count == 15
    assert summary.precip_interval_mm == 75.0
    assert summary.max_daily_precip_mm == 35.0
    assert summary.heavy_rain_days_count == 3
    assert summary.flood_meteo_trigger == "extreme_rainfall"
    assert summary.meteo_confirmation is True


def test_analyze_meteo_precursors_empty():
    summary = analyze_meteo_precursors(pd.DataFrame(), pair_id="empty_pair")
    assert summary.has_meteo_data is False
    assert summary.precip_interval_mm == 0.0
    assert summary.flood_meteo_trigger == "no_data"
    assert summary.meteo_confirmation is False


def test_data_loader_era5_integration():
    loader = DataLoader()
    pairs = loader.get_pairs()
    assert len(pairs) > 0
    pair_id = pairs[0]["pair_id"]

    # Проверка вызова через loader
    meteo_summary = loader.compute_meteo_summary(pair_id)
    assert isinstance(meteo_summary, dict)
    assert "has_meteo_data" in meteo_summary

    timeseries = loader.get_meteo_timeseries(pair_id)
    assert isinstance(timeseries, list)
    if meteo_summary["has_meteo_data"]:
        assert len(timeseries) > 0
        assert "precip_mm" in timeseries[0]
