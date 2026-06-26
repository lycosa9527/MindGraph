"""Tests for MindMate export Dify raw dump admin helpers and API."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from starlette.datastructures import UploadFile

import main as _main_app

assert _main_app.app.title

from services.dify.export.raw_dump_admin import (
    delete_incoming_file,
    delete_snapshot,
    import_incoming_file,
    list_dump_inventory,
    save_uploaded_zip,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "dify_raw_dump" / "dify" / "minimal"


def _build_zip(tmp_path: Path, name: str, label: str = "dify") -> Path:
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
    manifest["server_label"] = label
    zip_path = tmp_path / name
    with zipfile.ZipFile(zip_path, "w") as archive:
        for csv_name in FIXTURE_DIR.glob("*.csv"):
            archive.write(csv_name, f"2026-06-26_120000Z/{csv_name.name}")
        archive.writestr("2026-06-26_120000Z/manifest.json", json.dumps(manifest))
    return zip_path


@pytest.mark.asyncio
async def test_save_upload_and_import_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Upload to incoming, list, import, and see snapshot in inventory."""
    monkeypatch.setenv("MINDMATE_EXPORT_RAW_DUMP_DIR", str(tmp_path))
    zip_path = _build_zip(tmp_path, "dify-dump_dify_test.zip")
    with zip_path.open("rb") as handle:
        upload = UploadFile(filename=zip_path.name, file=handle)
        saved = await save_uploaded_zip(zip_path.name, upload)
    assert saved.path.name == "dify-dump_dify_test.zip"
    inventory = list_dump_inventory(tmp_path)
    assert len(inventory["incoming"]) == 1
    assert inventory["incoming"][0]["server_label"] == "dify"
    imported = import_incoming_file("dify-dump_dify_test.zip", tmp_path)
    assert "2026-06-26_120000Z" in imported["imported"]
    after = list_dump_inventory(tmp_path)
    assert len(after["incoming"]) == 0
    assert after["labels"]["dify"]["active_snapshot"] is not None


def test_delete_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Delete removes extracted snapshot directory."""
    monkeypatch.setenv("MINDMATE_EXPORT_RAW_DUMP_DIR", str(tmp_path))
    zip_path = _build_zip(tmp_path, "dify-dump_dify_test.zip")
    dest = tmp_path / "incoming"
    dest.mkdir(parents=True)
    dest.joinpath(zip_path.name).write_bytes(zip_path.read_bytes())
    import_incoming_file("dify-dump_dify_test.zip", tmp_path)
    delete_snapshot("dify", "2026-06-26_120000Z", tmp_path)
    assert not (tmp_path / "dify" / "2026-06-26_120000Z").exists()


def test_delete_incoming(tmp_path: Path) -> None:
    """Delete incoming zip without importing."""
    incoming = tmp_path / "incoming"
    incoming.mkdir(parents=True)
    (incoming / "dify-dump_dify_x.zip").write_bytes(b"fake")
    delete_incoming_file("dify-dump_dify_x.zip", tmp_path)
    assert not (incoming / "dify-dump_dify_x.zip").exists()


@pytest.mark.asyncio
async def test_save_upload_rejects_oversized_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Uploads larger than MINDMATE_EXPORT_DUMP_MAX_UPLOAD_BYTES are rejected."""
    monkeypatch.setenv("MINDMATE_EXPORT_RAW_DUMP_DIR", str(tmp_path))
    monkeypatch.setenv("MINDMATE_EXPORT_DUMP_MAX_UPLOAD_BYTES", "16")
    zip_path = _build_zip(tmp_path, "dify-dump_dify_big.zip")
    with zip_path.open("rb") as handle:
        upload = UploadFile(filename=zip_path.name, file=handle)
        with pytest.raises(ValueError, match="upload exceeds max size"):
            await save_uploaded_zip(zip_path.name, upload)
