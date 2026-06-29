"""SmartEdu tab panel for the file-reader desktop app."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable, Dict, List, Optional

from file_reader.api_client import FileReaderApiClient, PackageItem
from file_reader.dpapi_store import DpapiError
from file_reader.i18n import I18n
from file_reader.smartedu import metadata as smartedu_metadata
from file_reader.smartedu.downloader import download_asset
from file_reader.smartedu.models import SmartEduAsset, SmartEduLesson
from file_reader.smartedu.token_store import (
    clear_smartedu_token,
    load_smartedu_token,
    save_smartedu_token,
)
from file_reader.smartedu.url_parser import parse_smartedu_url
from file_reader.smartedu_login import open_smartedu_login_async, pywebview_available
from file_reader.theme import (
    ACCENT,
    BG_APP,
    BG_CARD,
    BG_DISABLED,
    BG_MUTED,
    BORDER,
    FONT_BODY,
    FONT_CAPTION,
    FONT_HEADER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

StatusCallback = Callable[[str, str, str], None]


class SmartEduPanel(tk.Frame):
    """Paste SmartEdu URL, pick assets, download locally, optional MindGraph upload."""

    def __init__(
        self,
        master: tk.Misc,
        i18n: I18n,
        client_factory: Callable[[], FileReaderApiClient],
        on_status: StatusCallback,
        *,
        authenticated: bool = False,
    ) -> None:
        super().__init__(master, bg=BG_APP)
        self._i18n = i18n
        self._client_factory = client_factory
        self._on_status = on_status
        self._authenticated = authenticated
        self._lesson: Optional[SmartEduLesson] = None
        self._packages: List[PackageItem] = []
        self._asset_vars: Dict[str, tk.BooleanVar] = {}
        self._busy = False
        self._token = load_smartedu_token()

        default_dir = Path.home() / "Downloads" / "MindGraph" / "SmartEdu"
        self._save_dir = tk.StringVar(value=str(default_dir))
        self._upload_var = tk.BooleanVar(value=False)

        card = tk.Frame(self, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True)

        inner = tk.Frame(card, bg=BG_CARD, padx=16, pady=14)
        inner.pack(fill="both", expand=True)

        self._title = tk.Label(inner, bg=BG_CARD, fg=TEXT_PRIMARY, font=FONT_HEADER)
        self._title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self._url_label = tk.Label(inner, bg=BG_CARD, fg=TEXT_SECONDARY, font=FONT_CAPTION)
        self._url_label.grid(row=1, column=0, sticky="w")
        self._url_var = tk.StringVar()
        url_entry = tk.Entry(
            inner,
            textvariable=self._url_var,
            font=FONT_BODY,
            relief="flat",
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
        )
        url_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(8, 0), ipady=6)
        url_entry.bind("<FocusOut>", lambda _event: self._parse_url_quiet())

        login_row = tk.Frame(inner, bg=BG_CARD)
        login_row.grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self._login_btn = tk.Button(
            login_row,
            font=FONT_BODY,
            relief="flat",
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
            padx=12,
            pady=6,
            command=self._open_login,
        )
        self._login_btn.pack(side="left")
        self._token_label = tk.Label(login_row, bg=BG_CARD, fg=TEXT_MUTED, font=FONT_CAPTION)
        self._token_label.pack(side="left", padx=(12, 0))
        self._paste_btn = tk.Button(
            login_row,
            font=FONT_BODY,
            relief="flat",
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
            padx=10,
            pady=6,
            command=self._paste_token,
        )
        self._paste_btn.pack(side="left", padx=(8, 0))
        self._clear_token_btn = tk.Button(
            login_row,
            font=FONT_BODY,
            relief="flat",
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
            padx=10,
            pady=6,
            command=self._clear_token,
        )
        self._clear_token_btn.pack(side="left", padx=(8, 0))

        self._lesson_label = tk.Label(inner, bg=BG_CARD, fg=TEXT_PRIMARY, font=FONT_BODY, anchor="w", justify="left")
        self._lesson_label.grid(row=3, column=0, columnspan=3, sticky="w", pady=(12, 4))

        self._asset_frame = tk.Frame(inner, bg=BG_CARD)
        self._asset_frame.grid(row=4, column=0, columnspan=3, sticky="w")

        self._folder_label = tk.Label(inner, bg=BG_CARD, fg=TEXT_SECONDARY, font=FONT_CAPTION)
        self._folder_label.grid(row=5, column=0, sticky="w", pady=(12, 0))
        tk.Entry(
            inner,
            textvariable=self._save_dir,
            font=FONT_BODY,
            relief="flat",
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
        ).grid(row=5, column=1, sticky="ew", padx=(8, 8), pady=(12, 0), ipady=6)
        self._browse_btn = tk.Button(
            inner,
            font=FONT_BODY,
            relief="flat",
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
            padx=12,
            pady=6,
            command=self._browse_folder,
        )
        self._browse_btn.grid(row=5, column=2, pady=(12, 0))

        upload_row = tk.Frame(inner, bg=BG_CARD)
        upload_row.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self._upload_check = tk.Checkbutton(
            upload_row,
            variable=self._upload_var,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=FONT_BODY,
            selectcolor=BG_MUTED,
            activebackground=BG_CARD,
            command=self._sync_upload_controls,
        )
        self._upload_check.pack(side="left")
        self._package_label = tk.Label(upload_row, bg=BG_CARD, fg=TEXT_SECONDARY, font=FONT_CAPTION)
        self._package_label.pack(side="left", padx=(12, 4))
        self._package_combo = ttk.Combobox(upload_row, state="disabled", width=36)
        self._package_combo.pack(side="left", fill="x", expand=True)

        self._download_btn = tk.Button(
            inner,
            font=FONT_BODY,
            bg=ACCENT,
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief="flat",
            padx=16,
            pady=10,
            command=self._download_selected,
        )
        self._download_btn.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(14, 0))

        self._hint = tk.Label(inner, bg=BG_CARD, fg=TEXT_MUTED, font=FONT_CAPTION, wraplength=640, justify="left")
        self._hint.grid(row=8, column=0, columnspan=3, sticky="w", pady=(8, 0))

        inner.columnconfigure(1, weight=1)
        self.apply_texts()
        self._refresh_token_badge()
        self._sync_upload_controls()

        self._overlay = tk.Frame(self, bg=BG_DISABLED)
        self._overlay_label = tk.Label(
            self._overlay,
            bg=BG_DISABLED,
            fg=TEXT_SECONDARY,
            font=FONT_BODY,
            wraplength=640,
            justify="center",
        )
        self._overlay_label.place(relx=0.5, rely=0.5, anchor="center")
        if not self._authenticated:
            self._show_auth_overlay()

    def _show_auth_overlay(self) -> None:
        self._overlay_label.configure(text=self._i18n.translate("smartedu.overlay"))
        self._overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._overlay.lift()

    def _hide_auth_overlay(self) -> None:
        self._overlay.place_forget()

    def apply_texts(self) -> None:
        """Refresh labels for the active locale."""
        self._title.configure(text=self._i18n.translate("smartedu.title"))
        self._url_label.configure(text=self._i18n.translate("smartedu.url"))
        self._login_btn.configure(text=self._i18n.translate("smartedu.login"))
        self._paste_btn.configure(text=self._i18n.translate("smartedu.paste_token"))
        self._clear_token_btn.configure(text=self._i18n.translate("smartedu.clear_token"))
        self._folder_label.configure(text=self._i18n.translate("smartedu.save_folder"))
        self._browse_btn.configure(text=self._i18n.translate("smartedu.browse"))
        self._upload_check.configure(text=self._i18n.translate("smartedu.upload"))
        self._package_label.configure(text=self._i18n.translate("smartedu.package"))
        self._download_btn.configure(text=self._i18n.translate("smartedu.download"))
        self._hint.configure(text=self._i18n.translate("smartedu.hint"))
        self._refresh_token_badge()
        self._render_assets()

    def set_authenticated(self, authenticated: bool, packages: Optional[List[PackageItem]] = None) -> None:
        """Update MindGraph auth state and package dropdown."""
        self._authenticated = authenticated
        if authenticated:
            self._hide_auth_overlay()
        else:
            self._show_auth_overlay()
        if packages is not None:
            self._packages = packages
        names = [pkg.name.strip() or self._i18n.translate("packages.untitled") for pkg in self._packages]
        self._package_combo.configure(values=names)
        if names:
            self._package_combo.current(0)
        self._sync_upload_controls()

    def is_busy(self) -> bool:
        """True while parse/download/upload is running."""
        return self._busy

    def _sync_upload_controls(self) -> None:
        enabled = self._upload_var.get() and self._authenticated and bool(self._packages)
        state = "readonly" if enabled else "disabled"
        self._package_combo.configure(state=state)

    def _refresh_token_badge(self) -> None:
        if self._token:
            self._token_label.configure(
                text=self._i18n.translate("smartedu.token_connected"),
                fg="#059669",
            )
        else:
            self._token_label.configure(
                text=self._i18n.translate("smartedu.token_missing"),
                fg="#dc2626",
            )

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self._download_btn.configure(state=state)
        self._login_btn.configure(state=state)

    def _open_login(self) -> None:
        if self._busy:
            return
        if not pywebview_available():
            messagebox.showinfo(
                self._i18n.translate("dialog.title"),
                self._i18n.translate("smartedu.pywebview_missing"),
            )
            return
        self._on_status("connecting", self._i18n.translate("smartedu.status.login_primary"), "")
        self._set_busy(True)

        def on_done(token: str) -> None:
            self.after(0, lambda: self._finish_login(token))

        open_smartedu_login_async(on_done)

    def _finish_login(self, token: str) -> None:
        self._set_busy(False)
        if not token:
            self._on_status("warning", self._i18n.translate("smartedu.status.login_cancel"), "")
            return
        try:
            save_smartedu_token(token)
        except DpapiError:
            messagebox.showerror(
                self._i18n.translate("dialog.title"),
                self._i18n.translate("error.credentials_encrypt_failed"),
            )
            return
        self._token = token
        self._refresh_token_badge()
        self._on_status("success", self._i18n.translate("smartedu.status.login_ok"), "")

    def _paste_token(self) -> None:
        if self._busy:
            return
        token = simpledialog.askstring(
            self._i18n.translate("smartedu.paste_token_title"),
            self._i18n.translate("smartedu.paste_token_body"),
            parent=self,
        )
        if not token or not token.strip():
            return
        try:
            save_smartedu_token(token.strip())
        except DpapiError:
            messagebox.showerror(
                self._i18n.translate("dialog.title"),
                self._i18n.translate("error.credentials_encrypt_failed"),
            )
            return
        self._token = token.strip()
        self._refresh_token_badge()

    def _clear_token(self) -> None:
        if self._busy:
            return
        if not messagebox.askyesno(
            self._i18n.translate("smartedu.clear_token_title"),
            self._i18n.translate("smartedu.clear_token_body"),
        ):
            return
        clear_smartedu_token()
        self._token = ""
        self._refresh_token_badge()

    def _browse_folder(self) -> None:
        chosen = filedialog.askdirectory()
        if chosen:
            self._save_dir.set(chosen)

    def _parse_url_quiet(self) -> None:
        if self._busy:
            return
        url = self._url_var.get().strip()
        if not url:
            return
        try:
            parsed = parse_smartedu_url(url)
            lesson = smartedu_metadata.fetch_lesson(parsed)
        except ValueError:
            return
        self._apply_lesson(lesson)

    def _ensure_lesson(self) -> Optional[SmartEduLesson]:
        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning(
                self._i18n.translate("dialog.title"),
                self._i18n.translate("smartedu.error.no_url"),
            )
            return None
        try:
            parsed = parse_smartedu_url(url)
            lesson = smartedu_metadata.fetch_lesson(parsed)
        except ValueError as exc:
            messagebox.showerror(self._i18n.translate("dialog.title"), str(exc))
            return None
        self._apply_lesson(lesson)
        return lesson

    def _apply_lesson(self, lesson: SmartEduLesson) -> None:
        self._lesson = lesson
        self._lesson_label.configure(text=self._i18n.translate("smartedu.lesson", title=lesson.title))
        self._render_assets()

    def _render_assets(self) -> None:
        for child in self._asset_frame.winfo_children():
            child.destroy()
        self._asset_vars.clear()
        if self._lesson is None:
            return
        for index, asset in enumerate(self._lesson.assets):
            var = tk.BooleanVar(value=asset.selected)
            self._asset_vars[asset.asset_id] = var
            label = self._asset_label(asset)
            row = index // 2
            col = index % 2
            tk.Checkbutton(
                self._asset_frame,
                text=label,
                variable=var,
                bg=BG_CARD,
                fg=TEXT_PRIMARY,
                font=FONT_BODY,
                selectcolor=BG_MUTED,
                activebackground=BG_CARD,
                anchor="w",
            ).grid(row=row, column=col, sticky="w", padx=(0, 24), pady=2)

    def _asset_label(self, asset: SmartEduAsset) -> str:
        key = f"smartedu.asset.{asset.resource_type}"
        fmt = asset.format.upper()
        translated = self._i18n.translate(key)
        if translated == key:
            translated = asset.alias
        return f"{translated} ({fmt})"

    def _selected_assets(self) -> List[SmartEduAsset]:
        if self._lesson is None:
            return []
        selected: List[SmartEduAsset] = []
        for asset in self._lesson.assets:
            var = self._asset_vars.get(asset.asset_id)
            if var is not None and var.get():
                selected.append(asset)
        return selected

    def _download_selected(self) -> None:
        if self._busy:
            return
        lesson = self._ensure_lesson()
        if lesson is None:
            return
        assets = self._selected_assets()
        if not assets:
            messagebox.showwarning(
                self._i18n.translate("dialog.title"),
                self._i18n.translate("smartedu.error.no_assets"),
            )
            return
        folder = Path(self._save_dir.get().strip() or str(Path.home() / "Downloads"))
        upload = self._upload_var.get() and self._authenticated
        package_id = 0
        if upload:
            if not self._packages:
                messagebox.showwarning(
                    self._i18n.translate("dialog.title"),
                    self._i18n.translate("smartedu.error.no_package"),
                )
                return
            index = max(self._package_combo.current(), 0)
            package_id = self._packages[index].id

        token = self._token or load_smartedu_token()
        if not token:
            messagebox.showwarning(
                self._i18n.translate("dialog.title"),
                self._i18n.translate("smartedu.error.no_token"),
            )
            return

        self._set_busy(True)
        self._on_status(
            "sending",
            self._i18n.translate("smartedu.status.download_primary"),
            self._i18n.translate("smartedu.status.download_secondary", count=len(assets)),
        )

        def run() -> None:
            errors: List[str] = []
            saved: List[Path] = []
            for index, asset in enumerate(assets):
                fraction = index / max(len(assets), 1)
                asset_alias = asset.alias
                self.after(
                    0,
                    lambda f=fraction, name=asset_alias: self._on_status(
                        "sending",
                        self._i18n.translate("smartedu.status.download_item", name=name),
                        "",
                    ),
                )

                def make_progress(alias: str) -> Callable[[str, float], None]:
                    def progress(_name: str, frac: float) -> None:
                        self.after(
                            0,
                            lambda ff=frac, nm=alias: self._on_status(
                                "sending",
                                self._i18n.translate("smartedu.status.download_item", name=nm),
                                f"{int(ff * 100)}%",
                            ),
                        )

                    return progress

                try:
                    path = download_asset(
                        asset,
                        folder,
                        lesson.title,
                        token,
                        progress=make_progress(asset_alias),
                    )
                    saved.append(path)
                    asset.local_path = path
                except ValueError as exc:
                    errors.append(f"{asset.alias}: {exc}")

            upload_errors: List[str] = []
            if upload and package_id and saved:
                client = self._client_factory()
                for path in saved:
                    if path.suffix.lower() != ".pdf":
                        continue
                    self.after(
                        0,
                        lambda p=path.name: self._on_status(
                            "sending",
                            self._i18n.translate("smartedu.status.upload_item", name=p),
                            "",
                        ),
                    )
                    result = client.upload_package_document(package_id, path)
                    if not result.ok:
                        detail = result.error.message(self._i18n) if result.error else "upload failed"
                        upload_errors.append(f"{path.name}: {detail}")

            self.after(0, lambda: self._finish_download(saved, errors, upload_errors))

        threading.Thread(target=run, daemon=True).start()

    def _finish_download(self, saved: List[Path], errors: List[str], upload_errors: List[str]) -> None:
        self._set_busy(False)
        if saved and not errors and not upload_errors:
            self._on_status(
                "success",
                self._i18n.translate("smartedu.status.done_primary", count=len(saved)),
                self._i18n.translate("smartedu.status.done_secondary", folder=str(saved[0].parent)),
            )
            return
        if saved:
            primary = self._i18n.translate("smartedu.status.partial_primary", ok=len(saved))
            parts = errors + upload_errors
            secondary = "; ".join(parts[:3])
            self._on_status("warning", primary, secondary)
            return
        detail = "; ".join((errors + upload_errors)[:2]) or self._i18n.translate("smartedu.status.failed")
        self._on_status("error", self._i18n.translate("smartedu.status.failed"), detail)
