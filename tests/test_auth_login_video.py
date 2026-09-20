"""Unit tests for /auth login-hero catalog and Wan video body builder."""

from __future__ import annotations

from PIL import Image

from scripts.auth_login_video.catalog import (
    CONCEPTS,
    clip_duration,
    clip_prompt,
    clip_public_id,
    clip_stem,
    concept_by_id,
    desktop_original_name,
    desktop_reencode_name,
    hero_object_name,
    public_clip_ids,
)
from scripts.auth_login_video.paths import BLACK_STILL
from scripts.auth_login_video.plates import write_character_plate
from scripts.auth_login_video.ship_stills import (
    DEFAULT_STILL_ID,
    STILL_MAX_WIDTH,
    compress_still,
)
from scripts.auth_login_video.stills import OPTIONS, option_prompt
from scripts.training_roles.wan_client import (
    HAPPYHORSE_T2V,
    MODEL,
    WAN3_VIDEO_PRIME,
    build_video_body,
)
from services.auth.login_hero_clips import LOGIN_HERO_CLIPS, parse_hero_clip_id


def test_concept_lookup_accepts_packed_id() -> None:
    """01 and 01-awaken-cosmos resolve to the same storyboard."""
    by_short = concept_by_id("01")
    by_packed = concept_by_id("01-awaken-cosmos")
    assert by_short["slug"] == "awaken-cosmos"
    assert by_packed["name"] == by_short["name"]
    assert len(CONCEPTS) == 4


def test_clip_duration_caps_happyhorse() -> None:
    """HappyHorse stays at 15s; Wan 3.0 keeps the longer storyboard."""
    cosmos = concept_by_id("01")
    assert clip_duration(cosmos, HAPPYHORSE_T2V) == 15
    assert clip_duration(cosmos, WAN3_VIDEO_PRIME) == 18
    assert clip_stem(cosmos, WAN3_VIDEO_PRIME) == "01-awaken-cosmos-wan3"
    assert desktop_original_name(cosmos) == "01-awaken-cosmos-original.mp4"
    assert desktop_reencode_name(cosmos) == "01-awaken-cosmos-reencode.mp4"
    assert clip_public_id(cosmos) == "01-awaken-cosmos"
    assert hero_object_name(cosmos) == "01-awaken-cosmos.mp4"
    assert public_clip_ids() == LOGIN_HERO_CLIPS
    assert parse_hero_clip_id("01.mp4") == "01-awaken-cosmos"


def test_wan3_prompt_locks_reference_stills() -> None:
    """Wan 3.0 prompt must lock Image 1/2 without opening on the still."""
    prompt = clip_prompt(concept_by_id("01"), WAN3_VIDEO_PRIME)
    assert "图1和图2" in prompt
    assert "不是成片第一帧" in prompt
    assert "16:9" in prompt
    assert "绿幕" in prompt
    assert "红白格子" in prompt


def test_build_video_body_happyhorse_omits_wan_only_fields() -> None:
    """HappyHorse T2V has no negative, audio, or prompt_extend."""
    body = build_video_body(
        HAPPYHORSE_T2V,
        "一只黑猫",
        negative="绿幕",
        resolution="1080P",
        duration=15,
        ratio="16:9",
        audio=True,
        prompt_extend=False,
        watermark=False,
    )
    assert body["model"] == HAPPYHORSE_T2V
    assert "negative_prompt" not in body["input"]
    assert "media" not in body["input"]
    assert body["parameters"]["resolution"] == "1080P"
    assert "audio" not in body["parameters"]
    assert "prompt_extend" not in body["parameters"]
    assert body["parameters"]["watermark"] is False


def test_build_video_body_i2v_keeps_course_builder_defaults() -> None:
    """Existing Wan 2.7 I2V payload still uses first_frame and no ratio."""
    body = build_video_body(
        MODEL,
        "课堂开场",
        negative="教室",
        media=[{"type": "first_frame", "url": "data:image/jpeg;base64,yy"}],
        resolution="720P",
        duration=5,
    )
    assert body["model"] == MODEL
    assert body["input"]["media"][0]["type"] == "first_frame"
    assert body["parameters"]["duration"] == 5
    assert "ratio" not in body["parameters"]
    assert body["parameters"]["prompt_extend"] is False


def test_character_plate_is_dark_not_green(tmp_path) -> None:
    """Reference stills must be keyed onto a dark 16:9 plate."""
    dest = tmp_path / "plate.jpg"
    write_character_plate(BLACK_STILL, dest)
    image = Image.open(dest)
    assert image.size == (1920, 1080)
    corner = image.getpixel((10, 10))
    if not isinstance(corner, tuple):
        raise AssertionError("plate must be RGB")
    assert corner[1] < 40


def test_still_options_leave_room_on_the_right() -> None:
    """Local still candidates are independent of the four video storyboards."""
    assert len(OPTIONS) == 5
    prompt = option_prompt(OPTIONS[0])
    assert "右侧" in prompt
    assert "16:9" in prompt
    assert "红白格子" in prompt
    assert OPTIONS[0]["id"] == "l-reading-book"
    assert OPTIONS[-1]["id"] == "p-teaching-board"
    assert "看书" in prompt
    assert DEFAULT_STILL_ID in {option["id"] for option in OPTIONS}


def test_compress_still_writes_capped_webp(tmp_path) -> None:
    """Shipped /auth poster is a 1080p-capped WebP, not the 2K source."""
    source = tmp_path / "source.jpg"
    pixels = bytes((index * 37) % 256 for index in range(2048 * 1152 * 3))
    Image.frombytes("RGB", (2048, 1152), pixels).save(source, format="JPEG", quality=95)
    dest = tmp_path / "login-hero.webp"
    compress_still(source, dest)
    shipped = Image.open(dest)
    assert shipped.format == "WEBP"
    assert shipped.size == (STILL_MAX_WIDTH, 1080)
    assert dest.stat().st_size < source.stat().st_size
