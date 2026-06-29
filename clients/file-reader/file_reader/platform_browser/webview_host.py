"""Embedded WebView2 host using tkwebview2 on Windows."""

from __future__ import annotations

import sys
import tkinter as tk
from typing import Any, Callable, Optional

from file_reader.smartedu.debug_log import log_platform_browser, redact_url_for_log
from file_reader.smartedu_browser import DEFAULT_HOME_URL, browser_storage_path, configure_webview_storage
from file_reader.platform_browser.youtube_po import is_youtube_stream_capture_url
from file_reader.tencent_meeting.url_parser import is_tencent_media_url
from file_reader.wechat_channels.url_parser import is_channels_media_url

try:
    from tkwebview2.tkwebview2 import WebView2, have_runtime, install_runtime
except ImportError:
    WebView2 = None

    def have_runtime() -> bool:
        """Return False when tkwebview2 is not installed."""
        return False

    def install_runtime() -> None:
        """No-op when tkwebview2 is not installed."""
        return None


try:
    from Python.Runtime import PythonException as NetPythonException
except ImportError:
    NetPythonException = None


def _webview_init_errors() -> tuple[type[BaseException], ...]:
    """Exception types raised while creating the embedded WebView2 widget."""
    types: tuple[type[BaseException], ...] = (
        RuntimeError,
        OSError,
        ValueError,
        TypeError,
        ImportError,
        AttributeError,
    )
    if NetPythonException is not None:
        return types + (NetPythonException,)
    return types


def webview_init_error_types() -> tuple[type[BaseException], ...]:
    """Return exception types that WebView2 creation may raise."""
    return _webview_init_errors()


LoadedCallback = Callable[[], None]
ResourceUrlCallback = Callable[[str], None]
ResourceHookFailedCallback = Callable[[], None]


class _WebViewStorageState:
    """Process-wide guard so user-data folder is configured once."""

    configured = False


