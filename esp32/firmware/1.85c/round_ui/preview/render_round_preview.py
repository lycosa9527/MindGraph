#!/usr/bin/env python3
"""Render 1.85C circular launcher previews to PNG."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 360
CENTER = 180
RADIUS = 180
FACE = (17, 19, 24)
BEZEL = (26, 26, 26)
TEXT = (242, 242, 242)
MUTED = (154, 160, 168)
TILE = (42, 47, 56)
KEY = (58, 64, 76)
LINE = (216, 216, 216)
STATUS = (40, 44, 54, 230)
FONT_PATH = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
OUT_DIR = Path(__file__).resolve().parent


def load_font(size: int) -> ImageFont.FreeTypeFont:
    """Load Noto Sans CJK at the given pixel size."""
    return ImageFont.truetype(str(FONT_PATH), size=size, index=0)


def new_face() -> Image.Image:
    """Create a circular 360x360 watch face on a dark bezel plate."""
    plate = Image.new("RGBA", (SIZE + 24, SIZE + 24), (11, 12, 16, 255))
    draw = ImageDraw.Draw(plate)
    draw.ellipse((2, 2, SIZE + 21, SIZE + 21), fill=BEZEL)
    face = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(face).ellipse((0, 0, SIZE - 1, SIZE - 1), fill=FACE)
    plate.paste(face, (12, 12), face)
    return plate


def face_draw(plate: Image.Image) -> ImageDraw.ImageDraw:
    """Return a draw context whose (0,0) is the 360 panel origin."""
    cropped = plate.crop((12, 12, 12 + SIZE, 12 + SIZE))
    return ImageDraw.Draw(cropped), cropped, plate


def blit_face(plate: Image.Image, face: Image.Image) -> None:
    """Clip the 360 panel back onto the bezel as a circle."""
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, SIZE - 1, SIZE - 1), fill=255)
    plate.paste(face, (12, 12), mask)


def draw_status(draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont) -> None:
    """Wear-style 12 o'clock capsule."""
    draw.rounded_rectangle((100, 34, 260, 58), radius=12, fill=STATUS)
    draw.ellipse((118, 42, 126, 50), fill=(125, 221, 136))
    draw.text((168, 38), "19:05", font=font, fill=TEXT)


def draw_tile(
    draw: ImageDraw.ImageDraw,
    left: int,
    top: int,
    width: int,
    height: int,
    name: str,
    font: ImageFont.FreeTypeFont,
) -> None:
    """One launcher icon + label."""
    icon = 48
    icon_left = left + (width - icon) // 2
    icon_top = top + 8
    draw.rounded_rectangle(
        (icon_left, icon_top, icon_left + icon, icon_top + icon),
        radius=12,
        fill=TILE,
    )
    label_top = top + height - 18
    bbox = draw.textbbox((0, 0), name, font=font)
    text_w = bbox[2] - bbox[0]
    draw.text((left + (width - text_w) // 2, label_top), name, font=font, fill=TEXT)


def clip_content(face: Image.Image) -> None:
    """Hide pixels outside Super's 216dp launcher content band."""
    overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    mask = ImageDraw.Draw(overlay)
    mask.rectangle((0, 0, SIZE, 64), fill=(17, 19, 24, 255))
    mask.rectangle((0, 280, SIZE, SIZE), fill=(17, 19, 24, 255))
    face.alpha_composite(overlay)


def render_now(path: Path) -> None:
    """Current firmware: 112 pitch, labels clipped by the content band."""
    plate = new_face()
    draw, face, plate = face_draw(plate)
    draw_status(draw, load_font(13))
    font = load_font(12)
    origin_x = 62
    origin_y = 64 + 6
    names = (("设置", 0, 0), ("文件", 1, 0), ("应用商店", 0, 1), ("智回", 1, 1))
    for name, col, row in names:
        left = origin_x + col * 130
        top = origin_y + row * 130
        draw_tile(draw, left, top, 92, 86, name, font)
    clip_content(face)
    blit_face(plate, face)
    plate.convert("RGB").save(path)


def render_fixed(path: Path) -> None:
    """Patched 80x10 / 2-column grid inside the inscribed band."""
    plate = new_face()
    draw, face, plate = face_draw(plate)
    draw_status(draw, load_font(13))
    font = load_font(12)
    origin_x = 62 + 33
    origin_y = 64 + 12
    names = (("设置", 0, 0), ("文件", 1, 0), ("应用商店", 0, 1), ("智回", 1, 1))
    for name, col, row in names:
        left = origin_x + col * 90
        top = origin_y + row * 90
        draw_tile(draw, left, top, 80, 80, name, font)
    blit_face(plate, face)
    plate.convert("RGB").save(path)


def render_keyboard(path: Path) -> None:
    """九宫格 with a visible outline on every key."""
    plate = new_face()
    draw, face, plate = face_draw(plate)
    draw_status(draw, load_font(13))
    font = load_font(11)
    small = load_font(9)
    labels = (
        ("1", ""),
        ("2", "ABC"),
        ("3", "DEF"),
        ("4", "GHI"),
        ("5", "JKL"),
        ("6", "MNO"),
        ("7", "PQRS"),
        ("8", "TUV"),
        ("9", "WXYZ"),
        ("EN", ""),
        ("spc", ""),
        ("OK", ""),
    )
    left0 = 62
    top0 = 76
    cell_w = 74
    cell_h = 40
    gap = 6
    for index, (title, hint) in enumerate(labels):
        col = index % 3
        row = index // 3
        left = left0 + col * (cell_w + gap)
        top = top0 + row * (cell_h + gap)
        draw.rounded_rectangle(
            (left, top, left + cell_w, top + cell_h),
            radius=8,
            fill=KEY,
            outline=LINE,
            width=2,
        )
        if hint:
            draw.text((left + 28, top + 6), title, font=font, fill=TEXT)
            draw.text((left + 22, top + 20), hint, font=small, fill=MUTED)
        else:
            draw.text((left + 24, top + 12), title, font=font, fill=TEXT)
    blit_face(plate, face)
    plate.convert("RGB").save(path)


def main() -> int:
    """Write now / fixed / keyboard PNGs next to this script."""
    render_now(OUT_DIR / "launcher_now.png")
    render_fixed(OUT_DIR / "launcher_fixed.png")
    render_keyboard(OUT_DIR / "keyboard.png")
    print(f"wrote previews in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
