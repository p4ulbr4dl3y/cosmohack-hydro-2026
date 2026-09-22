"""Вспомогательные функции для скачивания и распаковки внешнего датасета HydroWatch Amur.

Сцены Sentinel-1 (S1_pre_*.tif / S1_peak_*.tif, ~2.9 GB) не хранятся
в git (см. .gitignore) и распространяются организаторами кейса через
Google Drive. Этот модуль предоставляет безопасный распаковщик (только стандартная библиотека, без внешнего
бинарника ``unzip``) и проверку того, у каких пар всё ещё нет сцен S1.
"""

from __future__ import annotations

import csv
import glob
import zipfile
from pathlib import Path

#: Ссылка также описана в docs/Ссылка на данные.txt
DATA_URL = "https://drive.google.com/file/d/15bwUajgK31XtiW_EiMAAfvTAaqzA6skV/view?usp=sharing"


def safe_extract(archive_path: Path, dest: Path) -> int:
    """Распаковывает zip-архив в ``dest``, защищаясь от zip-slip.

    Возвращает число распакованных записей. Цель каждой записи должна оставаться
    внутри ``dest``; иначе до распаковки возникает ``RuntimeError``.
    """
    dest = dest.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            target = (dest / info.filename).resolve()
            if not target.is_relative_to(dest):
                raise RuntimeError(f"Небезопасный путь в архиве: {info.filename}")
        archive.extractall(dest)
        return len(archive.infolist())


def missing_s1_pairs(pairs_csv: Path, data_dir: Path) -> list[str]:
    """Возвращает идентификаторы пар, для которых сцены S1 pre/peak отсутствуют на диске."""
    if not pairs_csv.exists():
        return []
    missing: list[str] = []
    with pairs_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rasters_dir = data_dir / str(row["rasters_dir"])
            pre = glob.glob(str(rasters_dir / "S1_pre_*.tif"))
            peak = glob.glob(str(rasters_dir / "S1_peak_*.tif"))
            if not pre or not peak:
                missing.append(str(row["pair_id"]))
    return missing
