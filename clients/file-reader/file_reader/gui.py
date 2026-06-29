"""MindGraph file-reader desktop UI."""

from __future__ import annotations

import sys
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Sequence

from file_reader import __version__
from file_reader.chat import messages as chat_messages
from file_reader.dingtalk import folder_export as dingtalk_reader
from file_reader.wechat import folder_export as wechat_reader
from file_reader.api_client import ConnectResult, FileReaderApiClient, LiveSession, PackageItem, UserProfile
from file_reader.dpapi_store import DpapiError
from file_reader.errors import AppError, ErrorCode
from file_reader.i18n import I18n
from file_reader.server_url import ServerUrlError, normalize_server_url
from file_reader.settings import DEFAULT_SERVER_URL, FileReaderSettings
from file_reader.smartedu_panel import SmartEduPanel
from file_reader.status_dock import StatusDock
from file_reader.auth_dialog import AuthDialog
from file_reader.chat.paths import default_chat_export_dir, unique_export_path
from file_reader.platform_status import PlatformStatusPanel
from file_reader.theme import BG_APP, BG_DISABLED, FONT_BODY, TEXT_SECONDARY, WINDOW_MIN_HEIGHT, WINDOW_MIN_WIDTH
from file_reader.wechat.local import WeChatLocalStatus, detect_wechat_local
from file_reader.wechat.probe import WeChatProbeReport, run_wechat_key_probe
from file_reader.wechat.db_reader import (
    WeChatDbError,
    WeChatDbReader,
    WeChatSessionPreview,
    format_chat_preview,
    format_session_time,
)
from file_reader.wechat.crypto import WeChatKeyError
from file_reader.wechat.key_extract import resolve_db_dir
from file_reader.wechat.key_store import cache_entry_exists, load_wechat_key_cache
from file_reader.wechat.wcdb import DecryptedDbCache, default_cache_dir
from file_reader.dingtalk.db_reader import (
    DingTalkDbError,
    DingTalkDbReader,
    DingTalkSessionPreview,
    format_chat_preview as format_dingtalk_chat_preview,
    format_session_time as format_dingtalk_session_time,
)
from file_reader.dingtalk.db_cache import DingTalkDbCache
from file_reader.wechat.debug_log import log_wechat
from file_reader.dingtalk.local import DingTalkLocalStatus, account_from_status, detect_dingtalk_local
from file_reader.dingtalk.probe import DingTalkProbeReport, load_dingtalk_sessions, run_dingtalk_probe
from file_reader.wecom.db_reader import (
    WeComDbError,
    WeComDbReader,
    WeComSessionPreview,
    format_chat_preview as format_wecom_chat_preview,
    format_session_time as format_wecom_session_time,
)
from file_reader.wecom.key_store import cache_entry_exists as wecom_cache_entry_exists
from file_reader.wecom.local import WeComLocalStatus, detect_wecom_local
from file_reader.wecom.debug_log import log_wecom
from file_reader.wecom.probe import WeComProbeReport, load_wecom_sessions, run_wecom_probe
from file_reader.chat.live_mode import LiveChatSession
from file_reader.chat.messages import ExportPreview
from file_reader.chat.messages import ChatMessage
from file_reader.widgets import AppHeader, SendPanel

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_ICON_REF: List[tk.PhotoImage] = []
_LIVE_POLL_MS = 2000
_WECHAT_POLL_MS = 4000
_DINGTALK_POLL_MS = 4000
_WECOM_POLL_MS = 4000


