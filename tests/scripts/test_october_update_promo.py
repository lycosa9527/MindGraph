"""October promo stays closed-mouth, with foley on the clip and one instrumental bed."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from scripts.october_update_promo.board import board_mask, crop_at
from scripts.october_update_promo.catalog import (
    BGM_PROMPT,
    CLIPS,
    NEGATIVE,
    clip_prompt,
    clip_stem,
    select_clips,
    total_seconds,
)
from scripts.october_update_promo.music import FUN_MUSIC, build_music_body
from scripts.october_update_promo.paths import DESKTOP_DIR, screenshot_for
from scripts.sync_classroom_video.roles import RoleStill
from scripts.training_roles.wan_client import WAN3_VIDEO_PRIME, build_video_body


def _role(slug: str, label: str, tmp_path: Path) -> RoleStill:
    still = tmp_path / f"{slug}.png"
    Image.new("RGB", (32, 32), (0, 255, 0)).save(still)
    return {
        "folder": slug,
        "slug": slug,
        "label": label,
        "lock": f"{label}锁定",
        "still": still,
    }


def test_promo_is_seven_silent_beats() -> None:
    """Durations match the 145-second cut, and mouths stay shut."""
    assert [clip["id"] for clip in CLIPS] == ["01", "02", "03", "04", "05", "06", "07"]
    assert [clip["seconds"] for clip in CLIPS] == [22, 22, 22, 22, 22, 20, 15]
    assert total_seconds() == 145
    assert [clip["id"] for clip in select_clips("02,07")] == ["02", "07"]
    assert clip_stem(CLIPS[0]) == "01-new-canvas"
    assert DESKTOP_DIR.name == "v3"
    assert screenshot_for("01").name == "01.png"
    assert "各位老师" in CLIPS[0]["speech"]
    for clip in CLIPS:
        assert "嘴闭合" in clip["prompt"]
        assert clip["link"]
        assert clip["sfx"]
        assert clip["overlay"]
        assert clip["speech"]
        assert len(clip["crops"]) >= 2
        for name in ("导师", "白猫", "暹罗猫", "乌鸦", "黑猫"):
            assert name in clip["prompt"]
        for left, top, width, height in clip["crops"]:
            assert 0 <= left <= 1 and 0 <= top <= 1
            assert width > 0.2 and height > 0.2
            assert left + width <= 1.001
            assert top + height <= 1.001
        assert "导图发光" not in clip["prompt"]
        assert "脉冲光" not in clip["prompt"]
        assert "字幕条" not in clip["prompt"]


def test_screenshot_pan_stays_on_the_green_board() -> None:
    """The move is a crop of the real screenshot, and only the board is replaced."""
    mid = crop_at(((0.0, 0.0, 1.0, 1.0), (0.2, 0.2, 0.6, 0.6)), 0.5)
    assert mid == (0.1, 0.1, 0.8, 0.8)
    frame = np.zeros((180, 320, 3), dtype=np.uint8)
    frame[:, :] = (190, 180, 170)
    frame[30:110, 70:250] = (70, 160, 100)
    frame[150, 20] = (40, 200, 40)
    mask = board_mask(frame)
    assert bool(mask[60, 150])
    assert not bool(mask[10, 10])
    assert not bool(mask[150, 20])


def test_prompt_asks_for_foley_not_speech(tmp_path: Path) -> None:
    """Wan hears objects, not voices, and the bed is instrumental."""
    roles = [_role("black", "黑猫", tmp_path)]
    prompt = clip_prompt(CLIPS[0], roles)
    assert "图1是黑猫" in prompt
    assert "首尾相接" in prompt
    assert "干净纯绿" in prompt
    assert "同一位置" in prompt
    assert "镜头可以推近" in prompt
    assert "不要人声" in prompt
    assert "紧接上一段" in clip_prompt(CLIPS[1], roles)
    assert "开口说话" in NEGATIVE
    assert "vocals" in NEGATIVE
    body = build_music_body()
    assert body["model"] == FUN_MUSIC
    assert body["input"]["is_instrumental"] is True
    assert "No vocals" in BGM_PROMPT
    assert len(BGM_PROMPT) <= 2000
    video = build_video_body(
        WAN3_VIDEO_PRIME,
        prompt,
        negative=NEGATIVE,
        media=[{"type": "reference_image", "url": "data:image/jpeg;base64,xx"}],
        resolution="1080P",
        duration=22,
        ratio="16:9",
        audio=True,
    )
    assert video["parameters"]["audio"] is True
    assert video["parameters"]["duration"] == 22
