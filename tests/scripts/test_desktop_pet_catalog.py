"""Desktop-pet scenes stay on Wan 3.0, fifty per mascot, plus ten pair clips."""

from __future__ import annotations

from scripts.desktop_pet.actions import ACTIONS_BY_SLUG, actions_for
from scripts.desktop_pet.actions.pack import clip_id
from scripts.desktop_pet.catalog import SCENES_PER_MASCOT, VIDEO_MODEL
from scripts.desktop_pet.interactions import PAIRS, pair_prompt
from scripts.desktop_pet.mascots import MASCOTS, clip_prompt, mascot_by_slug
from scripts.training_roles.wan_client import WAN3_VIDEO, WAN3_VIDEO_PRIME


def test_each_mascot_has_fifty_distinct_scenes() -> None:
    """Every character has a full set of readable scenes, not a shared nod list."""
    assert [mascot["slug"] for mascot in MASCOTS] == ["black", "white", "siamese", "raven", "schnauzer"]
    for slug in ACTIONS_BY_SLUG:
        actions = actions_for(slug)
        assert len(actions) == SCENES_PER_MASCOT
        assert len({clip_id(action) for action in actions}) == SCENES_PER_MASCOT


def test_video_model_is_wan3_not_prime() -> None:
    """Review clips call wan3.0-video, never the prime snapshot."""
    assert VIDEO_MODEL == WAN3_VIDEO
    assert VIDEO_MODEL != WAN3_VIDEO_PRIME
    assert "prime" not in VIDEO_MODEL


def test_black_arcade_is_a_complete_scene_and_costume_replaces_the_scarf() -> None:
    """The black cat's first scene is the arcade, and a named outfit drops the scarf."""
    black = mascot_by_slug("black")
    arcade = actions_for("black")[0]
    prompt = clip_prompt(black, arcade["prompt"], arcade.get("costume", ""))
    assert "街机" in prompt
    assert "游戏卫衣" in prompt
    assert "红白格子围巾" not in prompt
    assert "电子游戏" in clip_prompt(black, "站着。")
    siamese = mascot_by_slug("siamese")
    assert "深海军蓝" in siamese["default_outfit"]
    assert "浅薄荷色细项圈" not in siamese["default_outfit"]
    assert "深海军蓝" in clip_prompt(siamese, "站着。")
    everyday = clip_prompt(siamese, "站着。")
    assert "眉毛放松" in everyday
    assert "看起来高兴" in everyday
    assert "不要放大" in everyday
    assert "眉心" not in everyday
    assert "不要皱眉" in everyday
    check = clip_prompt(siamese, actions_for("siamese")[0]["prompt"])
    assert "高兴地点头" in check
    assert "认真" not in check


def test_ten_pair_scenes_name_both_mascots() -> None:
    """Interaction clips keep two characters and a green field."""
    assert len(PAIRS) == 10
    text = pair_prompt(PAIRS[0])
    assert "黑猫" in text
    assert "白猫" in text
    assert "#00FF00" in text
