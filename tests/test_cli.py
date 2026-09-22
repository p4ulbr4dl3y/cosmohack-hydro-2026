"""Тесты унифицированного CLI HydroWatch Amur."""

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
    assert f"ОТЧЕТ: {pair_id}" in captured.out
    # Площадь паводка должна совпадать с поставляемым submission.csv (единый источник истины)
    sub = pd.read_csv(Path("submission.csv"))
    expected = float(sub.loc[sub["pair_id"] == pair_id, "flood_ha"].iloc[0])
    assert f"Затопление: {expected:.2f} га" in captured.out
    assert "Прирост воды:" in captured.out
    assert "Затопление пашни:" in captured.out


def test_cli_report_output_json(tmp_path):
    out_json = tmp_path / "report.json"
    pair_id = "flood_2019_07_amur__blagoveshchensk"
    run_report(pair_id=pair_id, output=out_json)
    assert out_json.exists()
    with open(out_json, encoding="utf-8") as f:
        data = json.load(f)
    assert data["pair_id"] == pair_id
    sub = pd.read_csv(Path("submission.csv"))
    expected = float(sub.loc[sub["pair_id"] == pair_id, "flood_ha"].iloc[0])
    assert data["flood_ha"] == expected
    assert "cropland_ha" in data["landcover"]


def test_cli_report_output_csv(tmp_path):
    out_csv = tmp_path / "reports.csv"
    run_report(output=out_csv)
    assert out_csv.exists()
    df = pd.read_csv(out_csv)
    assert len(df) == 11
    assert "flood_ha" in df.columns
    assert "builtup_ha" in df.columns


def test_cli_subcommands_parser():
    # Проверка, что main не падает на некорректных аргументах при вызове с --help
    with pytest.raises(SystemExit) as exc:
        sys.argv = ["hydrowatch-cli", "--help"]
        main()
    assert exc.value.code == 0


def test_check_s1_data_missing(tmp_path):
    # Отсутствует каталог данных -> снимки S1 отсутствуют -> проверка должна завершиться неудачей без падения
    assert check_s1_data_available(Path("hydrowatch_amur/pairs.csv"), Path("/nonexistent")) is False


def test_predict_without_s1_prints_hint(tmp_path, capsys):
    """predict в репозитории без снимков S1 должен завершиться с понятной подсказкой о загрузке, а не с сырым traceback."""
    sys.argv = [
        "hydrowatch-cli",
        "predict",
        "--data-dir",
        str(tmp_path),  # пустой каталог: растры полностью отсутствуют
    ]
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    out = capsys.readouterr().err
    assert "нужны сцены Sentinel-1" in out
    assert "src.cli fetch" in out
    assert "docs/Ссылка на данные.txt" in out
    # Разовая внешняя загрузка должна быть указана явно (D1: честный офлайн-сценарий).
    assert "2.9 GB" in out
    assert "drive.google.com" in out
    assert "НЕ воспроизводится офлайн" in out


def test_cli_report_unknown_pair_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        run_report(pair_id="unknown_xyz")
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "Ошибка: пара 'unknown_xyz' не найдена" in err


def test_run_benchmark_mocked(tmp_path, monkeypatch, capsys):
    from src.cli import run_benchmark

    dummy_csv = tmp_path / "pairs.csv"
    dummy_csv.write_text("pair_id\npair1\n", encoding="utf-8")

    # Отсутствующий csv приводит к выходу
    with pytest.raises(SystemExit):
        run_benchmark(tmp_path / "missing.csv", tmp_path, tmp_path)

    # Корректный запуск с замоканным process_pair, создающим файл в predictions_dir
    def mock_process_pair(predictions_dir, **kwargs):
        (predictions_dir / "bench_file.tif").write_text("data")

    monkeypatch.setattr("src.cli.process_pair", mock_process_pair)
    run_benchmark(dummy_csv, tmp_path, tmp_path, iterations=1)
    out = capsys.readouterr().out
    assert "РЕЗУЛЬТАТЫ БЕНЧМАРКА" in out
    assert "Пропускная способность:" in out


def test_run_benchmark_writes_json_summary(tmp_path, monkeypatch):
    """Сводка бенчмарка сохраняется как машиночитаемый артефакт."""
    from src.cli import run_benchmark

    dummy_csv = tmp_path / "pairs.csv"
    dummy_csv.write_text("pair_id\npair1\n", encoding="utf-8")

    monkeypatch.setattr("src.cli.process_pair", lambda predictions_dir, **kwargs: None)

    out_json = tmp_path / "bench.json"
    summary = run_benchmark(dummy_csv, tmp_path, tmp_path, iterations=1, output_json=out_json)

    assert out_json.exists()
    with open(out_json, encoding="utf-8") as fp:
        stored = json.load(fp)
    assert stored == summary
    assert stored["scenes_processed"] == 1.0
    assert stored["avg_latency_s_per_pair"] >= 0.0
    assert stored["peak_rss_mb"] > 0.0
    assert stored["gpu_vram_mb"] == 0.0


