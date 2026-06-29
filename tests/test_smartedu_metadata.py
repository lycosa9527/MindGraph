"""Tests for SmartEdu metadata extraction."""

from __future__ import annotations

import json
from pathlib import Path

from file_reader.smartedu.metadata import extract_assets_from_detail

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "doc-extract" / "smartedu" / "class_activity_b45c766e.json"


def test_extract_four_assets_from_fixture() -> None:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assets = extract_assets_from_detail(data)
    assert len(assets) == 4
    aliases = {asset.alias for asset in assets}
    assert "视频课程" in aliases
    assert "课件" in aliases
    assert "教学设计" in aliases
    assert "学习任务单" in aliases
    video = next(asset for asset in assets if asset.resource_type == "micro_lesson_video")
    assert video.format == "mp4"
    assert video.download_url.endswith(".m3u8")
