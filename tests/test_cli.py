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


def test_cli_report_unknown_pair_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        run_report(pair_id="unknown_xyz")
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "Error: Pair 'unknown_xyz' not found" in err


def test_run_benchmark_mocked(tmp_path, monkeypatch, capsys):
    from src.cli import run_benchmark

    dummy_csv = tmp_path / "pairs.csv"
    dummy_csv.write_text("pair_id\npair1\n", encoding="utf-8")

    # Missing csv exits
    with pytest.raises(SystemExit):
        run_benchmark(tmp_path / "missing.csv", tmp_path, tmp_path)

    # Valid run with mocked process_pair
    monkeypatch.setattr("src.cli.process_pair", lambda **kwargs: None)
    run_benchmark(dummy_csv, tmp_path, tmp_path, iterations=1)
    out = capsys.readouterr().out
    assert "BENCHMARK RESULTS" in out
    assert "Throughput:" in out


def test_run_fetch_mocked(tmp_path, monkeypatch, capsys):
    from src.cli import run_fetch

    dummy_csv = tmp_path / "pairs.csv"
    dummy_csv.write_text("pair_id\n", encoding="utf-8")
    archive = tmp_path / "archive.zip"
    archive.write_bytes(b"PK00fake")

    monkeypatch.setattr("src.cli.safe_extract", lambda arc, dest: 5)
    monkeypatch.setattr("src.cli.missing_s1_pairs", lambda pairs, d: [])

    run_fetch(dummy_csv, tmp_path / "extracted", archive_output=archive, keep_archive=False)
    assert not archive.exists()  # deleted because keep_archive=False
    captured = capsys.readouterr()
    assert "Extracted 5 entries" in captured.err


def test_main_subcommand_dispatching(monkeypatch):
    called = {}

    monkeypatch.setattr("src.cli.predict_main", lambda: called.setdefault("predict", True))
    monkeypatch.setattr("src.cli.evaluate_main", lambda: called.setdefault("evaluate", True))
    monkeypatch.setattr("src.cli.run_report", lambda **kwargs: called.setdefault("report", True))
    monkeypatch.setattr("src.cli.run_fetch", lambda **kwargs: called.setdefault("fetch", True))
    monkeypatch.setattr("src.cli.run_benchmark", lambda **kwargs: called.setdefault("benchmark", True))
    monkeypatch.setattr("src.cli.check_s1_data_available", lambda *args: True)

    monkeypatch.setattr("sys.argv", ["hydrowatch-cli", "predict"])
    main()
    assert called.get("predict")

    monkeypatch.setattr("sys.argv", ["hydrowatch-cli", "evaluate", "--run-ablations"])
    main()
    assert called.get("evaluate")

    monkeypatch.setattr("sys.argv", ["hydrowatch-cli", "report"])
    main()
    assert called.get("report")

    monkeypatch.setattr("sys.argv", ["hydrowatch-cli", "fetch"])
    main()
    assert called.get("fetch")

    monkeypatch.setattr("sys.argv", ["hydrowatch-cli", "benchmark"])
    main()
    assert called.get("benchmark")
