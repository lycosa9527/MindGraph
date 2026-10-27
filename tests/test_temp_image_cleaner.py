"""Local temp PNGs age out, including seminar canvas snapshots."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from services.utils.temp_image_cleaner import cleanup_temp_images


def _touch(path: Path, *, age_seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"png")
    stamped = time.time() - age_seconds
    os.utime(path, (stamped, stamped))


@pytest.mark.asyncio
async def test_cleanup_removes_old_dingtalk_and_diagram_pngs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Canvas snapshots use diagram_*.png and must not outlive the dingtalk cache."""
    old_ding = tmp_path / "dingtalk_abcd1234_1.png"
    old_diagram = tmp_path / ("diagram_" + ("ab" * 16) + ".png")
    fresh_diagram = tmp_path / ("diagram_" + ("cd" * 16) + ".png")
    other = tmp_path / "notes.txt"
    _touch(old_ding, age_seconds=200_000)
    _touch(old_diagram, age_seconds=200_000)
    _touch(fresh_diagram, age_seconds=60)
    other.write_text("keep", encoding="utf-8")
    monkeypatch.setattr("services.utils.temp_image_cleaner.temp_images_dir", lambda: tmp_path)

    deleted = await cleanup_temp_images(max_age_seconds=86_400)

    assert deleted == 2
    assert not old_ding.exists()
    assert not old_diagram.exists()
    assert fresh_diagram.is_file()
    assert other.is_file()
