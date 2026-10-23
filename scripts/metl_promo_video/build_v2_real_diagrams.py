#!/usr/bin/env python3
"""Keep Wan v2 intro/outro; replace gibberish diagram beats with real diagram I2V montage."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.metl_promo_video.ffmpeg_bin import ffmpeg_exe as ffmpeg

V2 = Path("/mnt/c/Users/roywa/Desktop/迈特宣传片/02-product/01-metl-reveal-v2/motion.mp4")
OUT = Path("/mnt/c/Users/roywa/Desktop/迈特宣传片/02-product/01-metl-reveal-v2/motion-real-diagrams.mp4")
WORK = Path("/mnt/c/Users/roywa/Desktop/迈特宣传片/02-product/01-metl-reveal-v2/.real-diagrams-work")
I2V_DIR = Path("/mnt/c/Users/roywa/Desktop/迈特宣传片/02-product/01-metl-reveal-v2/diagram-i2v")
MANIFEST = Path("/mnt/c/Users/roywa/Desktop/迈特宣传片/02-product/01-metl-reveal-hybrid/diagrams/manifest.json")
PNG_DIR = Path("/mnt/c/Users/roywa/Desktop/迈特宣传片/02-product/01-metl-reveal-hybrid/diagrams")
INTRO_END = 6.0
OUTRO_START = 10.0
SLIDE_SECONDS = 1.0


def cut_v2(source: Path, dest: Path, start: float, end: float) -> None:
    """Extract a segment from the v2 Wan plate."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg(),
            "-y",
            "-v",
            "error",
            "-ss",
            f"{start:.3f}",
            "-to",
            f"{end:.3f}",
            "-i",
            str(source),
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


def ordered_pngs() -> list[Path]:
    """PNG stills in manifest order."""
    if MANIFEST.is_file():
        raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            paths: list[Path] = []
            for row in raw:
                if isinstance(row, dict) and isinstance(row.get("file"), str):
                    path = PNG_DIR / row["file"]
                    if path.is_file():
                        paths.append(path)
            if paths:
                return paths
    return sorted(PNG_DIR.glob("*.png"))


def png_slide(png: Path, dest: Path, seconds: float) -> None:
    """One animated slide: slow zoom on a real diagram PNG."""
    frames = max(1, int(seconds * 30))
    scale = (
        f"scale=1920:1080:force_original_aspect_ratio=decrease,"
        f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x141414,"
        f"zoompan=z='min(zoom+0.0012,1.05)':d={frames}:s=1920x1080:fps=30,"
        f"fade=t=in:st=0:d=0.12,fade=t=out:st={max(0.0, seconds - 0.12):.3f}:d=0.12"
    )
    subprocess.run(
        [
            ffmpeg(),
            "-y",
            "-v",
            "error",
            "-loop",
            "1",
            "-i",
            str(png),
            "-vf",
            scale,
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
            str(dest),
        ],
        check=True,
    )


def png_montage(dest: Path, work: Path, seconds: float) -> None:
    """Ken Burns montage from exported PNGs (text stays perfect)."""
    pngs = ordered_pngs()
    if not pngs:
        raise RuntimeError(f"no PNGs under {PNG_DIR}")
    work.mkdir(parents=True, exist_ok=True)
    slides: list[Path] = []
    for index, png in enumerate(pngs):
        slide = work / f"slide_{index:02d}.mp4"
        png_slide(png, slide, seconds)
        slides.append(slide)
    xfade_montage(slides, dest, fade=0.15)


def ordered_clips(i2v_dir: Path) -> list[Path]:
    """Diagram I2V clips in manifest order."""
    if MANIFEST.is_file():
        raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            paths: list[Path] = []
            for row in raw:
                if not isinstance(row, dict):
                    continue
                slug = row.get("slug")
                if isinstance(slug, str):
                    clip = i2v_dir / f"{slug}.mp4"
                    if clip.is_file():
                        paths.append(clip)
            if paths:
                return paths
    return sorted(i2v_dir.glob("*.mp4"))


