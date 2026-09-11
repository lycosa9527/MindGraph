#!/usr/bin/env python3
"""Generate the 校本培训 Super launcher icon with Wan 2.7 image."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops
from requests.exceptions import RequestException

from scripts.cat_emoji.paths import BLACK_STILL_FRONT, REPO_ROOT
from scripts.cat_office_battles.wan_image import download_image, poll_storyboard, submit_icon
from scripts.training_roles.paths import WORK_DIR

DEST = REPO_ROOT / "esp32" / "firmware" / "1.85c" / "round_ui" / "training" / "images" / "launcher_icon.png"
ICON_PX = 92
PROMPT = (
    "Square watch-app launcher icon that must stay readable at 48 pixels. "
    "ONE funny black kitten FACE only, like a simple cat emoji sticker: huge "
    "round head filling the frame, short black fur, oversized shiny green eyes, "
    "tiny pink nose, red gingham bandana, cheeky grin, almost no neck. Same "
    "face as the reference, not a new cat. Soft mint background. No body, no "
    "paws, no remote, no classroom props, no text, no watermark. Cute 3D toy "
    "emoji, thick simple shapes, high contrast, small margin."
)


def _subject_box(image: Image.Image) -> tuple[int, int, int, int]:
    rgb = image.convert("RGB")
    bg = Image.new("RGB", rgb.size, rgb.getpixel((4, 4)))
    bbox = ImageChops.difference(rgb, bg).getbbox()
    if bbox is None:
        return (0, 0, image.width, image.height)
    return bbox


def _square_icon(src: Path, dest: Path) -> None:
    image = Image.open(src).convert("RGBA")
    left, top, right, bottom = _subject_box(image)
    box_w = right - left
    box_h = bottom - top
    side = max(box_w, box_h)
    margin = max(6, int(side * 0.06))
    side += margin * 2
    center_x = (left + right) // 2
    center_y = (top + bottom) // 2
    half = side // 2
    cropped = image.crop(
        (
            max(0, center_x - half),
            max(0, center_y - half),
            min(image.width, center_x + half),
            min(image.height, center_y + half),
        )
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    resized = cropped.resize((ICON_PX, ICON_PX), Image.Resampling.LANCZOS)
    resized.save(dest, format="PNG")
    print(f"icon {dest} {ICON_PX}x{ICON_PX}", flush=True)


def main() -> None:
    """Submit one Wan still and write the 92x92 Super tile icon."""
    if not BLACK_STILL_FRONT.is_file():
        raise RuntimeError(f"still missing: {BLACK_STILL_FRONT}")
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    raw = WORK_DIR / "training-watch-icon.png"
    task_id = submit_icon(PROMPT, [BLACK_STILL_FRONT])
    urls = poll_storyboard(task_id)
    if not urls:
        raise RuntimeError("Wan returned no image urls")
    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            download_image(urls[0], raw)
            last_error = None
            break
        except (OSError, RuntimeError, RequestException) as exc:
            last_error = exc
            print(f"download attempt={attempt} {type(exc).__name__}", flush=True)
    if last_error is not None:
        raise last_error
    _square_icon(raw, DEST)
    print("all-done", flush=True)


if __name__ == "__main__":
    main()
