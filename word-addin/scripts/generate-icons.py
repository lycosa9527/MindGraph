#!/usr/bin/env python3
"""Generate 16/32/80 ribbon PNGs for MindGraph Word add-in."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "icons"

# name -> (bg RGB, glyph kind)
SPECS: dict[str, tuple[tuple[int, int, int], str]] = {
    "mindmate": ((37, 99, 235), "chat"),
    "mindgraph": ((16, 185, 129), "graph"),
    "voice": ((217, 70, 239), "mic"),
    "showcase": ((245, 158, 11), "grid"),
    "manual": ((99, 102, 241), "book"),
    "settings": ((100, 116, 139), "gear"),
}


def _rounded_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int],
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _draw_chat(draw: ImageDraw.ImageDraw, size: int, color: tuple[int, int, int]) -> None:
    m = size // 5
    _rounded_rect(draw, (m, m, size - m, size - m - size // 10), size // 8, color)
    tip = [
        (m + size // 6, size - m - size // 10),
        (m + size // 4, size - m),
        (m + size // 3, size - m - size // 10),
    ]
    draw.polygon(tip, fill=color)


def _draw_graph(draw: ImageDraw.ImageDraw, size: int, color: tuple[int, int, int]) -> None:
    cx, cy = size // 2, size // 2
    r = size // 7
    nodes = [
        (cx, cy - size // 4),
        (cx - size // 4, cy + size // 6),
        (cx + size // 4, cy + size // 6),
    ]
    for a, b in ((0, 1), (0, 2), (1, 2)):
        draw.line([nodes[a], nodes[b]], fill=color, width=max(2, size // 16))
    for x, y in nodes:
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)


def _draw_mic(draw: ImageDraw.ImageDraw, size: int, color: tuple[int, int, int]) -> None:
    cx = size // 2
    top = size // 4
    bot = size // 2 + size // 10
    w = size // 7
    _rounded_rect(draw, (cx - w, top, cx + w, bot), w, color)
    draw.arc(
        (cx - size // 4, bot - size // 10, cx + size // 4, bot + size // 4),
        start=0,
        end=180,
        fill=color,
        width=max(2, size // 16),
    )
    draw.line(
        [(cx, bot + size // 5), (cx, size - size // 5)],
        fill=color,
        width=max(2, size // 16),
    )


def _draw_grid(draw: ImageDraw.ImageDraw, size: int, color: tuple[int, int, int]) -> None:
    pad = size // 5
    gap = size // 16
    cell = (size - 2 * pad - gap) // 2
    for row in range(2):
        for col in range(2):
            x0 = pad + col * (cell + gap)
            y0 = pad + row * (cell + gap)
            _rounded_rect(draw, (x0, y0, x0 + cell, y0 + cell), size // 16, color)


def _draw_book(draw: ImageDraw.ImageDraw, size: int, color: tuple[int, int, int]) -> None:
    pad = size // 5
    _rounded_rect(draw, (pad, pad, size - pad, size - pad), size // 14, color)
    mid = size // 2
    draw.line([(mid, pad + 2), (mid, size - pad - 2)], fill=(255, 255, 255), width=max(2, size // 20))


def _draw_gear(draw: ImageDraw.ImageDraw, size: int, color: tuple[int, int, int]) -> None:
    cx = cy = size // 2
    outer = size // 3
    inner = size // 7
    draw.ellipse((cx - outer, cy - outer, cx + outer, cy + outer), outline=color, width=max(3, size // 12))
    draw.ellipse((cx - inner, cy - inner, cx + inner, cy + inner), fill=color)
    for angle in range(0, 360, 45):
        import math

        rad = math.radians(angle)
        x = cx + int(math.cos(rad) * (outer + size // 14))
        y = cy + int(math.sin(rad) * (outer + size // 14))
        r = size // 12
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)


DRAWERS = {
    "chat": _draw_chat,
    "graph": _draw_graph,
    "mic": _draw_mic,
    "grid": _draw_grid,
    "book": _draw_book,
    "gear": _draw_gear,
}


def render(name: str, bg: tuple[int, int, int], kind: str, size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = max(1, size // 16)
    _rounded_rect(draw, (margin, margin, size - margin - 1, size - margin - 1), size // 5, bg)
    glyph = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glyph)
    DRAWERS[kind](gdraw, size, (255, 255, 255))
    # Shrink glyph slightly inside the tile
    inset = size // 8
    glyph = glyph.crop((inset, inset, size - inset, size - inset)).resize(
        (size - 2 * inset, size - 2 * inset), Image.Resampling.LANCZOS
    )
    img.paste(glyph, (inset, inset), glyph)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (bg, kind) in SPECS.items():
        for size in (16, 32, 80):
            path = OUT / f"{name}-{size}.png"
            render(name, bg, kind, size).save(path, format="PNG")
        # Default alias used by IconUrl / older refs
        render(name, bg, kind, 80).save(OUT / f"{name}.png", format="PNG")
        print(f"wrote {name} 16/32/80")


if __name__ == "__main__":
    main()
