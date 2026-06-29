"""Diagnose Playwright bundled Chromium launch (dev or frozen layout)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from file_reader.platform_browser.playwright_env import (
    bundled_chromium_executable,
    configure_playwright_runtime,
)

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


def main() -> int:
    if sync_playwright is None:
        print("playwright not installed")
        return 1

    driver_root = configure_playwright_runtime()
    chrome = bundled_chromium_executable()
    print(f"driver root: {driver_root}")
    print(f"bundled chrome.exe: {chrome}")
    print(f"frozen={getattr(sys, 'frozen', False)} meipass={getattr(sys, '_MEIPASS', '')}")

    profile = Path.cwd() / ".mg-pw-diagnose"
    profile.mkdir(parents=True, exist_ok=True)
    started = time.time()
    try:
        with sync_playwright() as pw:
            print(f"sync_playwright ok in {time.time() - started:.1f}s")
            if chrome is None:
                raise RuntimeError("bundled Chromium not found")
            t0 = time.time()
            context = pw.chromium.launch_persistent_context(
                str(profile),
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            print(f"launch_persistent_context ok in {time.time() - t0:.1f}s pages={len(context.pages)}")
            context.close()
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        print(f"FAILED after {time.time() - started:.1f}s: {exc}")
        return 1
    print("SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
