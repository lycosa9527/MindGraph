"""Seminar preview copies leave disk once COS holds the upload."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from services.features.mindmate_seminar.seminar_file_storage import (
    cleanup_seminar_disk_cache,
    release_seminar_preview_cache_sync,
)


def _touch(path: Path, *, age_seconds: float, body: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    stamped = time.time() - age_seconds
    os.utime(path, (stamped, stamped))


def test_cleanup_drops_cos_copies_and_scratch_keeps_the_only_local_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A local file is removed only when the bucket already has that key."""
    on_cos = tmp_path / "2026" / "10" / "on-cos.docx"
    only_local = tmp_path / "2026" / "10" / "only-local.docx"
    fresh = tmp_path / "2026" / "10" / "fresh.docx"
    preview = tmp_path / "2026" / "10" / "on-cos.docx.preview.pdf"
    preview_local_only = tmp_path / "2026" / "10" / "only-local.docx.preview.pdf"
    scratch = tmp_path / "2026" / "10" / "on-cos.docx.preview.pdf.tmp"
    work = tmp_path / "2026" / "10" / ".preview-work-on-cos"
    _touch(on_cos, age_seconds=200_000)
    _touch(only_local, age_seconds=200_000)
    _touch(fresh, age_seconds=60)
    _touch(preview, age_seconds=200_000)
    _touch(preview_local_only, age_seconds=200_000)
    _touch(scratch, age_seconds=200_000)
    work.mkdir(parents=True)
    (work / "source.docx").write_bytes(b"work")
    stamped = time.time() - 200_000
    os.utime(work, (stamped, stamped))

    monkeypatch.setattr(
        "services.features.mindmate_seminar.seminar_file_storage.cos_seminar_enabled",
        lambda: True,
    )

    def _has(logical_key: str) -> bool:
        return logical_key in {
            "2026/10/on-cos.docx",
            "2026/10/on-cos.docx.preview.pdf",
        }

    monkeypatch.setattr(
        "services.features.mindmate_seminar.seminar_file_storage._cos_has_logical_key",
        _has,
    )

    removed = cleanup_seminar_disk_cache(tmp_path, max_age_seconds=86_400)

    assert removed == 4
    assert not on_cos.exists()
    assert not preview.exists()
    assert not scratch.exists()
    assert not work.exists()
    assert only_local.is_file()
    assert preview_local_only.is_file()
    assert fresh.is_file()


def test_release_drops_locals_once_cos_has_source_and_preview(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """After a preview upload, scratch and the local copies are not left on disk."""
    source = tmp_path / "plan.docx"
    preview = tmp_path / "plan.docx.preview.pdf"
    scratch = preview.with_suffix(".pdf.tmp")
    work = tmp_path / ".preview-work-plan"
    source.write_bytes(b"docx")
    preview.write_bytes(b"%PDF")
    scratch.write_bytes(b"tmp")
    work.mkdir()
    (work / "source.docx").write_bytes(b"work")
    monkeypatch.setattr(
        "services.features.mindmate_seminar.seminar_file_storage.cos_seminar_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "services.features.mindmate_seminar.seminar_file_storage._cos_has_logical_key",
        lambda key: key in {"2026/10/plan.docx", "2026/10/plan.docx.preview.pdf"},
    )

    release_seminar_preview_cache_sync("2026/10/plan.docx", source, preview)

    assert not source.exists()
    assert not preview.exists()
    assert not scratch.exists()
    assert not work.exists()


def test_release_keeps_the_only_copy_when_cos_misses_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Scratch goes away even when the bucket does not have the file yet."""
    source = tmp_path / "plan.docx"
    preview = tmp_path / "plan.docx.preview.pdf"
    work = tmp_path / ".preview-work-plan"
    source.write_bytes(b"docx")
    preview.write_bytes(b"%PDF")
    work.mkdir()
    monkeypatch.setattr(
        "services.features.mindmate_seminar.seminar_file_storage.cos_seminar_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "services.features.mindmate_seminar.seminar_file_storage._cos_has_logical_key",
        lambda _key: False,
    )

    release_seminar_preview_cache_sync("2026/10/plan.docx", source, preview)

    assert source.is_file()
    assert preview.is_file()
    assert not work.exists()


def test_cleanup_keeps_uploads_when_cos_is_off(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """COS off means the disk file is the only copy."""
    upload = tmp_path / "2026" / "10" / "notes.docx"
    preview = tmp_path / "2026" / "10" / "notes.docx.preview.pdf"
    _touch(upload, age_seconds=200_000)
    _touch(preview, age_seconds=200_000)
    monkeypatch.setattr(
        "services.features.mindmate_seminar.seminar_file_storage.cos_seminar_enabled",
        lambda: False,
    )

    removed = cleanup_seminar_disk_cache(tmp_path, max_age_seconds=86_400)

    assert removed == 1
    assert upload.is_file()
    assert not preview.exists()
