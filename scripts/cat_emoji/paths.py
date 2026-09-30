"""Repo green-screen stills plus Pictures/mascots export folders."""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[1]
STILLS_DIR = PACKAGE_DIR / "stills"
BLACK_STILLS_DIR = STILLS_DIR / "black"
WHITE_STILLS_DIR = STILLS_DIR / "white"
SIAMESE_STILLS_DIR = STILLS_DIR / "siamese"
RAVEN_STILLS_DIR = STILLS_DIR / "raven"
SCHNAUZER_STILLS_DIR = STILLS_DIR / "schnauzer"
BLACK_STILL_FRONT = BLACK_STILLS_DIR / "fullbody-still-noptr-2.png"
BLACK_STILL_THREE_QUARTER = BLACK_STILLS_DIR / "fullbody-still-noptr-1.png"
WHITE_STILL_FRONT = WHITE_STILLS_DIR / "fullbody-still-noptr-2.png"
WHITE_STILL_THREE_QUARTER = WHITE_STILLS_DIR / "fullbody-still-noptr-1.png"
SIAMESE_STILL_FRONT = SIAMESE_STILLS_DIR / "fullbody-still-noptr-2.png"
SIAMESE_STILL_THREE_QUARTER = SIAMESE_STILLS_DIR / "fullbody-still-noptr-1.png"
RAVEN_STILL_FRONT = RAVEN_STILLS_DIR / "fullbody-still-noptr-2.png"
RAVEN_STILL_THREE_QUARTER = RAVEN_STILLS_DIR / "fullbody-still-noptr-1.png"
SCHNAUZER_STILL_FRONT = SCHNAUZER_STILLS_DIR / "fullbody-still-noptr-2.png"
SCHNAUZER_STILL_THREE_QUARTER = SCHNAUZER_STILLS_DIR / "fullbody-still-noptr-1.png"
MASCOTS_DIR = Path("/mnt/c/Users/roywa/Pictures/mascots")
BLACK_DESKTOP_DIR = MASCOTS_DIR / "black-cat-mascot"
WHITE_DESKTOP_DIR = MASCOTS_DIR / "white-cat-mascot"
SIAMESE_DESKTOP_DIR = MASCOTS_DIR / "siamese-cat-mascot"
BATTLES_DESKTOP_DIR = MASCOTS_DIR / "cat-office-battles"
