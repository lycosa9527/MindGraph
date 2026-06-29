"""国家智慧教育平台 tab — platform browser with multi-site download detection."""

from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import Any, List, Optional

from file_reader.dpapi_store import DpapiError
from file_reader.i18n import I18n
from file_reader.platform_browser.cookie_jar import cleanup_stale_cookie_files
from file_reader.platform_browser.download_runner import download_detected_assets
from file_reader.platform_browser.models import DetectedAsset, ProbeContext
from file_reader.platform_browser.registry import probe_assets
from file_reader.platform_browser.sites import detect_platform, download_auth_ready, format_status_line
from file_reader.platform_browser.browser_factory import create_platform_browser
from file_reader.platform_browser.webview_host import webview_init_error_types
from file_reader.platform_browser.youtube_po import (
    YOUTUBE_PO_CLEANUP_JS,
    YOUTUBE_PO_HOOK_JS,
    YOUTUBE_PO_READ_JS,
    YouTubePoCapture,
    is_youtube_stream_capture_url,
    merge_youtube_po_capture,
)
from file_reader.tencent_meeting.url_parser import MEDIA_PROBE_JS, is_tencent_media_url, parse_media_urls
from file_reader.wechat_channels.models import CapturedChannelVideo
from file_reader.wechat_channels.url_parser import (
    CHANNELS_CLEANUP_JS,
    CHANNELS_HOOK_JS,
    CHANNELS_KEYSTREAM_JS,
    CHANNELS_READ_JS,
    is_channels_media_url,
    merge_channels_captures,
)
from file_reader.smartedu.debug_log import debug_log_path_display, log_platform_browser
from file_reader.smartedu.token_store import load_smartedu_token, save_smartedu_token
from file_reader.smartedu_browser import (
    DEFAULT_HOME_URL,
    LOGIN_STATE_JS,
    merge_cookie_login_flags,
    normalize_nav_url,
    parse_login_state,
)
from file_reader.smartedu_panel_download import open_asset_download_dialog, show_download_result
from file_reader.theme import (
    ACCENT,
    BG_APP,
    BG_CARD,
    BG_MUTED,
    BORDER,
    FONT_BODY,
    FONT_CAPTION,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

_POLL_MS = 3000
_PROBE_DEBOUNCE_MS = 1000
_IDLE_PROBE_MS = 2500
_NAV_SYNC_MS = 400


class SmartEduPanel(tk.Frame):
    """Browser-style panel for multi-platform browsing and downloads."""

    def __init__(self, master: tk.Misc, i18n: I18n) -> None:
        super().__init__(master, bg=BG_APP)
        self._i18n = i18n
        self._browser: Any = None
        self._busy = False
        self._probing = False
        self._pending_probe = False
        self._badge_count = 0
        self._token = load_smartedu_token()
        self._login_state: dict[str, Any] = {}
        self._detected_assets: List[DetectedAsset] = []
        self._captured_media_urls: tuple[str, ...] = ()
        self._captured_channels_videos: tuple = ()
        self._youtube_po_capture: YouTubePoCapture | None = None
        self._probe_status_hint = ""
        self._last_probe_url = ""
        self._poll_after_id: Optional[str] = None
        self._probe_after_id: Optional[str] = None
        self._idle_probe_after_id: Optional[str] = None
        self._nav_sync_after_id: Optional[str] = None
        self._probe_generation = 0
        self._resource_capture_enabled = True
        self._download_cancel = threading.Event()
        self._browser_init_state = "pending"
        self._browser_init_timeout_id: Optional[str] = None

        self._url_var = tk.StringVar(value=DEFAULT_HOME_URL)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = tk.Frame(self, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        toolbar.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 4))
        toolbar.columnconfigure(3, weight=1)

        self._back_btn = tk.Button(
            toolbar,
            text="←",
            font=FONT_BODY,
            relief="flat",
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
            padx=8,
            pady=4,
            command=self._nav_back,
        )
        self._back_btn.grid(row=0, column=0, padx=(8, 2), pady=8)
        self._forward_btn = tk.Button(
            toolbar,
            text="→",
            font=FONT_BODY,
            relief="flat",
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
            padx=8,
            pady=4,
            command=self._nav_forward,
        )
        self._forward_btn.grid(row=0, column=1, padx=2, pady=8)
        self._refresh_btn = tk.Button(
            toolbar,
            text="↻",
            font=FONT_BODY,
            relief="flat",
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
            padx=8,
            pady=4,
            command=self._nav_refresh,
        )
        self._refresh_btn.grid(row=0, column=2, padx=(2, 8), pady=8)

        self._address = tk.Entry(
            toolbar,
            textvariable=self._url_var,
            font=FONT_BODY,
            relief="flat",
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
        )
        self._address.grid(row=0, column=3, sticky="ew", ipady=6, pady=8)
        self._address.bind("<Return>", lambda _event: self._navigate_address())

        download_wrap = tk.Frame(toolbar, bg=BG_CARD)
        download_wrap.grid(row=0, column=4, padx=(8, 8), pady=8)
        self._download_btn = tk.Button(
            download_wrap,
            font=FONT_BODY,
            relief="flat",
            bg=ACCENT,
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            padx=12,
            pady=6,
            command=self._download_current,
        )
        self._download_btn.pack()
        self._badge = tk.Label(
            download_wrap,
            text="",
            bg="#dc2626",
            fg="#ffffff",
            font=FONT_CAPTION,
            padx=4,
            pady=0,
        )
        self._badge.place(relx=1.0, x=4, y=-4, anchor="ne")
        self._badge.place_forget()

        self._cancel_btn = tk.Button(
            toolbar,
            font=FONT_BODY,
            relief="flat",
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
            padx=10,
            pady=6,
            command=self._cancel_download,
        )
        self._cancel_btn.grid(row=0, column=5, padx=(0, 8), pady=8)
        self._cancel_btn.grid_remove()

        self._browser_host = tk.Frame(self, bg=BG_MUTED, highlightbackground=BORDER, highlightthickness=1)
        self._browser_host.grid(row=1, column=0, sticky="nsew")

        self._fallback = tk.Label(
            self._browser_host,
            bg=BG_MUTED,
            fg=TEXT_SECONDARY,
            font=FONT_BODY,
            wraplength=520,
            justify="center",
        )
        self._fallback.place(relx=0.5, rely=0.5, anchor="center")

        status = tk.Frame(self, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        status.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        status.columnconfigure(0, weight=1)

        self._platform_status = tk.Label(
            status,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=FONT_BODY,
            anchor="w",
            justify="left",
        )
        self._platform_status.grid(row=0, column=0, sticky="ew", padx=12, pady=8)

        self.apply_texts()
        self._refresh_status_labels()
        self._fallback.configure(text=self._i18n.translate("smartedu.browser_tab_pending"))

    def _browser_is_ready(self) -> bool:
        if self._browser is None:
            return False
        if hasattr(self._browser, "is_operational"):
            return bool(self._browser.is_operational)
        return self._browser.widget is not None

    def _browser_supports_resource_hook_failure(self) -> bool:
        if self._browser is None:
            return False
        return bool(getattr(self._browser, "supports_resource_hook_failure", False))

    def set_tab_visible(self, visible: bool) -> None:
        """Lazy-init the platform browser when the SmartEdu tab is shown."""
        if not visible:
            return
        if self._browser_init_state == "ready":
            return
        if self._browser_init_state == "loading":
            return
        if self._browser_init_state == "failed":
            if self._browser is not None:
                self._browser.destroy()
                self._browser = None
            log_platform_browser("browser init retry after failure")
        self._browser_init_state = "loading"
        self._fallback.configure(text=self._i18n.translate("smartedu.browser_loading"))
        self._fallback.place(relx=0.5, rely=0.5, anchor="center")
        if self._browser_init_timeout_id is not None:
            self.after_cancel(self._browser_init_timeout_id)
        self._browser_init_timeout_id = self.after(45000, self._browser_init_timeout)
        self.after(200, self._begin_browser_init)

    def apply_texts(self) -> None:
        """Refresh labels for the active locale."""
        self._download_btn.configure(text=self._i18n.translate("smartedu.browser_download"))
        self._cancel_btn.configure(text=self._i18n.translate("smartedu.download_cancel"))
        if self._browser_init_state == "pending":
            self._fallback.configure(text=self._i18n.translate("smartedu.browser_tab_pending"))
        if self._browser is not None and hasattr(self._browser, "set_hint_text"):
            self._browser.set_hint_text(self._i18n.translate("smartedu.browser_external_hint"))
        self._refresh_status_labels()

    def is_busy(self) -> bool:
        """True while a download is running."""
        return self._busy

    def shutdown(self) -> None:
        """Stop background polling and close the platform browser."""
        if self._browser_init_timeout_id is not None:
            self.after_cancel(self._browser_init_timeout_id)
            self._browser_init_timeout_id = None
        if self._poll_after_id is not None:
            self.after_cancel(self._poll_after_id)
            self._poll_after_id = None
        if self._probe_after_id is not None:
            self.after_cancel(self._probe_after_id)
            self._probe_after_id = None
        if self._idle_probe_after_id is not None:
            self.after_cancel(self._idle_probe_after_id)
            self._idle_probe_after_id = None
        if self._nav_sync_after_id is not None:
            self.after_cancel(self._nav_sync_after_id)
            self._nav_sync_after_id = None
        if self._browser is not None:
            self._browser.destroy()
            self._browser = None
        log_platform_browser("panel shutdown")

    def _begin_browser_init(self) -> None:
        if self._browser_init_state != "loading":
            return
        self._browser_host.update_idletasks()
        log_platform_browser("browser init from visible tab")
        try:
            self._init_browser()
        except webview_init_error_types() as exc:
            log_platform_browser(f"browser init crashed: {exc}", level="ERROR")
            self._show_browser_failed(str(exc))

    def _finish_browser_init(self) -> None:
        if self._browser_init_state != "loading":
            return
        if not self._browser_is_ready():
            log_platform_browser("browser host not operational after ready callback", level="ERROR")
            self._show_browser_failed("browser not operational")
            return
        if self._browser_init_timeout_id is not None:
            self.after_cancel(self._browser_init_timeout_id)
            self._browser_init_timeout_id = None
        self._browser_init_state = "ready"
        self._fallback.place_forget()
        self._set_toolbar_state(True)
        self._schedule_poll()
        self._schedule_idle_probe()
        log_platform_browser("platform browser ready")

    def _browser_init_timeout(self) -> None:
        self._browser_init_timeout_id = None
        if self._browser_init_state == "loading":
            log_platform_browser("browser init timed out", level="ERROR")
            self._show_browser_failed("timeout")

    def _show_browser_failed(self, detail: str) -> None:
        if self._browser_init_timeout_id is not None:
            self.after_cancel(self._browser_init_timeout_id)
            self._browser_init_timeout_id = None
        self._browser_init_state = "failed"
        message = self._i18n.translate("smartedu.browser_unavailable")
        message = f"{message}\n{detail}\n{debug_log_path_display()}"
        self._fallback.configure(text=message)
        self._fallback.place(relx=0.5, rely=0.5, anchor="center")
        self._set_toolbar_state(False)

    def _init_browser(self) -> None:
        cleanup_stale_cookie_files()
        log_platform_browser("browser init start")
        try:
            self._browser = create_platform_browser(
                self._browser_host,
                on_loaded=self._on_page_loaded,
                on_resource_url=self._capture_resource_url,
                on_resource_hook_failed=self._on_resource_hook_failed,
                on_ready=self._finish_browser_init,
                on_init_failed=self._show_browser_failed,
                hint_text=self._i18n.translate("smartedu.browser_external_hint"),
            )
        except (RuntimeError, OSError, ValueError, TypeError) as exc:
            log_platform_browser(f"create_platform_browser failed: {exc}", level="ERROR")
            self._show_browser_failed(str(exc))
            return
        if self._browser.is_operational:
            self._finish_browser_init()
            return
        if self._browser.widget is None:
            self._show_browser_failed("browser backend unavailable")
            return
        self._fallback.place_forget()

    def _compute_download_ready(self) -> bool:
        """Return True when the current page has downloadable assets and auth."""
        if self._busy or not self._browser_is_ready():
            return False
        if not self._detected_assets:
            return False
        site = detect_platform(self._url_var.get())
        return download_auth_ready(
            site,
            self._login_state,
            smartedu_token=self._token,
            asset_count=len(self._detected_assets),
        )

    def _set_toolbar_state(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled and not self._busy else tk.DISABLED
        for widget in (
            self._back_btn,
            self._forward_btn,
            self._refresh_btn,
            self._address,
        ):
            widget.configure(state=state)
        download_state = tk.NORMAL if enabled and self._compute_download_ready() else tk.DISABLED
        self._download_btn.configure(state=download_state)
        if self._busy:
            self._cancel_btn.grid()
        else:
            self._cancel_btn.grid_remove()

    def _cancel_download(self) -> None:
        self._download_cancel.set()
        log_platform_browser("download cancel requested", level="WARN")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._set_toolbar_state(True)

    def _update_badge(self) -> None:
        count = self._badge_count
        if count <= 0:
            self._badge.place_forget()
            return
        self._badge.configure(text=str(count))
        self._badge.place(relx=1.0, x=4, y=-4, anchor="ne")

    def _clear_download_detection(self) -> None:
        """Drop stale asset detection state for the previous page."""
        self._detected_assets = []
        self._badge_count = 0
        self._probe_status_hint = ""
        self._update_badge()
        self._set_toolbar_state(self._browser_is_ready())

    def _reset_detection_for_url(self, new_url: str) -> None:
        """Invalidate in-flight probes and platform capture when the page changes."""
        if self._busy:
            return
        normalized = new_url.strip()
        if not normalized or normalized == self._last_probe_url:
            return
        previous_site = detect_platform(self._last_probe_url) if self._last_probe_url else None
        self._last_probe_url = normalized
        self._probe_generation += 1
        self._clear_download_detection()
        new_site = detect_platform(normalized)
        if previous_site is not None and previous_site.site_id != new_site.site_id:
            self._cleanup_platform_hooks(previous_site.site_id)
        if new_site.site_id != "tencent_meeting":
            self._captured_media_urls = ()
        if new_site.site_id != "wechat_channels":
            self._captured_channels_videos = ()
        if new_site.site_id != "youtube":
            self._youtube_po_capture = None
        log_platform_browser(f"page context reset url={normalized[:120]}")

    def _apply_browser_url(self, raw_url: str) -> bool:
        """Sync the address bar and reset detection when navigation changes the page."""
        current = (raw_url or "").strip()
        if not current:
            return False
        previous = self._url_var.get().strip()
        if current != previous:
            self._url_var.set(current)
        if self._busy:
            return current != previous
        if current != previous or current != self._last_probe_url:
            self._reset_detection_for_url(current)
            return True
        return False

    def _cleanup_platform_hooks(self, site_id: str) -> None:
        if self._browser is None:
            return
        if site_id == "youtube":
            try:
                self._browser.evaluate_js(YOUTUBE_PO_CLEANUP_JS)
            except (RuntimeError, OSError, ValueError, TypeError):
                pass
        if site_id == "wechat_channels":
            try:
                self._browser.evaluate_js(CHANNELS_CLEANUP_JS)
            except (RuntimeError, OSError, ValueError, TypeError):
                pass

    def _on_resource_hook_failed(self) -> None:
        self._resource_capture_enabled = False
        self._probe_status_hint = "resource_capture_disabled"
        self._refresh_status_labels()

    def _sync_page_from_browser(self) -> bool:
        """Read the live document URL and react to SPA or history navigations."""
        if self._browser is None:
            return False
        try:
            current = self._browser.get_current_url()
        except (RuntimeError, OSError, ValueError, TypeError):
            return False
        return self._apply_browser_url(current)

    def _schedule_nav_sync(self) -> None:
        if self._nav_sync_after_id is not None:
            self.after_cancel(self._nav_sync_after_id)
        self._nav_sync_after_id = self.after(_NAV_SYNC_MS, self._sync_nav_and_probe)

    def _sync_nav_and_probe(self) -> None:
        self._nav_sync_after_id = None
        if self._browser is None:
            return
        changed = self._sync_page_from_browser()
        if changed:
            self._inject_platform_hooks()
            self._refresh_status_labels()
            self._schedule_asset_probe(immediate=True)
        self._schedule_idle_probe()

    def _schedule_idle_probe(self) -> None:
        """Keep probing downloadable pages until resources appear or the user leaves."""
        if self._idle_probe_after_id is not None:
            self.after_cancel(self._idle_probe_after_id)
        self._idle_probe_after_id = self.after(_IDLE_PROBE_MS, self._run_idle_probe)

    def _run_idle_probe(self) -> None:
        self._idle_probe_after_id = None
        if self._browser is None or self._busy:
            self._schedule_idle_probe()
            return
        self._sync_page_from_browser()
        site = detect_platform(self._url_var.get())
        if not site.supports_download:
            return
        skip_reprobe = {"youtube", "tencent_meeting", "wechat_channels", "douyin", "tiktok"}
        if self._detected_assets and site.site_id not in skip_reprobe:
            return
        self._schedule_asset_probe()
        self._schedule_idle_probe()

    def _capture_resource_url(self, url: str) -> None:
        if is_tencent_media_url(url):
            merged = parse_media_urls([url], captured=self._captured_media_urls)
            if merged == self._captured_media_urls:
                return
            self._captured_media_urls = merged
            log_platform_browser(f"media URL captured count={len(merged)}")
            self._schedule_asset_probe(immediate=True)
            return
        if is_youtube_stream_capture_url(url):
            merged_po = merge_youtube_po_capture(self._youtube_po_capture, stream_url=url)
            if merged_po == self._youtube_po_capture:
                return
            self._youtube_po_capture = merged_po
            self._probe_status_hint = "youtube_po_ready"
            self._refresh_status_labels()
            self._schedule_asset_probe(immediate=True)
            return
        if is_channels_media_url(url):
            self._capture_channels_resource(url)

    def _capture_channels_resource(self, url: str) -> None:
        merged = merge_channels_captures(self._captured_channels_videos, network_url=url)
        if merged == self._captured_channels_videos:
            return
        self._captured_channels_videos = merged
        log_platform_browser(f"WeChat Channels URL captured count={len(merged)}")
        self._schedule_asset_probe(immediate=True)

    def _inject_platform_hooks(self) -> None:
        if self._browser is None:
            return
        site = detect_platform(self._url_var.get())
        if site.site_id == "youtube":
            try:
                self._browser.evaluate_js(YOUTUBE_PO_HOOK_JS)
            except (RuntimeError, OSError, ValueError, TypeError) as exc:
                log_platform_browser(f"YouTube PO hook failed: {exc}", level="WARN")
        if site.site_id == "wechat_channels":
            try:
                self._browser.evaluate_js(CHANNELS_HOOK_JS)
            except (RuntimeError, OSError, ValueError, TypeError) as exc:
                log_platform_browser(f"Channels hook failed: {exc}", level="WARN")

    def _schedule_poll(self) -> None:
        if self._poll_after_id is not None:
            self.after_cancel(self._poll_after_id)
        self._poll_after_id = self.after(_POLL_MS, self._poll_login_state)

    def _schedule_asset_probe(self, *, immediate: bool = False) -> None:
        if self._probe_after_id is not None:
            self.after_cancel(self._probe_after_id)
        delay = 0 if immediate else _PROBE_DEBOUNCE_MS
        self._probe_after_id = self.after(delay, self._start_asset_probe)

    def _on_page_loaded(self) -> None:
        if self._browser is None:
            return
        current = self._browser.get_current_url()
        if current:
            log_platform_browser(f"page loaded {current}")
        self._apply_browser_url(current or self._url_var.get())
        self._inject_platform_hooks()
        self._poll_login_state()
        self._schedule_asset_probe(immediate=True)
        self._schedule_idle_probe()

    def _poll_login_state(self) -> None:
        self._poll_after_id = None
        if self._browser is None:
            return

        def run() -> None:
            state: dict[str, Any] = {}
            media_raw: Any = None
            try:
                raw = self._browser.evaluate_js(LOGIN_STATE_JS)
                state = parse_login_state(raw)
            except (RuntimeError, OSError, ValueError, TypeError) as exc:
                log_platform_browser(f"login JS failed: {exc}", level="WARN")
                state = {}
            try:
                cookies = self._browser.get_cookies()
                state = merge_cookie_login_flags(state, cookies)
            except (RuntimeError, OSError, AttributeError, TypeError):
                pass
            site = detect_platform(self._url_var.get())
            youtube_po_raw: Any = None
            channels_raw: Any = None
            if site.site_id == "tencent_meeting":
                try:
                    media_raw = self._browser.evaluate_js(MEDIA_PROBE_JS)
                except (RuntimeError, OSError, ValueError, TypeError):
                    media_raw = None
            if site.site_id == "youtube":
                try:
                    youtube_po_raw = self._browser.evaluate_js(YOUTUBE_PO_READ_JS)
                except (RuntimeError, OSError, ValueError, TypeError):
                    youtube_po_raw = None
            if site.site_id == "wechat_channels":
                try:
                    channels_raw = self._browser.evaluate_js(CHANNELS_READ_JS)
                except (RuntimeError, OSError, ValueError, TypeError):
                    channels_raw = None
            browser_url = ""
            try:
                browser_url = self._browser.get_current_url()
            except (RuntimeError, OSError, ValueError, TypeError):
                browser_url = ""
            self.after(
                0,
                lambda: self._apply_login_state(
                    state,
                    media_raw,
                    youtube_po_raw,
                    channels_raw,
                    browser_url=browser_url,
                ),
            )

        threading.Thread(target=run, daemon=True).start()
        self._schedule_poll()

    def _apply_login_state(
        self,
        state: dict[str, Any],
        media_raw: Any,
        youtube_po_raw: Any = None,
        channels_raw: Any = None,
        *,
        browser_url: str = "",
    ) -> None:
        if browser_url:
            self._apply_browser_url(browser_url)
        self._login_state = state
        token = str(state.get("access_token") or "").strip()
        if token and token != self._token:
            try:
                save_smartedu_token(token)
                self._token = token
                log_platform_browser("SmartEdu token saved")
                self._schedule_asset_probe(immediate=True)
            except DpapiError as exc:
                log_platform_browser(f"token save failed: {exc}", level="WARN")
        media_changed = False
        if media_raw is not None:
            previous = self._captured_media_urls
            self._captured_media_urls = parse_media_urls(media_raw, captured=self._captured_media_urls)
            media_changed = self._captured_media_urls != previous
        if youtube_po_raw is not None:
            merged_po = merge_youtube_po_capture(self._youtube_po_capture, probe_raw=youtube_po_raw)
            if merged_po != self._youtube_po_capture:
                self._youtube_po_capture = merged_po
                if merged_po is not None and merged_po.usable_for_ytdlp():
                    self._probe_status_hint = "youtube_po_ready"
        channels_changed = False
        if channels_raw is not None:
            previous_channels = self._captured_channels_videos
            self._captured_channels_videos = merge_channels_captures(
                self._captured_channels_videos,
                hook_raw=channels_raw,
            )
            channels_changed = self._captured_channels_videos != previous_channels
        self._refresh_status_labels()
        if (
            media_changed
            or channels_changed
            or (
                youtube_po_raw is not None
                and self._youtube_po_capture is not None
                and self._youtube_po_capture.usable_for_ytdlp()
            )
        ):
            self._schedule_asset_probe(immediate=True)
        else:
            self._schedule_asset_probe()
        self._schedule_idle_probe()

    def _refresh_status_labels(self) -> None:
        site = detect_platform(self._url_var.get())
        status_hint = self._probe_status_hint
        if (
            not self._resource_capture_enabled
            and self._browser_supports_resource_hook_failure()
            and not self._compute_download_ready()
        ):
            status_hint = "resource_capture_disabled"
        line = format_status_line(
            self._i18n,
            site,
            self._login_state,
            smartedu_token=self._token,
            page_url=self._url_var.get(),
            status_hint=status_hint,
            download_ready=self._compute_download_ready(),
        )
        if self._probing:
            line = f"{line} · {self._i18n.translate('smartedu.platform.probing')}"
        self._platform_status.configure(text=line)
        self._set_toolbar_state(self._browser_is_ready())

    def _probe_context(self) -> ProbeContext:
        cookies: list[Any] = []
        if self._browser is not None:
            cookies = self._browser.get_cookies()
        return ProbeContext(
            page_url=self._url_var.get().strip(),
            login_state=self._login_state,
            cookies=cookies,
            smartedu_token=self._token,
            captured_media_urls=self._captured_media_urls,
            youtube_po_capture=self._youtube_po_capture,
            captured_channels_videos=self._captured_channels_videos,
            channels_keystreams=(),
        )

    def _build_channels_keystreams(self, assets: List[DetectedAsset]) -> tuple[tuple[str, str], ...]:
        if self._browser is None:
            return ()
        pairs: list[tuple[str, str]] = []
        for asset in assets:
            if asset.extractor != "channels":
                continue
            video = asset.meta.get("channels_video")
            if not isinstance(video, CapturedChannelVideo):
                continue
            decode_key = video.decode_key.strip()
            if not decode_key:
                continue
            script = f"({CHANNELS_KEYSTREAM_JS})({json.dumps(decode_key)})"
            try:
                raw = self._browser.evaluate_js(script)
            except (RuntimeError, OSError, ValueError, TypeError):
                raw = ""
            hex_value = str(raw or "").strip()
            if hex_value:
                pairs.append((video.asset_id(), hex_value))
        return tuple(pairs)

    def _start_asset_probe(self) -> None:
        self._probe_after_id = None
        if self._browser is None:
            return
        self._sync_page_from_browser()
        if self._probing:
            self._pending_probe = True
            return
        url = self._url_var.get().strip()
        if not url:
            return
        self._probing = True
        self._pending_probe = False
        self._probe_generation += 1
        generation = self._probe_generation
        context = self._probe_context()
        self._refresh_status_labels()

        def run() -> None:
            result = probe_assets(context)
            self.after(0, lambda: self._apply_probe_result(generation, result))

        threading.Thread(target=run, daemon=True).start()

    def _apply_probe_result(self, generation: int, result: Any) -> None:
        self._probing = False
        pending = self._pending_probe
        self._pending_probe = False
        if generation == self._probe_generation:
            self._detected_assets = list(result.assets)
            self._badge_count = int(result.badge_count)
            self._probe_status_hint = str(result.status_hint or "")
            if self._detected_assets:
                self._probe_status_hint = ""
            elif (
                self._youtube_po_capture is not None
                and self._youtube_po_capture.usable_for_ytdlp()
                and self._probe_status_hint == "youtube_po_needed"
            ):
                self._probe_status_hint = "youtube_po_retry"
            self._update_badge()
            self._set_toolbar_state(True)
            if self._detected_assets:
                log_platform_browser(
                    f"download ready count={len(self._detected_assets)} badge={self._badge_count}",
                )
        self._refresh_status_labels()
        if pending:
            self._schedule_asset_probe()

    def _nav_back(self) -> None:
        if self._browser is None or self._busy:
            return
        self._browser.go_back()
        self._schedule_nav_sync()

    def _nav_forward(self) -> None:
        if self._browser is None or self._busy:
            return
        self._browser.go_forward()
        self._schedule_nav_sync()

    def _nav_refresh(self) -> None:
        if self._browser is None or self._busy:
            return
        current = self._url_var.get().strip() or DEFAULT_HOME_URL
        self._browser.load_url(current)

    def _navigate_address(self) -> None:
        if self._browser is None or self._busy:
            return
        try:
            url = normalize_nav_url(self._url_var.get())
        except ValueError:
            messagebox.showwarning(
                self._i18n.translate("dialog.title"),
                self._i18n.translate("smartedu.error.bad_url"),
            )
            return
        self._url_var.set(url)
        self._reset_detection_for_url(url)
        self._browser.load_url(url)
        self._schedule_idle_probe()

    def _download_current(self) -> None:
        if self._busy or self._browser is None or not self._compute_download_ready():
            if not self._busy and self._browser is not None:
                self._schedule_asset_probe(immediate=True)
            return
        open_asset_download_dialog(
            self,
            self._i18n,
            list(self._detected_assets),
            self._url_var.get(),
            on_download=self._run_download,
        )

    def _run_download(self, assets: List[DetectedAsset], folder: Path) -> None:
        if self._browser is None:
            return
        self._download_cancel.clear()
        keystreams = self._build_channels_keystreams(assets)
        base_context = self._probe_context()
        context = ProbeContext(
            page_url=base_context.page_url,
            login_state=base_context.login_state,
            cookies=base_context.cookies,
            smartedu_token=base_context.smartedu_token,
            captured_media_urls=base_context.captured_media_urls,
            youtube_po_capture=base_context.youtube_po_capture,
            captured_channels_videos=base_context.captured_channels_videos,
            channels_keystreams=keystreams,
            download_folder=folder,
        )
        self._set_busy(True)
        log_platform_browser(f"download start count={len(assets)} folder={folder}")

        def run() -> None:
            saved: List[Path] = []
            errors: List[str] = []
            try:
                saved, errors = download_detected_assets(
                    assets,
                    context,
                    cancel_event=self._download_cancel,
                )
                channels_assets = [asset for asset in assets if asset.extractor == "channels"]
                channel_errors = [error for error in errors if any(asset.title in error for asset in channels_assets)]
                if channels_assets and channel_errors and not self._download_cancel.is_set():
                    retry_keys = self._build_channels_keystreams(channels_assets)
                    if retry_keys:
                        errors = [
                            error for error in errors if not any(asset.title in error for asset in channels_assets)
                        ]
                        retry_context = ProbeContext(
                            page_url=context.page_url,
                            login_state=context.login_state,
                            cookies=context.cookies,
                            smartedu_token=context.smartedu_token,
                            captured_media_urls=context.captured_media_urls,
                            youtube_po_capture=context.youtube_po_capture,
                            captured_channels_videos=context.captured_channels_videos,
                            channels_keystreams=retry_keys,
                            download_folder=folder,
                        )
                        retry_saved, retry_errors = download_detected_assets(
                            channels_assets,
                            retry_context,
                            cancel_event=self._download_cancel,
                        )
                        saved.extend(retry_saved)
                        errors.extend(retry_errors)
            except OSError as exc:
                errors.append(str(exc))
                log_platform_browser(f"download batch failed: {exc}", level="WARN")
            finally:
                self.after(0, lambda: self._finish_download(saved, errors))

        threading.Thread(target=run, daemon=True).start()

    def _finish_download(self, saved: List[Path], errors: List[str]) -> None:
        self._set_busy(False)
        self._refresh_status_labels()
        log_platform_browser(f"download done saved={len(saved)} errors={len(errors)}")
        show_download_result(self, self._i18n, saved, errors)
