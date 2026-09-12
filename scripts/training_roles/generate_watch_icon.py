#!/usr/bin/env python3
"""Generate the 校本培训 Super launcher icon with Wan 2.7 image."""

from __future__ import annotations

from scripts.cat_emoji.paths import REPO_ROOT
from scripts.training_roles.super_icon import generate_pixel_icon

DEST = REPO_ROOT / "esp32" / "firmware" / "1.85c" / "round_ui" / "training" / "images" / "launcher_icon.png"
PROMPT = (
    "Square 16-bit pixel-art watch-app launcher icon, readable at 48 pixels. "
    "ONE simple presentation clicker as a chunky game sprite, front view, "
    "filling most of the frame: short rounded white remote with FOUR huge "
    "saturated buttons — blue up triangle, green down triangle, yellow play "
    "triangle, red stop square — plus one red power LED. Soft mint pastel "
    "background. Limited palette, thick pixel blocks, high contrast, small "
    "margin. No tiny keypad, no cat, no person, no phone, no screen, no text, "
    "no watermark, no logo."
)


def main() -> None:
    """Submit one Wan still and write the 92x92 Super tile icon."""
    generate_pixel_icon(PROMPT, DEST, "training-watch-icon.png")
    print("all-done", flush=True)


if __name__ == "__main__":
    main()
