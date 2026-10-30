"""Scratch, Pictures, Desktop review, and packaged asset folders."""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[1]
WORK_DIR = PACKAGE_DIR / ".work"
ASSETS_DIR = REPO_ROOT / "clients" / "desktop-pet" / "assets"
DESKTOP_REVIEW_DIR = Path("/mnt/c/Users/roywa/Desktop/mindgraph-pet")