class FileReaderApp:
    """Desktop helper to send local chat exports to Document Summary."""

    def __init__(self, root: tk.Tk, i18n: Optional[I18n] = None) -> None:
        self.root = root
        self.i18n = i18n or I18n.auto()
        self.root.title(self.i18n.translate("app.title", version=__version__))
        self.root.configure(bg=BG_APP)
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.geometry("860x780")

        self.settings = FileReaderSettings.load()
        self.platform = tk.StringVar(value=self.settings.platform)
        self._profile: Optional[UserProfile] = None
        self._packages: List[PackageItem] = []
        self._live_sessions: List[LiveSession] = []
        self._previews: List[ExportPreview] = []
        self._db_sessions: List[WeChatSessionPreview] = []
        self._dingtalk_sessions: List[DingTalkSessionPreview] = []
        self._selected_file: Optional[ExportPreview] = None
        self._selected_chat: Optional[LiveChatSession] = None
        self._live_db_mode = False
        self._wechat_chats_loading = False
        self._sending = False
        self._exporting = False
        self._connecting = False
        self._selected_session: Optional[LiveSession] = None
        self._live_poll_after_id: Optional[str] = None
        self._persisted_error: Optional[AppError] = None
        self._session_load_error: Optional[AppError] = None
        self._smartedu_status: tuple[str, str, str] = ("", "", "")
        self._wechat_status: WeChatLocalStatus = WeChatLocalStatus(False, None, None, 0)
        self._wechat_poll_after_id: Optional[str] = None
        self._wechat_live_unlocked = False
        self._wechat_probing = False
        self._wechat_probe_report: Optional[WeChatProbeReport] = None
        self._chat_preview_token = 0
        self._wechat_cache_restore_running = False
        self._wechat_saved_keys_cache_key: Optional[tuple[int, str, str, str]] = None
        self._wechat_saved_keys_cached: Optional[bool] = None
        self._dingtalk_status: DingTalkLocalStatus = DingTalkLocalStatus(
            False, None, None, None, None, None, False, False
        )
        self._dingtalk_poll_after_id: Optional[str] = None
        self._dingtalk_live_unlocked = False
        self._dingtalk_probing = False
        self._dingtalk_db_reader: Optional[DingTalkDbReader] = None
        self._wecom_sessions: List[WeComSessionPreview] = []
        self._wecom_status: WeComLocalStatus = WeComLocalStatus(False, None, None, None, 0, 0)
        self._wecom_poll_after_id: Optional[str] = None
        self._wecom_live_unlocked = False
        self._wecom_probing = False
        self._wecom_db_reader: Optional[WeComDbReader] = None
        self._wecom_probe_keys: Dict[str, str] = {}
        self._wecom_cache_restore_running = False

        self._header = AppHeader(
            root,
            self.i18n,
            on_connect_account=self._open_connect_dialog,
            on_relogin=self._open_connect_dialog,
            on_logout=self._clear_credentials,
            on_settings=self._open_connect_dialog,
        )
        self._header.pack(fill="x")

        self._dock = StatusDock(root)
        self._dock.pack(side="bottom", fill="x")

        body = tk.Frame(root, bg=BG_APP, padx=20, pady=16)
        body.pack(fill="both", expand=True)

        self._auth = AuthDialog(
            root,
            self.i18n,
            on_connect=self._connect,
            on_clear=self._clear_credentials,
        )
        self._auth.set_values(self.settings.server_url, self.settings.api_token, self.settings.account_phone)

        content_shell = tk.Frame(body, bg=BG_APP)
        content_shell.pack(fill="both", expand=True)

        self._notebook = ttk.Notebook(content_shell)
        self._notebook.pack(fill="both", expand=True)

        self._content_overlay = tk.Frame(content_shell, bg=BG_DISABLED)
        self._content_overlay_label = tk.Label(
            self._content_overlay,
            bg=BG_DISABLED,
            fg=TEXT_SECONDARY,
            font=FONT_BODY,
            wraplength=560,
            justify="center",
        )
        self._content_overlay_label.place(relx=0.5, rely=0.5, anchor="center")
        self._content_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._content_overlay.lift()

        chat_tab = tk.Frame(self._notebook, bg=BG_APP)
        smartedu_tab = tk.Frame(self._notebook, bg=BG_APP)
        self._notebook.add(chat_tab, text=self.i18n.translate("tabs.chat"))
        self._notebook.add(smartedu_tab, text=self.i18n.translate("tabs.smartedu"))

        chat_row = tk.Frame(chat_tab, bg=BG_APP)
        chat_row.pack(fill="both", expand=True)
        chat_row.columnconfigure(0, weight=1)
        chat_row.columnconfigure(1, minsize=268)
        chat_row.rowconfigure(0, weight=1)

        self._send = SendPanel(
            chat_row,
            self.i18n,
            on_browse=self._browse_folder,
            on_export=self._export_selected,
            on_send=self._send_selected,
            on_chat_select=self._on_select_chat,
            on_chat_check_change=self._on_chat_check_changed,
            platform_var=self.platform,
        )
        self._send.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self._send.set_export_enabled(False)
        self._send.set_upload_enabled(False)
        self._send.set_controls_enabled(False)
        self._send.set_authenticated(False)

        self._platform_status = PlatformStatusPanel(
            chat_row,
            self.i18n,
            on_wechat_start=self._on_wechat_start_probe,
            on_dingtalk_start=self._on_dingtalk_start_probe,
            on_wecom_start=self._on_wecom_start_probe,
        )
        self._platform_status.grid(row=0, column=1, sticky="ns")
        self._platform_status.set_platform(self.platform.get())
        if self.platform.get() == "wechat":
            self._publish_wechat_panel(self._wechat_status)
        elif self.platform.get() == "dingtalk":
            self._publish_dingtalk_panel(self._dingtalk_status)
        elif self.platform.get() == "wecom":
            self._publish_wecom_panel(self._wecom_status)

        self._smartedu = SmartEduPanel(
            smartedu_tab,
            self.i18n,
            client_factory=self._client,
            on_status=self._on_smartedu_status,
        )
        self._smartedu.pack(fill="both", expand=True)

        self.platform.trace_add("write", self._on_platform_changed)
        self._send.file_list.bind("<<ListboxSelect>>", self._on_select_file)
        self._notebook.bind("<<NotebookTabChanged>>", lambda _event: self._sync_status_dock())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._sync_status_dock()
        self._set_content_blocked(True, connecting=False)

        if self.settings.api_token and self.settings.account_phone:
            self.root.after(400, self._connect)
        elif not self.settings.api_token and not self.settings.account_phone:
            self.root.after(600, self._open_connect_dialog)

    def _on_platform_changed(self, *_args: object) -> None:
        platform = self.platform.get()
        was_live = self._live_db_mode
        self._abandon_platform_probes()
        self._platform_status.set_platform(platform)
        if platform == "wechat":
            self._publish_wechat_panel(self._wechat_status)
        elif platform == "dingtalk":
            self._publish_dingtalk_panel(self._dingtalk_status)
        elif platform == "wecom":
            self._publish_wecom_panel(self._wecom_status)
        else:
            self._wechat_live_unlocked = False
            self._wechat_probe_report = None
            self._dingtalk_live_unlocked = False
            self._dingtalk_db_reader = None
            self._wecom_live_unlocked = False
            self._wecom_db_reader = None
            self._wecom_probe_keys = {}
            self._live_db_mode = False
            self._send.set_upload_mode(False)
            self._send.set_folder_row_visible(True)
            self._refresh_files()
        self._sync_live_source_mode()
        if was_live and not self._live_db_mode:
            self._clear_live_chat_ui()
        elif self._live_db_mode:
            self._restore_active_platform_chats()
        elif platform in ("wechat", "dingtalk", "wecom"):
            self._send.set_status("")
        self._sync_platform_polls(platform)
        self._update_send_state()
        self._sync_status_dock()

    def _abandon_platform_probes(self) -> None:
        """Drop in-flight probe work so stale callbacks cannot repaint the UI."""
        self._platform_status.abandon_probes()
        self._wechat_probing = False
        self._dingtalk_probing = False
        self._wecom_probing = False
        self._wechat_chats_loading = False
        self._wechat_cache_restore_running = False
        self._wecom_cache_restore_running = False

    def _clear_live_chat_ui(self) -> None:
        """Remove live chat rows, preview, and status from the send panel."""
        self._selected_chat = None
        self._chat_preview_token += 1
        self._send.clear_chat_rows()
        self._send.clear_chat_preview()
        self._send.clear_list_summary()
        self._send.set_status("")

    def _sync_platform_polls(self, platform: str) -> None:
        """Keep background detection running only for the selected platform."""
        if platform != "wechat":
            self._stop_wechat_poll()
        if platform != "dingtalk":
            self._stop_dingtalk_poll()
        if platform != "wecom":
            self._stop_wecom_poll()
        if self._profile is None:
            return
        if platform == "wechat":
            self._start_wechat_poll()
        elif platform == "dingtalk":
            self._start_dingtalk_poll()
        elif platform == "wecom":
            self._start_wecom_poll()

    def _restore_active_platform_chats(self) -> None:
        """Repaint the live chat list after switching back to an unlocked platform."""
        platform = self.platform.get()
        if platform == "wechat" and self._wechat_live_unlocked:
            self._apply_wechat_chats(self._db_sessions, None)
        elif platform == "dingtalk" and self._dingtalk_live_unlocked:
            self._apply_dingtalk_chats(self._dingtalk_sessions, None)
        elif platform == "wecom" and self._wecom_live_unlocked:
            self._apply_wecom_chats(self._wecom_sessions, None)

    def _stop_wechat_poll(self) -> None:
        if self._wechat_poll_after_id is not None:
            self.root.after_cancel(self._wechat_poll_after_id)
            self._wechat_poll_after_id = None

    def _stop_dingtalk_poll(self) -> None:
        if self._dingtalk_poll_after_id is not None:
            self.root.after_cancel(self._dingtalk_poll_after_id)
            self._dingtalk_poll_after_id = None

    def _start_dingtalk_poll(self) -> None:
        self._stop_dingtalk_poll()
        self._refresh_dingtalk_status()
        self._dingtalk_poll_after_id = self.root.after(_DINGTALK_POLL_MS, self._start_dingtalk_poll)

    def _refresh_dingtalk_status(self) -> None:
        if self._profile is None:
            return

        def run() -> None:
            status = detect_dingtalk_local()
            self.root.after(0, lambda: self._apply_dingtalk_status(status))

        threading.Thread(target=run, daemon=True).start()

    def _apply_dingtalk_status(self, status: DingTalkLocalStatus) -> None:
        previous = self._dingtalk_status
        account_changed = (
            previous.account_folder_id != status.account_folder_id
            or previous.storage_version != status.storage_version
            or previous.real_uid != status.real_uid
        )
        if self._dingtalk_live_unlocked and account_changed:
            self._dingtalk_live_unlocked = False
            self._dingtalk_probing = False
            self._dingtalk_db_reader = None
            self._dingtalk_sessions = []
            if self.platform.get() == "dingtalk":
                self._selected_chat = None
                self._clear_live_chat_ui()
                self._sync_live_source_mode()
        self._dingtalk_status = status
        if self.platform.get() == "dingtalk" and not self._dingtalk_probing:
            self._clear_stale_dingtalk_probe()
            self._publish_dingtalk_panel(status)
        if self._dingtalk_live_unlocked:
            return
        if self._profile is not None and self.platform.get() == "dingtalk":
            export_dir = default_chat_export_dir(self._profile)
            if not self._send.export_dir.get().strip():
                self._send.export_dir.set(str(export_dir))
            if not self._live_db_mode:
                self._refresh_files()
        self._sync_live_source_mode()
        self._sync_status_dock()

    def _safe_detect_wechat_local(self) -> WeChatLocalStatus:
        try:
            return detect_wechat_local()
        except (OSError, ValueError, RuntimeError, NameError) as exc:
            log_wechat(f"detect_wechat_local failed: {exc}", level="ERROR")
            return self._wechat_status

    def _clear_stale_wechat_probe(self) -> None:
        """Drop orphan busy flags when the right panel is no longer probing."""
        if not self._wechat_probing:
            return
        if self._platform_status.is_probing():
            return
        self._wechat_probing = False
        self._wechat_chats_loading = False
        self._wechat_cache_restore_running = False
        self._platform_status.clear_probing()

    def _clear_stale_dingtalk_probe(self) -> None:
        if not self._dingtalk_probing:
            return
        if self._platform_status.is_probing():
            return
        self._dingtalk_probing = False
        self._platform_status.clear_probing()

    def _publish_wechat_panel(self, status: WeChatLocalStatus) -> None:
        if self.platform.get() != "wechat":
            return
        saved_keys = self._wechat_saved_keys_available(status)
        if self._wechat_probing:
            self._platform_status.set_wechat_probing(status, saved_keys_available=saved_keys)
        else:
            self._platform_status.set_wechat_status(status, saved_keys_available=saved_keys)

    def _publish_dingtalk_panel(self, status: DingTalkLocalStatus) -> None:
        if self.platform.get() != "dingtalk":
            return
        if self._dingtalk_probing:
            self._platform_status.set_dingtalk_probing(status)
        else:
            self._platform_status.set_dingtalk_status(status)

    def _refresh_wechat_status_now(self) -> WeChatLocalStatus:
        """Re-scan WeChat on disk before Connect (avoid stale poll snapshot)."""
        self._clear_stale_wechat_probe()
        status = self._safe_detect_wechat_local()
        previous = self._wechat_status
        fingerprint_changed = self._wechat_crypto_fingerprint(previous) != self._wechat_crypto_fingerprint(status)
        if self._wechat_live_unlocked and fingerprint_changed:
            self._reset_wechat_live_on_client_change(previous, status)
            status = self._safe_detect_wechat_local()
        self._wechat_status = status
        if fingerprint_changed:
            self._invalidate_wechat_saved_keys_cache()
        self._publish_wechat_panel(status)
        return status

    def _refresh_dingtalk_status_now(self) -> DingTalkLocalStatus:
        """Re-scan DingTalk on disk before Connect."""
        self._clear_stale_dingtalk_probe()
        status = detect_dingtalk_local()
        self._dingtalk_status = status
        self._publish_dingtalk_panel(status)
        return status

    def _on_dingtalk_start_probe(self) -> None:
        if self._profile is None:
            return
        self._clear_stale_dingtalk_probe()
        if self._dingtalk_probing:
            return
        status = self._refresh_dingtalk_status_now()
        if not status.local_dbs_present:
            messagebox.showwarning(
                self.i18n.translate("dialog.title"),
                self.i18n.translate("platform.dingtalk.db_missing"),
            )
            return
        if not status.unlock_ready:
            messagebox.showwarning(
                self.i18n.translate("dialog.title"),
                self._dingtalk_unlock_hint(status),
            )
            return
        self._dingtalk_probing = True
        self._dingtalk_live_unlocked = False
        self._dingtalk_db_reader = None
        self._selected_chat = None
        self._send.clear_chat_rows()
        self._send.file_list.delete(0, tk.END)
        self._send.set_list_summary(self.i18n.translate("send.loading_chats"))
        self._send.set_status(self.i18n.translate("send.scanning_dingtalk_db"))
        self._update_send_state()
        self._platform_status.set_dingtalk_probing(status)
        self._sync_live_source_mode()
        self._sync_status_dock()
        probe_token = self._platform_status.probe_token("dingtalk")
        profile = self._profile

        def run() -> None:
            current = status
            sessions: List[DingTalkSessionPreview] = []
            chat_error: Optional[Exception] = None
            report: Optional[DingTalkProbeReport] = None
            user_id = profile.user_id
            phone = profile.phone or self.settings.account_phone
            try:
                current, sessions, chat_error = load_dingtalk_sessions(
                    status,
                    mindgraph_user_id=user_id,
                    mindgraph_phone=phone,
                )
                report = run_dingtalk_probe(
                    current,
                    mindgraph_user_id=user_id,
                    mindgraph_phone=phone,
                )
            except (DingTalkDbError, OSError, ValueError) as exc:
                chat_error = exc
                current = detect_dingtalk_local()
                report = run_dingtalk_probe(
                    current,
                    mindgraph_user_id=user_id,
                    mindgraph_phone=phone,
                )
            self.root.after(
                0,
                lambda c=current, r=report, s=sessions, e=chat_error, t=probe_token: self._apply_dingtalk_probe(
                    c,
                    r,
                    s,
                    e,
                    probe_token=t,
                ),
            )

        threading.Thread(target=run, daemon=True).start()

    def _dingtalk_unlock_hint(self, status: DingTalkLocalStatus) -> str:
        if status.real_uid is None:
            return self.i18n.translate("platform.dingtalk.uid_missing")
        if status.storage_version == "v3" and not status.salt_present:
            return self.i18n.translate("platform.dingtalk.salt_missing")
        return self.i18n.translate("platform.dingtalk.db_missing")

    def _apply_dingtalk_probe(
        self,
        status: DingTalkLocalStatus,
        report: Optional[DingTalkProbeReport],
        sessions: List[DingTalkSessionPreview],
        chat_error: Optional[Exception],
        *,
        probe_token: int,
    ) -> None:
        if self._platform_status.probe_stale("dingtalk", probe_token) or self.platform.get() != "dingtalk":
            return
        self._dingtalk_probing = False
        self._dingtalk_status = status
        self._platform_status.clear_probing()
        if report is None:
            self._publish_dingtalk_panel(status)
            if chat_error is not None:
                self._send.set_status(
                    self.i18n.translate("error.dingtalk_db_read", detail=str(chat_error)),
                    error=True,
                )
            self._update_send_state()
            self._sync_status_dock()
            return
        self._dingtalk_live_unlocked = report.success and chat_error is None
        self._platform_status.set_dingtalk_probe_result(status, report)
        self._sync_live_source_mode()
        if self._dingtalk_live_unlocked:
            self._apply_dingtalk_chats(sessions, chat_error)
            self._platform_status.set_dingtalk_hint("platform.hint.dingtalk_live")
        elif report.success and chat_error is not None:
            self._send.set_status(
                self.i18n.translate("error.dingtalk_db_read", detail=str(chat_error)),
                error=True,
            )
        elif not report.success:
            if self._profile is not None:
                self._setup_export_folder()
            self._send.set_status(
                self.i18n.translate("send.dingtalk_scan_failed"),
                error=True,
            )
            detail = report.error[:160] if report.error else self.i18n.translate("send.dingtalk_scan_failed")
            self._dock.flash(
                "error",
                self.i18n.translate("platform.dingtalk.decrypt_failed"),
                detail,
                duration_ms=10000,
            )
        self._update_send_state()
        self._sync_status_dock()

    def _apply_dingtalk_chats(
        self,
        sessions: List[DingTalkSessionPreview],
        error: Optional[Exception],
    ) -> None:
        self._dingtalk_sessions = sessions
        self._selected_chat = None
        self._chat_preview_token += 1
        self._send.clear_chat_preview()
        self._send.clear_chat_rows()
        if error is not None:
            self._dingtalk_live_unlocked = False
            self._live_db_mode = False
            self._send.set_upload_mode(False)
            self._send.set_folder_row_visible(True)
            self._send.clear_list_summary()
            if self._profile is not None and not self._send.export_dir.get().strip():
                self._send.export_dir.set(str(default_chat_export_dir(self._profile)))
            self._send.set_status(
                self.i18n.translate("error.dingtalk_db_read", detail=str(error)),
                error=True,
            )
            self._update_send_state()
            self._sync_status_dock()
            return
        if not sessions:
            self._send.set_status(self.i18n.translate("send.chats_empty"))
            self._send.set_list_summary(self.i18n.translate("send.chats_empty"))
        else:
            self._send.set_status("")
            self._send.set_list_summary(
                self.i18n.translate("send.chats_loaded", count=len(sessions)),
            )
        chat_labels = [
            self._send.format_chat_row(
                session.display_name,
                is_group=session.is_group,
                time_label=format_dingtalk_session_time(session.last_timestamp),
            )
            for session in sessions
        ]
        self._send.set_chat_rows(chat_labels)
        self._update_send_state()
        self._sync_status_dock()

    def _stop_wecom_poll(self) -> None:
        if self._wecom_poll_after_id is not None:
            self.root.after_cancel(self._wecom_poll_after_id)
            self._wecom_poll_after_id = None

    def _start_wecom_poll(self) -> None:
        self._stop_wecom_poll()
        self._refresh_wecom_status()
        self._wecom_poll_after_id = self.root.after(_WECOM_POLL_MS, self._start_wecom_poll)

    def _refresh_wecom_status(self) -> None:
        if self._profile is None:
            return

        def run() -> None:
            status = detect_wecom_local()
            self.root.after(0, lambda: self._apply_wecom_status(status))

        threading.Thread(target=run, daemon=True).start()

    def _apply_wecom_status(self, status: WeComLocalStatus) -> None:
        previous = self._wecom_status
        account_changed = (
            str(previous.data_root) != str(status.data_root) or previous.account_label != status.account_label
        )
        if self._wecom_live_unlocked and account_changed:
            self._wecom_live_unlocked = False
            self._wecom_probing = False
            self._wecom_db_reader = None
            self._wecom_probe_keys = {}
            self._wecom_sessions = []
            if self.platform.get() == "wecom":
                self._selected_chat = None
                self._clear_live_chat_ui()
                self._sync_live_source_mode()
        self._wecom_status = status
        if self.platform.get() == "wecom" and not self._wecom_probing:
            self._clear_stale_wecom_probe()
            self._publish_wecom_panel(status)
        if self._wecom_live_unlocked:
            return
        if self._profile is not None and self.platform.get() == "wecom":
            export_dir = default_chat_export_dir(self._profile)
            if not self._send.export_dir.get().strip():
                self._send.export_dir.set(str(export_dir))
            if not self._live_db_mode:
                self._refresh_files()
        self._sync_live_source_mode()
        self._sync_status_dock()

    def _clear_stale_wecom_probe(self) -> None:
        if not self._wecom_probing:
            return
        if self._platform_status.is_probing():
            return
        self._wecom_probing = False
        self._wecom_cache_restore_running = False
        self._platform_status.clear_probing()

    def _publish_wecom_panel(self, status: WeComLocalStatus) -> None:
        if self.platform.get() != "wecom":
            return
        saved_keys = self._wecom_saved_keys_available(status)
        if self._wecom_probing:
            self._platform_status.set_wecom_probing(status, saved_keys_available=saved_keys)
        else:
            self._platform_status.set_wecom_status(status, saved_keys_available=saved_keys)

    def _refresh_wecom_status_now(self) -> WeComLocalStatus:
        self._clear_stale_wecom_probe()
        status = detect_wecom_local()
        self._wecom_status = status
        self._publish_wecom_panel(status)
        return status

    def _wecom_saved_keys_available(self, status: WeComLocalStatus) -> bool:
        if self._profile is None or status.data_root is None or not status.account_label:
            return False
        if not wecom_cache_entry_exists(
            mindgraph_user_id=self._profile.user_id,
            account_label=status.account_label,
            data_dir=status.data_root,
        ):
            return False
        return True

    def _on_wecom_start_probe(self) -> None:
        if self._profile is None:
            return
        self._clear_stale_wecom_probe()
        if self._wecom_probing:
            return
        status = self._refresh_wecom_status_now()
        if not status.local_dbs_present:
            messagebox.showwarning(
                self.i18n.translate("dialog.title"),
                self.i18n.translate("platform.wecom.db_missing"),
            )
            return
        saved_keys = self._wecom_saved_keys_available(status)
        if not status.process_running and not saved_keys:
            messagebox.showwarning(
                self.i18n.translate("dialog.title"),
                self.i18n.translate("platform.wecom.process_missing"),
            )
            return
        self._wecom_probing = True
        self._wecom_live_unlocked = False
        self._wecom_db_reader = None
        self._wecom_probe_keys = {}
        self._selected_chat = None
        self._send.clear_chat_rows()
        self._send.file_list.delete(0, tk.END)
        self._send.set_list_summary(self.i18n.translate("send.loading_chats"))
        scan_key = "send.scanning_wecom_db" if saved_keys else "platform.wecom.probing_scan_keys"
        self._send.set_status(self.i18n.translate(scan_key))
        self._update_send_state()
        self._platform_status.set_wecom_probing(status, saved_keys_available=saved_keys)
        self._sync_live_source_mode()
        self._sync_status_dock()
        user_id = self._profile.user_id
        phone = self._profile.phone or self.settings.account_phone
        probe_token = self._platform_status.probe_token("wecom")

        def run() -> None:
            current = status
            sessions: List[WeComSessionPreview] = []
            chat_error: Optional[Exception] = None
            report: Optional[WeComProbeReport] = None
            try:
                report = run_wecom_probe(
                    status,
                    mindgraph_user_id=user_id,
                    mindgraph_phone=phone,
                    prefer_cache=saved_keys,
                )
                if report.success and report.keys:
                    current, sessions, chat_error = load_wecom_sessions(status, keys=report.keys)
            except (WeComDbError, OSError, ValueError) as exc:
                chat_error = exc
                current = detect_wecom_local()
                report = run_wecom_probe(current, mindgraph_user_id=user_id, mindgraph_phone=phone)
            self.root.after(
                0,
                lambda c=current, r=report, s=sessions, e=chat_error, t=probe_token: self._apply_wecom_probe(
                    c,
                    r,
                    s,
                    e,
                    probe_token=t,
                ),
            )

        threading.Thread(target=run, daemon=True).start()

    def _apply_wecom_probe(
        self,
        status: WeComLocalStatus,
        report: Optional[WeComProbeReport],
        sessions: List[WeComSessionPreview],
        chat_error: Optional[Exception],
        *,
        probe_token: int,
    ) -> None:
        if self._platform_status.probe_stale("wecom", probe_token) or self.platform.get() != "wecom":
            log_wecom(
                f"apply_wecom_probe skipped stale={self._platform_status.probe_stale('wecom', probe_token)} "
                f"platform={self.platform.get()}",
                level="WARN",
            )
            return
        self._wecom_probing = False
        self._wecom_cache_restore_running = False
        self._wecom_status = status
        self._platform_status.clear_probing()
        saved_keys = self._wecom_saved_keys_available(status)
        if report is None:
            self._publish_wecom_panel(status)
            if chat_error is not None:
                self._send.set_status(
                    self.i18n.translate("error.wecom_db_read", detail=str(chat_error)),
                    error=True,
                )
            self._update_send_state()
            self._sync_status_dock()
            return
        if report.keys:
            self._wecom_probe_keys = dict(report.keys)
        self._wecom_live_unlocked = report.success and chat_error is None
        self._platform_status.set_wecom_probe_result(status, report, saved_keys_available=saved_keys)
        self._sync_live_source_mode()
        if self._wecom_live_unlocked:
            self._apply_wecom_chats(sessions, chat_error)
            self._platform_status.set_wecom_hint("platform.hint.wecom_live")
        elif report.success and chat_error is not None:
            self._send.set_status(
                self.i18n.translate("error.wecom_db_read", detail=str(chat_error)),
                error=True,
            )
        elif not report.success:
            if self._profile is not None:
                self._setup_export_folder()
            self._send.set_status(
                self.i18n.translate("send.wecom_scan_failed"),
                error=True,
            )
            detail = report.error[:160] if report.error else self.i18n.translate("send.wecom_scan_failed")
            self._dock.flash(
                "error",
                self.i18n.translate("platform.wecom.decrypt_failed"),
                detail,
                duration_ms=10000,
            )
        self._update_send_state()
        self._sync_status_dock()

    def _apply_wecom_chats(
        self,
        sessions: List[WeComSessionPreview],
        error: Optional[Exception],
    ) -> None:
        self._wecom_sessions = sessions
        self._selected_chat = None
        self._chat_preview_token += 1
        self._send.clear_chat_preview()
        self._send.clear_chat_rows()
        if error is not None:
            self._wecom_live_unlocked = False
            self._live_db_mode = False
            self._send.set_upload_mode(False)
            self._send.set_folder_row_visible(True)
            self._send.clear_list_summary()
            if self._profile is not None and not self._send.export_dir.get().strip():
                self._send.export_dir.set(str(default_chat_export_dir(self._profile)))
            self._send.set_status(
                self.i18n.translate("error.wecom_db_read", detail=str(error)),
                error=True,
            )
            self._update_send_state()
            self._sync_status_dock()
            return
        if not sessions:
            self._send.set_status(self.i18n.translate("send.chats_empty"))
            self._send.set_list_summary(self.i18n.translate("send.chats_empty"))
        else:
            self._send.set_status("")
            self._send.set_list_summary(
                self.i18n.translate("send.chats_loaded", count=len(sessions)),
            )
        chat_labels = [
            self._send.format_chat_row(
                session.display_name,
                is_group=session.is_group,
                time_label=format_wecom_session_time(session.last_timestamp),
            )
            for session in sessions
        ]
        self._send.set_chat_rows(chat_labels)
        self._update_send_state()
        self._sync_status_dock()

    def _maybe_restore_wecom_from_cache(self) -> None:
        if (
            self._wecom_probing
            or self._wecom_live_unlocked
            or self._wecom_cache_restore_running
            or self._profile is None
            or self.platform.get() != "wecom"
        ):
            return
        status = self._wecom_status
        if not status.local_dbs_present or not self._wecom_saved_keys_available(status):
            return
        self._wecom_cache_restore_running = True
        self._on_wecom_start_probe()

    def _live_sessions_list(self) -> Sequence[LiveChatSession]:
        platform = self.platform.get()
        if platform == "dingtalk":
            return self._dingtalk_sessions
        if platform == "wecom":
            return self._wecom_sessions
        return self._db_sessions

    def _session_message_key(self, chat: LiveChatSession) -> str:
        if isinstance(chat, DingTalkSessionPreview):
            return chat.cid
        if isinstance(chat, WeComSessionPreview):
            return chat.conversation_id
        return chat.username

    def _build_dingtalk_db_reader(self) -> DingTalkDbReader:
        if self._dingtalk_db_reader is not None:
            return self._dingtalk_db_reader
        account = account_from_status(self._dingtalk_status)
        if account is None:
            raise DingTalkDbError("No DingTalk account database found")
        reader = DingTalkDbReader(DingTalkDbCache(account))
        self._dingtalk_db_reader = reader
        return reader

    def _build_wecom_db_reader(self) -> WeComDbReader:
        if self._wecom_db_reader is not None:
            return self._wecom_db_reader
        if not self._wecom_probe_keys:
            raise WeComDbError("WeCom database keys not available")
        reader = WeComDbReader.from_local_detection(self._wecom_probe_keys)
        self._wecom_db_reader = reader
        return reader

    def _load_live_messages(self, chat: LiveChatSession) -> List[ChatMessage]:
        if isinstance(chat, DingTalkSessionPreview):
            return self._build_dingtalk_db_reader().load_messages(chat.cid)
        if isinstance(chat, WeComSessionPreview):
            return self._build_wecom_db_reader().load_messages(chat.conversation_id)
        return self._build_wechat_db_reader().load_messages(chat.username)

    def _start_wechat_poll(self) -> None:
        self._stop_wechat_poll()
        self._refresh_wechat_status()
        self._wechat_poll_after_id = self.root.after(_WECHAT_POLL_MS, self._start_wechat_poll)

    def _refresh_wechat_status(self) -> None:
        if self._profile is None:
            return

        def run() -> None:
            status = self._safe_detect_wechat_local()
            self.root.after(0, lambda: self._apply_wechat_status(status))

        threading.Thread(target=run, daemon=True).start()

    def _wechat_crypto_fingerprint(self, status: WeChatLocalStatus) -> tuple[str, str, bool]:
        return (
            status.weixin_version or "",
            status.client_variant or "",
            status.requires_wx_key_hook,
        )

    def _reset_wechat_live_on_client_change(
        self,
        previous: WeChatLocalStatus,
        current: WeChatLocalStatus,
    ) -> None:
        """Drop live unlock when WeChat version or crypto path changes after an update."""
        self._wechat_live_unlocked = False
        self._wechat_probe_report = None
        self._wechat_probing = False
        self._wechat_cache_restore_running = False
        self._wechat_chats_loading = False
        self._selected_chat = None
        self._db_sessions = []
        self._invalidate_wechat_saved_keys_cache()
        self._sync_wechat_source_mode()
        old_version = previous.weixin_version or self.i18n.translate("platform.wechat.version_unknown")
        new_version = current.weixin_version or self.i18n.translate("platform.wechat.version_unknown")
        if self.platform.get() == "wechat":
            self._clear_live_chat_ui()
            self._platform_status.set_wechat_status(
                current,
                saved_keys_available=self._wechat_saved_keys_available(current),
            )
            self._platform_status.set_wechat_hint(
                "platform.hint.wechat_version_changed",
                old=old_version,
                new=new_version,
            )
            self._send.set_status(
                self.i18n.translate(
                    "platform.hint.wechat_version_changed",
                    old=old_version,
                    new=new_version,
                ),
            )
        self._update_send_state()
        self._sync_status_dock()

    def _invalidate_wechat_saved_keys_cache(self) -> None:
        self._wechat_saved_keys_cache_key = None
        self._wechat_saved_keys_cached = None

    def _wechat_saved_keys_available(self, status: WeChatLocalStatus) -> bool:
        if self._profile is None or not status.wxid or status.data_root is None:
            return False
        account_path = str(status.data_root.resolve())
        version_label = status.weixin_version or ""
        cache_key = (self._profile.user_id, status.wxid, account_path, version_label)
        if self._wechat_saved_keys_cache_key == cache_key and self._wechat_saved_keys_cached is not None:
            return self._wechat_saved_keys_cached
        if not cache_entry_exists(
            mindgraph_user_id=self._profile.user_id,
            wxid=status.wxid,
            account_dir=status.data_root,
        ):
            self._wechat_saved_keys_cache_key = cache_key
            self._wechat_saved_keys_cached = False
            return False
        db_dir = resolve_db_dir(status.data_root, status.client_variant)
        record = load_wechat_key_cache(
            status.data_root,
            db_dir,
            mindgraph_user_id=self._profile.user_id,
            wxid=status.wxid,
            current_weixin_version=status.weixin_version,
        )
        validated = record is not None
        self._wechat_saved_keys_cache_key = cache_key
        self._wechat_saved_keys_cached = validated
        return validated

    def _apply_wechat_status(self, status: WeChatLocalStatus) -> None:
        previous = self._wechat_status
        fingerprint_changed = self._wechat_crypto_fingerprint(previous) != self._wechat_crypto_fingerprint(status)
        if self._wechat_live_unlocked and fingerprint_changed:
            self._reset_wechat_live_on_client_change(previous, status)
        self._wechat_status = status
        if fingerprint_changed:
            self._invalidate_wechat_saved_keys_cache()
        if self.platform.get() == "wechat":
            self._clear_stale_wechat_probe()
            self._publish_wechat_panel(status)
        if self._wechat_live_unlocked:
            return
        if self._profile is not None and self.platform.get() == "wechat":
            export_dir = default_chat_export_dir(self._profile)
            if not self._send.export_dir.get().strip():
                self._send.export_dir.set(str(export_dir))
            if not self._live_db_mode:
                self._refresh_files()
            self._maybe_restore_wechat_from_cache()
        self._sync_wechat_source_mode()
        self._sync_status_dock()

    def _maybe_restore_wechat_from_cache(self) -> None:
        if (
            self._wechat_probing
            or self._wechat_live_unlocked
            or self._wechat_cache_restore_running
            or self._profile is None
            or self.platform.get() != "wechat"
        ):
            return
        status = self._wechat_status
        if not status.local_dbs_present or status.data_root is None or not status.wxid:
            return
        if not self._wechat_saved_keys_available(status):
            return
        saved_keys = True
        self._wechat_cache_restore_running = True
        self._wechat_probing = True
        self._wechat_chats_loading = True
        self._send.set_list_summary(self.i18n.translate("send.loading_chats"))
        self._send.set_status(
            self.i18n.translate(self._wechat_scan_status_key(status, saved_keys=saved_keys)),
        )
        self._platform_status.set_wechat_probing(status, saved_keys_available=saved_keys)
        self._update_send_state()
        self._sync_status_dock()
        probe_token = self._platform_status.probe_token("wechat")

        def run() -> None:
            probe_status = status
            report: Optional[WeChatProbeReport] = None
            sessions: List[WeChatSessionPreview] = []
            chat_error: Optional[Exception] = None
            try:
                probe_status, report, sessions, chat_error = self._probe_wechat_and_load_sessions(
                    prefer_cache_only=True,
                )
            except (WeChatDbError, WeChatKeyError, OSError, ValueError) as exc:
                chat_error = exc
                probe_status = self._safe_detect_wechat_local()
            self.root.after(
                0,
                lambda ps=probe_status, r=report, s=sessions, e=chat_error, t=probe_token: self._finish_cache_restore(
                    ps,
                    r,
                    s,
                    e,
                    probe_token=t,
                ),
            )

        threading.Thread(target=run, daemon=True).start()

    def _finish_cache_restore(
        self,
        status: WeChatLocalStatus,
        report: Optional[WeChatProbeReport],
        sessions: List[WeChatSessionPreview],
        chat_error: Optional[Exception],
        *,
        probe_token: int,
    ) -> None:
        if self._platform_status.probe_stale("wechat", probe_token) or self.platform.get() != "wechat":
            return
        self._wechat_cache_restore_running = False
        self._wechat_chats_loading = False
        self._wechat_status = status
        if report is None or not report.success or not report.from_cache:
            self._wechat_probing = False
            self._platform_status.clear_probing()
            self._publish_wechat_panel(status)
            self._update_send_state()
            self._sync_status_dock()
            return
        self._apply_wechat_probe(status, report, sessions, chat_error, probe_token=probe_token)

    def _probe_wechat_and_load_sessions(
        self,
        *,
        prefer_cache_only: bool = False,
    ) -> tuple[
        WeChatLocalStatus,
        Optional[WeChatProbeReport],
        List[WeChatSessionPreview],
        Optional[Exception],
    ]:
        status = self._safe_detect_wechat_local()
        profile = self._profile
        if profile is None or status.data_root is None:
            return status, None, [], None
        account_dir = status.data_root
        variant = status.client_variant
        report = run_wechat_key_probe(
            account_dir,
            client_variant=variant,
            mindgraph_user_id=profile.user_id,
            mindgraph_phone=profile.phone,
            wxid=status.wxid,
            prefer_cache=True,
            current_weixin_version=status.weixin_version,
        )
        if prefer_cache_only and not report.from_cache:
            return status, None, [], None
        if not report.success:
            return status, report, [], None
        sessions: List[WeChatSessionPreview] = []
        chat_error: Optional[Exception] = None
        try:
            reader = self._build_wechat_db_reader_with_keys(report.keys, variant, status)
            sessions = reader.list_sessions()
        except (WeChatDbError, WeChatKeyError, OSError, ValueError) as exc:
            chat_error = exc
            report = WeChatProbeReport(
                success=False,
                key_count=0,
                crypto_variant=variant,
                method=report.method,
                weixin_version=report.weixin_version,
                duration_sec=report.duration_sec,
                error=str(exc),
                keys={},
                from_cache=report.from_cache,
            )
        return status, report, sessions, chat_error

    def _build_wechat_db_reader_with_keys(
        self,
        keys: Dict[str, str],
        variant: Optional[str],
        status: Optional[WeChatLocalStatus] = None,
    ) -> WeChatDbReader:
        account_status = status or self._wechat_status
        account_dir = account_status.data_root
        if account_dir is None:
            raise WeChatDbError("WeChat account folder not found")
        db_dir = resolve_db_dir(account_dir, variant)
        cache = DecryptedDbCache(
            db_dir,
            default_cache_dir(account_dir),
            keys=keys,
            client_variant=variant,
            account_dir=account_dir,
        )
        return WeChatDbReader(account_dir, cache=cache, client_variant=variant)

    def _on_wechat_start_probe(self) -> None:
        if self._profile is None:
            return
        log_wechat("Connect button clicked")
        self._clear_stale_wechat_probe()
        if self._wechat_probing:
            return
        status = self._refresh_wechat_status_now()
        saved_keys = self._wechat_saved_keys_available(status)
        if not status.data_root or not status.local_dbs_present:
            self._publish_wechat_panel(status)
            messagebox.showwarning(
                self.i18n.translate("dialog.title"),
                self.i18n.translate("platform.wechat.db_missing"),
                parent=self.root,
            )
            return
        if not saved_keys and not status.process_running:
            self._publish_wechat_panel(status)
            messagebox.showwarning(
                self.i18n.translate("dialog.title"),
                self.i18n.translate("platform.wechat.process_missing"),
                parent=self.root,
            )
            return
        self._wechat_probing = True
        self._wechat_live_unlocked = False
        self._wechat_probe_report = None
        self._wechat_chats_loading = True
        self._selected_chat = None
        self._send.clear_chat_rows()
        self._send.file_list.delete(0, tk.END)
        self._send.set_list_summary(self.i18n.translate("send.loading_chats"))
        self._send.set_status(
            self.i18n.translate(self._wechat_scan_status_key(status, saved_keys=saved_keys)),
        )
        self._update_send_state()
        self._platform_status.set_wechat_probing(status, saved_keys_available=saved_keys)
        self._sync_wechat_source_mode()
        self._sync_status_dock()
        probe_token = self._platform_status.probe_token("wechat")

        def run() -> None:
            probe_status = status
            report: Optional[WeChatProbeReport] = None
            sessions: List[WeChatSessionPreview] = []
            chat_error: Optional[Exception] = None
            try:
                probe_status, report, sessions, chat_error = self._probe_wechat_and_load_sessions()
            except (WeChatDbError, WeChatKeyError, OSError, ValueError) as exc:
                chat_error = exc
                probe_status = self._safe_detect_wechat_local()
            self.root.after(
                0,
                lambda ps=probe_status, r=report, s=sessions, e=chat_error, t=probe_token: self._apply_wechat_probe(
                    ps,
                    r,
                    s,
                    e,
                    probe_token=t,
                ),
            )

        threading.Thread(target=run, daemon=True).start()

    def _wechat_scan_status_key(
        self,
        status: WeChatLocalStatus,
        *,
        saved_keys: bool = False,
    ) -> str:
        if saved_keys:
            return "send.scanning_keys_cached"
        if status.requires_wx_key_hook:
            return "send.scanning_keys_v41_hook"
        key_map = {
            "v3": "send.scanning_keys_v3",
            "v4": "send.scanning_keys_v4",
            "v4.1": "send.scanning_keys_v41",
        }
        return key_map.get(status.client_variant or "", "platform.wechat.probing_generic")

    def _wechat_keys_error_detail(self, report: WeChatProbeReport) -> str:
        if report.error and "wx_key.dll" in report.error.lower():
            if "not found" in report.error.lower():
                return self.i18n.translate("error.wechat_wx_key_dll_missing")
            return self.i18n.translate("error.wechat_wx_key_hook_failed")
        key_map = {
            "v3": "error.wechat_keys_v3_short",
            "v4": "error.wechat_keys_v4_short",
            "v4.1": "error.wechat_keys_v41_hook_short",
        }
        variant = report.crypto_variant or ""
        key = key_map.get(variant, "")
        if key:
            return self.i18n.translate(key)
        if report.error:
            return report.error[:160]
        return self.i18n.translate("send.keys_scan_failed")

    def _apply_wechat_probe(
        self,
        status: WeChatLocalStatus,
        report: Optional[WeChatProbeReport],
        sessions: List[WeChatSessionPreview],
        chat_error: Optional[Exception],
        *,
        probe_token: int,
    ) -> None:
        if self._platform_status.probe_stale("wechat", probe_token) or self.platform.get() != "wechat":
            return
        self._wechat_probing = False
        self._wechat_chats_loading = False
        self._wechat_status = status
        self._platform_status.clear_probing()
        if report is None:
            self._publish_wechat_panel(status)
            if chat_error is not None:
                self._send.set_status(
                    self.i18n.translate("error.wechat_db_read", detail=str(chat_error)),
                    error=True,
                )
            self._update_send_state()
            self._sync_status_dock()
            return
        self._wechat_probe_report = report
        self._wechat_live_unlocked = report.success and chat_error is None
        self._invalidate_wechat_saved_keys_cache()
        saved_keys = self._wechat_saved_keys_available(self._wechat_status)
        self._platform_status.set_wechat_probe_result(
            self._wechat_status,
            report,
            saved_keys_available=saved_keys,
        )
        self._sync_wechat_source_mode()
        if self._wechat_live_unlocked:
            self._apply_wechat_chats(sessions, chat_error)
            self._platform_status.set_wechat_hint("platform.hint.wechat_live")
        elif report.success and chat_error is not None:
            self._send.set_status(
                self.i18n.translate("error.wechat_db_read", detail=str(chat_error)),
                error=True,
            )
            self._refresh_files()
        elif not report.success:
            if self._profile is not None:
                self._setup_export_folder()
            self._refresh_files()
            self._send.set_status(
                self.i18n.translate("send.keys_scan_failed"),
                error=True,
            )
            detail = self._wechat_keys_error_detail(report)
            self._dock.flash(
                "error",
                self.i18n.translate(
                    "platform.wechat.keys_failed",
                    seconds=f"{report.duration_sec:.1f}",
                ),
                detail,
                duration_ms=10000,
            )
        self._update_send_state()
        self._sync_status_dock()

    def _sync_live_source_mode(self) -> None:
        """Toggle between live DB chat list and manual export folder mode."""
        was_live = self._live_db_mode
        platform = self.platform.get()
        live = (
            (platform == "wechat" and self._wechat_live_unlocked)
            or (platform == "dingtalk" and self._dingtalk_live_unlocked)
            or (platform == "wecom" and self._wecom_live_unlocked)
        )
        self._live_db_mode = live
        self._send.set_upload_mode(live)
        self._send.set_folder_row_visible(not live)
        if live:
            self._selected_file = None
        else:
            if was_live:
                self._clear_live_chat_ui()
            else:
                self._selected_chat = None
            if was_live and self._profile is not None and platform in ("wechat", "dingtalk", "wecom"):
                self._refresh_files()
        self._update_send_state()

    def _sync_wechat_source_mode(self) -> None:
        """Backward-compatible alias."""
        self._sync_live_source_mode()

    def _setup_export_folder(self) -> None:
        if self._profile is None:
            return
        export_dir = default_chat_export_dir(self._profile)
        self._send.export_dir.set(str(export_dir))
        if not self._live_db_mode:
            self._refresh_files()

    def _open_connect_dialog(self) -> None:
        """Show the connect-account dialog from the header menu."""
        self._auth.set_values(self.settings.server_url, self.settings.api_token, self.settings.account_phone)
        self._auth.show()

    def _set_content_blocked(self, blocked: bool, *, connecting: bool = False) -> None:
        """Grey out tab content until MindGraph auth succeeds."""
        if blocked:
            if connecting:
                text = self.i18n.translate("content.overlay.connecting")
            else:
                text = self.i18n.translate("content.overlay.sign_in")
            self._content_overlay_label.configure(text=text)
            self._content_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._content_overlay.lift()
            return
        self._content_overlay.place_forget()

    def _on_close(self) -> None:
        self._stop_live_poll()
        self._stop_wechat_poll()
        self._stop_dingtalk_poll()
        self._stop_wecom_poll()
        self.root.destroy()

    def _err_text(self, err: Optional[AppError]) -> str:
        if err is None:
            return self.i18n.translate("error.connection_failed")
        return err.message(self.i18n)

    def _show_error(self, err: AppError, *, auth: bool = True) -> None:
        """Surface an error on the auth panel and bottom status dock."""
        self._persisted_error = err
        msg = self._err_text(err)
        if auth:
            self._auth.set_status(msg, error=True)
        self._sync_status_dock()

    def _clear_errors(self) -> None:
        self._persisted_error = None
        self._session_load_error = None

    def _package_name(self, session: LiveSession) -> str:
        return session.package_name.strip() or self.i18n.translate("packages.untitled")

    def _diagram_line(self, session: LiveSession) -> str:
        diagram = (session.diagram_title or "").strip()
        code = session.code
        if diagram:
            return self.i18n.translate("status.session.secondary_diagram", diagram=diagram, code=code)
        return self.i18n.translate("status.session.secondary_no_diagram", code=code)

    def _on_smartedu_status(self, kind: str, primary: str, secondary: str = "") -> None:
        """Receive status updates from the SmartEdu tab."""
        self._smartedu_status = (kind, primary, secondary)
        self._sync_status_dock()

    def _active_tab_index(self) -> int:
        try:
            return int(self._notebook.index(self._notebook.select()))
        except tk.TclError:
            return 0

    def _sync_status_dock(self) -> None:
        """Refresh the bottom status dock from current app state."""
        if self._active_tab_index() == 1:
            kind, primary, secondary = self._smartedu_status
            if primary:
                dock_kind = (
                    kind
                    if kind
                    in (
                        "offline",
                        "connecting",
                        "connected",
                        "waiting",
                        "ready",
                        "sending",
                        "success",
                        "warning",
                        "error",
                    )
                    else "waiting"
                )
                self._dock.set_context(dock_kind, primary, secondary)
                return
            if self._smartedu.is_busy():
                self._dock.set_context(
                    "sending",
                    self.i18n.translate("smartedu.status.download_primary"),
                    "",
                )
                return

        if self._connecting:
            self._dock.set_context(
                "connecting",
                self.i18n.translate("status.connecting.primary"),
                self.i18n.translate("status.connecting.secondary"),
            )
            return

        if self._sending:
            package = self._package_name(self._selected_session) if self._selected_session else "—"
            self._dock.set_context(
                "sending",
                self.i18n.translate("status.sending.primary"),
                self.i18n.translate("status.sending.secondary", package=package),
            )
            return

        if self._persisted_error is not None:
            self._dock.persist("error", self._err_text(self._persisted_error), "")
            return

        if self._profile is None:
            self._dock.set_context(
                "offline",
                self.i18n.translate("status.offline.primary"),
                self.i18n.translate("status.offline.secondary"),
            )
            return

        if self._session_load_error is not None:
            self._dock.persist(
                "warning" if self._session_load_error.code == ErrorCode.FEATURE_DISABLED else "error",
                self._err_text(self._session_load_error),
                self.i18n.translate("status.wait_web.secondary"),
            )
            return

        display = self._profile.name.strip() or self._profile.phone

        if self._selected_session is not None:
            code = self._selected_session.code
            package = self._package_name(self._selected_session)
            if self._selected_file is not None:
                self._dock.set_context(
                    "ready",
                    self.i18n.translate("status.pairing.primary", code=code),
                    self.i18n.translate(
                        "status.ready.export",
                        file=self._selected_file.title,
                        package=package,
                    ),
                )
                return
            if self._selected_chat is not None:
                self._dock.set_context(
                    "ready",
                    self.i18n.translate("status.pairing.primary", code=code),
                    self.i18n.translate(
                        "status.ready.chat",
                        chat=self._selected_chat.display_name,
                        package=package,
                    ),
                )
                return
            checked = self._checked_chat_indices()
            if checked:
                sessions = self._live_sessions_list()
                if len(checked) == 1:
                    chat_name = sessions[checked[0]].display_name
                    secondary = self.i18n.translate(
                        "status.ready.chat",
                        chat=chat_name,
                        package=package,
                    )
                else:
                    secondary = self.i18n.translate(
                        "status.ready.chats",
                        count=len(checked),
                        package=package,
                    )
                self._dock.set_context(
                    "ready",
                    self.i18n.translate("status.pairing.primary", code=code),
                    secondary,
                )
                return
            self._dock.set_context(
                "connected",
                self.i18n.translate("status.pairing.primary", code=code),
                self.i18n.translate("status.pairing.secondary", package=package),
            )
            return

        if self._wechat_probing and self.platform.get() == "wechat":
            self._dock.set_context(
                "connecting",
                self.i18n.translate("status.sync.primary"),
                self.i18n.translate(
                    self._wechat_scan_status_key(self._wechat_status),
                ),
            )
            return

        if self._dingtalk_probing and self.platform.get() == "dingtalk":
            self._dock.set_context(
                "connecting",
                self.i18n.translate("status.sync.primary"),
                self.i18n.translate("send.scanning_dingtalk_db"),
            )
            return

        if self._wecom_probing and self.platform.get() == "wecom":
            self._dock.set_context(
                "connecting",
                self.i18n.translate("status.sync.primary"),
                self.i18n.translate("send.scanning_wecom_db"),
            )
            return

        if self._live_db_mode and self.platform.get() == "dingtalk":
            secondary = self.i18n.translate("status.sync.dingtalk_live")
            if self._dingtalk_probing:
                secondary = self.i18n.translate("send.scanning_dingtalk_db")
            self._dock.set_context(
                "connected",
                self.i18n.translate("status.sync.primary"),
                secondary,
            )
            return

        if self._dingtalk_status.unlock_ready and self.platform.get() == "dingtalk":
            self._dock.set_context(
                "connected",
                self.i18n.translate("status.sync.primary"),
                self.i18n.translate("status.sync.dingtalk_ready"),
            )
            return

        if self._live_db_mode and self.platform.get() == "wecom":
            secondary = self.i18n.translate("status.sync.wecom_live")
            if self._wecom_probing:
                secondary = self.i18n.translate("send.scanning_wecom_db")
            self._dock.set_context(
                "connected",
                self.i18n.translate("status.sync.primary"),
                secondary,
            )
            return

        if self._wecom_status.local_dbs_present and self.platform.get() == "wecom":
            self._dock.set_context(
                "connected",
                self.i18n.translate("status.sync.primary"),
                self.i18n.translate("status.sync.wecom_ready"),
            )
            return

        if self._live_db_mode and self.platform.get() == "wechat":
            secondary = self.i18n.translate("status.sync.wechat_live")
            if self._wechat_chats_loading:
                secondary = self.i18n.translate(
                    self._wechat_scan_status_key(self._wechat_status),
                )
            self._dock.set_context(
                "connected",
                self.i18n.translate("status.sync.primary"),
                secondary,
            )
            return

        if self._wechat_status.db_ready and self.platform.get() == "wechat":
            self._dock.set_context(
                "connected",
                self.i18n.translate("status.sync.primary"),
                self.i18n.translate("status.sync.wechat_ready"),
            )
            return

        self._dock.set_context(
            "waiting",
            self.i18n.translate("status.sync.primary"),
            self.i18n.translate("status.sync.secondary", name=display),
        )

    def _current_settings(self) -> FileReaderSettings:
        server, token, phone = self._auth.get_values()
        return FileReaderSettings(
            server_url=server,
            api_token=token,
            account_phone=phone,
            platform=self.platform.get(),
        )

    def _client(self) -> FileReaderApiClient:
        return FileReaderApiClient(self._current_settings())

    def _stop_live_poll(self) -> None:
        if self._live_poll_after_id is not None:
            self.root.after_cancel(self._live_poll_after_id)
            self._live_poll_after_id = None

    def _start_live_poll(self) -> None:
        self._stop_live_poll()
        self._refresh_live_sessions()
        self._live_poll_after_id = self.root.after(_LIVE_POLL_MS, self._start_live_poll)

    def _refresh_live_sessions(self) -> None:
        if self._profile is None:
            return

        def run() -> None:
            ok, sessions, err = self._client().list_waiting_sessions()
            self.root.after(0, lambda: self._apply_live_sessions(ok, sessions, err))

        threading.Thread(target=run, daemon=True).start()

    def _apply_live_sessions(
        self,
        ok: bool,
        sessions: List[LiveSession],
        err: Optional[AppError],
    ) -> None:
        if not ok:
            self._session_load_error = err
            self._sync_status_dock()
            return

        self._session_load_error = None
        previous_code = self._selected_session.code if self._selected_session else None
        self._live_sessions = sessions
        self._selected_session = None
        if previous_code:
            for session in sessions:
                if session.code == previous_code:
                    self._selected_session = session
                    break
        if self._selected_session is None and sessions:
            self._selected_session = sessions[0]
        self._update_send_state()
        self._sync_status_dock()

    def _apply_connect_result(self, result: ConnectResult) -> None:
        self._profile = result.profile if result.credentials_valid else None
        self._packages = result.packages if result.credentials_valid else []
        authenticated = result.credentials_valid and result.profile is not None
        self._header.set_profile(result.profile if authenticated else None)
        self._send.set_authenticated(authenticated)
        self._send.set_controls_enabled(authenticated)
        self._smartedu.set_authenticated(authenticated, self._packages)
        self._set_content_blocked(not authenticated)
        if authenticated and not result.ok:
            self._session_load_error = result.error
        else:
            self._session_load_error = None
        if authenticated:
            self._setup_export_folder()
            self._wechat_status = self._safe_detect_wechat_local()
            self._dingtalk_status = detect_dingtalk_local()
            self._wecom_status = detect_wecom_local()
            self._clear_stale_wechat_probe()
            self._clear_stale_dingtalk_probe()
            self._clear_stale_wecom_probe()
            if self.platform.get() == "wechat":
                self._publish_wechat_panel(self._wechat_status)
            elif self.platform.get() == "dingtalk":
                self._publish_dingtalk_panel(self._dingtalk_status)
            elif self.platform.get() == "wecom":
                self._publish_wecom_panel(self._wecom_status)
            self._start_live_poll()
            self._sync_platform_polls(self.platform.get())
            self.root.after(800, self._maybe_restore_wechat_from_cache)
            self.root.after(900, self._maybe_restore_wecom_from_cache)
        else:
            self._abandon_platform_probes()
            self._stop_live_poll()
            self._stop_wechat_poll()
            self._stop_dingtalk_poll()
            self._stop_wecom_poll()
            self._live_sessions = []
            self._selected_session = None
            self._packages = []
            self._selected_chat = None
            self._db_sessions = []
            self._dingtalk_sessions = []
            self._wecom_sessions = []
            self._live_db_mode = False
            self._wechat_live_unlocked = False
            self._dingtalk_live_unlocked = False
            self._wecom_live_unlocked = False
            self._wechat_probe_report = None
            self._dingtalk_db_reader = None
            self._wecom_db_reader = None
            self._wecom_probe_keys = {}
            self._wechat_chats_loading = False
            self._clear_live_chat_ui()
            self._send.set_upload_mode(False)
            self._send.set_folder_row_visible(True)
        self._update_send_state()
        self._sync_status_dock()

    def _on_chat_check_changed(self) -> None:
        self._update_send_state()
        self._sync_status_dock()

    def _checked_chat_indices(self) -> List[int]:
        if not self._live_db_mode:
            return []
        return self._send.get_checked_chat_indices()

    def _update_send_state(self) -> None:
        if self._live_db_mode:
            checked = self._checked_chat_indices()
            has_selection = len(checked) > 0
        else:
            has_selection = self._selected_file is not None
        busy = (
            self._sending
            or self._exporting
            or self._connecting
            or self._wechat_chats_loading
            or self._dingtalk_probing
            or self._wecom_probing
        )
        can_export = self._profile is not None and not busy
        if self._live_db_mode:
            can_export = can_export and has_selection
        can_upload = self._profile is not None and self._selected_session is not None and has_selection and not busy
        self._send.set_export_enabled(can_export)
        self._send.set_upload_enabled(can_upload)
        self._send.set_controls_enabled(self._profile is not None and not self._connecting)

    def _validate_server_url(self, server_url: str) -> Optional[str]:
        """Return normalized server URL or show an error."""
        try:
            return normalize_server_url(server_url)
        except ServerUrlError:
            self._show_error(AppError(code=ErrorCode.SERVER_URL_INVALID))
            return None

    def _clear_credentials(self) -> None:
        if self._connecting or self._sending or self._smartedu.is_busy():
            return
        if not messagebox.askyesno(
            self.i18n.translate("auth.clear_confirm_title"),
            self.i18n.translate("auth.clear_confirm_body"),
        ):
            return
        self._stop_live_poll()
        self._stop_wechat_poll()
        self._stop_dingtalk_poll()
        self._stop_wecom_poll()
        self.settings.clear()
        self._clear_errors()
        self._selected_file = None
        self._selected_chat = None
        self._db_sessions = []
        self._dingtalk_sessions = []
        self._wecom_sessions = []
        self._live_db_mode = False
        self._wechat_chats_loading = False
        self._dingtalk_live_unlocked = False
        self._dingtalk_probing = False
        self._dingtalk_db_reader = None
        self._wecom_live_unlocked = False
        self._wecom_probing = False
        self._wecom_db_reader = None
        self._wecom_probe_keys = {}
        self._invalidate_wechat_saved_keys_cache()
        self._auth.set_values(DEFAULT_SERVER_URL, "", "")
        self._apply_connect_result(ConnectResult(credentials_valid=False, profile=None, packages=[], error=None))
        self._auth.set_status(self.i18n.translate("auth.cleared"))
        self._dock.flash(
            "success",
            self.i18n.translate("status.cleared.primary"),
            self.i18n.translate("status.cleared.secondary"),
            duration_ms=6000,
        )

    def _connect(self) -> None:
        if self._connecting:
            return
        self.settings = self._current_settings()
        normalized = self._validate_server_url(self.settings.server_url)
        if normalized is None:
            return
        self.settings.server_url = normalized
        if not self.settings.api_token or not self.settings.account_phone:
            text = self.i18n.translate("auth.enter_credentials")
            self._show_error(AppError(code=ErrorCode.MISSING_CREDENTIALS))
            self._auth.set_status(text, error=True)
            return

        self._connecting = True
        self._clear_errors()
        self._auth.set_busy(True)
        self._auth.set_status(self.i18n.translate("auth.connecting"))
        self._set_content_blocked(True, connecting=True)
        self._sync_status_dock()
        client = FileReaderApiClient(self.settings)

        def run() -> None:
            result = client.connect()
            self.root.after(0, lambda: self._finish_connect(result))

        threading.Thread(target=run, daemon=True).start()

    def _finish_connect(self, result: ConnectResult) -> None:
        self._connecting = False
        self._auth.set_busy(False)
        encrypt_err = AppError(code=ErrorCode.CREDENTIALS_ENCRYPT_FAILED)

        if result.ok and result.profile is not None:
            try:
                self.settings.save()
            except DpapiError:
                self._show_error(encrypt_err)
                return
            self._clear_errors()
            self._apply_connect_result(result)
            self._auth.set_status(self.i18n.translate("auth.saved"))
            display = result.profile.name.strip() or result.profile.phone
            self._dock.flash(
                "success",
                self.i18n.translate("status.connected.primary", name=display),
                self.i18n.translate("status.connected.secondary", server=self.settings.server_url),
                duration_ms=5000,
            )
            if self._auth.is_open():
                self._auth.close()
            self._sync_status_dock()
            return

        if result.credentials_valid and result.profile is not None:
            try:
                self.settings.save()
            except DpapiError:
                self._show_error(encrypt_err)
                return
            self._session_load_error = result.error
            self._apply_connect_result(result)
            if result.error is not None:
                self._show_error(result.error)
            return

        self._apply_connect_result(result)
        if result.error is not None:
            self._show_error(result.error)
            self._open_connect_dialog()

    def _browse_folder(self) -> None:
        if self._profile is None:
            return
        chosen = filedialog.askdirectory()
        if not chosen:
            return
        self._send.export_dir.set(chosen)
        self._refresh_files()

    def _refresh_wechat_chats(self) -> None:
        if not self._live_db_mode or self._profile is None:
            return
        if self._wechat_probe_report and self._wechat_probe_report.success:
            return
        self._on_wechat_start_probe()

    def _apply_wechat_chats(
        self,
        sessions: List[WeChatSessionPreview],
        error: Optional[Exception],
    ) -> None:
        self._wechat_chats_loading = False
        self._db_sessions = sessions
        self._selected_chat = None
        self._chat_preview_token += 1
        self._send.clear_chat_preview()
        self._send.clear_chat_rows()
        if error is not None:
            self._wechat_live_unlocked = False
            self._live_db_mode = False
            self._send.set_upload_mode(False)
            self._send.set_folder_row_visible(True)
            self._send.clear_list_summary()
            if self._profile is not None and not self._send.export_dir.get().strip():
                self._send.export_dir.set(str(default_chat_export_dir(self._profile)))
            self._send.set_status(
                self.i18n.translate("error.wechat_db_read", detail=str(error)),
                error=True,
            )
            self._refresh_files()
            self._update_send_state()
            self._sync_status_dock()
            return
        if not sessions:
            self._send.set_status(self.i18n.translate("send.chats_empty"))
            self._send.set_list_summary(self.i18n.translate("send.chats_empty"))
        else:
            self._send.set_status("")
            self._send.set_list_summary(
                self.i18n.translate("send.chats_loaded", count=len(sessions)),
            )
        chat_labels = [
            self._send.format_chat_row(
                session.display_name,
                is_group=session.is_group,
                time_label=format_session_time(session.last_timestamp),
            )
            for session in sessions
        ]
        self._send.set_chat_rows(chat_labels)
        self._update_send_state()
        self._sync_status_dock()

    def _on_select_chat(self, index: int) -> None:
        sessions = self._live_sessions_list()
        if not self._live_db_mode or index < 0 or index >= len(sessions):
            return
        chat = sessions[index]
        self._selected_chat = chat
        self._selected_file = None
        self._send.chat_title.set(chat.display_name)
        self._chat_preview_token += 1
        token = self._chat_preview_token
        self._send.set_chat_preview(self.i18n.translate("send.chat_preview_loading"))
        threading.Thread(
            target=self._load_chat_preview,
            args=(chat, token),
            daemon=True,
        ).start()
        self._update_send_state()
        self._sync_status_dock()

    def _build_wechat_db_reader(self) -> WeChatDbReader:
        keys = self._wechat_probe_report.keys if self._wechat_probe_report else None
        if not keys:
            raise WeChatDbError("WeChat database keys are not loaded")
        return self._build_wechat_db_reader_with_keys(keys, self._wechat_status.client_variant)

    def _load_chat_preview(self, chat: LiveChatSession, token: int) -> None:
        try:
            messages = self._load_live_messages(chat)
        except (WeChatDbError, WeChatKeyError, DingTalkDbError, OSError, ValueError) as exc:
            detail = self.i18n.translate("send.chat_preview_error", detail=str(exc))
            self.root.after(0, lambda: self._apply_chat_preview("", detail, token))
            return
        shown = min(len(messages), 40)
        if not messages:
            header = self.i18n.translate("send.chat_preview_empty")
            body = ""
        else:
            header = self.i18n.translate(
                "send.chat_preview_count",
                count=len(messages),
                shown=shown,
            )
            if isinstance(chat, DingTalkSessionPreview):
                body = format_dingtalk_chat_preview(messages)
            elif isinstance(chat, WeComSessionPreview):
                body = format_wecom_chat_preview(messages)
            else:
                body = format_chat_preview(messages)
        preview_text = header if not body else f"{header}\n\n{body}"
        self.root.after(0, lambda: self._apply_chat_preview(preview_text, "", token))

    def _apply_chat_preview(self, text: str, error: str, token: int) -> None:
        if token != self._chat_preview_token:
            return
        self._send.set_chat_preview(error or text)

    def _refresh_files(self) -> None:
        if self._live_db_mode:
            return
        root_path = Path(self._send.export_dir.get())
        if self.platform.get() == "dingtalk":
            self._previews = dingtalk_reader.list_export_files(root_path)
        else:
            self._previews = wechat_reader.list_export_files(root_path)
        self._selected_file = None
        self._send.clear_chat_rows()
        self._send.file_list.delete(0, tk.END)
        for preview in self._previews:
            self._send.file_list.insert(
                tk.END,
                self._send.format_file_row(preview.title, preview.message_count),
            )
        if self._previews:
            self._send.set_list_summary(
                self.i18n.translate("send.export_files_loaded", count=len(self._previews)),
            )
        else:
            self._send.clear_list_summary()
        self._sync_status_dock()

    def _on_select_file(self, _event: object) -> None:
        selection = self._send.file_list.curselection()
        if not selection:
            self._selected_file = None
            self._selected_chat = None
            self._update_send_state()
            self._sync_status_dock()
            return
        preview = self._previews[selection[0]]
        self._selected_file = preview
        self._selected_chat = None
        self._send.chat_title.set(preview.title)
        self._update_send_state()
        self._sync_status_dock()

    def _export_selected(self) -> None:
        if self._exporting or self._profile is None:
            return
        export_dir = Path(self._send.export_dir.get())
        if not self._live_db_mode:
            if not export_dir.is_dir():
                messagebox.showwarning(
                    self.i18n.translate("dialog.title"),
                    self.i18n.translate("send.export_folder_missing"),
                )
                return
            if sys.platform == "win32":
                subprocess.run(["explorer", str(export_dir.resolve())], check=False)
                return
            messagebox.showinfo(
                self.i18n.translate("dialog.title"),
                str(export_dir),
            )
            return

        selection = self._checked_chat_indices()
        if not selection:
            messagebox.showwarning(
                self.i18n.translate("dialog.title"),
                self.i18n.translate("dialog.pick_chat"),
            )
            return
        if not export_dir.is_dir():
            messagebox.showwarning(
                self.i18n.translate("dialog.title"),
                self.i18n.translate("send.export_folder_missing"),
            )
            return
        chats = [self._live_sessions_list()[index] for index in selection]
        platform = self.platform.get()

        def run() -> None:
            self._exporting = True
            self.root.after(0, self._update_send_state)
            exported_names: List[str] = []
            try:
                total = len(chats)
                for step, chat in enumerate(chats, start=1):
                    chat_title = chat.display_name
                    out_path = unique_export_path(export_dir, chat_title)
                    self.root.after(
                        0,
                        lambda s=step, t=total, name=chat_title: self._send.set_status(
                            self.i18n.translate(
                                "send.export_batch_progress",
                                current=s,
                                total=t,
                                name=name,
                            ),
                        ),
                    )
                    messages = self._load_live_messages(chat)
                    chat_messages.write_export_file(
                        out_path,
                        messages,
                        title=chat_title,
                        platform=platform,
                    )
                    exported_names.append(out_path.name)
            except (WeChatDbError, WeChatKeyError, DingTalkDbError, OSError, ValueError) as exc:
                if isinstance(exc, (WeChatDbError, DingTalkDbError)):
                    code = ErrorCode.WECHAT_DB_READ
                else:
                    code = ErrorCode.PARSE_FILE
                parse_err = AppError(code=code, raw_detail=str(exc))
                self.root.after(0, lambda pe=parse_err: self._show_error(pe, auth=False))
            else:

                def on_success() -> None:
                    summary = self.i18n.translate(
                        "send.export_batch_done",
                        count=len(exported_names),
                    )
                    self._send.set_status(summary)
                    self._dock.flash(
                        "success",
                        summary,
                        str(export_dir),
                        duration_ms=6000,
                    )

                self.root.after(0, on_success)
            finally:
                self._exporting = False
                self.root.after(0, self._update_send_state)

        threading.Thread(target=run, daemon=True).start()

    def _send_selected(self) -> None:
        if self._sending or self._profile is None:
            return
        session = self._selected_session
        if session is None:
            messagebox.showwarning(
                self.i18n.translate("dialog.title"),
                self.i18n.translate("dialog.open_web_import"),
            )
            return
        if self._live_db_mode:
            selection = self._checked_chat_indices()
            if not selection:
                messagebox.showwarning(
                    self.i18n.translate("dialog.title"),
                    self.i18n.translate("dialog.pick_chat"),
                )
                return
            selected_chats = [self._live_sessions_list()[index] for index in selection]
        else:
            selection = self._send.file_list.curselection()
            if not selection:
                messagebox.showwarning(
                    self.i18n.translate("dialog.title"),
                    self.i18n.translate("dialog.pick_file"),
                )
                return
            preview = self._previews[selection[0]]
            self._selected_file = preview
            selected_chats = []
        self.settings = self._current_settings()
        normalized = self._validate_server_url(self.settings.server_url)
        if normalized is None:
            return
        self.settings.server_url = normalized
        try:
            self.settings.save()
        except DpapiError:
            self._show_error(AppError(code=ErrorCode.CREDENTIALS_ENCRYPT_FAILED))
            return
        client = FileReaderApiClient(self.settings)
        platform = self.platform.get()
        pairing_code = session.code
        preview = None if self._live_db_mode else self._selected_file

        def run() -> None:
            self._sending = True
            self.root.after(0, self._update_send_state)
            self.root.after(0, self._sync_status_dock)
            uploaded_count = 0
            try:
                if self._live_db_mode:
                    total = len(selected_chats)
                    for step, chat in enumerate(selected_chats, start=1):
                        chat_title = chat.display_name
                        source_name = self._session_message_key(chat)
                        self.root.after(
                            0,
                            lambda s=step, t=total, name=chat_title: self._send.set_status(
                                self.i18n.translate(
                                    "send.upload_batch_progress",
                                    current=s,
                                    total=t,
                                    name=name,
                                ),
                            ),
                        )
                        try:
                            messages = self._load_live_messages(chat)
                            content = chat_messages.messages_to_markdown(
                                messages,
                                chat_title,
                                platform,
                            ).strip()
                        except (OSError, ValueError, UnicodeDecodeError, WeChatDbError, DingTalkDbError) as parse_exc:
                            code = (
                                ErrorCode.WECHAT_DB_READ
                                if isinstance(parse_exc, (WeChatDbError, DingTalkDbError))
                                else ErrorCode.PARSE_FILE
                            )
                            parse_err = AppError(code=code, raw_detail=str(parse_exc))
                            self.root.after(0, lambda pe=parse_err: self._show_error(pe, auth=False))
                            return
                        result = client.ingest_transcript(
                            code=pairing_code,
                            platform=platform,
                            chat_title=chat_title,
                            content=content,
                            source_export_name=source_name,
                        )
                        if not result.ok:
                            upload_err = result.error or AppError(code=ErrorCode.UPLOAD_FAILED)
                            self.root.after(0, lambda ue=upload_err: self._show_error(ue, auth=False))
                            return
                        uploaded_count += 1
                else:
                    chat_title = self._send.chat_title.get()
                    source_name = preview.path.name if preview is not None else ""
                    try:
                        if preview is not None and platform == "dingtalk":
                            messages = dingtalk_reader.parse_export_file(preview.path)
                            content = chat_messages.messages_to_markdown(
                                messages,
                                chat_title,
                                platform,
                            ).strip()
                        elif preview is not None:
                            content = chat_messages.export_content_for_upload(
                                preview.path,
                                chat_title,
                                platform,
                            )
                        else:
                            raise ValueError("no chat source selected")
                    except (OSError, ValueError, UnicodeDecodeError, WeChatDbError) as parse_exc:
                        code = (
                            ErrorCode.WECHAT_DB_READ if isinstance(parse_exc, WeChatDbError) else ErrorCode.PARSE_FILE
                        )
                        parse_err = AppError(code=code, raw_detail=str(parse_exc))
                        self.root.after(0, lambda: self._show_error(parse_err, auth=False))
                        return
                    result = client.ingest_transcript(
                        code=pairing_code,
                        platform=platform,
                        chat_title=chat_title,
                        content=content,
                        source_export_name=source_name,
                    )
                    if not result.ok:
                        err = result.error or AppError(code=ErrorCode.UPLOAD_FAILED)
                        self.root.after(0, lambda: self._show_error(err, auth=False))
                        return
                    uploaded_count = 1
            finally:
                self._sending = False
                self.root.after(0, self._update_send_state)
                self.root.after(0, self._sync_status_dock)

            if uploaded_count <= 0:
                return

            if uploaded_count == 1:
                primary = self.i18n.translate("status.sent.primary")
                secondary = self.i18n.translate("status.sent.secondary_generic")
            else:
                primary = self.i18n.translate("status.sent_batch.primary", count=uploaded_count)
                secondary = self.i18n.translate("status.sent_batch.secondary")

            def on_success() -> None:
                self._dock.flash("success", primary, secondary, duration_ms=8000)
                self._refresh_live_sessions()
                self._sync_status_dock()

            self.root.after(0, on_success)

        threading.Thread(target=run, daemon=True).start()


def _resolve_icon_path() -> Optional[Path]:
    candidates: List[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if isinstance(meipass, str):
        candidates.append(Path(meipass) / "assets" / "icon.png")
    candidates.append(_ASSETS_DIR / "icon.png")
    for path in candidates:
        if path.is_file():
            return path
    return None


def _apply_window_icon(root: tk.Tk) -> None:
    icon_path = _resolve_icon_path()
    if icon_path is None:
        return
    try:
        image = tk.PhotoImage(file=str(icon_path))
        _ICON_REF.append(image)
        root.iconphoto(True, image)
    except tk.TclError:
        pass


def run_gui() -> None:
    """Launch the file reader window."""
    root = tk.Tk()
    _apply_window_icon(root)
    FileReaderApp(root)
    root.mainloop()
