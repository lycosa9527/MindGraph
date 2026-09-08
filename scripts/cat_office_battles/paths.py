"""Character stills, desktop exports, and local Wan scratch."""

from __future__ import annotations

from pathlib import Path

from scripts.cat_emoji.paths import (
    BATTLES_DESKTOP_DIR,
    BLACK_STILL_FRONT,
    WHITE_STILL_FRONT,
)

PACKAGE_DIR = Path(__file__).resolve().parent
WORK_DIR = PACKAGE_DIR / ".work"
BLACK_STILL = BLACK_STILL_FRONT
WHITE_STILL = WHITE_STILL_FRONT
DESKTOP_DIR = BATTLES_DESKTOP_DIR
ACTIONS_DIR = DESKTOP_DIR / "actions"
WECHAT_DIR = ACTIONS_DIR / "wechat-emoji"


def zone_dir(zone_id: str, slug: str) -> Path:
    """Desktop folder for one battle zone, e.g. 01-desk-stare."""
    return DESKTOP_DIR / f"{zone_id}-{slug}"
