"""Repo green-screen stills plus desktop export folders."""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[1]
STILLS_DIR = PACKAGE_DIR / "stills"
BLACK_STILLS_DIR = STILLS_DIR / "black"
WHITE_STILLS_DIR = STILLS_DIR / "white"
BLACK_STILL_FRONT = BLACK_STILLS_DIR / "fullbody-still-noptr-2.png"
BLACK_STILL_THREE_QUARTER = BLACK_STILLS_DIR / "fullbody-still-noptr-1.png"
WHITE_STILL_FRONT = WHITE_STILLS_DIR / "fullbody-still-noptr-2.png"
WHITE_STILL_THREE_QUARTER = WHITE_STILLS_DIR / "fullbody-still-noptr-1.png"
BLACK_DESKTOP_DIR = Path("/mnt/c/Users/roywa/Desktop/black-cat-mascot")
WHITE_DESKTOP_DIR = Path("/mnt/c/Users/roywa/Desktop/white-cat-mascot")
BATTLES_DESKTOP_DIR = Path("/mnt/c/Users/roywa/Desktop/cat-office-battles")
