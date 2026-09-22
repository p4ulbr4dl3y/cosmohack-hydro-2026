from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from src.cli import main as cli_main
from src.cli import run_manifest
from src.manifest import (
    DEFAULT_MANIFEST_PATH,
    collect_artifact_files,
    compute_file_sha256,
    create_artifact_entry,
    generate_manifest,
    verify_manifest,
)
from src.manifest import (
    main as manifest_main,
)


def test_compute_file_sha256(tmp_path: Path) -> None:
    test_file = tmp_path / "sample.bin"
    payload = b"HydroWatch Amur MRV Verification Test Payload 2026"
    test_file.write_bytes(payload)

    expected = hashlib.sha256(payload).hexdigest()
    actual = compute_file_sha256(test_file, chunk_size=8)
    assert actual == expected
    assert len(actual) == 64


def test_create_artifact_entry(tmp_path: Path) -> None:
    f = tmp_path / "result.json"
    content = b'{"status": "ok"}'
    f.write_bytes(content)

    entry = create_artifact_entry(f, base_dir=tmp_path)
    assert entry["filepath"] == "result.json"
    assert entry["size_bytes"] == len(content)
    assert entry["sha256"] == hashlib.sha256(content).hexdigest()
    assert "generated_at" in entry
    assert "T" in entry["generated_at"]


def test_collect_artifact_files_and_ignores(tmp_path: Path) -> None:
    pred_dir = tmp_path / "predictions"
    pred_dir.mkdir()
    f1 = pred_dir / "flood_1.tif"
    f1.write_bytes(b"raster1")
    f2 = pred_dir / "flood_2.tif"
    f2.write_bytes(b"raster2")
    hidden = pred_dir / ".DS_Store"
    hidden.write_bytes(b"ignore")

    data_file = tmp_path / "results.json"
    data_file.write_bytes(b"{}")

    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_bytes(b"{}")

    collected = collect_artifact_files(
        targets=[pred_dir, data_file, manifest_file],
        base_dir=tmp_path,
        ignore_manifest_path=manifest_file,
    )

    rel_names = [p.relative_to(tmp_path).as_posix() for p in collected]
    assert "predictions/flood_1.tif" in rel_names
    assert "predictions/flood_2.tif" in rel_names
    assert "results.json" in rel_names
    assert "predictions/.DS_Store" not in rel_names
    assert "manifest.json" not in rel_names


def test_generate_and_verify_manifest_in_temp(tmp_path: Path) -> None:
    # 1. Подготовка тестовых файлов
    preds = tmp_path / "predictions"
    preds.mkdir()
    (preds / "pair_a_flood.tif").write_bytes(b"TIFF DATA A")
    (preds / "pair_b_flood.tif").write_bytes(b"TIFF DATA B")

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    eval_json = data_dir / "final_evaluation_results.json"
    eval_json.write_text('{"score": 0.95}', encoding="utf-8")

    manifest_path = data_dir / "artifacts_manifest.json"

    # 2. Генерация
    manifest = generate_manifest(
        targets=[preds, eval_json],
        base_dir=tmp_path,
        output_path=manifest_path,
    )

    assert manifest_path.exists()
    assert manifest["total_files"] == 3
    assert manifest["total_size_bytes"] > 0
    assert len(manifest["merkle_root"]) == 64
    assert len(manifest["artifacts"]) == 3

    # Проверка формата записей
    for item in manifest["artifacts"]:
        assert "filepath" in item
        assert "sha256" in item
        assert "size_bytes" in item
        assert "generated_at" in item

    # 3. Успешная верификация
    res = verify_manifest(manifest_path, base_dir=tmp_path)
    assert res.is_valid is True
    assert res.verified_count == 3
    assert len(res.errors) == 0
    assert res.merkle_valid is True

    # Проверка распаковки в кортеж
    is_valid, errors = res
    assert is_valid is True
    assert len(errors) == 0


