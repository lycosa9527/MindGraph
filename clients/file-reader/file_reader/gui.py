"""MindGraph file-reader desktop UI."""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import List, Optional

from file_reader import dingtalk_reader, wechat_reader
from file_reader.api_client import ConnectResult, FileReaderApiClient, LiveSession, UserProfile
from file_reader.dpapi_store import DpapiError
from file_reader.errors import AppError, ErrorCode
from file_reader.i18n import I18n
from file_reader.server_url import ServerUrlError, normalize_server_url
from file_reader.settings import DEFAULT_SERVER_URL, FileReaderSettings
from file_reader.status_dock import StatusDock
from file_reader.theme import BG_APP, WINDOW_MIN_HEIGHT, WINDOW_MIN_WIDTH
from file_reader.wechat_reader import ExportPreview
from file_reader.widgets import AppHeader, AuthPanel, LiveSessionPanel, SendPanel

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_ICON_REF: List[tk.PhotoImage] = []
_LIVE_POLL_MS = 2000


class FileReaderApp:
    """Desktop helper to send local chat exports to Document Summary."""

    def __init__(self, root: tk.Tk, i18n: Optional[I18n] = None) -> None:
        self.root = root
        self.i18n = i18n or I18n.auto()
        self.root.title(self.i18n.translate("app.title"))
        self.root.configure(bg=BG_APP)
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.geometry("820x720")

        self.settings = FileReaderSettings.load()
        self.platform = tk.StringVar(value=self.settings.platform)
        self._profile: Optional[UserProfile] = None
        self._live_sessions: List[LiveSession] = []
        self._previews: List[ExportPreview] = []
        self._selected_file: Optional[ExportPreview] = None
        self._sending = False
        self._connecting = False
        self._selected_session: Optional[LiveSession] = None
        self._live_poll_after_id: Optional[str] = None
        self._persisted_error: Optional[AppError] = None
        self._session_load_error: Optional[AppError] = None

        self._header = AppHeader(root, self.i18n)
        self._header.pack(fill="x")

        self._dock = StatusDock(root)
        self._dock.pack(side="bottom", fill="x")

        body = tk.Frame(root, bg=BG_APP, padx=20, pady=16)
        body.pack(fill="both", expand=True)

        self._auth = AuthPanel(body, self.i18n, on_connect=self._connect, on_clear=self._clear_credentials)
        self._auth.pack(fill="x", pady=(0, 14))
        self._auth.set_values(self.settings.server_url, self.settings.api_token, self.settings.account_phone)

        self._live = LiveSessionPanel(body, self.i18n, on_select=self._on_session_selected)
        self._live.pack(fill="both", expand=True, pady=(0, 14))

        self._send = SendPanel(
            body,
            self.i18n,
            on_browse=self._browse_folder,
            on_send=self._send_selected,
            platform_var=self.platform,
        )
        self._send.pack(fill="both", expand=True)
        self._send.set_send_enabled(False)

        self.platform.trace_add("write", lambda *_args: self._refresh_files())
        self._send.file_list.bind("<<ListboxSelect>>", self._on_select_file)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._sync_status_dock()

        if self.settings.api_token and self.settings.account_phone:
            self.root.after(400, self._connect)

    def _on_close(self) -> None:
        self._stop_live_poll()
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

    def _sync_status_dock(self) -> None:
        """Refresh the bottom status dock from current app state."""
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

        if self._selected_session is not None and self._selected_file is not None:
            package = self._package_name(self._selected_session)
            diagram = (self._selected_session.diagram_title or "").strip()
            secondary = (
                self.i18n.translate("status.ready.secondary", package=package, diagram=diagram)
                if diagram
                else self.i18n.translate("status.ready.secondary_no_diagram", package=package)
            )
            self._dock.set_context(
                "ready",
                self.i18n.translate("status.ready.primary", file=self._selected_file.title),
                secondary,
            )
            return

        if self._selected_session is not None:
            package = self._package_name(self._selected_session)
            self._dock.set_context(
                "connected",
                self.i18n.translate("status.session.primary", package=package),
                self._diagram_line(self._selected_session),
            )
            return

        if self._live_sessions:
            self._dock.set_context(
                "waiting",
                self.i18n.translate("status.sessions.primary", count=len(self._live_sessions)),
                self.i18n.translate("status.sessions.secondary"),
            )
            return

        self._dock.set_context(
            "waiting",
            self.i18n.translate("status.connected.primary", name=display),
            self.i18n.translate("status.wait_web.secondary"),
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
            if err and err.code == ErrorCode.FEATURE_DISABLED:
                self._live.set_load_error(self._err_text(err))
            self._sync_status_dock()
            return

        self._session_load_error = None
        self._live.set_load_error(None)
        previous_code = self._selected_session.code if self._selected_session else None
        self._live_sessions = sessions
        self._live.set_sessions(sessions)
        if previous_code:
            for session in sessions:
                if session.code == previous_code:
                    self._selected_session = session
                    break
            else:
                self._selected_session = None
        elif len(sessions) == 1:
            self._live.select_first_if_none()
            self._selected_session = self._live.selected_session()
        self._update_send_state()
        self._sync_status_dock()

    def _apply_connect_result(self, result: ConnectResult) -> None:
        self._profile = result.profile if result.credentials_valid else None
        authenticated = result.credentials_valid and result.profile is not None
        self._header.set_profile(result.profile if authenticated else None)
        self._live.set_authenticated(authenticated)
        if authenticated and not result.ok:
            self._session_load_error = result.error
            self._live.set_load_error(self._err_text(result.error))
        else:
            self._session_load_error = None
            self._live.set_load_error(None)
        if authenticated:
            self._start_live_poll()
        else:
            self._stop_live_poll()
            self._live.set_sessions([])
            self._selected_session = None
        self._update_send_state()
        self._sync_status_dock()

    def _update_send_state(self) -> None:
        enabled = (
            self._profile is not None
            and self._selected_session is not None
            and not self._sending
            and not self._connecting
        )
        self._send.set_send_enabled(enabled)

    def _on_session_selected(self, session: LiveSession) -> None:
        self._selected_session = session
        self._update_send_state()
        self._sync_status_dock()

    def _validate_server_url(self, server_url: str) -> Optional[str]:
        """Return normalized server URL or show an error."""
        try:
            return normalize_server_url(server_url)
        except ServerUrlError:
            self._show_error(AppError(code=ErrorCode.SERVER_URL_INVALID))
            return None

    def _clear_credentials(self) -> None:
        if self._connecting or self._sending:
            return
        if not messagebox.askyesno(
            self.i18n.translate("auth.clear_confirm_title"),
            self.i18n.translate("auth.clear_confirm_body"),
        ):
            return
        self._stop_live_poll()
        self.settings.clear()
        self._clear_errors()
        self._selected_file = None
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

    def _browse_folder(self) -> None:
        chosen = filedialog.askdirectory()
        if not chosen:
            return
        self._send.export_dir.set(chosen)
        self._refresh_files()

    def _refresh_files(self) -> None:
        root_path = Path(self._send.export_dir.get())
        if self.platform.get() == "dingtalk":
            self._previews = dingtalk_reader.list_export_files(root_path)
        else:
            self._previews = wechat_reader.list_export_files(root_path)
        self._selected_file = None
        self._send.file_list.delete(0, tk.END)
        for preview in self._previews:
            self._send.file_list.insert(
                tk.END,
                self._send.format_file_row(preview.title, preview.message_count),
            )
        self._sync_status_dock()

    def _on_select_file(self, _event: object) -> None:
        selection = self._send.file_list.curselection()
        if not selection:
            self._selected_file = None
            self._sync_status_dock()
            return
        preview = self._previews[selection[0]]
        self._selected_file = preview
        self._send.chat_title.set(preview.title)
        self._sync_status_dock()

    def _send_selected(self) -> None:
        if self._sending or self._profile is None:
            return
        session = self._live.selected_session() or self._selected_session
        if session is None:
            messagebox.showwarning(
                self.i18n.translate("dialog.title"),
                self.i18n.translate("dialog.pick_session"),
            )
            return
        selection = self._send.file_list.curselection()
        if not selection:
            messagebox.showwarning(
                self.i18n.translate("dialog.title"),
                self.i18n.translate("dialog.pick_file"),
            )
            return

        preview = self._previews[selection[0]]
        self._selected_file = preview
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
        chat_title = self._send.chat_title.get()
        pairing_code = session.code

        def run() -> None:
            self._sending = True
            self.root.after(0, self._update_send_state)
            self.root.after(0, self._sync_status_dock)
            try:
                try:
                    if platform == "dingtalk":
                        messages = dingtalk_reader.parse_export_file(preview.path)
                        payload = dingtalk_reader.messages_to_payload(messages)
                    else:
                        messages = wechat_reader.parse_export_file(preview.path)
                        payload = wechat_reader.messages_to_payload(messages)
                except (OSError, ValueError, UnicodeDecodeError) as parse_exc:
                    parse_err = AppError(code=ErrorCode.PARSE_FILE, raw_detail=str(parse_exc))
                    self.root.after(0, lambda: self._show_error(parse_err, auth=False))
                    return
                result = client.ingest_transcript(
                    code=pairing_code,
                    platform=platform,
                    chat_title=chat_title,
                    messages=payload,
                    source_export_name=preview.path.name,
                )
                if result.ok:
                    if result.document_id is not None:
                        primary = self.i18n.translate("status.sent.primary")
                        secondary = self.i18n.translate(
                            "status.sent.secondary",
                            id=result.document_id,
                        )
                    else:
                        primary = self.i18n.translate("status.sent.primary")
                        secondary = self.i18n.translate("status.sent.secondary_generic")

                    def on_success() -> None:
                        self._dock.flash("success", primary, secondary, duration_ms=8000)
                        self._refresh_live_sessions()
                        self._sync_status_dock()

                    self.root.after(0, on_success)
                else:
                    err = result.error or AppError(code=ErrorCode.UPLOAD_FAILED)
                    self.root.after(0, lambda: self._show_error(err, auth=False))
            finally:
                self._sending = False
                self.root.after(0, self._update_send_state)
                self.root.after(0, self._sync_status_dock)

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
