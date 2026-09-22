"""Криптографический манифест целостности артефактов (SHA-256 / MRV verification).

Модуль сканирует ключевые артефакты пайплайна (предсказания, итоговые метрики, абляции,
файл сабмишна), вычисляет для каждого файла криптографический хеш SHA-256, размер
и отметку времени генерации, а также вычисляет корневой Merkle-хеш манифеста
для обеспечения полной математической воспроизводимости и MRV-верификации.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.audit import build_merkle_tree

logger = logging.getLogger(__name__)

DEFAULT_MANIFEST_PATH = Path("data/artifacts_manifest.json")
DEFAULT_TARGETS: list[str] = [
    "predictions",
    "data/final_evaluation_results.json",
    "data/ablation_results.json",
    "data/holdout_results.json",
    "data/benchmark_results.json",
    "submission.csv",
]


@dataclass
class ManifestVerificationResult:
    """Результат проверки целостности манифеста."""

    is_valid: bool
    verified_count: int
    missing_files: list[str]
    corrupted_files: list[str]
    size_mismatches: list[str]
    merkle_valid: bool
    errors: list[str]

    def __iter__(self) -> Iterator[Any]:
        """Позволяет распаковку в кортеж (is_valid, errors)."""
        return iter((self.is_valid, self.errors))

    def summary(self) -> str:
        """Текстовая сводка результатов верификации."""
        status = "PASSED" if self.is_valid else "FAILED"
        lines = [
            f"Integrity check status: {status}",
            f"Verified files: {self.verified_count}",
            f"Missing files: {len(self.missing_files)}",
            f"Corrupted files: {len(self.corrupted_files)}",
            f"Size mismatches: {len(self.size_mismatches)}",
            f"Merkle root valid: {self.merkle_valid}",
        ]
        if self.errors:
            lines.append("Errors:")
            for err in self.errors:
                lines.append(f"  - {err}")
        return "\n".join(lines)


def compute_file_sha256(file_path: Path | str, chunk_size: int = 65536) -> str:
    """Вычисляет криптографический дайджест SHA-256 для файла через потоковое чтение."""
    path = Path(file_path)
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def collect_artifact_files(
    targets: Sequence[str | Path] | None = None,
    base_dir: Path | str = ".",
    ignore_manifest_path: Path | str | None = None,
) -> list[Path]:
    """Собирает и сортирует список файлов артефактов для включения в манифест."""
    base_path = Path(base_dir).resolve()
    target_list = list(targets) if targets is not None else DEFAULT_TARGETS
    collected: dict[str, Path] = {}

    ignore_resolved: Path | None = None
    if ignore_manifest_path:
        ignore_resolved = (
            Path(ignore_manifest_path)
            if Path(ignore_manifest_path).is_absolute()
            else (base_path / ignore_manifest_path).resolve()
        )

    for target in target_list:
        t_path = Path(target)
        if not t_path.is_absolute():
            t_path = base_path / t_path

        if not t_path.exists():
            # Если целевой файл/каталог из списка по умолчанию отсутствует, пропускаем
            if targets is not None:
                logger.warning("Target artifact does not exist: %s", t_path)
            continue

        if t_path.is_dir():
            for child in sorted(t_path.rglob("*")):
                if child.is_file() and not child.name.startswith("."):
                    if ignore_resolved and child.resolve() == ignore_resolved:
                        continue
                    try:
                        rel = child.relative_to(base_path).as_posix()
                    except ValueError:
                        rel = child.as_posix()
                    collected[rel] = child
        elif t_path.is_file() and not t_path.name.startswith("."):
            if ignore_resolved and t_path.resolve() == ignore_resolved:
                continue
            try:
                rel = t_path.relative_to(base_path).as_posix()
            except ValueError:
                rel = t_path.as_posix()
            collected[rel] = t_path

    # Возвращаем детерминированно отсортированные пути по относительному имени
    return [collected[k] for k in sorted(collected.keys())]


def create_artifact_entry(
    file_path: Path,
    base_dir: Path | str = ".",
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Формирует запись манифеста для одного файла артефакта."""
    base_path = Path(base_dir).resolve()
    try:
        rel_posix = file_path.resolve().relative_to(base_path).as_posix()
    except ValueError:
        rel_posix = file_path.name

    size_bytes = file_path.stat().st_size
    sha256 = compute_file_sha256(file_path)

    # Используем отметку времени модификации файла или переданный timestamp
    if timestamp is not None:
        file_ts = timestamp
    else:
        file_ts = datetime.fromtimestamp(file_path.stat().st_mtime, tz=UTC).isoformat()

    return {
        "filepath": rel_posix,
        "sha256": sha256,
        "size_bytes": size_bytes,
        "generated_at": file_ts,
    }


