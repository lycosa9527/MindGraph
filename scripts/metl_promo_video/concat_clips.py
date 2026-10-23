#!/usr/bin/env python3
"""Concat silent MP4 plates for Act 02 hybrid (brand + montage + models)."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import imageio_ffmpeg

DEFAULT_OUT = Path("/mnt/c/Users/roywa/Desktop/迈特宣传片/02-product/01-metl-reveal-hybrid/motion.mp4")


def ffmpeg() -> str:
    """Bundled ffmpeg."""
    return imageio_ffmpeg.get_ffmpeg_exe()


def concat_parts(parts: list[Path], dest: Path) -> None:
    """Lossless concat when codecs match."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    work = dest.parent / ".concat-list.txt"
    work.write_text("\n".join(f"file '{p}'" for p in parts) + "\n", encoding="utf-8")
    subprocess.run(
        [
            ffmpeg(),
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(work),
            "-c",
            "copy",
            str(dest),
        ],
        check=True,
    )
    print(f"concat {dest.name} parts={len(parts)}", flush=True)


def main() -> None:
    """CLI entry."""
    parser = argparse.ArgumentParser(description="Concat hybrid act2 clips")
    parser.add_argument("parts", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    for part in args.parts:
        if not part.is_file():
            raise SystemExit(f"missing {part}")
    concat_parts(args.parts, args.out)


if __name__ == "__main__":
    main()