class EmbeddedPlatformBrowser:
    """Thin adapter over tkwebview2 with pywebview-compatible helpers."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_loaded: Optional[LoadedCallback] = None,
        on_resource_url: Optional[ResourceUrlCallback] = None,
        on_resource_hook_failed: Optional[ResourceHookFailedCallback] = None,
    ) -> None:
        self._on_loaded = on_loaded
        self._on_resource_url = on_resource_url
        self._on_resource_hook_failed = on_resource_hook_failed
        self._widget: Any = None
        self._window: Any = None
        self._loaded_bound = False
        self._core_hook_bound = False
        self._init_widget(parent)

    @property
    def widget(self) -> Any:
        """Underlying tkinter Frame/WebView2 widget."""
        return self._widget

    @property
    def is_operational(self) -> bool:
        """Return True when the embedded WebView2 widget was created."""
        return self._widget is not None

    @property
    def supports_resource_hook_failure(self) -> bool:
        """Embedded WebView2 can fail to attach CoreWebView2 resource hooks."""
        return True

    def load_url(self, url: str) -> None:
        """Navigate to a URL."""
        if self._widget is None:
            return
        log_platform_browser(f"navigate {redact_url_for_log(url)}")
        self._widget.load_url(url)

    def reload(self) -> None:
        """Reload the current page."""
        if self._widget is None:
            return
        if hasattr(self._widget, "reload"):
            self._widget.reload()
            return
        current = self.get_current_url() or DEFAULT_HOME_URL
        self.load_url(current)

    def go_back(self) -> None:
        """Navigate back if supported."""
        if self._widget is not None and hasattr(self._widget, "go_back"):
            self._widget.go_back()
            return
        self.evaluate_js("window.history.back()")

    def go_forward(self) -> None:
        """Navigate forward if supported."""
        if self._widget is not None and hasattr(self._widget, "go_forward"):
            self._widget.go_forward()
            return
        self.evaluate_js("window.history.forward()")

    def evaluate_js(self, script: str) -> Any:
        """Run JavaScript in the page."""
        if self._widget is None:
            return None
        return self._widget.evaluate_js(script)

    def get_current_url(self) -> str:
        """Return the active document URL."""
        if self._window is not None and hasattr(self._window, "get_current_url"):
            try:
                current = self._window.get_current_url()
            except (RuntimeError, OSError, ValueError, AttributeError):
                current = ""
            if current:
                return str(current)
        try:
            raw = self.evaluate_js("location.href")
        except (RuntimeError, OSError, ValueError, TypeError):
            return ""
        return str(raw or "")

    def get_cookies(self) -> list[Any]:
        """Return cookies from the embedded session."""
        if self._window is not None and hasattr(self._window, "get_cookies"):
            try:
                cookies = self._window.get_cookies()
            except (RuntimeError, OSError, AttributeError, TypeError):
                return []
            return list(cookies or [])
        return []

    def destroy(self) -> None:
        """Release the embedded browser widget."""
        if self._widget is not None:
            try:
                self._widget.destroy()
            except (RuntimeError, OSError, tk.TclError):
                pass
        self._widget = None
        self._window = None

    def _init_widget(self, parent: tk.Misc) -> None:
        if sys.platform != "win32":
            log_platform_browser("embedded browser requires Windows", level="WARN")
            return
        if WebView2 is None:
            log_platform_browser("tkwebview2 not installed", level="WARN")
            return
        if not have_runtime():
            log_platform_browser("WebView2 runtime missing; attempting install", level="WARN")
            try:
                install_runtime()
            except (RuntimeError, OSError, ValueError) as exc:
                log_platform_browser(f"WebView2 runtime install failed: {exc}", level="ERROR")
                return
        if not _WebViewStorageState.configured:
            storage = configure_webview_storage(browser_storage_path())
            log_platform_browser(f"init embedded browser storage={storage}")
            _WebViewStorageState.configured = True
        parent.update_idletasks()
        width = max(int(parent.winfo_width()), 640)
        height = max(int(parent.winfo_height()), 480)
        try:
            self._widget = WebView2(parent, width, height, url=DEFAULT_HOME_URL)
        except _webview_init_errors() as exc:
            log_platform_browser(f"WebView2 widget creation failed: {exc}", level="ERROR")
            return
        self._widget.pack(fill="both", expand=True)
        self._window = getattr(self._widget, "window", None)
        self._bind_loaded_event()
        self._bind_core_events()
        if self._window is not None and hasattr(self._window, "resize"):
            self._window.resize(width, height)

    def _bind_loaded_event(self) -> None:
        if self._loaded_bound or self._widget is None:
            return
        if hasattr(self._widget, "event_loaded"):
            self._widget.event_loaded(self._handle_loaded)
            self._loaded_bound = True
            return
        if self._window is not None and hasattr(self._window, "events"):
            self._window.events.loaded += self._handle_loaded
            self._loaded_bound = True

    def _bind_core_events(self) -> None:
        if self._core_hook_bound or self._widget is None or self._on_resource_url is None:
            return
        if hasattr(self._widget, "event_core_completed"):
            self._widget.event_core_completed(self._on_core_ready)
            self._core_hook_bound = True

    def _on_core_ready(self, sender: Any, _args: Any) -> None:
        if self._on_resource_url is None:
            return
        try:
            core = sender.CoreWebView2
            core.WebResourceResponseReceived += self._handle_resource_response
            log_platform_browser("WebView2 resource URL capture enabled")
        except (RuntimeError, OSError, AttributeError, TypeError) as exc:
            log_platform_browser(f"WebView2 resource hook failed: {exc}", level="WARN")
            if self._on_resource_hook_failed is not None:
                self._on_resource_hook_failed()

    def _handle_resource_response(self, _sender: Any, args: Any) -> None:
        if self._on_resource_url is None:
            return
        try:
            uri = str(args.Request.Uri)
        except (RuntimeError, OSError, AttributeError, TypeError):
            return
        if not is_tencent_media_url(uri) and not is_youtube_stream_capture_url(uri) and not is_channels_media_url(uri):
            return
        log_platform_browser(f"captured resource URL {redact_url_for_log(uri)}")
        self._on_resource_url(uri)

    def _handle_loaded(self, *_args: object) -> None:
        if self._on_loaded is not None:
            self._on_loaded()


def webview_runtime_available() -> bool:
    """Return True when tkwebview2 and WebView2 runtime are usable."""
    if sys.platform != "win32" or WebView2 is None:
        return False
    return bool(have_runtime())
