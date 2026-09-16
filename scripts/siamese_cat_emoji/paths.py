"""Repo green-screen stills, Pictures exports, and local Wan scratch."""

from __future__ import annotations

from pathlib import Path

from scripts.cat_emoji.paths import (
    SIAMESE_DESKTOP_DIR,
    SIAMESE_STILL_FRONT,
    SIAMESE_STILL_THREE_QUARTER,
    SIAMESE_STILLS_DIR,
)

PACKAGE_DIR = Path(__file__).resolve().parent
WORK_DIR = PACKAGE_DIR / ".work"
EXPORT_DIR = SIAMESE_DESKTOP_DIR
STILL_FRONT = SIAMESE_STILL_FRONT
STILL_THREE_QUARTER = SIAMESE_STILL_THREE_QUARTER
STILLS_DIR = SIAMESE_STILLS_DIR
OUT_DIR = EXPORT_DIR / "actions"
WECHAT_DIR = OUT_DIR / "wechat-emoji"
STILL_SIZE = "1280*1920"


def still_filename(variant: str) -> str:
    """Return fullbody-still-noptr-1.png or -2.png."""
    if variant in {"1", "three-quarter", "3q"}:
        return "fullbody-still-noptr-1.png"
    if variant in {"2", "front", ""}:
        return "fullbody-still-noptr-2.png"
    raise ValueError(f"Unknown still variant: {variant}")


def export_still_path(variant: str) -> Path:
    """Pictures/mascots green-screen still."""
    return EXPORT_DIR / still_filename(variant)


def repo_still_path(variant: str) -> Path:
    """Committed still used later as the I2V first frame."""
    if variant in {"1", "three-quarter", "3q"}:
        return STILL_THREE_QUARTER
    if variant in {"2", "front", ""}:
        return STILL_FRONT
    raise ValueError(f"Unknown still variant: {variant}")


def still_path(variant: str) -> Path:
    """Prefer the repo still; fall back to the Pictures export."""
    repo = repo_still_path(variant)
    if repo.is_file():
        return repo
    return export_still_path(variant)
