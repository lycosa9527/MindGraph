#!/usr/bin/env python3
"""Resize cat art into LittleFS assets for the LVGL Kitty face."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None
    ImageDraw = None

REPO_ROOT = Path(__file__).resolve().parents[4]
STILL_IDLE = REPO_ROOT / "scripts" / "cat_emoji" / "stills" / "black" / "fullbody-still-noptr-1.png"
STILL_SPEAK = REPO_ROOT / "scripts" / "cat_emoji" / "stills" / "black" / "fullbody-still-noptr-2.png"
PIXEL = REPO_ROOT / "esp32" / "apps" / "kitty" / "assets" / "pixel-kitty.png"
SIZE = 140


def _write_png(image: Image.Image, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, format="PNG", optimize=True)
    print(f"kitty stills: {dest} ({dest.stat().st_size} bytes)")


def _resize(src: Path, dest: Path, size: int = SIZE) -> bool:
    """Write a square PNG. True when dest exists afterwards."""
    if not src.is_file() or Image is None:
        return dest.is_file()
    with Image.open(src) as image:
        rgba = image.convert("RGBA")
        rgba.thumbnail((size, size))
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        left = (size - rgba.width) // 2
        top = (size - rgba.height) // 2
        canvas.paste(rgba, (left, max(0, top)), rgba)
        _write_png(canvas, dest)
    return dest.is_file()


def _crop_face(src: Path, dest: Path, size: int = SIZE) -> bool:
    """Square crop of the pixel-cat bust."""
    if not src.is_file() or Image is None:
        return dest.is_file()
    with Image.open(src) as image:
        rgba = image.convert("RGBA")
        width, height = rgba.size
        side = min(width, int(height * 0.78))
        left = (width - side) // 2
        top = int(height * 0.02)
        crop = rgba.crop((left, top, left + side, top + side))
        _write_png(crop.resize((size, size), Image.Resampling.LANCZOS), dest)
    return dest.is_file()


def _write_mic(dest: Path, size: int = 128) -> bool:
    """White microphone glyph, supersampled so the 52px button stays sharp."""
    if Image is None or ImageDraw is None:
        return dest.is_file()
    src = size * 4
    tile = Image.new("RGBA", (src, src), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tile)
    white = (255, 255, 255, 255)
    unit = src / 24.0

    def box(left: float, top: float, right: float, bottom: float) -> tuple[int, int, int, int]:
        return (
            int(round(left * unit)),
            int(round(top * unit)),
            int(round(right * unit)),
            int(round(bottom * unit)),
        )

    stroke = max(1, int(round(2.2 * unit)))
    draw.rounded_rectangle(box(9.0, 2.2, 15.0, 13.6), radius=int(round(3.0 * unit)), fill=white)
    draw.arc(box(6.4, 8.2, 17.6, 19.4), start=0, end=180, fill=white, width=stroke)
    draw.rounded_rectangle(box(11.1, 17.4, 12.9, 20.6), radius=int(round(0.9 * unit)), fill=white)
    draw.rounded_rectangle(box(7.4, 20.2, 16.6, 22.2), radius=int(round(1.0 * unit)), fill=white)
    out = tile.resize((size, size), Image.Resampling.LANCZOS)
    _write_png(out, dest)
    return dest.is_file()


def prepare(littlefs: Path) -> None:
    """Copy mascot, speaking still, and mic into the LittleFS image."""
    dest_dir = littlefs / "kitty"
    if PIXEL.is_file():
        _crop_face(PIXEL, dest_dir / "mascot.png")
    else:
        _resize(STILL_IDLE, dest_dir / "mascot.png")
    _resize(STILL_SPEAK, dest_dir / "speaking.png")
    _write_mic(dest_dir / "mic.png")


def main() -> int:
    """CLI: --littlefs path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--littlefs", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.littlefs.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
