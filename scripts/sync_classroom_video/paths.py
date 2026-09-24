"""Mascot stills, local scratch, and Pictures/mascots publish folder."""

from __future__ import annotations

from pathlib import Path

from scripts.cat_emoji.paths import MASCOTS_DIR, REPO_ROOT

PACKAGE_DIR = Path(__file__).resolve().parent
WORK_DIR = PACKAGE_DIR / ".work"
DESKTOP_DIR = MASCOTS_DIR / "sync-classroom"
ENV_PATH = REPO_ROOT / ".env"
STILL_NAME = "fullbody-still-noptr-2.png"
SKIP_FOLDERS = frozenset(
    {
        "auth-login",
        "cat-office-battles",
        "sync-classroom",
    }
)
