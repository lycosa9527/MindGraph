#!/usr/bin/env python3
"""Build a silent diagram montage MP4 from exported PNGs (correct MindGraph pixels)."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg

DEFAULT_DIAGRAMS = Path("/mnt/c/Users/roywa/Desktop/迈特宣传片/02-product/01-metl-reveal-hybrid/diagrams")
DEFAULT_OUT = Path("/mnt/c/Users/roywa/Desktop/迈特宣传片/02-product/01-metl-reveal-hybrid/montage/motion.mp4")
SECONDS_PER_SLIDE = 1.0
FPS = 30


def ffmpeg() -> str:
    """Bundled ffmpeg."""
    return imageio_ffmpeg.get_ffmpeg_exe()


def ordered_pngs(diagrams_dir: Path) -> list[Path]:
    """PNG paths in manifest order."""
    manifest_path = diagrams_dir / "manifest.json"
    if manifest_path.is_file():
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            paths: list[Path] = []
            for row in raw:
                if isinstance(row, dict) and isinstance(row.get("file"), str):
                    path = diagrams_dir / row["file"]
                    if path.is_file():
                        paths.append(path)
            if paths:
                return paths
    return sorted(diagrams_dir.glob("*.png"))


def build(diagrams_dir: Path, dest: Path, seconds: float) -> None:
    """Concat scaled slides with short crossfade."""
    slides = ordered_pngs(diagrams_dir)
    if not slides:
        raise RuntimeError(f"no PNGs in {diagrams_dir}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    work = dest.parent / ".ffmpeg-montage"
    work.mkdir(parents=True, exist_ok=True)
    clip_paths: list[Path] = []
    scale = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x141414"
    for index, png in enumerate(slides):
        clip = work / f"slide_{index:02d}.mp4"
        subprocess.run(
            [
                ffmpeg(),
                "-y",
                "-loop",
                "1",
                "-i",
                str(png),
                "-vf",
                f"{scale},format=yuv420p",
                "-t",
                f"{seconds:.3f}",
                "-r",
                str(FPS),
                "-c:v",
                "libx264",
                "-crf",
                "18",
                "-preset",
                "fast",
                str(clip),
            ],
            check=True,
        )
        clip_paths.append(clip)
    list_file = work / "concat.txt"
    list_file.write_text(
        "\n".join(f"file '{path}'" for path in clip_paths) + "\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            ffmpeg(),
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(dest),
        ],
        check=True,
    )
    print(f"montage {dest} slides={len(slides)}", flush=True)


def main() -> None:
    """CLI entry."""
    parser = argparse.ArgumentParser(description="PNG diagram montage")
    parser.add_argument("--diagrams", type=Path, default=DEFAULT_DIAGRAMS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seconds", type=float, default=SECONDS_PER_SLIDE)
    args = parser.parse_args()
    build(args.diagrams, args.out, args.seconds)


if __name__ == "__main__":
    main()
