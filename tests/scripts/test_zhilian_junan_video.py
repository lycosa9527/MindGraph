"""智联均安 Wan 3.0 catalog stays cinematic, silent, and text-free."""

from __future__ import annotations

from PIL import Image

from scripts.training_roles.wan_client import WAN3_VIDEO_PRIME, build_video_body
from scripts.zhilian_junan_video.catalog import (
    AGENT_NEGATIVE,
    AGENT_SCENES,
    AGENT_SECONDS,
    DEFAULT_SECONDS,
    INTRO_NEGATIVE,
    NEGATIVE,
    RATIO,
    RESOLUTION,
    SCENES,
    clip_prompt,
    clip_stem,
    environment_source,
    scene_by_id,
    select_scenes,
    uses_agent,
    uses_intro,
    uses_travel,
)
from scripts.zhilian_junan_video.intro import INTRO_SCENES, INTRO_SECONDS
from scripts.zhilian_junan_video.paths import AGENT_DIR, INTRO_DIR, TRAVEL_DIR, WORK_DIR
from scripts.zhilian_junan_video.travel import TRAVEL_SCENES
from scripts.zhilian_junan_video.plates import write_agent_plate

SHELL_FRAGMENT = "ARRI Alexa 65"


def test_scene_lookup_accepts_packed_id() -> None:
    """00 and 00-studio-bg resolve to the same empty-shot studio."""
    by_short = scene_by_id("00")
    by_packed = scene_by_id("00-studio-bg")
    assert by_short["slug"] == "studio-bg"
    assert by_packed["name"] == by_short["name"]
    assert clip_stem(by_short) == "00-studio-bg"
    assert len(SCENES) == 17
    assert not uses_agent(by_short)


def test_every_clip_is_short_widescreen_b_roll() -> None:
    """Promo plates stay 4s 16:9 so later subtitles and logos have a clean plate."""
    ids = [scene["id"] for scene in SCENES]
    assert ids[:5] == ["00", "01", "02", "03", "04"]
    assert "05a" in ids and "05b" in ids
    assert "09a" in ids and "t3" in ids
    for scene in SCENES:
        assert scene["seconds"] == DEFAULT_SECONDS
        prompt = clip_prompt(scene)
        assert SHELL_FRAGMENT in prompt
        assert "无文字" in prompt
        assert "不要出现" in prompt
        assert "赛博朋克" in NEGATIVE


def test_select_scenes_filters_by_comma_ids() -> None:
    """CLI --ids keeps catalog order for the requested plates only."""
    picked = select_scenes("t1,00,09b")
    assert [scene["id"] for scene in picked] == ["t1", "00", "09b"]


def test_agent_catalog_locks_the_yellow_dragon() -> None:
    """Dragon plates are a short 5s set and never ask Wan to paint letters."""
    assert [scene["id"] for scene in AGENT_SCENES] == ["a1", "a2", "a3", "a4"]
    assert [scene["id"] for scene in select_scenes(None, agent=True)] == ["a1", "a2", "a3", "a4"]
    recreate = scene_by_id("a1-recreate")
    assert uses_agent(recreate)
    assert recreate["seconds"] == AGENT_SECONDS
    prompt = clip_prompt(recreate)
    assert "图1和图2" in prompt
    assert "黄色小龙" in prompt
    assert "无文字" in prompt
    assert "豆包" in AGENT_NEGATIVE
    assert AGENT_DIR.name == "AI吉祥物"


def test_travel_catalog_changes_the_dragon_pose() -> None:
    """Each earlier environment gets a new gesture, never the standing book pose."""
    ids = [scene["id"] for scene in TRAVEL_SCENES]
    assert ids[0] == "d00"
    assert "d01" in ids and "dt1" in ids
    assert [scene["id"] for scene in select_scenes(None, travel=True)] == ids
    walk = scene_by_id("d01-campus-walk")
    assert uses_travel(walk)
    assert uses_agent(walk)
    prompt = clip_prompt(walk)
    assert "图3" in prompt
    assert "身体姿态必须和参考图不同" in prompt
    assert "小跑" in prompt
    assert environment_source(walk) == "01-campus-dawn.mp4"
    assert TRAVEL_DIR.name == "AI吉祥物-穿景"


