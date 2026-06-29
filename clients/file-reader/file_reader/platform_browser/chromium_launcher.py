"""Launch bundled Playwright Chromium with a persistent profile."""

from __future__ import annotations

from typing import Any

from file_reader.platform_browser.playwright_env import bundled_chromium_executable
from file_reader.smartedu.debug_log import log_platform_browser


def launch_chromium_context(
    playwright: Any,
    user_data: str,
    start_url: str,
    *,
    cancel_event: Any = None,
) -> Any:
    """Start bundled Chromium with a persistent profile and open the home URL."""
    if cancel_event is not None and cancel_event.is_set():
        raise RuntimeError("Chromium launch cancelled")
    chrome_exe = bundled_chromium_executable()
    if chrome_exe is None:
        raise RuntimeError("Bundled Chromium not found — run PLAYWRIGHT_BROWSERS_PATH=0 playwright install chromium")
    log_platform_browser(f"launch bundled Chromium profile={user_data} exe={chrome_exe.name}")
    context = playwright.chromium.launch_persistent_context(
        user_data,
        headless=False,
        args=["--disable-blink-features=AutomationControlled"],
    )
    page = context.pages[0] if context.pages else context.new_page()
    if start_url:
        page.goto(start_url, wait_until="domcontentloaded")
    return context
