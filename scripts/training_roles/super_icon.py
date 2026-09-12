"""Crop a Wan still into a 92x92 pixel Super launcher tile."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops
from requests.exceptions import RequestException

from scripts.cat_office_battles.wan_image import download_image, poll_storyboard, submit_icon
from scripts.training_roles.paths import WORK_DIR

ICON_PX = 92
DIFF_THRESHOLD = 36


def subject_box(image: Image.Image) -> tuple[int, int, int, int]:
    """Return a tight box around the main sprite, ignoring faint corner marks."""
    rgb = image.convert("RGB")
    background = Image.new("RGB", rgb.size, rgb.getpixel((4, 4)))
    diff = ImageChops.difference(rgb, background).convert("L")
    lut = [255 if value > DIFF_THRESHOLD else 0 for value in range(256)]
    mask = diff.point(lut)
    bbox = mask.getbbox()
    if bbox is None:
        return (0, 0, image.width, image.height)
    return bbox


def square_pixel_icon(src: Path, dest: Path) -> None:
    """Crop the subject and scale to 92px, keeping the Wan pixel-art edges."""
    image = Image.open(src).convert("RGBA")
    left, top, right, bottom = subject_box(image)
    box_w = right - left
    box_h = bottom - top
    side = max(box_w, box_h)
    margin = max(4, int(side * 0.04))
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
    icon = cropped.resize((ICON_PX, ICON_PX), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    icon.save(dest, format="PNG")
    print(f"icon {dest} {ICON_PX}x{ICON_PX}", flush=True)


def generate_pixel_icon(prompt: str, dest: Path, raw_name: str) -> None:
    """Submit one text-only Wan still and write the Super tile."""
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    raw = WORK_DIR / raw_name
    task_id = submit_icon(prompt, [])
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
    square_pixel_icon(raw, dest)