def test_check_s1_data_available_success(tmp_path, monkeypatch):
    from src.cli import check_s1_data_available

    monkeypatch.setattr("src.cli.missing_s1_pairs", lambda p, d: [])
    assert check_s1_data_available(tmp_path / "pairs.csv", tmp_path) is True


def test_run_fetch_download_and_missing_scenes(tmp_path, monkeypatch, capsys):
    import sys
    import types

    from src.cli import run_fetch

    dummy_csv = tmp_path / "pairs.csv"
    dummy_csv.write_text("pair_id\n", encoding="utf-8")
    archive = tmp_path / "to_download.zip"

    fake_gdown = types.ModuleType("gdown")
    fake_gdown.download = lambda url, output, quiet: Path(output).write_bytes(b"PKfake")
    monkeypatch.setitem(sys.modules, "gdown", fake_gdown)
    monkeypatch.setattr("src.cli.safe_extract", lambda arc, dest: 3)
    monkeypatch.setattr("src.cli.missing_s1_pairs", lambda pairs, d: ["missing_pair_1"])

    run_fetch(dummy_csv, tmp_path / "extracted", archive_output=archive, keep_archive=True)
    captured = capsys.readouterr()
    assert "Загрузка датасета" in captured.err
    assert "Предупреждение: сцены S1 все еще отсутствуют" in captured.err


def test_run_fetch_mocked(tmp_path, monkeypatch, capsys):
    from src.cli import run_fetch

    dummy_csv = tmp_path / "pairs.csv"
    dummy_csv.write_text("pair_id\n", encoding="utf-8")
    archive = tmp_path / "archive.zip"
    archive.write_bytes(b"PK00fake")

    monkeypatch.setattr("src.cli.safe_extract", lambda arc, dest: 5)
    monkeypatch.setattr("src.cli.missing_s1_pairs", lambda pairs, d: [])

    run_fetch(dummy_csv, tmp_path / "extracted", archive_output=archive, keep_archive=False)
    assert not archive.exists()  # удалён, так как keep_archive=False
    captured = capsys.readouterr()
    assert "Извлечено 5 записей" in captured.err


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


def test_cli_evaluate_holdout_forwards_flag(monkeypatch):
    """``evaluate --holdout`` должен передавать ``--holdout`` в src.evaluate.main."""
    captured = {}

    def fake_evaluate_main():
        captured["argv"] = list(sys.argv)

    monkeypatch.setattr("src.cli.evaluate_main", fake_evaluate_main)

    monkeypatch.setattr("sys.argv", ["hydrowatch-cli", "evaluate", "--holdout"])
    main()
    assert "--holdout" in captured["argv"]

    # Без флага аргумент НЕ должен добавляться (путь по умолчанию не меняется).
    captured.clear()
    monkeypatch.setattr("sys.argv", ["hydrowatch-cli", "evaluate"])
    main()
    assert "--holdout" not in captured["argv"]
    assert captured["argv"][0] == "hydrowatch-cli"


def test_cli_main_module_execution(monkeypatch):
    import runpy

    with pytest.raises(SystemExit) as exc:
        monkeypatch.setattr("sys.argv", ["hydrowatch-cli", "--help"])
        runpy.run_module("src.cli", run_name="__main__")
    assert exc.value.code == 0


def test_cli_predict_workers_flag(monkeypatch):
    called = {}
    monkeypatch.setattr("src.cli.predict_main", lambda: called.setdefault("predict_args", list(sys.argv)))
    monkeypatch.setattr("src.cli.check_s1_data_available", lambda *args: True)

    monkeypatch.setattr("sys.argv", ["hydrowatch-cli", "predict", "--workers", "4"])
    main()
    assert "--workers" in called.get("predict_args", [])
    assert "4" in called.get("predict_args", [])