def xfade_montage(clips: list[Path], dest: Path, fade: float) -> None:
    """Crossfade diagram clips (fancy middle, real pixels)."""
    if not clips:
        raise RuntimeError("no diagram i2v clips")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if len(clips) == 1:
        shutil.copy2(clips[0], dest)
        return
    inputs: list[str] = []
    for clip in clips:
        inputs.extend(["-i", str(clip)])
    parts: list[str] = []
    offset = 0.0
    for index in range(len(clips) - 1):
        left = "[0:v]" if index == 0 else f"[v{index}]"
        right = f"[{index + 1}:v]"
        out = f"[v{index + 1}]" if index < len(clips) - 2 else "[vout]"
        duration_probe = _duration(clips[index])
        offset += max(0.05, duration_probe - fade)
        parts.append(f"{left}{right}xfade=transition=fade:duration={fade:.3f}:offset={offset:.3f}{out}")
    graph = ";".join(parts)
    subprocess.run(
        [
            ffmpeg(),
            "-y",
            "-v",
            "error",
            *inputs,
            "-filter_complex",
            graph,
            "-map",
            "[vout]",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            str(dest),
        ],
        check=True,
    )


def _duration(path: Path) -> float:
    completed = subprocess.run(
        [ffmpeg(), "-i", str(path), "-f", "null", "-"],
        check=False,
        capture_output=True,
        text=True,
    )
    for line in completed.stderr.splitlines():
        if "Duration:" not in line:
            continue
        stamp = line.split("Duration:", 1)[1].split(",", 1)[0].strip()
        hours, minutes, seconds = stamp.split(":")
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    raise RuntimeError(f"no duration for {path}")


def concat_three(intro: Path, middle: Path, outro: Path, dest: Path) -> None:
    """Join intro, diagram montage, outro."""
    listing = WORK / "concat.txt"
    listing.write_text(
        "\n".join(f"file '{p}'" for p in (intro, middle, outro)) + "\n",
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
    """Build motion-real-diagrams.mp4 next to v2."""
    parser = argparse.ArgumentParser(description="v2 bookends + real diagram montage")
    parser.add_argument("--i2v", action="store_true", help="Use Wan I2V clips instead of PNG Ken Burns")
    parser.add_argument("--skip-i2v", action="store_true", help="With --i2v, do not submit; use existing clips")
    args = parser.parse_args()
    if not V2.is_file():
        raise SystemExit(f"missing {V2}")
    WORK.mkdir(parents=True, exist_ok=True)
    intro = WORK / "intro.mp4"
    outro = WORK / "outro.mp4"
    middle = WORK / "diagram-montage.mp4"
    cut_v2(V2, intro, 0.0, INTRO_END)
    cut_v2(V2, outro, OUTRO_START, 15.0)
    if args.i2v:
        if not args.skip_i2v:
            subprocess.run(
                [
                    _python(),
                    "-m",
                    "scripts.metl_promo_video.i2v_diagram",
                    "--out",
                    str(I2V_DIR),
                ],
                check=True,
                cwd="/home/roywa/src/MindGraph",
                env=_env(),
            )
        clips = ordered_clips(I2V_DIR)
        if not clips:
            raise SystemExit(f"no clips in {I2V_DIR}; run i2v_diagram first")
        xfade_montage(clips, middle, fade=0.18)
    else:
        png_montage(middle, WORK / "png-slides", SLIDE_SECONDS)
    concat_three(intro, middle, outro, OUT)
    print(f"done {OUT}", flush=True)


def _python() -> str:
    return sys.executable


def _env() -> dict[str, str]:
    env = os.environ.copy()
    root = "/home/roywa/src/MindGraph"
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = root if not prev else f"{root}:{prev}"
    return env


if __name__ == "__main__":
    main()
