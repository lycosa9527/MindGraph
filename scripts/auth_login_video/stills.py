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
    "主色是珍珠白、丁香白和科技紫，教育场景，科幻干净。"
    "黑猫吉祥物和紫色全息思维导图都在画面左侧约55%。"
    "右侧约45%是浅丁香白#F4F0FC到#EEE8F8干净留白给登录卡片："
    "不要主体、不要大光斑、不要可读文字。"
    "左到右80到120像素柔和羽化。不要字幕，不要水印，不要绿幕，不要UI截图。"
)


class StillOption(TypedDict):
    """One local-dev still candidate."""

    id: str
    prompt: str


OPTIONS: tuple[StillOption, ...] = (
    {
        "id": "l-reading-book",
        "prompt": (
            "动作：黑猫坐在白色课桌左侧，身体微侧，两只短爪捧着一本摊开的厚书，"
            "低头认真看书，头稍低，不是正面呆站。书页没有可读文字，只有淡紫色块图。"
            "身旁漂浮一圈紫色全息思维导图。丁香白教室，右侧干净留空。"
        ),
    },
    {
        "id": "m-drawing-map",
        "prompt": (
            "动作：黑猫侧身站在全息白板前，右爪举起一支细光笔，正在画思维导图节点，"
            "身体前倾，像在认真作图，不是双手垂下呆站。白板上是无文字的紫白节点连线。"
            "珍珠白教研室。右侧浅丁香白留空。"
        ),
    },
    {
        "id": "n-pointing-node",
        "prompt": (
            "动作：黑猫坐在台阶上，身体转向右前方的悬浮导图，一只爪子指向发光节点，"
            "头跟着看过去，像在讲解，不是面对镜头摆拍。图书馆紫白书架在身后虚化。"
            "右侧浅紫白雾化留空。"
        ),
    },
    {
        "id": "o-writing-tablet",
        "prompt": (
            "动作：黑猫趴在白色圆桌上，前爪按着一块发光平板，正在写画示意图，"
            "尾巴自然垂下，专注低头，不是站立正面。桌上有合上的书和淡紫粒子。"
            "霜白工作室。右侧纯净霜白留空。"
        ),
    },
    {
        "id": "p-teaching-board",
        "prompt": (
            "动作：黑猫侧立在紫色全息黑板旁，一只爪子按着板面，另一只爪子比划讲解，"
            "头转向黑板，像小老师上课，不是双手空垂正面站。黑板只有抽象节点没有文字。"
            "白色校园中庭。右侧浅白紫留空。"
        ),
    },
)


def option_prompt(option: StillOption) -> str:
    """Identity lock + empty-right layout + one action pose."""
    pose = "图1和图2只锁定同一只黑猫的脸、围巾和体型，允许坐、侧身、举手、看书、画画。"
    return f"{CAT_LOCK}{pose}{STILL_LAYOUT}{option['prompt']} 不要出现：{NEGATIVE}"


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
