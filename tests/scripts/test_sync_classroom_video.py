"""Classroom Wan 3.0 catalog locks every discovered mascot still."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from scripts.sync_classroom_video.catalog import (
    CLIPS,
    NEGATIVE,
    clip_by_id,
    clip_prompt,
    clip_stem,
    select_clips,
)
from scripts.sync_classroom_video.roles import RoleStill, discover_roles, identity_shell
from scripts.training_roles.wan_client import WAN3_VIDEO_PRIME, build_video_body


def _role(folder: str, slug: str, label: str, tmp_path: Path) -> RoleStill:
    still = tmp_path / f"{slug}.png"
    Image.new("RGB", (32, 32), (0, 255, 0)).save(still)
    return {
        "folder": folder,
        "slug": slug,
        "label": label,
        "lock": f"{label}锁定",
        "still": still,
    }


def test_discover_roles_uses_repo_raven_when_desktop_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Laptop fallback keeps the committed raven until the desktop still is present."""
    monkeypatch.setattr(
        "scripts.sync_classroom_video.roles.MASCOTS_DIR",
        tmp_path / "missing-mascots",
    )
    roles = discover_roles()
    raven = next(role for role in roles if role["folder"] == "raven-teacher-mascot")
    assert raven["label"] == "乌鸦"
    assert raven["still"].name == "fullbody-still-noptr-2.png"
    assert "scripts/cat_emoji/stills/raven/" in raven["still"].as_posix()
    assert "黄色领结" in raven["lock"]


def test_discover_roles_keeps_desktop_raven(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A Pictures/mascots raven still wins over the committed stand-in."""
    monkeypatch.setattr("scripts.sync_classroom_video.roles.MASCOTS_DIR", tmp_path)
    raven_dir = tmp_path / "raven-teacher-mascot"
    raven_dir.mkdir()
    Image.new("RGB", (256, 256), (0, 255, 0)).save(raven_dir / "fullbody-still-noptr-2.png")
    roles = discover_roles()
    raven = next(role for role in roles if role["folder"] == "raven-teacher-mascot")
    assert raven["still"] == raven_dir / "fullbody-still-noptr-2.png"


def test_discover_roles_reads_front_stills(tmp_path: Path) -> None:
    """Only folders with a front green-screen still are roles."""
    black = tmp_path / "black-cat-mascot"
    black.mkdir()
    Image.new("RGB", (256, 256), (0, 255, 0)).save(black / "fullbody-still-noptr-2.png")
    (tmp_path / "auth-login").mkdir()
    Image.new("RGB", (256, 256), (0, 255, 0)).save((tmp_path / "auth-login") / "fullbody-still-noptr-2.png")
    roles = discover_roles(tmp_path)
    assert [role["label"] for role in roles] == ["黑猫"]


def test_clip_prompt_locks_reference_stills(tmp_path: Path) -> None:
    """Prompts name every role and forbid opening on the stills."""
    roles = [
        _role("black-cat-mascot", "black", "黑猫", tmp_path),
        _role("schnauzer-professor", "mentor", "雪纳瑞导师", tmp_path),
    ]
    prompt = clip_prompt(clip_by_id("01"), roles)
    assert "图1是黑猫" in prompt
    assert "图2是雪纳瑞导师" in prompt
    assert "不是成片第一帧" in identity_shell(roles)
    assert "嘴始终闭合" in prompt
    assert clip_stem(clip_by_id("04a")) == "04a-wrong-answers-a"
    assert [clip["id"] for clip in select_clips("03,05")] == ["03", "05"]
    assert len(CLIPS) == 8


def test_build_video_body_is_silent_wan3() -> None:
    """Classroom jobs stay 16:9, silent, and reference-image based."""
    body = build_video_body(
        WAN3_VIDEO_PRIME,
        "课堂",
        negative=NEGATIVE,
        media=[{"type": "reference_image", "url": "data:image/jpeg;base64,xx"}],
        resolution="1080P",
        duration=12,
        ratio="16:9",
        audio=False,
        prompt_extend=False,
        watermark=False,
    )
    assert body["model"] == WAN3_VIDEO_PRIME
    assert body["input"]["media"][0]["type"] == "reference_image"
    assert body["parameters"]["audio"] is False
    assert body["parameters"]["duration"] == 12
