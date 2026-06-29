"""Playwright-backed platform browser using bundled Chromium."""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from typing import Any, Callable, Optional

from file_reader.platform_browser.chromium_launcher import launch_chromium_context
from file_reader.platform_browser.cookie_view import CookieView, normalize_cookie
from file_reader.platform_browser.playwright_env import (
    bundled_chromium_executable,
    configure_playwright_runtime,
    playwright_driver_root,
)
from file_reader.platform_browser.webview_host import LoadedCallback, ResourceHookFailedCallback, ResourceUrlCallback
from file_reader.platform_browser.youtube_po import is_youtube_stream_capture_url
from file_reader.smartedu.debug_log import log_platform_browser, redact_url_for_log
from file_reader.smartedu_browser import DEFAULT_HOME_URL, playwright_storage_path
from file_reader.tencent_meeting.url_parser import is_tencent_media_url
from file_reader.wechat_channels.url_parser import is_channels_media_url

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:
    PlaywrightError = None
    sync_playwright = None

ReadyCallback = Callable[[], None]
InitFailedCallback = Callable[[str], None]

_COMMAND_TIMEOUT_S = 45.0
_INIT_WATCHDOG_MS = 45000
_THREAD_JOIN_S = 5.0


def unwrap_browser_command_result(result: Any) -> Any:
    """Raise command failures returned from the browser worker thread."""
    if isinstance(result, BaseException):
        raise result
    return result


def _command_error_types() -> tuple[type[BaseException], ...]:
    types: tuple[type[BaseException], ...] = (RuntimeError, OSError, ValueError, TimeoutError)
    if PlaywrightError is not None:
        return types + (PlaywrightError,)
    return types


class _Command:
    __slots__ = ("args", "kind", "reply")

    def __init__(self, kind: str, *args: object, reply: queue.Queue[Any] | None = None) -> None:
        self.kind = kind
        self.args = args
        self.reply = reply


