"""Tests for Document Summary temporary upload cleanup."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from services.knowledge.doc_summary_temp import (
    remove_job_dir,
    sweep_stale_doc_summary_temps,
    write_upload_temp,
)


def test_write_and_remove_job_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Upload temps land under doc_summary_tmp and are removed with the job dir."""
    monkeypatch.setenv("KNOWLEDGE_STORAGE_DIR", str(tmp_path))
    # Reload config cache is tricky; patch the root builder instead.
    monkeypatch.setattr(
        "services.knowledge.doc_summary_temp.doc_summary_tmp_root",
        lambda: tmp_path / "doc_summary_tmp",
    )
    job_dir, file_path = write_upload_temp(
        user_id=1,
        package_id=2,
        file_name="talk.mp3",
        content=b"audio-bytes",
    )
    assert file_path.is_file()
    assert file_path.read_bytes() == b"audio-bytes"
    remove_job_dir(job_dir)
    assert not Path(job_dir).exists()


def test_sweep_stale_temps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stale job directories older than the cutoff are removed."""
    root = tmp_path / "doc_summary_tmp"
    monkeypatch.setattr("services.knowledge.doc_summary_temp.doc_summary_tmp_root", lambda: root)
    job = root / "user_1" / "pkg_2" / "oldjob"
    job.mkdir(parents=True)
    (job / "file.pptx").write_bytes(b"x")
    old = time.time() - 7200
    # Force mtime into the past.
    Path(job).touch()
    os.utime(job, (old, old))
    removed = sweep_stale_doc_summary_temps(max_age_seconds=3600)
    assert removed == 1
    assert not job.exists()
