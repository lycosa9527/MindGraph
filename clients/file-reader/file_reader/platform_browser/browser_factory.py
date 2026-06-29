"""Select the platform browser backend."""

from __future__ import annotations

import os
import sys
from typing import Any, Callable, Optional

import tkinter as tk

from file_reader.platform_browser.playwright_host import PlaywrightPlatformBrowser, playwright_available
from file_reader.platform_browser.webview_host import EmbeddedPlatformBrowser, webview_runtime_available
from file_reader.smartedu.debug_log import log_platform_browser

ReadyCallback = Callable[[], None]
InitFailedCallback = Callable[[str], None]
LoadedCallback = Callable[[], None]
ResourceUrlCallback = Callable[[str], None]
ResourceHookFailedCallback = Callable[[], None]


def preferred_browser_backend() -> str:
    """Return configured backend name: playwright or webview2."""
    value = os.environ.get("MINDGRAPH_BROWSER", "playwright").strip().lower()
    if value in {"playwright", "webview2"}:
        return value
    log_platform_browser(f"unknown MINDGRAPH_BROWSER={value!r}; using playwright", level="WARN")
    return "playwright"


def create_platform_browser(
    parent: tk.Misc,
    *,
    on_loaded: Optional[LoadedCallback] = None,
    on_resource_url: Optional[ResourceUrlCallback] = None,
    on_resource_hook_failed: Optional[ResourceHookFailedCallback] = None,
    on_ready: Optional[ReadyCallback] = None,
    on_init_failed: Optional[InitFailedCallback] = None,
    hint_text: str = "",
) -> Any:
    """Create the configured browser host for the platform tab."""
    backend = preferred_browser_backend()
    if backend == "webview2" and sys.platform == "win32" and webview_runtime_available():
        return EmbeddedPlatformBrowser(
            parent,
            on_loaded=on_loaded,
            on_resource_url=on_resource_url,
            on_resource_hook_failed=on_resource_hook_failed,
        )
    if playwright_available():
        return PlaywrightPlatformBrowser(
            parent,
            on_loaded=on_loaded,
            on_resource_url=on_resource_url,
            on_resource_hook_failed=on_resource_hook_failed,
            on_ready=on_ready,
            on_init_failed=on_init_failed,
            hint_text=hint_text,
        )
    if sys.platform == "win32" and webview_runtime_available():
        return EmbeddedPlatformBrowser(
            parent,
            on_loaded=on_loaded,
            on_resource_url=on_resource_url,
            on_resource_hook_failed=on_resource_hook_failed,
        )
    raise RuntimeError("No supported browser backend is available")