class PlaywrightPlatformBrowser:
    """Control a persistent Chromium window from the tkinter panel."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_loaded: Optional[LoadedCallback] = None,
        on_resource_url: Optional[ResourceUrlCallback] = None,
        on_resource_hook_failed: Optional[ResourceHookFailedCallback] = None,
        on_ready: Optional[ReadyCallback] = None,
        on_init_failed: Optional[InitFailedCallback] = None,
        hint_text: str = "",
    ) -> None:
        del on_resource_hook_failed  # Playwright captures media via response events.
        self._on_loaded = on_loaded
        self._on_resource_url = on_resource_url
        self._on_ready = on_ready
        self._on_init_failed = on_init_failed
        self._ready = False
        self._init_failed = False
        self._stop = threading.Event()
        self._commands: queue.Queue[_Command | None] = queue.Queue()
        self._active_page: Any = None
        self._watchdog_after_id: Optional[str] = None
        self._widget = tk.Label(
            parent,
            bg="#f3f4f6",
            fg="#4b5563",
            font=("Segoe UI", 11),
            wraplength=560,
            justify="center",
            text=hint_text,
        )
        self._widget.pack(fill="both", expand=True)
        self._thread = threading.Thread(target=self._run_loop, name="playwright-browser", daemon=True)
        self._thread.start()
        self._schedule_init_watchdog()

    @property
    def widget(self) -> tk.Label:
        """Placeholder label shown inside the panel."""
        return self._widget

    @property
    def is_operational(self) -> bool:
        """Return True once the external browser window is ready."""
        return self._ready

    @property
    def supports_resource_hook_failure(self) -> bool:
        """Playwright always captures media via response events."""
        return False

    def set_hint_text(self, text: str) -> None:
        """Update the in-panel hint shown beside the external browser window."""
        try:
            self._widget.configure(text=text)
        except tk.TclError:
            pass

    def load_url(self, url: str) -> None:
        """Navigate the external browser to a URL."""
        self._dispatch("load_url", url)

    def reload(self) -> None:
        """Reload the current page in the external browser."""
        self._dispatch("reload")

    def go_back(self) -> None:
        """Navigate back in the external browser."""
        self._dispatch("go_back")

    def go_forward(self) -> None:
        """Navigate forward in the external browser."""
        self._dispatch("go_forward")

    def evaluate_js(self, script: str) -> Any:
        """Evaluate JavaScript in the active page."""
        return self._dispatch("evaluate_js", script, expect_result=True)

    def get_current_url(self) -> str:
        """Return the active page URL."""
        result = self._dispatch("get_current_url", expect_result=True)
        return str(result or "")

    def get_cookies(self) -> list[CookieView]:
        """Return cookies from the persistent browser profile."""
        result = self._dispatch("get_cookies", expect_result=True)
        if not isinstance(result, list):
            return []
        return [normalize_cookie(item) for item in result]

    def destroy(self) -> None:
        """Close the external browser and remove the placeholder widget."""
        self._cancel_init_watchdog()
        self._ready = False
        self._stop.set()
        self._commands.put(None)
        if self._thread.is_alive():
            self._thread.join(timeout=_THREAD_JOIN_S)
        try:
            self._widget.destroy()
        except (RuntimeError, tk.TclError):
            pass

    def _dispatch(self, kind: str, *args: object, expect_result: bool = False) -> Any:
        if not self._ready:
            return None if expect_result else None
        reply: queue.Queue[Any] | None = queue.Queue(maxsize=1) if expect_result else None
        self._commands.put(_Command(kind, *args, reply=reply))
        if reply is None:
            return None
        try:
            result = reply.get(timeout=_COMMAND_TIMEOUT_S)
        except queue.Empty as exc:
            raise TimeoutError(f"browser command timed out: {kind}") from exc
        return unwrap_browser_command_result(result)

    def _run_loop(self) -> None:
        if sys.platform != "win32":
            self._fail_init("Playwright browser requires Windows")
            return
        if sync_playwright is None or PlaywrightError is None:
            self._fail_init("playwright is not installed")
            return

        driver_root = configure_playwright_runtime()
        log_platform_browser(f"playwright driver root={driver_root}")
        user_data = str(playwright_storage_path().resolve())
        try:
            with sync_playwright() as playwright:
                log_platform_browser("playwright driver started")
                context = launch_chromium_context(
                    playwright,
                    user_data,
                    DEFAULT_HOME_URL,
                    cancel_event=self._stop,
                )
                page = context.pages[0] if context.pages else context.new_page()
                self._bind_page(page)
                context.on("page", self._bind_page)
                self._ready = True
                log_platform_browser("playwright browser ready")
                self._cancel_init_watchdog()
                self._notify_ready()
                self._serve(context)
                try:
                    context.close()
                except PlaywrightError as exc:
                    log_platform_browser(f"playwright context close: {exc}", level="WARN")
        except PlaywrightError as exc:
            self._fail_init(str(exc))
        except (RuntimeError, OSError, ValueError, TimeoutError) as exc:
            self._fail_init(str(exc))

    def _bind_page(self, page: Any) -> None:
        page.on("response", self._handle_response)
        page.on("load", lambda: self._on_page_load(page))

    def _on_page_load(self, page: Any) -> None:
        """Track the tab the user is viewing (most recently loaded page)."""
        self._active_page = page
        if self._on_loaded is None:
            return
        self._marshal_to_ui(self._on_loaded)

    def _serve(self, context: Any) -> None:
        while not self._stop.is_set():
            try:
                command = self._commands.get(timeout=0.2)
            except queue.Empty:
                continue
            if command is None:
                break
            try:
                result = self._execute(context, command)
            except _command_error_types() as exc:
                log_platform_browser(f"playwright command failed {command.kind}: {exc}", level="WARN")
                result = exc
            if command.reply is not None:
                command.reply.put(result)

    def _execute(self, context: Any, command: _Command) -> Any:
        page = self._active_page
        if page is None:
            raise RuntimeError("browser page not ready")
        kind = command.kind
        if kind == "load_url":
            url = str(command.args[0])
            log_platform_browser(f"navigate {redact_url_for_log(url)}")
            page.goto(url, wait_until="domcontentloaded")
            return None
        if kind == "reload":
            page.reload(wait_until="domcontentloaded")
            return None
        if kind == "go_back":
            page.go_back(wait_until="domcontentloaded")
            return None
        if kind == "go_forward":
            page.go_forward(wait_until="domcontentloaded")
            return None
        if kind == "evaluate_js":
            script = str(command.args[0])
            return page.evaluate(script)
        if kind == "get_current_url":
            return page.url
        if kind == "get_cookies":
            return context.cookies()
        raise ValueError(f"unsupported browser command: {kind}")

    def _handle_response(self, response: Any) -> None:
        if self._on_resource_url is None:
            return
        try:
            uri = str(response.url)
        except (RuntimeError, OSError, AttributeError, TypeError):
            return
        if not is_tencent_media_url(uri) and not is_youtube_stream_capture_url(uri) and not is_channels_media_url(uri):
            return
        log_platform_browser(f"captured resource URL {redact_url_for_log(uri)}")
        on_resource_url = self._on_resource_url
        if on_resource_url is not None:
            self._marshal_to_ui(lambda: on_resource_url(uri))

    def _schedule_init_watchdog(self) -> None:
        try:
            root = self._widget.winfo_toplevel()
            self._watchdog_after_id = root.after(_INIT_WATCHDOG_MS, self._init_watchdog)
        except tk.TclError:
            self._watchdog_after_id = None

    def _cancel_init_watchdog(self) -> None:
        if self._watchdog_after_id is None:
            return
        try:
            self._widget.winfo_toplevel().after_cancel(self._watchdog_after_id)
        except tk.TclError:
            pass
        self._watchdog_after_id = None

    def _init_watchdog(self) -> None:
        self._watchdog_after_id = None
        if self._ready or self._init_failed or self._stop.is_set():
            return
        detail = "Chromium did not start within 45s"
        if playwright_driver_root() is None:
            detail = f"{detail} — Playwright driver missing in frozen bundle"
        elif bundled_chromium_executable() is None:
            detail = f"{detail} — bundled Chromium missing (rebuild with playwright install chromium)"
        self._fail_init(detail)

    def _marshal_to_ui(self, callback: Callable[[], None]) -> None:
        try:
            root = self._widget.winfo_toplevel()
            root.after(0, callback)
        except tk.TclError:
            callback()

    def _notify_ready(self) -> None:
        if self._on_ready is None:
            return
        self._marshal_to_ui(self._on_ready)

    def _fail_init(self, detail: str) -> None:
        if self._init_failed:
            return
        self._init_failed = True
        self._cancel_init_watchdog()
        log_platform_browser(f"playwright init failed: {detail}", level="ERROR")
        if self._on_init_failed is None:
            return
        on_init_failed = self._on_init_failed
        self._marshal_to_ui(lambda: on_init_failed(detail))


def playwright_available() -> bool:
    """Return True when Playwright can be imported on this platform."""
    return sys.platform == "win32" and sync_playwright is not None
