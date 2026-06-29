"""Generate file-reader PNG + ICO from the MindGraph favicon M logo design."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union

from PIL import Image, ImageDraw, ImageFont

_SCRIPT_DIR = Path(__file__).resolve().parent
_ASSETS_DIR = _SCRIPT_DIR.parent / "assets"
_STONE_900 = (28, 25, 23, 255)
_ICO_SIZES = (16, 32, 48, 64, 128, 256)

_FONT_CANDIDATES = [
    Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "Fonts" / "segoeuib.ttf",
    Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "Fonts" / "segoeui.ttf",
    Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "Fonts" / "arialbd.ttf",
]


def _load_font(size: int) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
    for path in _FONT_CANDIDATES:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _make_icon_image(size: int) -> Image.Image:
    """Render the MindGraph M logo (matches frontend/public/favicon.svg)."""
    radius = max(1, round(6 * size / 32))
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=_STONE_900)
    font_size = max(8, round(18 * size / 32))
    font = _load_font(font_size)
    draw.text((size / 2, size / 2), "M", fill=(255, 255, 255, 255), font=font, anchor="mm")
    return image


def main() -> None:
    """Write assets/icon.png and assets/icon.ico for tkinter + PyInstaller."""
    _ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    png_path = _ASSETS_DIR / "icon.png"
    ico_path = _ASSETS_DIR / "icon.ico"

    images = [_make_icon_image(size) for size in _ICO_SIZES]
    images[-1].save(png_path, "PNG")
    images[0].save(
        ico_path,
        format="ICO",
        sizes=[(size, size) for size in _ICO_SIZES],
        append_images=images[1:],
    )
    print(f"Wrote {png_path} and {ico_path}")


if __name__ == "__main__":
    main()