def test_intro_catalog_is_spoken_qisi_lou() -> None:
    """Three 20s beats introduce 均安起思楼 with voice and no on-screen words."""
    ids = [scene["id"] for scene in INTRO_SCENES]
    assert ids == ["i1", "i2", "i3"]
    assert [scene["id"] for scene in select_scenes(None, intro=True)] == ids
    hello = scene_by_id("i1-teachers")
    assert uses_intro(hello)
    assert uses_agent(hello)
    assert hello["seconds"] == INTRO_SECONDS
    prompt = clip_prompt(hello)
    assert "均安起思楼" in prompt
    assert "虚拟教研伙伴" in prompt
    assert "语速偏快" in prompt
    assert "不要背景音乐" in prompt
    assert "无文字" in prompt
    assert "BGM" in INTRO_NEGATIVE
    assert environment_source(scene_by_id("i2-students")) == "02-digital-classroom.mp4"
    assert environment_source(scene_by_id("i3-together")) == "09c-junan-model.mp4"
    assert INTRO_DIR.name == "AI吉祥物-自我介绍"
    body = build_video_body(
        WAN3_VIDEO_PRIME,
        prompt,
        negative=INTRO_NEGATIVE,
        media=[{"type": "reference_image", "url": "data:image/jpeg;base64,xx"}],
        resolution=RESOLUTION,
        duration=INTRO_SECONDS,
        ratio=RATIO,
        audio=True,
    )
    assert body["parameters"]["audio"] is True
    assert body["parameters"]["duration"] == 20


def test_wan3_body_is_silent_t2v() -> None:
    """Empty shots stay text-to-video; dragon shots attach two reference stills."""
    scene = scene_by_id("03")
    body = build_video_body(
        WAN3_VIDEO_PRIME,
        clip_prompt(scene),
        negative=NEGATIVE,
        resolution=RESOLUTION,
        duration=scene["seconds"],
        ratio=RATIO,
        audio=False,
        prompt_extend=False,
        watermark=False,
    )
    assert body["model"] == WAN3_VIDEO_PRIME
    assert "media" not in body["input"]
    assert body["input"]["negative_prompt"] == NEGATIVE
    assert body["parameters"]["duration"] == DEFAULT_SECONDS
    assert body["parameters"]["ratio"] == "16:9"
    assert body["parameters"]["audio"] is False
    assert body["parameters"]["watermark"] is False
    assert WORK_DIR.name == ".work"
    agent = build_video_body(
        WAN3_VIDEO_PRIME,
        clip_prompt(scene_by_id("a1")),
        negative=AGENT_NEGATIVE,
        media=[{"type": "reference_image", "url": "data:image/jpeg;base64,xx"}],
        resolution=RESOLUTION,
        duration=AGENT_SECONDS,
        ratio=RATIO,
        audio=False,
    )
    assert agent["input"]["media"][0]["type"] == "reference_image"
    assert agent["parameters"]["duration"] == AGENT_SECONDS


def test_agent_plate_covers_corner_watermark(tmp_path) -> None:
    """Doubao marks in the lower-right corner must not reach Wan."""
    source = tmp_path / "raw.jpg"
    image = Image.new("RGB", (720, 720), (244, 242, 236))
    image.putpixel((700, 700), (10, 10, 10))
    image.save(source, format="JPEG")
    dest = tmp_path / "clean.jpg"
    write_agent_plate(source, dest)
    cleaned = Image.open(dest)
    pixel = cleaned.getpixel((700, 700))
    if not isinstance(pixel, tuple):
        raise AssertionError("plate must be RGB")
    assert pixel[0] > 200
