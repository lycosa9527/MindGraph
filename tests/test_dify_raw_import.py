"""Tests for Dify raw dump zip import helpers."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

import main as _main_app

assert _main_app.app.title

from services.dify.export.raw_dump_import import (
    _member_dest,
    import_zip_file,
    peek_manifest_from_zip,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "dify_raw_dump" / "dify" / "minimal"


def test_peek_manifest_from_zip(tmp_path: Path) -> None:
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
    zip_path = tmp_path / "dify-dump_dify_test.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for csv_name in FIXTURE_DIR.glob("*.csv"):
            archive.write(csv_name, f"2026-06-26_120000Z/{csv_name.name}")
        archive.writestr("2026-06-26_120000Z/manifest.json", json.dumps(manifest))
    loaded = peek_manifest_from_zip(zip_path)
    assert loaded["server_label"] == "dify"


def test_member_dest_rejects_zip_slip(tmp_path: Path) -> None:
    """Path traversal members are rejected before extraction."""
    with pytest.raises(ValueError, match="zip slip|unsafe zip path"):
        _member_dest(tmp_path, "../escape.csv")


def test_import_zip_rejects_sha256_mismatch(tmp_path: Path) -> None:
    """Manifest archive_sha256 must match the uploaded zip bytes."""
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
    manifest["archive_sha256"] = "0" * 64
    incoming = tmp_path / "incoming"
    incoming.mkdir(parents=True)
    zip_path = incoming / "dify-dump_dify_test.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for csv_name in FIXTURE_DIR.glob("*.csv"):
            archive.write(csv_name, f"2026-06-26_120000Z/{csv_name.name}")
        archive.writestr("2026-06-26_120000Z/manifest.json", json.dumps(manifest))
    with pytest.raises(ValueError, match="sha256 mismatch"):
        import_zip_file(zip_path, tmp_path, move_to_done=False)
