"""Create local synthetic mind-map / document images for vision smoke tests."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "handdrawn_mindmap_smoke"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Best-effort TrueType font; fall back to default bitmap font."""
    for name in ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_bubble(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    fill: tuple[int, int, int],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> tuple[int, int, int, int]:
    """Draw a labeled oval; return its bounding box."""
    padding_x = 18
    padding_y = 12
    bbox = draw.textbbox((0, 0), text, font=font)
    width = int(bbox[2] - bbox[0]) + padding_x * 2
    height = int(bbox[3] - bbox[1]) + padding_y * 2
    left = xy[0] - width // 2
    top = xy[1] - height // 2
    box = (left, top, left + width, top + height)
    draw.ellipse(box, fill=fill, outline=(40, 40, 40), width=2)
    draw.text((xy[0], xy[1]), text, fill=(20, 20, 20), font=font, anchor="mm")
    return box


def make_mindmap_png(path: Path) -> None:
    """Radial mind map: center topic + four branches with children."""
    image = Image.new("RGB", (900, 640), (252, 250, 245))
    draw = ImageDraw.Draw(image)
    title_font = _font(22)
    node_font = _font(16)
    center = (450, 320)
    _draw_bubble(draw, center, "Learning Skills", fill=(255, 214, 102), font=title_font)

    branches = [
        ((180, 160), "Read", [(90, 90), (90, 220)]),
        ((720, 160), "Write", [(810, 90), (810, 220)]),
        ((180, 480), "Speak", [(90, 420), (90, 540)]),
        ((720, 480), "Think", [(810, 420), (810, 540)]),
    ]
    child_labels = {
        (90, 90): "skim",
        (90, 220): "notes",
        (810, 90): "draft",
        (810, 220): "edit",
        (90, 420): "present",
        (90, 540): "discuss",
        (810, 420): "analyze",
        (810, 540): "reflect",
    }
    for branch_xy, label, children in branches:
        draw.line([center, branch_xy], fill=(90, 90, 90), width=3)
        _draw_bubble(draw, branch_xy, label, fill=(173, 216, 230), font=node_font)
        for child_xy in children:
            draw.line([branch_xy, child_xy], fill=(120, 120, 120), width=2)
            _draw_bubble(
                draw,
                child_xy,
                child_labels[child_xy],
                fill=(220, 237, 200),
                font=node_font,
            )
    image.save(path, format="PNG")


def make_document_png(path: Path) -> None:
    """Plain document photo (should NOT auto-detect as mind map)."""
    image = Image.new("RGB", (800, 1000), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    font = _font(20)
    lines = [
        "Meeting Notes — 2026-07-20",
        "",
        "1. Budget review for Q3",
        "2. Hire two teaching assistants",
        "3. Update classroom schedule",
        "",
        "Action items:",
        "- Send draft to parents",
        "- Confirm lab booking",
    ]
    y = 60
    for line in lines:
        draw.text((48, y), line, fill=(30, 30, 30), font=font)
        y += 36
    image.save(path, format="PNG")


def main() -> None:
    """Write fixture PNGs under tmp/handdrawn_mindmap_smoke."""
    OUT.mkdir(parents=True, exist_ok=True)
    mindmap_path = OUT / "synthetic_mindmap.png"
    document_path = OUT / "synthetic_document.png"
    make_mindmap_png(mindmap_path)
    make_document_png(document_path)
    print("wrote", mindmap_path, mindmap_path.stat().st_size)
    print("wrote", document_path, document_path.stat().st_size)


if __name__ == "__main__":
    main()