def test_cli_run_audit_success(tmp_path, capsys):
    from src.cli import run_audit

    pair_id = "flood_2019_07_amur__blagoveshchensk"
    out_json = tmp_path / "audit.json"
    cert = run_audit(pair_id=pair_id, output_json=out_json)

    assert cert["pair_id"] == pair_id
    assert "merkle_root" in cert
    assert "signature_hash" in cert
    assert out_json.exists()

    with open(out_json, encoding="utf-8") as f:
        data = json.load(f)
    assert data["pair_id"] == pair_id

    captured = capsys.readouterr()
    assert f"ГИДРОЛОГИЧЕСКИЙ АУДИТОРСКИЙ СЕРТИФИКАТ: {cert['certificate_id']}" in captured.out
    assert "Аудиторский сертификат сохранен в" in captured.out


def test_cli_run_audit_unknown_pair_exits(capsys):
    from src.cli import run_audit

    with pytest.raises(SystemExit) as exc:
        run_audit(pair_id="unknown_pair_xyz")
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "Ошибка: пара 'unknown_pair_xyz' не найдена." in err


def test_cli_run_uncertainty_success(tmp_path, capsys):
    from src.cli import run_uncertainty

    pair_id = "flood_2019_07_amur__blagoveshchensk"
    out_json = tmp_path / "unc.json"
    res = run_uncertainty(
        pair_id=pair_id,
        confidence_level=0.90,
        spatial_correlation=0.15,
        output_json=out_json,
    )

    assert res["pair_id"] == pair_id
    assert res["confidence_level"] == 0.90
    assert res["spatial_correlation"] == 0.15
    assert res["flood_area_ha"] > 0
    assert out_json.exists()

    with open(out_json, encoding="utf-8") as f:
        data = json.load(f)
    assert data["confidence_level"] == 0.90

    captured = capsys.readouterr()
    assert f"АНАЛИЗ ПРОСТРАНСТВЕННОЙ НЕОПРЕДЕЛЕННОСТИ: {pair_id}" in captured.out
    assert "Сводка неопределенности сохранена в" in captured.out


def test_cli_run_uncertainty_unknown_pair_exits(capsys):
    from src.cli import run_uncertainty

    with pytest.raises(SystemExit) as exc:
        run_uncertainty(pair_id="unknown_pair_xyz")
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "Ошибка: пара 'unknown_pair_xyz' не найдена." in err


def test_cli_run_uncertainty_zero_flood(monkeypatch):
    from src.cli import run_uncertainty

    fake_loader = type(
        "FakeLoader",
        (),
        {"get_report": lambda self, pid: {"flood_ha": 0.0}},
    )
    monkeypatch.setattr("src.cli.DataLoader", fake_loader)

    res = run_uncertainty(pair_id="zero_pair")
    assert res["flood_area_ha"] == 0.0


def test_main_dispatch_audit_uncertainty_fetch_optical(monkeypatch):
    called = {}

    monkeypatch.setattr("src.cli.run_audit", lambda **kwargs: called.setdefault("audit", kwargs))
    monkeypatch.setattr("src.cli.run_uncertainty", lambda **kwargs: called.setdefault("uncertainty", kwargs))

    fake_scripts = type(
        "FakeScripts",
        (),
        {
            "fetch_real_s2": type(
                "FakeS2",
                (),
                {"fetch_optical_scenes": lambda **kwargs: called.setdefault("fetch_optical", kwargs)},
            )
        },
    )
    import sys

    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)
    monkeypatch.setitem(sys.modules, "scripts.fetch_real_s2", fake_scripts.fetch_real_s2)

    monkeypatch.setattr(
        "sys.argv",
        ["hydrowatch-cli", "audit", "--pair-id", "pair1", "--output-json", "audit.json"],
    )
    main()
    assert called.get("audit") == {"pair_id": "pair1", "output_json": Path("audit.json")}

    monkeypatch.setattr(
        "sys.argv",
        [
            "hydrowatch-cli",
            "uncertainty",
            "--pair-id",
            "pair2",
            "--confidence-level",
            "0.99",
            "--spatial-correlation",
            "0.25",
            "--output-json",
            "unc.json",
        ],
    )
    main()
    assert called.get("uncertainty") == {
        "pair_id": "pair2",
        "confidence_level": 0.99,
        "spatial_correlation": 0.25,
        "output_json": Path("unc.json"),
    }

    monkeypatch.setattr(
        "sys.argv",
        ["hydrowatch-cli", "fetch-optical", "--pair-id", "pair3"],
    )
    main()
    assert called.get("fetch_optical")["pair_id"] == "pair3"


