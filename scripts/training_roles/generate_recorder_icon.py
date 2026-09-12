#!/usr/bin/env python3
"""Generate the 语音笔记 Super launcher icon with Wan 2.7 image."""

from __future__ import annotations

from scripts.cat_emoji.paths import REPO_ROOT
from scripts.training_roles.super_icon import generate_pixel_icon

DEST = REPO_ROOT / "esp32" / "firmware" / "1.85c" / "round_ui" / "recorder" / "images" / "launcher_icon.png"
PROMPT = (
    "Square 16-bit pixel-art watch-app launcher icon, readable at 48 pixels. "
    "ONE handheld digital voice recorder as a chunky game sprite, front view, "
    "filling the frame: compact rounded body, a round microphone grill, a big "
    "red REC button, a tiny blank display. Soft peach pastel background. "
    "Limited palette, thick pixel blocks, high contrast, small margin. No cat, "
    "no person, no cassette tape, no headphones, no text, no watermark, no logo."
)


def main() -> None:
    """Submit one Wan still and write the 92x92 Super tile icon."""
    generate_pixel_icon(PROMPT, DEST, "recorder-watch-icon.png")
    print("all-done", flush=True)


if __name__ == "__main__":
    main()
