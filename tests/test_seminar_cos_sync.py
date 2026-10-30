"""Seminar disk copies are pushed to COS, including chat chips and ended rooms."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.features.mindmate_seminar import seminar_cos_sync
from services.features.mindmate_seminar.seminar_cos_sync import (
    mirror_seminar_disk_copy,
    sync_seminar_files_to_cos,
)


def test_mirror_uploads_the_file_and_its_preview(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A disk-only seminar file and its Office preview both go to COS."""
    disk = tmp_path / "notes.docx"
    disk.write_bytes(b"doc")
    preview = tmp_path / "notes.docx.preview.pdf"
    preview.write_bytes(b"pdf")
    seen: list[str] = []

    def _source(_storage_key: str, path: Path, *, content_type: str = "") -> bool:
        seen.append(f"file:{content_type}:{path.name}")
        return True

    def _preview(_storage_key: str, path: Path) -> bool:
        seen.append(f"preview:{path.name}")
        return True

    monkeypatch.setattr(
        "services.features.mindmate_seminar.seminar_cos_sync.seminar_disk_path",
        lambda _key: disk,
    )
    monkeypatch.setattr(
        "services.features.mindmate_seminar.seminar_cos_sync.mirror_local_seminar_file_sync",
        _source,
    )
    monkeypatch.setattr(
        "services.features.mindmate_seminar.seminar_cos_sync.mirror_cached_preview_pdf_sync",
        _preview,
    )

    assert mirror_seminar_disk_copy("2026/10/ab_notes.docx", "application/octet-stream") == 2
    assert seen == ["file:application/octet-stream:notes.docx", "preview:notes.docx.preview.pdf"]


def test_mirror_keeps_the_source_when_the_preview_upload_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed preview put does not undo the source upload."""
    disk = tmp_path / "notes.docx"
    disk.write_bytes(b"doc")
    preview = tmp_path / "notes.docx.preview.pdf"
    preview.write_bytes(b"pdf")
    monkeypatch.setattr(
        "services.features.mindmate_seminar.seminar_cos_sync.seminar_disk_path",
        lambda _key: disk,
    )
    monkeypatch.setattr(
        "services.features.mindmate_seminar.seminar_cos_sync.mirror_local_seminar_file_sync",
        lambda *_args, **_kwargs: True,
    )

    def _preview(_storage_key: str, _path: Path) -> bool:
        raise ValueError("upload_failed")

    monkeypatch.setattr(
        "services.features.mindmate_seminar.seminar_cos_sync.mirror_cached_preview_pdf_sync",
        _preview,
    )

    assert mirror_seminar_disk_copy("2026/10/ab_notes.docx", "application/octet-stream") == 1


@pytest.mark.asyncio
async def test_sync_skips_when_cos_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Local-only deployments do not open the database for a COS pass."""
    monkeypatch.setattr(
        "services.features.mindmate_seminar.seminar_cos_sync.cos_seminar_enabled",
        lambda: False,
    )

    assert await sync_seminar_files_to_cos() == 0


def test_sync_walks_every_file_row() -> None:
    """Chat chips and ended seminars are included. Only listed folder rows would miss them."""
    source = Path(seminar_cos_sync.__file__).read_text(encoding="utf-8")
    walker = source.split("async def sync_seminar_files_to_cos", 1)[1]
    assert "listed" not in walker
    assert "ended_at" not in walker
