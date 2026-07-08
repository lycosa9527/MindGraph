"""Regenerate extension PNG icons from the same design as frontend/public/favicon.svg."""

import os
from pathlib import Path

from typing import Union

from PIL import Image, ImageDraw, ImageFont

_SCRIPT_DIR = Path(__file__).resolve().parent
_ICONS_DIR = _SCRIPT_DIR.parent / "icons"
_STONE_900 = (28, 25, 23, 255)
# favicon.svg: viewBox 32, rx=6, font-size=18, text at (16, 23) baseline-centered on x.
_REF_SIZE = 32
_REF_RADIUS = 6
_REF_FONT_SIZE = 18
_REF_BASELINE_Y = 23

_FONT_CANDIDATES = [
    Path("/mnt/c/Windows/Fonts/segoeuib.ttf"),
    Path("/mnt/c/Windows/Fonts/segoeui.ttf"),
    Path("/mnt/c/Windows/Fonts/arialbd.ttf"),
    Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "Fonts" / "segoeuib.ttf",
    Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "Fonts" / "segoeui.ttf",
    Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "Fonts" / "arialbd.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
]


def _load_font(size: int) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
    for path in _FONT_CANDIDATES:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _scaled(value: int, size: int) -> int:
    return max(1, round(value * size / _REF_SIZE))


def _make_png(size: int, out_path: Path) -> None:
    radius = _scaled(_REF_RADIUS, size)
    font_size = max(4, _scaled(_REF_FONT_SIZE, size))
    baseline_y = _scaled(_REF_BASELINE_Y, size)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=_STONE_900)
    font = _load_font(font_size)
    draw.text(
        (size / 2, baseline_y),
        "M",
        fill=(255, 255, 255, 255),
        font=font,
        anchor="ms",
    )
    img.save(out_path, "PNG")


def main() -> None:
    _ICONS_DIR.mkdir(parents=True, exist_ok=True)
    for dim in (16, 32, 48, 128, 300):
        _make_png(dim, _ICONS_DIR / f"icon{dim}.png")
    print(
        "Wrote icon16.png, icon32.png, icon48.png, icon128.png, icon300.png in",
        _ICONS_DIR,
    )


if __name__ == "__main__":
    main()
