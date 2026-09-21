"""Tests for HydroWatch Amur unified CLI."""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from src.cli import check_s1_data_available, main, run_report


def test_cli_report_single_pair(capsys):
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    run_report(pair_id=pair_id)
    captured = capsys.readouterr()
    assert "REPORT: flood_2019_07_amur__blagoveshchensk" in captured.out
    assert "Flood: 1614.38 ha" in captured.out
    assert "Water Gain:" in captured.out


def test_cli_report_output_json(tmp_path):
    out_json = tmp_path / "report.json"
    run_report(pair_id="flood_2019_07_amur__blagoveshchensk", output=out_json)
    assert out_json.exists()
    with open(out_json, encoding="utf-8") as f:
        data = json.load(f)
    assert data["pair_id"] == "flood_2019_07_amur__blagoveshchensk"
    assert data["flood_ha"] == 1614.38


def test_cli_report_output_csv(tmp_path):
    out_csv = tmp_path / "reports.csv"
    run_report(output=out_csv)
    assert out_csv.exists()
    df = pd.read_csv(out_csv)
    assert len(df) == 11
    assert "flood_ha" in df.columns
    assert "builtup_ha" in df.columns


def test_cli_subcommands_parser():
    # Verify main doesn't crash on invalid args when called with --help
    with pytest.raises(SystemExit) as exc:
        sys.argv = ["hydrowatch-cli", "--help"]
        main()
    assert exc.value.code == 0


def test_check_s1_data_missing(tmp_path):
    # No data dir -> S1 scenes are absent -> check must fail without crash
    assert check_s1_data_available(Path("hydrowatch_amur/pairs.csv"), Path("/nonexistent")) is False


def test_predict_without_s1_prints_hint(tmp_path, capsys):
    """predict on a repo without S1 scenes must fail with a readable download hint, not a raw traceback."""
    sys.argv = [
        "hydrowatch-cli",
        "predict",
        "--data-dir",
        str(tmp_path),  # empty dir: no rasters at all
    ]
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    out = capsys.readouterr().err
    assert "Sentinel-1 scenes are required" in out
    assert "src.cli fetch" in out
    assert "docs/Ссылка на данные.txt" in out