def generate_manifest(
    targets: Sequence[str | Path] | None = None,
    base_dir: Path | str = ".",
    output_path: Path | str | None = DEFAULT_MANIFEST_PATH,
) -> dict[str, Any]:
    """Генерирует криптографический манифест целостности артефактов."""
    base_path = Path(base_dir).resolve()
    files = collect_artifact_files(
        targets=targets,
        base_dir=base_path,
        ignore_manifest_path=output_path,
    )

    manifest_generated_at = datetime.now(UTC).isoformat()
    artifact_entries: list[dict[str, Any]] = []
    leaf_hashes: list[str] = []

    for f_path in files:
        entry = create_artifact_entry(f_path, base_dir=base_path)
        artifact_entries.append(entry)
        leaf_hashes.append(entry["sha256"])

    merkle_root, _ = build_merkle_tree(leaf_hashes)

    manifest: dict[str, Any] = {
        "manifest_version": "1.0.0",
        "hash_algorithm": "sha256",
        "generated_at": manifest_generated_at,
        "total_files": len(artifact_entries),
        "total_size_bytes": sum(e["size_bytes"] for e in artifact_entries),
        "merkle_root": merkle_root,
        "artifacts": artifact_entries,
        "files": artifact_entries,  # Псевдоним для удобства
    }

    if output_path:
        out_path = Path(output_path)
        if not out_path.is_absolute():
            out_path = base_path / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fp:
            json.dump(manifest, fp, indent=2, ensure_ascii=False)
        logger.info("Manifest saved with %d artifacts to %s", len(artifact_entries), out_path)

    return manifest


def verify_manifest(
    manifest_or_path: dict[str, Any] | Path | str,
    base_dir: Path | str = ".",
) -> ManifestVerificationResult:
    """Проверяет целостность артефактов на диске по ранее сохранённому манифесту."""
    base_path = Path(base_dir).resolve()

    if isinstance(manifest_or_path, (str, Path)):
        p = Path(manifest_or_path)
        if not p.is_absolute():
            p = base_path / p
        with open(p, encoding="utf-8") as fp:
            manifest = json.load(fp)
    else:
        manifest = manifest_or_path

    raw_artifacts = manifest.get("artifacts") or manifest.get("files") or []
    artifacts = list(raw_artifacts.values()) if isinstance(raw_artifacts, dict) else list(raw_artifacts)

    missing: list[str] = []
    corrupted: list[str] = []
    size_mismatches: list[str] = []
    errors: list[str] = []
    leaf_hashes: list[str] = []
    verified_count = 0

    for item in artifacts:
        rel_posix = item.get("filepath", "")
        expected_sha = item.get("sha256", "").strip().lower()
        expected_size = item.get("size_bytes")

        f_path = base_path / rel_posix
        if not f_path.exists() or not f_path.is_file():
            missing.append(rel_posix)
            errors.append(f"Missing file: {rel_posix}")
            continue

        actual_size = f_path.stat().st_size
        if expected_size is not None and actual_size != expected_size:
            size_mismatches.append(rel_posix)
            errors.append(f"Size mismatch for {rel_posix}: expected {expected_size} bytes, got {actual_size} bytes")

        actual_sha = compute_file_sha256(f_path).lower()
        leaf_hashes.append(actual_sha)

        if actual_sha != expected_sha:
            corrupted.append(rel_posix)
            errors.append(f"SHA-256 mismatch for {rel_posix}: expected {expected_sha}, got {actual_sha}")
        else:
            verified_count += 1

    merkle_valid = True
    expected_merkle = manifest.get("merkle_root")
    if expected_merkle:
        if missing or corrupted:
            merkle_valid = False
        else:
            actual_merkle, _ = build_merkle_tree(leaf_hashes)
            if actual_merkle.lower() != expected_merkle.strip().lower():
                merkle_valid = False
                errors.append(f"Merkle root mismatch: expected {expected_merkle}, computed {actual_merkle}")

    is_valid = len(errors) == 0
    return ManifestVerificationResult(
        is_valid=is_valid,
        verified_count=verified_count,
        missing_files=missing,
        corrupted_files=corrupted,
        size_mismatches=size_mismatches,
        merkle_valid=merkle_valid,
        errors=errors,
    )


def main() -> None:
    """Точка входа командной строки для управления манифестом."""
    parser = argparse.ArgumentParser(
        description="Generate or verify SHA-256 integrity manifest for artifacts and MRV verification"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to manifest JSON file (default: data/artifacts_manifest.json)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify existing manifest against disk artifacts",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path("."),
        help="Base directory for artifact paths (default: current working directory)",
    )
    parser.add_argument(
        "--targets",
        nargs="*",
        default=None,
        help="Specific files or directories to include (defaults to standard predictions & results)",
    )

    args = parser.parse_args()

    if args.verify:
        result = verify_manifest(args.output, base_dir=args.base_dir)
        print(result.summary())
        if not result.is_valid:
            sys.exit(1)
    else:
        manifest = generate_manifest(
            targets=args.targets,
            base_dir=args.base_dir,
            output_path=args.output,
        )
        print(f"Artifacts manifest generated successfully: {args.output}")
        print(f"  Total artifacts : {manifest['total_files']}")
        print(f"  Total size      : {manifest['total_size_bytes'] / (1024 * 1024):.2f} MB")
        print(f"  Merkle root     : {manifest['merkle_root']}")


if __name__ == "__main__":
    main()
