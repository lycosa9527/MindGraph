#!/usr/bin/env python3
"""Composite correct Qwen, Doubao, Zhipu marks onto v2 motion tail (keep Wan look)."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

import imageio_ffmpeg

from services.infrastructure.utils.browser import BrowserContextManager

V2_DIR = Path("/mnt/c/Users/roywa/Desktop/迈特宣传片/02-product/01-metl-reveal-v2")
SOURCE = V2_DIR / "motion-before-logo-fix.mp4"
OUT = V2_DIR / "motion.mp4"
PATCH = V2_DIR / "logos" / "model-strip-patch.png"
ASSET = Path(__file__).resolve().parent / "assets" / "model_strip_patch.html"
WORK = V2_DIR / ".logo-fix"
HEAD_END = 10.0
TAIL_SECONDS = 5.0


def ffmpeg() -> str:
    """Bundled ffmpeg."""
    return imageio_ffmpeg.get_ffmpeg_exe()


async def render_patch() -> None:
    """1920×1080 transparent overlay aligned to v2 model cards."""
    PATCH.parent.mkdir(parents=True, exist_ok=True)
    url = ASSET.as_uri()
    async with BrowserContextManager() as context:
        page = await context.new_page()
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.goto(url, wait_until="networkidle")
        await page.screenshot(path=str(PATCH), omit_background=True)
    print(f"patch {PATCH.name} {PATCH.stat().st_size}", flush=True)


def cut_head(source: Path, dest: Path, seconds: float) -> None:
    """First N seconds, stream copy when possible."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg(),
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            "-t",
            f"{seconds:.3f}",
            "-c:v",
            "copy",
            "-an",
            str(dest),
        ],
        check=True,
    )


def build_tail(source: Path, patch: Path, dest: Path, start: float, duration: float) -> None:
    """Last segment with PNG overlay."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg(),
            "-y",
            "-v",
            "error",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(source),
            "-loop",
            "1",
            "-i",
            str(patch),
            "-t",
            f"{duration:.3f}",
            "-filter_complex",
            "[1:v]scale=1920:1080:flags=lanczos[p];[0:v][p]overlay=0:0:format=auto,format=yuv420p[v]",
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-crf",
            "17",
            "-preset",
            "fast",
            "-an",
            str(dest),
        ],
        check=True,
    )


def concat_two(first: Path, second: Path, dest: Path) -> None:
    """Join head and patched tail."""
    listing = WORK / "concat-composite.txt"
    listing.write_text(
        "\n".join(f"file '{p}'" for p in (first, second)) + "\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            ffmpeg(),
            "-y",
            "-v",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c",
            "copy",
            str(dest),
        ],
        check=True,
    )


def main() -> None:
    """Restore v2 reference plate with fixed provider logos on the model strip."""
    if not SOURCE.is_file():
        raise SystemExit(f"missing backup {SOURCE}")
    WORK.mkdir(parents=True, exist_ok=True)
    asyncio.run(render_patch())
    head = WORK / "head-copy.mp4"
    tail = WORK / "tail-patched.mp4"
    cut_head(SOURCE, head, HEAD_END)
    build_tail(SOURCE, PATCH, tail, HEAD_END, TAIL_SECONDS)
    staged = V2_DIR / "motion-logo-fixed.mp4"
    concat_two(head, tail, staged)
    shutil.copy2(staged, OUT)
    print(f"done {OUT} (from {SOURCE.name})", flush=True)


if __name__ == "__main__":
    main()
