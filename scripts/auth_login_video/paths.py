"""Repo stills, local scratch, desktop copies, and shipped public hero."""

from __future__ import annotations

from pathlib import Path

from scripts.cat_emoji.paths import (
    BLACK_STILL_FRONT,
    BLACK_STILL_THREE_QUARTER,
    MASCOTS_DIR,
    REPO_ROOT,
)

PACKAGE_DIR = Path(__file__).resolve().parent
WORK_DIR = PACKAGE_DIR / ".work"
DESKTOP_DIR = MASCOTS_DIR / "auth-login"
PUBLIC_AUTH_DIR = REPO_ROOT / "frontend" / "public" / "auth-hero"
SHIPPED_HERO = PUBLIC_AUTH_DIR / "login-hero.mp4"
SHIPPED_HERO_URL = "/auth-hero/login-hero.mp4"
SHIPPED_STILL = PUBLIC_AUTH_DIR / "login-hero.png"
SHIPPED_STILL_URL = "/auth-hero/login-hero.png"
STILL_OPTIONS_DIR = DESKTOP_DIR / "still-options"
ORIGINAL_STILLS_DIR = STILL_OPTIONS_DIR / "original"
BLACK_STILL = BLACK_STILL_FRONT
BLACK_STILL_SIDE = BLACK_STILL_THREE_QUARTER
