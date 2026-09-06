"""Repo green-screen stills, desktop exports, and local Wan scratch."""

from __future__ import annotations

from pathlib import Path

from scripts.cat_emoji.paths import (
    WHITE_DESKTOP_DIR,
    WHITE_STILL_FRONT,
    WHITE_STILL_THREE_QUARTER,
)

PACKAGE_DIR = Path(__file__).resolve().parent
WORK_DIR = PACKAGE_DIR / ".work"
DESKTOP_DIR = WHITE_DESKTOP_DIR
STILL_FRONT = WHITE_STILL_FRONT
STILL_THREE_QUARTER = WHITE_STILL_THREE_QUARTER
OUT_DIR = DESKTOP_DIR / "actions"
WECHAT_DIR = OUT_DIR / "wechat-emoji"


def still_path(variant: str) -> Path:
    """Return the front idle (2) or 3/4 (1) green-screen still."""
    if variant in {"1", "three-quarter", "3q"}:
        return STILL_THREE_QUARTER
    if variant in {"2", "front", ""}:
        return STILL_FRONT
    raise ValueError(f"Unknown still variant: {variant}")
