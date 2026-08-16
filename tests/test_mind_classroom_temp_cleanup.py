"""Classroom working copies age out like temp_images when COS is the store."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from services.mind_classroom.temp_cleanup import cleanup_classroom_temp_files, list_classroom_temp_files


def _touch(path: Path, *, age_seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    stamped = time.time() - age_seconds
    os.utime(path, (stamped, stamped))


def test_list_classroom_temp_files_only_known_dirs(tmp_path: Path) -> None:
    """Ignore files outside transcripts/ and generations/."""
    keep = tmp_path / "other" / "skip.txt"
    keep.parent.mkdir()
    keep.write_text("no", encoding="utf-8")
    md_path = tmp_path / "transcripts" / "job.md"
    _touch(md_path, age_seconds=0)
    listed = list_classroom_temp_files(tmp_path)
    assert md_path in listed
    assert keep not in listed


@pytest.mark.asyncio
async def test_cleanup_skips_when_cos_off(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Local files are durable when COS is disabled."""
    md_path = tmp_path / "transcripts" / "job.md"
    _touch(md_path, age_seconds=200_000)
    monkeypatch.setattr("services.mind_classroom.temp_cleanup.cos_zhihui_enabled", lambda: False)
    monkeypatch.setattr("services.mind_classroom.temp_cleanup.classroom_local_root", lambda: tmp_path)
    deleted = await cleanup_classroom_temp_files(max_age_seconds=86_400)
    assert deleted == 0
    assert md_path.is_file()


@pytest.mark.asyncio
async def test_cleanup_deletes_old_when_cos_on(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Expired working copies go away; fresh ones stay for the current session."""
    old_md = tmp_path / "transcripts" / "old.md"
    new_md = tmp_path / "transcripts" / "new.md"
    old_png = tmp_path / "generations" / "old.png"
    _touch(old_md, age_seconds=200_000)
    _touch(new_md, age_seconds=60)
    _touch(old_png, age_seconds=200_000)
    monkeypatch.setattr("services.mind_classroom.temp_cleanup.cos_zhihui_enabled", lambda: True)
    monkeypatch.setattr("services.mind_classroom.temp_cleanup.classroom_local_root", lambda: tmp_path)
    deleted = await cleanup_classroom_temp_files(max_age_seconds=86_400)
    assert deleted == 2
    assert not old_md.exists()
    assert not old_png.exists()
    assert new_md.is_file()
