"""Scratch under the repo, finished cuts on the Windows desktop."""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
WORK_DIR = PACKAGE_DIR / ".work"
DESKTOP_DIR = Path("/mnt/c/Users/roywa/Desktop/October-update-promo/v3")
SCREENSHOT_DIR = DESKTOP_DIR / "screenshots"


def screenshot_for(clip_id: str) -> Path:
    """Real canvas capture for one beat, named 01.png through 07.png."""
    return SCREENSHOT_DIR / f"{clip_id}.png"
