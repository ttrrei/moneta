"""Unit tests for pipeline/extract_oci.py."""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.extract_oci import (
    _safe_relative_path,
    _unique_target_path,
    ensure_dir,
    extract_all_zips_to_csv,
    load_config,
    sync_oci_par,
)


def test_ensure_dir(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "folder"
    res = ensure_dir(target)
    assert res.exists()
    assert res.is_dir()


def test_safe_relative_path(tmp_path: Path) -> None:
    # Valid relative path
    p = _safe_relative_path("2024/data.zip", tmp_path)
    assert p == (tmp_path / "2024" / "data.zip").resolve()

    # Traversal attempt
    assert _safe_relative_path("../outside.zip", tmp_path) is None
    assert _safe_relative_path("/absolute/path.zip", tmp_path) is None
    assert _safe_relative_path("", tmp_path) is None
    assert _safe_relative_path("folder/", tmp_path) is None


def test_unique_target_path(tmp_path: Path) -> None:
    f1 = _unique_target_path(tmp_path, "test.csv")
    assert f1.name == "test.csv"
    f1.write_text("content")

    f2 = _unique_target_path(tmp_path, "test.csv")
    assert f2.name == "test_1.csv"


def test_load_config_not_found(tmp_path: Path) -> None:
    missing = tmp_path / "nonexistent.yml"
    with pytest.raises(FileNotFoundError):
        load_config(missing)


def test_load_config_success(tmp_path: Path) -> None:
    cfg = tmp_path / "setting.yml"
    cfg.write_text('oci:\n  par_url: "https://example.com/par"\n', encoding="utf-8")
    data = load_config(cfg)
    assert data["oci"]["par_url"] == "https://example.com/par"


@patch("pipeline.extract_oci.requests.Session")
def test_sync_oci_par_mocked(mock_session_cls: MagicMock, tmp_path: Path) -> None:
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    # Mock list objects response
    list_resp = MagicMock()
    list_resp.json.return_value = {
        "objects": [
            {"name": "file1.zip", "size": 10},
            {"name": "folder/", "size": 0},
        ],
        "nextStartWith": None,
    }

    # Mock download response
    down_resp = MagicMock()
    down_resp.iter_content.return_value = [b"hello world"]

    mock_session.get.side_effect = [list_resp, down_resp]

    downloaded = sync_oci_par("https://example.com/par/", target_dir=tmp_path)
    assert len(downloaded) == 1
    assert downloaded[0].name == "file1.zip"
    assert downloaded[0].read_bytes() == b"hello world"


def test_extract_all_zips_to_csv(tmp_path: Path) -> None:
    zips_dir = tmp_path / "zips"
    csv_dir = tmp_path / "csvs"
    zips_dir.mkdir()
    csv_dir.mkdir()

    # Create a valid zip containing a CSV file
    zip_path = zips_dir / "test_data.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("subfolder/sample.csv", "time,price\n1,100\n")
        zf.writestr("readme.txt", "ignore me\n")

    extracted = extract_all_zips_to_csv(zips_dir, csv_dir)
    assert len(extracted) == 1
    assert extracted[0].name == "sample.csv"
    assert "time,price" in extracted[0].read_text(encoding="utf-8")


def test_extract_keeps_subdirectories_but_removes_stale_top_level_csv(tmp_path: Path) -> None:
    """Sub-directories hold other sources (e.g. OANDA backfills) and must survive re-extraction."""
    zips, target = tmp_path / "zips", tmp_path / "csv"
    zips.mkdir()
    (target / "GBP_USD").mkdir(parents=True)
    (target / "GBP_USD" / "oanda_backfill.csv").write_text("keep\n", encoding="utf-8")
    (target / "stale.csv").write_text("stale\n", encoding="utf-8")
    with zipfile.ZipFile(zips / "a.zip", "w") as archive:
        archive.writestr("prices_x.csv", "new\n")

    extract_all_zips_to_csv(zips, target)

    assert (target / "GBP_USD" / "oanda_backfill.csv").read_text(encoding="utf-8") == "keep\n"
    assert not (target / "stale.csv").exists()
    assert (target / "prices_x.csv").exists()
