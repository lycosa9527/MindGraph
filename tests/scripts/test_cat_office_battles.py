"""Office-battle catalog stays one zone per job."""

from __future__ import annotations

from PIL import Image

from scripts.cat_office_battles.catalog import (
    BATTLE_ZONES,
    MOTION_SHELL,
    SHELL,
    VIDEO_RESOLUTION,
    catalog_ids,
    opening_still_prompt,
    zone_by_id,
)
from scripts.cat_office_battles.export import center_crop_square, wechat_square
from scripts.cat_office_battles.paths import DESKTOP_DIR, zone_dir


def test_ten_unique_zones() -> None:
    """Ten separate storyboard jobs."""
    ids = catalog_ids()
    assert len(ids) == 10
    assert len(set(ids)) == 10
    assert ids[0] == "01-desk-stare"
    assert ids[-1] == "10-whiteboard-slam"
    assert BATTLE_ZONES[0]["n"] == 5


def test_zone_lookup_and_desktop_folder() -> None:
    """Look up by 01 or packed id and keep desktop output separate."""
    zone = zone_by_id("01")
    assert zone["slug"] == "desk-stare"
    assert zone_by_id("07-midnight-overtime")["name"] == "深夜加班·软绵绵互殴"
    assert zone_dir(zone["id"], zone["slug"]) == DESKTOP_DIR / "01-desk-stare"
    assert "永远臭脸" in SHELL
    assert "慢性子" in SHELL
    assert "永远臭脸" in SHELL
    assert "被压迫" not in SHELL
    assert "嘴可以张开" in SHELL
    assert "错拍才好笑" in MOTION_SHELL
    assert VIDEO_RESOLUTION == "1080P"
    assert "连续流畅" in MOTION_SHELL
    assert "不要气泡" in MOTION_SHELL
    assert "极简" in MOTION_SHELL
    assert "只有一只黑猫和一只白猫" in SHELL
    assert "道具最少" in MOTION_SHELL
    assert "三秒内让陌生人看懂" in MOTION_SHELL
    assert "全程闭嘴" not in MOTION_SHELL


def test_opening_still_keeps_first_two_sentences() -> None:
    """n=1 first frames must not stack the later gag beats into extra cats."""
    zone = zone_by_id("02")
    opening = opening_still_prompt(zone["prompt"])
    assert "大菱形" in opening
    assert "笔飞出去" not in opening
    assert opening.count("。") == 2


def test_battle_prompts_are_silent_mime() -> None:
    """No on-screen words. Mouths may move; bubbles and captions may not."""
    banned = ("气泡", "字幕", "「", "」", "V2", "V3", "Bug", "ESC")
    for zone in BATTLE_ZONES:
        for token in banned:
            assert token not in zone["prompt"], f"{zone['id']} still has {token}"


def test_wechat_emoji_is_center_cropped_1x1() -> None:
    """WeChat custom emoji is 240x240; crop the scene, do not letterbox."""
    scene = Image.new("RGB", (1920, 1080), (20, 80, 40))
    cropped = center_crop_square(scene)
    assert cropped.size == (1080, 1080)
    emoji = wechat_square(scene)
    assert emoji.size == (240, 240)
    assert emoji.mode == "RGB"
