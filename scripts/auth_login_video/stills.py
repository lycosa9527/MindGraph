#!/usr/bin/env python3
"""Generate /auth still options.

Wan 3.0 is video-only. Stills: ``wan2.7-image-pro`` (1080P) or
``qwen-image-3.0`` (16:9 2K, ``2048*1152``).

  python -m scripts.auth_login_video.stills --engine qwen --force
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import time
from pathlib import Path
from typing import TypedDict

import requests
from PIL import Image

from scripts.auth_login_video.catalog import CAT_LOCK, NEGATIVE
from scripts.auth_login_video.paths import (
    BLACK_STILL,
    BLACK_STILL_SIDE,
    ORIGINAL_STILLS_DIR,
    STILL_OPTIONS_DIR,
    WORK_DIR,
)
from scripts.auth_login_video.plates import write_character_plate
from services.t2i.image_client import image_client
from services.t2i.wan_image_studio import download_image, poll_storyboard, submit_icon

STILL_MODEL = "wan2.7-image-pro"
QWEN_STILL_MODEL = "qwen-image-3.0"
STILL_SIZE = "1920*1080"
QWEN_STILL_SIZE = "2048*1152"
STILL_LAYOUT = (
    "横向16:9电影宽银幕静帧，3D电影质感，不是扁平插画。"
    "黑猫吉祥物和发光思维导图都在画面左侧约55%。"
    "右侧约45%是干净留白给登录卡片：不要主体、不要大光斑、不要可读文字。"
    "左到右80到120像素柔和羽化。不要字幕，不要水印，不要绿幕，不要UI截图。"
)


class StillOption(TypedDict):
    """One local-dev still candidate."""

    id: str
    prompt: str


OPTIONS: tuple[StillOption, ...] = (
    {
        "id": "a-holographic-academic",
        "prompt": (
            "风格A暗色全息学术风。深空蓝黑底#0A1628。"
            "左侧是略虚的3D教室：悬浮书本、漂浮知识节点、全息黑板微光，霓虹青#00E5FF点缀。"
            "黑猫坐在左中前景，围巾清晰。发光思维导图从教室空间里长出。"
            "右侧纯净深色#0A0E1A到#1A1F35，仅极淡网格。"
        ),
    },
    {
        "id": "b-warm-study",
        "prompt": (
            "风格B暖金粒子学习风。左侧温暖3D书桌：台灯、摊开的书、暖琥珀粒子从书页升起。"
            "黑猫坐在书旁。金色加青蓝的思维导图在灯下轻轻发光。"
            "右侧深棕#2D2420到#1A1512暖灰留白，右边缘略暗。"
        ),
    },
    {
        "id": "c-cyber-corridor",
        "prompt": (
            "风格C赛博学术长廊。左侧一条纵深极强的3D走廊，两侧发光书架和全息屏，"
            "知识节点沿走廊漂浮。靛蓝#1A1A2E加霓虹紫#7C4DFF。"
            "黑猫站在走廊近端左侧。右侧纯黑#0D0D1A，紫蓝暗角。"
        ),
    },
    {
        "id": "c-teal-hologram",
        "prompt": (
            "冷青实验室氛围，干净、少道具。黑猫三分之四侧面站在左中，"
            "一扇半透明思维导图立在猫身侧后，节点如水母般缓慢发光。"
            "地面有轻微反射。右侧几乎全黑，只留一点青边光。"
        ),
    },
    {
        "id": "d-lab-white",
        "prompt": (
            "风格D实验室白科技风。左侧明亮3D实验室：全息投影台、悬浮思维导图、淡蓝数据面板。"
            "主色白#F5F7FA加科技蓝#2196F3。黑猫站在投影台前。"
            "右侧浅灰白#F0F2F5留空，边界柔和，不要脏污。"
        ),
    },
    {
        "id": "e-minimal-stardust",
        "prompt": (
            "风格E极简暗色粒子星尘。整体#0A0A0F深黑。"
            "左侧少量青紫神经节点#00E5FF与#7C4DFF缓慢漂浮，隐约勾出思维导图轮廓。"
            "黑猫很小，坐在左下。粒子密度向右衰减到零。右侧纯黑，极简高级。"
        ),
    },
    {
        "id": "f-swoosh-flow",
        "prompt": (
            "风格F动态Swoosh流线。暗色底上，左侧有流畅的蓝色科技光线和波纹轨迹，"
            "像思维在流动。黑猫立在流线之间，周围有稀疏发光节点。"
            "Swoosh从左向右自然衰减。右侧同色系极暗留白。"
        ),
    },
    {
        "id": "af-holographic-swoosh",
        "prompt": (
            "推荐组合：风格A底层加风格F流线。"
            "左侧暗色全息教室，悬浮书本和全息黑板，Swoosh光线在暗层上流动，"
            "黑猫前景，思维导图节点从猫身侧扩散。"
            "右侧#111827纯深色留空，左缘120像素羽化衔接。"
        ),
    },
)


def option_prompt(option: StillOption) -> str:
    """Identity lock + empty-right layout + one mood."""
    return f"{CAT_LOCK}图1和图2只锁定同一只黑猫的脸、围巾和体型。{STILL_LAYOUT}{option['prompt']} 不要出现：{NEGATIVE}"


def _reference_plates() -> list[Path]:
    """Dark 16:9 plates so Wan does not lock onto green-screen stills."""
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    front = WORK_DIR / "still-ref-front.jpg"
    side = WORK_DIR / "still-ref-side.jpg"
    write_character_plate(BLACK_STILL, front)
    write_character_plate(BLACK_STILL_SIDE, side)
    return [front, side]


def _plate_data_url(path: Path) -> str:
    """Keep the 1920 plate; do not shrink the identity lock to 1024."""
    image = Image.open(path).convert("RGB")
    dest = WORK_DIR / f"qwen-ref-{path.name}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, format="JPEG", quality=92, optimize=True)
    payload = base64.b64encode(dest.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{payload}"


def _is_two_k(path: Path) -> bool:
    """True when the still is already the Qwen 16:9 2K size."""
    if not path.is_file():
        return False
    with Image.open(path) as image:
        return image.size == (2048, 1152)


async def generate_qwen_option(option: StillOption, ref_urls: list[str], force: bool) -> Path:
    """One qwen-image-3.0 2048x1152 still → original + still-options."""
    dest = STILL_OPTIONS_DIR / f"{option['id']}.jpg"
    master = ORIGINAL_STILLS_DIR / f"{option['id']}.jpg"
    if not force and _is_two_k(master):
        print(f"skip {option['id']} already-2k", flush=True)
        return master
    print(f"still {option['id']} model={QWEN_STILL_MODEL} size={QWEN_STILL_SIZE}", flush=True)
    url = await image_client.generate_image(
        option_prompt(option),
        model=QWEN_STILL_MODEL,
        size=QWEN_STILL_SIZE,
        prompt_extend=False,
        watermark=False,
        negative_prompt=NEGATIVE,
        reference_images=ref_urls,
    )
    work = WORK_DIR / f"{option['id']}-qwen.png"
    last_error: Exception | None = None
    for attempt in range(1, 5):
        try:
            download_image(url, work)
            last_error = None
            break
        except requests.RequestException as exc:
            last_error = exc
            print(f"download retry {attempt}: {type(exc).__name__}", flush=True)
            time.sleep(2 * attempt)
    if last_error is not None:
        raise RuntimeError(f"download failed for {option['id']}") from last_error
    STILL_OPTIONS_DIR.mkdir(parents=True, exist_ok=True)
    ORIGINAL_STILLS_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(work.read_bytes())
    master.write_bytes(work.read_bytes())
    print(f"saved {master} bytes={master.stat().st_size}", flush=True)
    return master


async def generate_qwen_options(chosen: list[StillOption], force: bool) -> None:
    """Generate the selected stills with Qwen Image 3.0."""
    refs = _reference_plates()
    ref_urls = [_plate_data_url(path) for path in refs]
    for option in chosen:
        await generate_qwen_option(option, ref_urls, force)


def generate_option(option: StillOption, refs: list[Path]) -> Path:
    """Write one candidate into Pictures/mascots/auth-login/still-options."""
    dest = STILL_OPTIONS_DIR / f"{option['id']}.jpg"
    if dest.is_file() and dest.stat().st_size > 10000:
        print(f"skip {dest.name}", flush=True)
        return dest
    print(f"still {option['id']} model={STILL_MODEL}", flush=True)
    task_id = submit_icon(
        option_prompt(option),
        refs,
        size=STILL_SIZE,
        model=STILL_MODEL,
    )
    urls = poll_storyboard(task_id)
    if not urls:
        raise RuntimeError(f"no still url for {option['id']}")
    work = WORK_DIR / f"{option['id']}.jpg"
    last_error: Exception | None = None
    for attempt in range(1, 5):
        try:
            download_image(urls[0], work)
            last_error = None
            break
        except requests.RequestException as exc:
            last_error = exc
            print(f"download retry {attempt}: {type(exc).__name__}", flush=True)
            time.sleep(2 * attempt)
    if last_error is not None:
        raise RuntimeError(f"download failed for {option['id']}") from last_error
    STILL_OPTIONS_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(work.read_bytes())
    print(f"saved {dest} bytes={dest.stat().st_size}", flush=True)
    return dest


def main() -> None:
    """CLI: generate still options for the user to pick."""
    parser = argparse.ArgumentParser(description="Generate /auth still options")
    parser.add_argument("--force", action="store_true", help="Regenerate existing options")
    parser.add_argument("--ids", help="Comma option ids, default all")
    parser.add_argument(
        "--engine",
        choices=("wan", "qwen"),
        default="wan",
        help="wan2.7-image-pro 1080P or qwen-image-3.0 2K",
    )
    args = parser.parse_args()
    chosen = list(OPTIONS)
    if args.ids:
        wanted = {item.strip() for item in args.ids.split(",") if item.strip()}
        chosen = [option for option in OPTIONS if option["id"] in wanted]
    if args.force:
        for option in chosen:
            dest = STILL_OPTIONS_DIR / f"{option['id']}.jpg"
            if dest.is_file():
                dest.unlink()
    if args.engine == "qwen":
        asyncio.run(generate_qwen_options(chosen, args.force))
    else:
        refs = _reference_plates()
        for option in chosen:
            generate_option(option, refs)
    print(f"options {STILL_OPTIONS_DIR}", flush=True)


if __name__ == "__main__":
    main()