def test_verify_manifest_detects_corruption(tmp_path: Path) -> None:
    sub = tmp_path / "submission.csv"
    sub.write_text("pair_id,flood_ha\n1,10.5\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    generate_manifest(targets=[sub], base_dir=tmp_path, output_path=manifest_path)

    # Портим файл
    sub.write_text("pair_id,flood_ha\n1,999.9\n", encoding="utf-8")

    res = verify_manifest(manifest_path, base_dir=tmp_path)
    assert res.is_valid is False
    assert "submission.csv" in res.corrupted_files
    assert res.merkle_valid is False
    assert any("SHA-256 mismatch" in e for e in res.errors)


def test_verify_manifest_detects_missing_file(tmp_path: Path) -> None:
    f1 = tmp_path / "file1.txt"
    f1.write_text("hello", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"

    generate_manifest(targets=[f1], base_dir=tmp_path, output_path=manifest_path)

    # Удаляем файл
    f1.unlink()

    res = verify_manifest(manifest_path, base_dir=tmp_path)
    assert res.is_valid is False
    assert "file1.txt" in res.missing_files
    assert any("Missing file" in e for e in res.errors)


def test_verify_manifest_detects_size_mismatch(tmp_path: Path) -> None:
    f1 = tmp_path / "file1.txt"
    f1.write_text("12345", encoding="utf-8")

    manifest_dict = {
        "manifest_version": "1.0.0",
        "artifacts": [
            {
                "filepath": "file1.txt",
                "sha256": hashlib.sha256(b"12345").hexdigest(),
                "size_bytes": 9999,  # неверный размер
                "generated_at": "2026-09-22T00:00:00Z",
            }
        ],
    }
    res = verify_manifest(manifest_dict, base_dir=tmp_path)
    assert res.is_valid is False
    assert "file1.txt" in res.size_mismatches
    assert any("Size mismatch" in e for e in res.errors)


def test_verify_actual_repository_manifest() -> None:
    """Проверяет реальный репозиторный манифест data/artifacts_manifest.json."""
    if not DEFAULT_MANIFEST_PATH.exists():
        pytest.skip("artifacts_manifest.json not generated yet")

    res = verify_manifest(DEFAULT_MANIFEST_PATH, base_dir=Path("."))
    assert res.is_valid is True, f"Repository manifest integrity errors: {res.errors}"
    assert res.verified_count >= 40
    assert res.merkle_valid is True


def test_cli_manifest_generate_and_verify(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    test_target = tmp_path / "target.txt"
    test_target.write_text("sample content", encoding="utf-8")
    out_manifest = tmp_path / "data" / "manifest.json"

    # Генерация через run_manifest
    res_gen = run_manifest(
        output_path=out_manifest,
        verify=False,
        base_dir=tmp_path,
        targets=[str(test_target)],
    )
    assert res_gen is not None
    assert res_gen["total_files"] == 1
    assert out_manifest.exists()

    # Верификация через run_manifest
    run_manifest(output_path=out_manifest, verify=True, base_dir=tmp_path)
    captured = capsys.readouterr()
    assert "Integrity check status: PASSED" in captured.out


def test_cli_subcommand_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    test_target = tmp_path / "data.bin"
    test_target.write_bytes(b"123456")
    manifest_file = tmp_path / "m.json"

    with patch.object(
        sys,
        "argv",
        [
            "hydrowatch",
            "manifest",
            "--output",
            str(manifest_file),
            "--base-dir",
            str(tmp_path),
            "--targets",
            str(test_target),
        ],
    ):
        cli_main()

    assert manifest_file.exists()

    with patch.object(
        sys,
        "argv",
        [
            "hydrowatch",
            "manifest",
            "--verify",
            "--output",
            str(manifest_file),
            "--base-dir",
            str(tmp_path),
        ],
    ):
        cli_main()


def test_manifest_main_script(tmp_path: Path) -> None:
    test_f = tmp_path / "script_test.txt"
    test_f.write_text("cli test", encoding="utf-8")
    m_out = tmp_path / "script_manifest.json"

    with patch.object(
        sys,
        "argv",
        [
            "src/manifest.py",
            "--output",
            str(m_out),
            "--base-dir",
            str(tmp_path),
            "--targets",
            str(test_f),
        ],
    ):
        manifest_main()

    assert m_out.exists()

    with patch.object(
        sys,
        "argv",
        [
            "src/manifest.py",
            "--verify",
            "--output",
            str(m_out),
            "--base-dir",
            str(tmp_path),
        ],
    ):
        manifest_main()
