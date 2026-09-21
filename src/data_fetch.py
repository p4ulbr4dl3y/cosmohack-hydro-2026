"""Helpers for fetching and unpacking the external HydroWatch Amur dataset.

The Sentinel-1 scenes (S1_pre_*.tif / S1_peak_*.tif, ~2.9 GB) are not stored
in git (see .gitignore) and are distributed by the case organizers via
Google Drive. This module provides a safe unpacker (stdlib only, no external
``unzip`` binary required) and a check for which pairs still lack S1 scenes.
"""

from __future__ import annotations

import csv
import glob
import zipfile
from pathlib import Path

#: Link also documented in docs/Ссылка на данные.txt
DATA_URL = "https://drive.google.com/file/d/15bwUajgK31XtiW_EiMAAfvTAaqzA6skV/view?usp=sharing"


def safe_extract(archive_path: Path, dest: Path) -> int:
    """Extract a zip archive into ``dest``, guarding against zip-slip.

    Returns the number of extracted entries. Every entry target must stay
    inside ``dest``; otherwise a ``RuntimeError`` is raised before extraction.
    """
    dest = dest.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            target = (dest / info.filename).resolve()
            if not target.is_relative_to(dest):
                raise RuntimeError(f"Unsafe path in archive: {info.filename}")
        archive.extractall(dest)
        return len(archive.infolist())


def missing_s1_pairs(pairs_csv: Path, data_dir: Path) -> list[str]:
    """Return pair ids whose S1 pre/peak scenes are not present on disk."""
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
