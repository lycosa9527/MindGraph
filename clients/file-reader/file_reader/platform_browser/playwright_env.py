"""Playwright runtime configuration for dev and frozen (PyInstaller) builds."""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

try:
    import playwright
except ImportError:
    playwright = None


def playwright_driver_root() -> Path | None:
    """Return the Playwright driver directory when present on disk."""
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        bundled = meipass / "playwright" / "driver"
        if bundled.is_dir():
            return bundled
    if playwright is None:
        return None
    root = Path(inspect.getfile(playwright)).resolve().parent / "driver"
    if root.is_dir():
        return root
    return None


def bundled_chromium_root() -> Path | None:
    """Return the Playwright local-browsers directory when Chromium is installed."""
    driver_root = playwright_driver_root()
    if driver_root is None:
        return None
    local_browsers = driver_root / "package" / ".local-browsers"
    if local_browsers.is_dir():
        return local_browsers
    return None


def bundled_chromium_executable() -> Path | None:
    """Return chrome.exe from a bundled Playwright Chromium install."""
    root = bundled_chromium_root()
    if root is None:
        return None
    patterns = ("chromium-*/chrome-win64/chrome.exe", "chromium-*/chrome-win/chrome.exe")
    for pattern in patterns:
        for candidate in root.glob(pattern):
            if candidate.is_file():
                return candidate
    return None


def configure_playwright_runtime() -> Path | None:
    """Configure env vars so the bundled Playwright Node driver is discoverable."""
    driver_root = playwright_driver_root()
    if driver_root is None:
        return None
    node_exe = driver_root / "node.exe"
    if node_exe.is_file():
        os.environ["PLAYWRIGHT_NODEJS_PATH"] = str(node_exe)
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")
    return driver_root
