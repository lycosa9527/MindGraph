"""Seminar preview copies leave disk once COS holds the upload."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from services.features.mindmate_collab.seminar_file_storage import cleanup_seminar_disk_cache


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
    scratch = tmp_path / "2026" / "10" / "on-cos.docx.preview.pdf.tmp"
    work = tmp_path / "2026" / "10" / ".preview-work-on-cos"
    _touch(on_cos, age_seconds=200_000)
    _touch(only_local, age_seconds=200_000)
    _touch(fresh, age_seconds=60)
    _touch(preview, age_seconds=200_000)
    _touch(scratch, age_seconds=200_000)
    work.mkdir(parents=True)
    (work / "source.docx").write_bytes(b"work")
    stamped = time.time() - 200_000
    os.utime(work, (stamped, stamped))

    monkeypatch.setattr(
        "services.features.mindmate_collab.seminar_file_storage.cos_seminar_enabled",
        lambda: True,
    )

    def _has(logical_key: str) -> bool:
        return logical_key.endswith("on-cos.docx")

    monkeypatch.setattr(
        "services.features.mindmate_collab.seminar_file_storage._cos_has_logical_key",
        _has,
    )

    removed = cleanup_seminar_disk_cache(tmp_path, max_age_seconds=86_400)

    assert removed == 4
    assert not on_cos.exists()
    assert not preview.exists()
    assert not scratch.exists()
    assert not work.exists()
    assert only_local.is_file()
    assert fresh.is_file()


def test_cleanup_keeps_uploads_when_cos_is_off(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """COS off means the disk file is the only copy."""
    upload = tmp_path / "2026" / "10" / "notes.docx"
    preview = tmp_path / "2026" / "10" / "notes.docx.preview.pdf"
    _touch(upload, age_seconds=200_000)
    _touch(preview, age_seconds=200_000)
    monkeypatch.setattr(
        "services.features.mindmate_collab.seminar_file_storage.cos_seminar_enabled",
        lambda: False,
    )

    removed = cleanup_seminar_disk_cache(tmp_path, max_age_seconds=86_400)

    assert removed == 1
    assert upload.is_file()
    assert not preview.exists()
