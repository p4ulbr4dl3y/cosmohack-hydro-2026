"""Tests for dataset fetching/unpacking helpers (src.data_fetch)."""

import zipfile

import pytest

from src.data_fetch import missing_s1_pairs, safe_extract


def test_safe_extract_normal(tmp_path):
    archive = tmp_path / "ds.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("hydrowatch_amur/pairs.csv", "pair_id\n")
        z.writestr("hydrowatch_amur/rasters/a/S1_pre_x.tif", "data")

    dest = tmp_path / "out"
    count = safe_extract(archive, dest)
    assert count == 2
    assert (dest / "hydrowatch_amur" / "pairs.csv").exists()
    assert (dest / "hydrowatch_amur" / "rasters" / "a" / "S1_pre_x.tif").exists()


def test_safe_extract_blocks_zip_slip(tmp_path):
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../../evil.txt", "pwned")

    with pytest.raises(RuntimeError, match="Unsafe path"):
        safe_extract(archive, tmp_path / "out")
    assert not (tmp_path / "evil.txt").exists()


def test_safe_extract_blocks_absolute(tmp_path):
    archive = tmp_path / "abs.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("/etc/evil", "pwned")

    with pytest.raises(RuntimeError, match="Unsafe path"):
        safe_extract(archive, tmp_path / "out")


def test_missing_s1_pairs(tmp_path):
    pairs = tmp_path / "pairs.csv"
    pairs.write_text(
        "pair_id,rasters_dir\na,rasters/a\nb,rasters/b\n",
        encoding="utf-8",
    )
    # Data for pair 'a': pre exists, peak missing -> 'a' missing
    (tmp_path / "rasters" / "a").mkdir(parents=True)
    (tmp_path / "rasters" / "a" / "S1_pre_1.tif").touch()
    # Data for pair 'b': both missing
    (tmp_path / "rasters" / "b").mkdir(parents=True)

    missing = missing_s1_pairs(pairs, tmp_path)
    assert missing == ["a", "b"]

    # Complete pair 'a': peak now present -> only 'b' missing
    (tmp_path / "rasters" / "a" / "S1_peak_1.tif").touch()
    assert missing_s1_pairs(pairs, tmp_path) == ["b"]


def test_missing_s1_pairs_missing_csv(tmp_path):
    assert missing_s1_pairs(tmp_path / "nope.csv", tmp_path) == []
