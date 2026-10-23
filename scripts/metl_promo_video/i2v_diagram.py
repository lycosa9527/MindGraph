#!/usr/bin/env python3
"""Animate exported diagram PNGs with I2V (first frame locked, subtle motion only)."""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg

from scripts.metl_promo_video.specs import PROMO_DIAGRAMS
from scripts.training_roles.env import dashscope_api_key
from scripts.training_roles.wan_client import (
    DEFAULT_POLL_SECONDS,
    download_mp4,
    poll_video_url,
    submit_i2v,
)

DEFAULT_PNG_DIR = Path("/mnt/c/Users/roywa/Desktop/迈特宣传片/02-product/01-metl-reveal-hybrid/diagrams")
DEFAULT_OUT = Path("/mnt/c/Users/roywa/Desktop/迈特宣传片/02-product/01-metl-reveal-v2/diagram-i2v")
TASKS_NAME = "tasks-i2v.json"
I2V_SECONDS = 5
PROMPT = (
    "Premium cinematic product film, 16:9. The first frame is a locked MindGraph diagram. "
    "Every node, connector, and Chinese label stays exactly as in the first frame — "
    "same layout, same spelling, same font size. "
    "Only subtle motion: gentle slow push-in, soft glass UI glow, faint light sweep. "
    "No morphing shapes, no new text, no redraw, no blur on letters."
)
NEGATIVE = (
    "garbled text, wrong characters, layout change, morphing nodes, new nodes, "
    "missing text, blur, cartoon, hand, watermark, 乱码，错别字，换布局"
)


def png_data_url(path: Path) -> str:
    """PNG as data URL for Wan first_frame."""
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{payload}"


def load_tasks(path: Path) -> dict[str, str]:
    """Saved task ids keyed by slug."""
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if k and v}


def save_tasks(path: Path, tasks: dict[str, str]) -> None:
    """Write task ids."""
    path.write_text(json.dumps(tasks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ready_mp4(path: Path) -> bool:
    """True when clip looks downloaded."""
    return path.is_file() and path.stat().st_size > 10000


def trim_clip(source: Path, dest: Path, seconds: float) -> None:
    """Shorten I2V clip for montage."""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            "-t",
            f"{seconds:.3f}",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(dest),
        ],
        check=True,
    )


def one_slug(
    slug: str,
    png_dir: Path,
    out_dir: Path,
    tasks: dict[str, str],
    force: bool,
    trim_seconds: float,
) -> None:
    """Submit or download one diagram I2V clip."""
    png = png_dir / f"{slug}.png"
    if not png.is_file():
        print(f"missing {png.name}, skip", flush=True)
        return
    raw_mp4 = out_dir / f"{slug}-raw.mp4"
    short_mp4 = out_dir / f"{slug}.mp4"
    if ready_mp4(short_mp4) and not force:
        print(f"skip {short_mp4.name}", flush=True)
        return
    api_key = dashscope_api_key()
    if not ready_mp4(raw_mp4) or force:
        if slug not in tasks or force:
            tasks[slug] = submit_i2v(
                api_key,
                png_data_url(png),
                PROMPT,
                NEGATIVE,
                slug,
                resolution="1080P",
                duration=I2V_SECONDS,
            )
            save_tasks(out_dir / TASKS_NAME, tasks)
        url = poll_video_url(
            api_key,
            tasks[slug],
            slug,
            timeout_seconds=DEFAULT_POLL_SECONDS,
        )
        download_mp4(url, raw_mp4)
    trim_clip(raw_mp4, short_mp4, trim_seconds)
    print(f"ready {short_mp4.name}", flush=True)


def main() -> None:
    """CLI: animate all exported PNGs that exist."""
    parser = argparse.ArgumentParser(description="I2V subtle motion on diagram PNGs")
    parser.add_argument("--png-dir", type=Path, default=DEFAULT_PNG_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--slug", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--trim", type=float, default=1.0)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks(args.out / TASKS_NAME)
    slugs = [args.slug] if args.slug else [row["slug"] for row in PROMO_DIAGRAMS]
    for slug in slugs:
        if slug and slug not in {row["slug"] for row in PROMO_DIAGRAMS}:
            raise SystemExit(f"unknown slug {slug}")
        one_slug(slug, args.png_dir, args.out, tasks, args.force, args.trim)


if __name__ == "__main__":
    main()
