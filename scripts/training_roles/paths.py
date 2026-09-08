"""Repo paths for packed stills, public WebPs, and local Wan scratch."""

from __future__ import annotations

from pathlib import Path

from scripts.cat_emoji.paths import (
    BLACK_STILL_FRONT,
    BLACK_STILL_THREE_QUARTER,
    BLACK_STILLS_DIR,
    REPO_ROOT,
)

PACKAGE_DIR = Path(__file__).resolve().parent
STILLS_DIR = BLACK_STILLS_DIR
WORK_DIR = PACKAGE_DIR / ".work"
PUBLIC_ROLES_DIR = REPO_ROOT / "frontend" / "public" / "training" / "roles"
ENV_PATH = REPO_ROOT / ".env"

STILL_FRONT = BLACK_STILL_FRONT
STILL_THREE_QUARTER = BLACK_STILL_THREE_QUARTER


def still_path(variant: str) -> Path:
    """Return the front idle (2) or 3/4 (1) green-screen still."""
    if variant in {"1", "three-quarter", "3q"}:
        return STILL_THREE_QUARTER
    if variant in {"2", "front", ""}:
        return STILL_FRONT
    raise ValueError(f"Unknown still variant: {variant}")
