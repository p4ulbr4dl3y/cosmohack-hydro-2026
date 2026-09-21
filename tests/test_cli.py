"""Tests for HydroWatch Amur unified CLI."""

import json

import pandas as pd
import pytest

from src.cli import main, run_report


def test_cli_report_single_pair(capsys):
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    run_report(pair_id=pair_id)
    captured = capsys.readouterr()
    assert "REPORT: flood_2019_07_amur__blagoveshchensk" in captured.out
    assert "Flood: 1335.69 ha" in captured.out
    assert "Water Gain:" in captured.out


def test_cli_report_output_json(tmp_path):
    out_json = tmp_path / "report.json"
    run_report(pair_id="flood_2019_07_amur__blagoveshchensk", output=out_json)
    assert out_json.exists()
    with open(out_json, encoding="utf-8") as f:
        data = json.load(f)
    assert data["pair_id"] == "flood_2019_07_amur__blagoveshchensk"
    assert data["flood_ha"] == 1335.69


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
        import sys

        sys.argv = ["hydrowatch-cli", "--help"]
        main()
    assert exc.value.code == 0