def test_run_benchmark_win32_memory_branch(tmp_path, monkeypatch):
    """Тестирует ветку измерения памяти на Windows (ctypes WinDLL psapi / fallback)."""
    import ctypes
    import sys
    from unittest.mock import MagicMock

    from src.cli import run_benchmark

    dummy_csv = tmp_path / "pairs.csv"
    dummy_csv.write_text("pair_id\npair1\n", encoding="utf-8")
    monkeypatch.setattr("src.cli.process_pair", lambda predictions_dir, **kwargs: None)

    # 1. win32 с успешным ctypes вызовом psapi
    monkeypatch.setattr("src.cli.resource", None)
    monkeypatch.setattr(sys, "platform", "win32")

    fake_k32 = MagicMock()
    fake_psapi = MagicMock()

    def fake_get_process_memory_info(handle, byref_pmc, size):
        pmc = byref_pmc._obj if hasattr(byref_pmc, "_obj") else byref_pmc
        pmc.PeakWorkingSetSize = 10485760  # 10 MB
        return 1

    fake_psapi.GetProcessMemoryInfo = fake_get_process_memory_info

    # ctypes на unix не имеет WinDLL атрибута по умолчанию, используем setattr
    monkeypatch.setattr(
        ctypes,
        "WinDLL",
        lambda name: fake_k32 if "kernel32" in name else fake_psapi,
        raising=False,
    )

    summary = run_benchmark(dummy_csv, tmp_path, tmp_path)
    assert summary["peak_rss_mb"] == 10.0

    # 2. win32 где GetProcessMemoryInfo возвращает False (ветка else: peak_mb = 1.0)
    fake_psapi.GetProcessMemoryInfo = lambda handle, byref_pmc, size: 0
    summary_fallback = run_benchmark(dummy_csv, tmp_path, tmp_path)
    assert summary_fallback["peak_rss_mb"] == 1.0

    # 3. win32 где возникает исключение (ветка except Exception: peak_mb = 1.0)
    def fake_error(*args):
        raise RuntimeError("psapi error")

    fake_psapi.GetProcessMemoryInfo = fake_error
    summary_exc = run_benchmark(dummy_csv, tmp_path, tmp_path)
    assert summary_exc["peak_rss_mb"] == 1.0

    # 4. Неизвестная платформа без resource (ветка else: peak_mb = 0.0)
    monkeypatch.setattr(sys, "platform", "unknown_os")
    summary_unknown = run_benchmark(dummy_csv, tmp_path, tmp_path)
    assert summary_unknown["peak_rss_mb"] == 0.0


def test_cli_run_manifest_generate(tmp_path, capsys):
    from src.cli import run_manifest

    test_file = tmp_path / "test.txt"
    test_file.write_text("hydrowatch amur", encoding="utf-8")
    out_json = tmp_path / "manifest.json"

    manifest = run_manifest(
        output_path=out_json,
        verify=False,
        base_dir=tmp_path,
        targets=["test.txt"],
    )
    assert manifest is not None
    assert manifest["total_files"] == 1
    assert out_json.exists()

    captured = capsys.readouterr()
    assert "Манифест артефактов успешно сформирован" in captured.out


def test_cli_run_manifest_verify_valid_and_invalid(tmp_path, capsys):
    from src.cli import run_manifest

    test_file = tmp_path / "data.bin"
    test_file.write_bytes(b"\x00\x01\x02")
    out_json = tmp_path / "manifest.json"

    # Сгенерировать
    run_manifest(output_path=out_json, verify=False, base_dir=tmp_path, targets=["data.bin"])

    # Проверить валидный
    run_manifest(output_path=out_json, verify=True, base_dir=tmp_path)
    captured = capsys.readouterr()
    assert "ПРОЙДЕНО" in captured.out

    # Повредить файл и проверить невалидный (должен sys.exit(1))
    test_file.write_bytes(b"\xff\xff")
    with pytest.raises(SystemExit) as exc:
        run_manifest(output_path=out_json, verify=True, base_dir=tmp_path)
    assert exc.value.code == 1
    captured_err = capsys.readouterr()
    assert "НЕ ПРОЙДЕНО" in captured_err.out


def test_main_dispatch_manifest(monkeypatch):
    called = {}
    monkeypatch.setattr("src.cli.run_manifest", lambda **kwargs: called.setdefault("manifest", kwargs))

    monkeypatch.setattr(
        "sys.argv",
        [
            "hydrowatch-cli",
            "manifest",
            "--output",
            "custom_manifest.json",
            "--verify",
            "--base-dir",
            "some_dir",
            "--targets",
            "file1",
            "file2",
        ],
    )
    main()
    assert called.get("manifest") == {
        "output_path": Path("custom_manifest.json"),
        "verify": True,
        "base_dir": Path("some_dir"),
        "targets": ["file1", "file2"],
    }
