"""Reusable UI widgets for the file-reader desktop app."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional

from file_reader.api_client import LiveSession, PackageItem, UserProfile
from file_reader.chat.conversation_list import ConversationCheckboxList
from file_reader.mousewheel import bind_vertical_mousewheel, wheel_scroll_units
from file_reader.edition_subtitle import edition_subtitle_for_profile
from file_reader.i18n import I18n
from file_reader.server_url import (
    DEFAULT_SERVER_PRESET_LABEL,
    SERVER_URL_PRESET_LABELS,
    ServerUrlError,
    preset_label_for_server_url,
    server_url_from_preset_label,
)
from file_reader.theme import (
    ACCENT,
    BG_APP,
    BG_CARD,
    BG_DISABLED,
    BG_HEADER,
    BG_MUTED,
    BORDER,
    BORDER_ACTIVE,
    BORDER_HOVER,
    CARD_GAP,
    CARD_HEIGHT,
    CARD_PAD,
    CARD_WIDTH,
    FONT_BODY,
    FONT_CAPTION,
    FONT_HEADER,
    FONT_LOGO,
    FONT_TITLE,
    SUCCESS,
    TEXT_MUTED,
    TEXT_ON_DARK,
    TEXT_ON_DARK_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class AppHeader(tk.Frame):
    """Dark header bar with MindGraph M logo and user account menu."""

    def __init__(
        self,
        master: tk.Misc,
        i18n: I18n,
        *,
        on_connect_account: Callable[[], None],
        on_relogin: Callable[[], None],
        on_logout: Callable[[], None],
        on_settings: Callable[[], None],
    ) -> None:
        super().__init__(master, bg=BG_HEADER, height=64)
        self._i18n = i18n
        self._on_connect_account = on_connect_account
        self._on_relogin = on_relogin
        self._on_logout = on_logout
        self._on_settings = on_settings
        self._hover_after_id: Optional[str] = None
        self._menu_open = False
        self.pack_propagate(False)

        logo_wrap = tk.Frame(self, bg=BG_HEADER)
        logo_wrap.pack(side="left", padx=(16, 10), pady=8)

        logo = tk.Canvas(logo_wrap, width=36, height=36, bg=BG_HEADER, highlightthickness=0)
        logo.pack(side="left")
        logo.create_rectangle(2, 2, 34, 34, fill=BG_HEADER, outline="#78716c", width=1)
        logo.create_text(18, 19, text="M", fill=TEXT_ON_DARK, font=FONT_LOGO)

        titles = tk.Frame(logo_wrap, bg=BG_HEADER)
        titles.pack(side="left", padx=(10, 0))
        self._app_title = tk.Label(titles, bg=BG_HEADER, fg=TEXT_ON_DARK, font=FONT_TITLE, padx=0, pady=0)
        self._app_title.pack(anchor="w", pady=(0, 0))
        self._app_subtitle = tk.Label(
            titles,
            bg=BG_HEADER,
            fg=TEXT_ON_DARK_MUTED,
            font=(FONT_CAPTION[0], 8),
            padx=0,
            pady=0,
        )
        self._app_subtitle.pack(anchor="w", pady=(0, 0))

        self._user_hit = tk.Frame(
            self,
            bg=BG_HEADER,
            highlightbackground="#57534e",
            highlightthickness=1,
            cursor="hand2",
        )
        self._user_hit.pack(side="right", padx=16, pady=10)

        inner_user = tk.Frame(self._user_hit, bg=BG_HEADER, padx=8, pady=4)
        inner_user.pack()

        self._name_label = tk.Label(
            inner_user,
            bg=BG_HEADER,
            fg=TEXT_ON_DARK_MUTED,
            font=FONT_BODY,
            cursor="hand2",
        )
        self._name_label.pack(side="left", padx=(0, 8))

        self._avatar_label = tk.Label(
            inner_user,
            text="👤",
            bg="#292524",
            fg=TEXT_ON_DARK,
            font=(FONT_BODY[0], 14),
            width=2,
            height=1,
            padx=4,
            pady=2,
            cursor="hand2",
        )
        self._avatar_label.pack(side="left")

        self._profile: Optional[UserProfile] = None

        for widget in (self._user_hit, inner_user, self._avatar_label, self._name_label):
            widget.bind("<Button-1>", self._on_user_click)
            widget.bind("<Enter>", self._on_user_enter)
            widget.bind("<Leave>", self._on_user_leave)

        self.apply_texts()

    def apply_texts(self) -> None:
        """Refresh labels for the active locale."""
        self._app_title.configure(text=self._i18n.translate("header.app_name"))
        if self._profile is None:
            self._name_label.configure(text=self._i18n.translate("header.not_signed_in"))
            self._app_subtitle.configure(text=self._i18n.translate("header.subtitle.guest"))
            return
        self._app_subtitle.configure(text=edition_subtitle_for_profile(self._i18n, self._profile))

    def set_profile(self, profile: Optional[UserProfile]) -> None:
        """Update avatar, display name, and edition subtitle."""
        self._profile = profile
        if profile is None:
            self._avatar_label.configure(text="👤")
            self._name_label.configure(text=self._i18n.translate("header.not_signed_in"), fg=TEXT_ON_DARK_MUTED)
            self._app_subtitle.configure(text=self._i18n.translate("header.subtitle.guest"))
            return
        avatar = profile.avatar.strip() or "👤"
        display = profile.name.strip() or profile.phone
        self._avatar_label.configure(text=avatar[:2] if len(avatar) > 2 else avatar)
        self._name_label.configure(text=display, fg=TEXT_ON_DARK)
        subtitle = edition_subtitle_for_profile(self._i18n, profile)
        self._app_subtitle.configure(text=subtitle)

    def _cancel_hover_menu(self) -> None:
        if self._hover_after_id is not None:
            self.after_cancel(self._hover_after_id)
            self._hover_after_id = None

    def _on_user_enter(self, _event: object) -> None:
        self._cancel_hover_menu()
        self._hover_after_id = self.after(350, self._show_user_menu)

    def _on_user_leave(self, _event: object) -> None:
        self._cancel_hover_menu()

    def _on_user_click(self, event: object) -> None:
        self._cancel_hover_menu()
        self._show_user_menu(event)

    def _show_user_menu(self, event: object | None = None) -> None:
        if self._menu_open:
            return
        self._menu_open = True
        menu = tk.Menu(self, tearoff=0)
        signed_in = self._profile is not None
        if signed_in:
            menu.add_command(
                label=self._i18n.translate("header.menu.relogin"),
                command=self._on_relogin,
            )
            menu.add_command(
                label=self._i18n.translate("header.menu.logout"),
                command=self._on_logout,
            )
            menu.add_separator()
        else:
            menu.add_command(
                label=self._i18n.translate("header.menu.connect"),
                command=self._on_connect_account,
            )
            menu.add_separator()
        menu.add_command(
            label=self._i18n.translate("header.menu.settings"),
            command=self._on_settings,
        )

        def close_menu() -> None:
            self._menu_open = False

        menu.bind("<Unmap>", lambda _event: close_menu())

        if event is not None and hasattr(event, "x_root") and hasattr(event, "y_root"):
            x_root = int(getattr(event, "x_root", 0))
            y_root = int(getattr(event, "y_root", 0))
            menu.post(x_root, y_root)
        else:
            self._user_hit.update_idletasks()
            x = self._user_hit.winfo_rootx()
            y = self._user_hit.winfo_rooty() + self._user_hit.winfo_height()
            menu.post(x, y)


class AuthPanel(tk.Frame):
    """Compact credential form."""

    def __init__(
        self,
        master: tk.Misc,
        i18n: I18n,
        on_connect: Callable[[], None],
        on_clear: Callable[[], None],
    ) -> None:
        super().__init__(master, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        self._i18n = i18n
        inner = tk.Frame(self, bg=BG_CARD, padx=16, pady=14)
        inner.pack(fill="x")

        self._title = tk.Label(inner, bg=BG_CARD, fg=TEXT_PRIMARY, font=FONT_HEADER)
        self._title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self._field_labels: List[tk.Label] = []
        self._server_label = tk.Label(inner, bg=BG_CARD, fg=TEXT_SECONDARY, font=FONT_CAPTION)
        self._server_label.grid(row=1, column=0, sticky="w", pady=4)
        self._field_labels.append(self._server_label)
        self._server_combo = ttk.Combobox(
            inner,
            values=list(SERVER_URL_PRESET_LABELS),
            state="readonly",
            font=FONT_BODY,
        )
        self._server_combo.grid(row=1, column=1, columnspan=2, sticky="ew", ipady=4, padx=(8, 0), pady=4)
        self._server_combo.set(DEFAULT_SERVER_PRESET_LABEL)

        self._entries: List[tk.Entry] = []
        for row_idx, show in ((2, "*"), (3, "")):
            label = tk.Label(inner, bg=BG_CARD, fg=TEXT_SECONDARY, font=FONT_CAPTION)
            label.grid(row=row_idx, column=0, sticky="w", pady=4)
            self._field_labels.append(label)
            entry = tk.Entry(
                inner,
                font=FONT_BODY,
                relief="flat",
                bg=BG_MUTED,
                fg=TEXT_PRIMARY,
                insertbackground=TEXT_PRIMARY,
                show=show,
            )
            entry.grid(row=row_idx, column=1, columnspan=2, sticky="ew", ipady=6, padx=(8, 0), pady=4)
            self._entries.append(entry)

        btn_row = tk.Frame(inner, bg=BG_CARD)
        btn_row.grid(row=4, column=1, columnspan=2, sticky="w", pady=(12, 0))

        self._connect_btn = tk.Button(
            btn_row,
            font=FONT_BODY,
            bg=ACCENT,
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief="flat",
            padx=16,
            pady=8,
            cursor="hand2",
            command=on_connect,
        )
        self._connect_btn.pack(side="left")

        self._clear_btn = tk.Button(
            btn_row,
            font=FONT_BODY,
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
            activebackground=BORDER,
            activeforeground=TEXT_PRIMARY,
            relief="flat",
            padx=14,
            pady=8,
            cursor="hand2",
            command=on_clear,
        )
        self._clear_btn.pack(side="left", padx=(8, 0))

        self._status = tk.Label(inner, text="", bg=BG_CARD, fg=TEXT_MUTED, font=FONT_CAPTION, wraplength=520)
        self._status.grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))

        inner.columnconfigure(1, weight=1)
        self.apply_texts()

    def apply_texts(self) -> None:
        """Refresh labels for the active locale."""
        self._title.configure(text=self._i18n.translate("auth.title"))
        keys = ("auth.server", "auth.token", "auth.phone")
        for label, key in zip(self._field_labels, keys):
            label.configure(text=self._i18n.translate(key))
        self._connect_btn.configure(text=self._i18n.translate("auth.connect"))
        self._clear_btn.configure(text=self._i18n.translate("auth.clear"))

    def set_values(self, server_url: str, api_token: str, phone: str) -> None:
        """Populate form fields."""
        try:
            preset_label = preset_label_for_server_url(server_url)
        except ServerUrlError:
            preset_label = DEFAULT_SERVER_PRESET_LABEL
        self._server_combo.set(preset_label)
        for entry, value in zip(self._entries, (api_token, phone)):
            entry.delete(0, tk.END)
            entry.insert(0, value)

    def get_values(self) -> tuple[str, str, str]:
        """Read server, token, phone from the form."""
        label = self._server_combo.get().strip()
        try:
            server_url = server_url_from_preset_label(label)
        except ServerUrlError:
            server_url = server_url_from_preset_label(DEFAULT_SERVER_PRESET_LABEL)
        return (
            server_url,
            self._entries[0].get().strip(),
            self._entries[1].get().strip(),
        )

    def set_status(self, text: str, *, error: bool = False) -> None:
        """Show helper or error text under the form."""
        color = "#dc2626" if error else TEXT_MUTED
        self._status.configure(text=text, fg=color)

    def set_busy(self, busy: bool) -> None:
        """Disable connect while a request is in flight."""
        state = tk.DISABLED if busy else tk.NORMAL
        self._connect_btn.configure(state=state)
        self._clear_btn.configure(state=state)


class LiveSessionPanel(tk.Frame):
    """Cards for website pairing sessions detected in real time."""

    def __init__(
        self,
        master: tk.Misc,
        i18n: I18n,
        on_select: Callable[[LiveSession], None],
    ) -> None:
        super().__init__(master, bg=BG_APP)
        self._i18n = i18n
        self._on_select = on_select
        self._authenticated = False
        self._sessions: List[LiveSession] = []
        self._selected_code: Optional[str] = None
        self._card_widgets: List[tk.Misc] = []

        header = tk.Frame(self, bg=BG_APP)
        header.pack(fill="x", padx=4, pady=(0, 8))
        self._title = tk.Label(header, bg=BG_APP, fg=TEXT_PRIMARY, font=FONT_HEADER)
        self._title.pack(side="left")
        self._hint = tk.Label(header, text="", bg=BG_APP, fg=TEXT_MUTED, font=FONT_CAPTION)
        self._hint.pack(side="right")

        self._canvas = tk.Canvas(self, bg=BG_APP, highlightthickness=0, height=260)
        self._scroll = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._inner = tk.Frame(self._canvas, bg=BG_APP)
        self._inner.bind(
            "<Configure>",
            lambda _event: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._canvas.configure(yscrollcommand=self._scroll.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._scroll.pack(side="right", fill="y")

        self._overlay = tk.Frame(self, bg=BG_DISABLED)
        self._overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._overlay_label = tk.Label(
            self._overlay,
            bg=BG_DISABLED,
            fg=TEXT_SECONDARY,
            font=FONT_BODY,
            wraplength=640,
            justify="center",
        )
        self._overlay_label.place(relx=0.5, rely=0.5, anchor="center")
        self._load_error: Optional[str] = None
        self.apply_texts()

    def set_load_error(self, message: Optional[str]) -> None:
        """Show a server-side load failure in the session list."""
        self._load_error = message.strip() if message else None
        self.set_sessions(self._sessions)

    def apply_texts(self) -> None:
        """Refresh labels for the active locale."""
        self._title.configure(text=self._i18n.translate("live.title"))
        self._overlay_label.configure(text=self._i18n.translate("live.overlay"))
        self.set_sessions(self._sessions)

    def set_authenticated(self, authenticated: bool) -> None:
        """Toggle grey overlay until credentials are verified."""
        self._authenticated = authenticated
        if authenticated:
            self._overlay.place_forget()
        else:
            self._overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._overlay.lift()

    def set_sessions(self, sessions: List[LiveSession]) -> None:
        """Render live session cards."""
        self._sessions = sessions
        for widget in self._card_widgets:
            widget.destroy()
        self._card_widgets.clear()

        if not sessions:
            empty_text = self._load_error if self._load_error else self._i18n.translate("live.empty")
            empty = tk.Label(
                self._inner,
                text=empty_text,
                bg=BG_APP,
                fg="#dc2626" if self._load_error else TEXT_MUTED,
                font=FONT_BODY,
                wraplength=640,
                justify="left",
            )
            empty.grid(row=0, column=0, padx=8, pady=12, sticky="w")
            self._card_widgets.append(empty)
            self._hint.configure(text=self._i18n.translate("live.polling"))
            return

        cols = 2
        for index, session in enumerate(sessions):
            row = index // cols
            col = index % cols
            card = self._build_card(self._inner, session)
            card.grid(row=row, column=col, padx=CARD_GAP // 2, pady=CARD_GAP // 2, sticky="nw")
            self._card_widgets.append(card)

        self._hint.configure(text=self._i18n.translate("live.count", count=len(sessions)))

    def _display_name(self, session: LiveSession) -> str:
        name = session.package_name.strip()
        return name or self._i18n.translate("packages.untitled")

    def _build_card(self, master: tk.Frame, session: LiveSession) -> tk.Frame:
        enabled = self._authenticated
        bg = BG_CARD if enabled else BG_DISABLED
        border = BORDER_ACTIVE if session.code == self._selected_code else BORDER
        frame = tk.Frame(
            master,
            bg=bg,
            width=CARD_WIDTH + 40,
            height=CARD_HEIGHT + 20,
            highlightbackground=border,
            highlightthickness=2,
            cursor="hand2" if enabled else "arrow",
        )
        frame.pack_propagate(False)

        inner = tk.Frame(frame, bg=bg, padx=CARD_PAD, pady=CARD_PAD)
        inner.pack(fill="both", expand=True)

        top = tk.Frame(inner, bg=bg)
        top.pack(fill="x")
        tk.Label(
            top,
            text=self._i18n.translate("live.badge"),
            bg="#ecfdf5",
            fg=SUCCESS,
            font=(FONT_CAPTION[0], 8, "bold"),
            padx=6,
            pady=1,
        ).pack(side="left")
        minutes = max(1, round(session.expires_in_seconds / 60))
        tk.Label(
            top,
            text=self._i18n.translate("live.expires", minutes=minutes),
            bg=bg,
            fg=TEXT_MUTED,
            font=FONT_CAPTION,
        ).pack(side="right")

        tk.Label(
            inner,
            text=self._display_name(session),
            bg=bg,
            fg=TEXT_PRIMARY if enabled else TEXT_MUTED,
            font=FONT_BODY,
            wraplength=CARD_WIDTH + 20,
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(8, 2))

        diagram = (session.diagram_title or "").strip()
        if diagram:
            tk.Label(
                inner,
                text=self._i18n.translate("live.diagram", diagram=diagram),
                bg=bg,
                fg=TEXT_SECONDARY,
                font=FONT_CAPTION,
                wraplength=CARD_WIDTH + 20,
                anchor="w",
                justify="left",
            ).pack(fill="x", pady=(0, 4))

        tk.Label(
            inner,
            text=session.code,
            bg=bg,
            fg=TEXT_PRIMARY,
            font=(FONT_BODY[0], 16, "bold"),
        ).pack(anchor="w")

        tk.Label(
            inner,
            text=self._i18n.translate("live.waiting"),
            bg=bg,
            fg=TEXT_SECONDARY,
            font=FONT_CAPTION,
        ).pack(anchor="w", pady=(6, 0))

        if enabled:

            def on_enter(_event: object, card_frame: tk.Frame = frame) -> None:
                card_frame.configure(highlightbackground=BORDER_HOVER)

            def on_leave(_event: object, card_frame: tk.Frame = frame, item: LiveSession = session) -> None:
                active = BORDER_ACTIVE if item.code == self._selected_code else BORDER
                card_frame.configure(highlightbackground=active)

            frame.bind("<Enter>", on_enter)
            frame.bind("<Leave>", on_leave)
            frame.bind("<Button-1>", lambda _e, s=session: self._select(s))
            for child in inner.winfo_children():
                child.bind("<Button-1>", lambda _e, s=session: self._select(s))

        return frame

    def _select(self, session: LiveSession) -> None:
        self._selected_code = session.code
        self.set_sessions(self._sessions)
        self._on_select(session)

    def select_first_if_none(self) -> None:
        """Select the only live session when unambiguous."""
        if self._selected_code is not None or not self._sessions:
            return
        self._select(self._sessions[0])

    def selected_session(self) -> Optional[LiveSession]:
        """Return the highlighted live session, if any."""
        for session in self._sessions:
            if session.code == self._selected_code:
                return session
        return None


class PackageCardGrid(tk.Frame):
    """Scrollable grid of Knowledge Space package cards."""

    def __init__(
        self,
        master: tk.Misc,
        i18n: I18n,
        on_select: Callable[[PackageItem], None],
    ) -> None:
        super().__init__(master, bg=BG_APP)
        self._i18n = i18n
        self._on_select = on_select
        self._authenticated = False
        self._packages: List[PackageItem] = []
        self._selected_id: Optional[int] = None
        self._card_widgets: List[tk.Misc] = []

        header = tk.Frame(self, bg=BG_APP)
        header.pack(fill="x", padx=4, pady=(0, 8))
        self._title = tk.Label(header, bg=BG_APP, fg=TEXT_PRIMARY, font=FONT_HEADER)
        self._title.pack(side="left")
        self._hint = tk.Label(header, text="", bg=BG_APP, fg=TEXT_MUTED, font=FONT_CAPTION)
        self._hint.pack(side="right")

        self._canvas = tk.Canvas(self, bg=BG_APP, highlightthickness=0, height=260)
        self._scroll = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._inner = tk.Frame(self._canvas, bg=BG_APP)
        self._inner.bind(
            "<Configure>",
            lambda _event: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._canvas.configure(yscrollcommand=self._scroll.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._scroll.pack(side="right", fill="y")

        self._overlay = tk.Frame(self, bg=BG_DISABLED)
        self._overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._overlay_label = tk.Label(
            self._overlay,
            bg=BG_DISABLED,
            fg=TEXT_SECONDARY,
            font=FONT_BODY,
        )
        self._overlay_label.place(relx=0.5, rely=0.5, anchor="center")
        self._load_error: Optional[str] = None
        self.apply_texts()

    def set_load_error(self, message: Optional[str]) -> None:
        """Show a server-side load failure instead of the empty-packages hint."""
        self._load_error = message.strip() if message else None
        self.set_packages(self._packages)

    def apply_texts(self) -> None:
        """Refresh labels for the active locale."""
        self._title.configure(text=self._i18n.translate("packages.title"))
        self._overlay_label.configure(text=self._i18n.translate("packages.overlay"))
        self.set_packages(self._packages)

    def set_authenticated(self, authenticated: bool) -> None:
        """Toggle grey overlay until credentials are verified."""
        self._authenticated = authenticated
        if authenticated:
            self._overlay.place_forget()
        else:
            self._overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._overlay.lift()

    def set_packages(self, packages: List[PackageItem]) -> None:
        """Render package cards."""
        self._packages = packages
        for widget in self._card_widgets:
            widget.destroy()
        self._card_widgets.clear()

        if not packages:
            empty_text = self._load_error if self._load_error else self._i18n.translate("packages.empty")
            empty = tk.Label(
                self._inner,
                text=empty_text,
                bg=BG_APP,
                fg="#dc2626" if self._load_error else TEXT_MUTED,
                font=FONT_BODY,
                wraplength=640,
                justify="left",
            )
            empty.grid(row=0, column=0, padx=8, pady=12, sticky="w")
            self._card_widgets.append(empty)
            self._hint.configure(text="")
            return

        cols = 3
        for index, package in enumerate(packages):
            row = index // cols
            col = index % cols
            card = self._build_card(self._inner, package)
            card.grid(
                row=row,
                column=col,
                padx=CARD_GAP // 2,
                pady=CARD_GAP // 2,
                sticky="nw",
            )
            self._card_widgets.append(card)

        self._hint.configure(text=self._i18n.translate("packages.count", count=len(packages)))

    def _display_name(self, package: PackageItem) -> str:
        name = package.name.strip()
        return name or self._i18n.translate("packages.untitled")

    def _build_card(self, master: tk.Frame, package: PackageItem) -> tk.Frame:
        enabled = self._authenticated
        bg = BG_CARD if enabled else BG_DISABLED
        border = BORDER_ACTIVE if package.id == self._selected_id else BORDER
        frame = tk.Frame(
            master,
            bg=bg,
            width=CARD_WIDTH,
            height=CARD_HEIGHT,
            highlightbackground=border,
            highlightthickness=2,
            cursor="hand2" if enabled else "arrow",
        )
        frame.pack_propagate(False)

        inner = tk.Frame(frame, bg=bg, padx=CARD_PAD, pady=CARD_PAD)
        inner.pack(fill="both", expand=True)

        title_color = TEXT_PRIMARY if enabled else TEXT_MUTED
        tk.Label(
            inner,
            text=self._display_name(package),
            bg=bg,
            fg=title_color,
            font=FONT_BODY,
            wraplength=CARD_WIDTH - CARD_PAD * 2,
            justify="left",
            anchor="w",
        ).pack(fill="x")

        meta = self._i18n.translate(
            "packages.sources",
            completed=package.completed_count,
            total=package.document_count,
        )
        if package.diagram_id:
            meta += self._i18n.translate("packages.linked_diagram")
        tk.Label(inner, text=meta, bg=bg, fg=TEXT_MUTED, font=FONT_CAPTION, anchor="w").pack(fill="x", pady=(6, 0))

        badge = package.source or package.status
        tk.Label(
            inner,
            text=badge,
            bg=BG_MUTED if enabled else "#cbd5e1",
            fg=TEXT_SECONDARY if enabled else TEXT_MUTED,
            font=FONT_CAPTION,
            padx=8,
            pady=2,
        ).pack(anchor="w", pady=(10, 0))

        if enabled:

            def on_enter(_event: object, card_frame: tk.Frame = frame) -> None:
                card_frame.configure(highlightbackground=BORDER_HOVER)

            def on_leave(_event: object, card_frame: tk.Frame = frame, pkg: PackageItem = package) -> None:
                active = BORDER_ACTIVE if pkg.id == self._selected_id else BORDER
                card_frame.configure(highlightbackground=active)

            frame.bind("<Enter>", on_enter)
            frame.bind("<Leave>", on_leave)
            frame.bind("<Button-1>", lambda _e, p=package: self._select(p))
            for child in inner.winfo_children():
                child.bind("<Button-1>", lambda _e, p=package: self._select(p))

        return frame

    def _select(self, package: PackageItem) -> None:
        self._selected_id = package.id
        self.set_packages(self._packages)
        self._on_select(package)

    def select_first_if_none(self) -> None:
        """Select the first package when nothing is selected yet."""
        if self._selected_id is not None or not self._packages:
            return
        self._select(self._packages[0])

    def selected_package(self) -> Optional[PackageItem]:
        """Return the currently highlighted package, if any."""
        for package in self._packages:
            if package.id == self._selected_id:
                return package
        return None


class SendPanel(tk.Frame):
    """Chat export picker and send action."""

    def __init__(
        self,
        master: tk.Misc,
        i18n: I18n,
        on_browse: Callable[[], None],
        on_export: Callable[[], None],
        on_send: Callable[[], None],
        on_chat_select: Callable[[int], None],
        on_chat_check_change: Callable[[], None],
        platform_var: tk.StringVar,
    ) -> None:
        super().__init__(master, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        self._i18n = i18n
        self._inner = tk.Frame(self, bg=BG_CARD, padx=16, pady=14)
        self._inner.pack(fill="both", expand=True)
        inner = self._inner

        self._title = tk.Label(inner, bg=BG_CARD, fg=TEXT_PRIMARY, font=FONT_HEADER)
        self._title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self._platform_label = tk.Label(inner, bg=BG_CARD, fg=TEXT_SECONDARY, font=FONT_CAPTION)
        self._platform_label.grid(row=1, column=0, sticky="w")
        plat = tk.Frame(inner, bg=BG_CARD)
        plat.grid(row=1, column=1, columnspan=2, sticky="w", padx=(8, 0))
        self._wechat_btn = tk.Radiobutton(
            plat,
            variable=platform_var,
            value="wechat",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=FONT_BODY,
            selectcolor=BG_MUTED,
            activebackground=BG_CARD,
        )
        self._wechat_btn.grid(row=0, column=0, sticky="w", padx=(0, 12))
        self._dingtalk_btn = tk.Radiobutton(
            plat,
            variable=platform_var,
            value="dingtalk",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=FONT_BODY,
            selectcolor=BG_MUTED,
            activebackground=BG_CARD,
        )
        self._dingtalk_btn.grid(row=0, column=1, sticky="w", padx=(0, 12))
        self._wecom_btn = tk.Radiobutton(
            plat,
            variable=platform_var,
            value="wecom",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=FONT_BODY,
            selectcolor=BG_MUTED,
            activebackground=BG_CARD,
        )
        self._wecom_btn.grid(row=0, column=2, sticky="w")

        self._folder_label = tk.Label(inner, bg=BG_CARD, fg=TEXT_SECONDARY, font=FONT_CAPTION)
        self._folder_label.grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.export_dir = tk.StringVar()
        self._folder_entry = tk.Entry(
            inner,
            textvariable=self.export_dir,
            font=FONT_BODY,
            relief="flat",
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
        )
        self._folder_entry.grid(row=2, column=1, sticky="ew", padx=(8, 8), pady=(8, 0), ipady=6)
        self._browse_btn = tk.Button(
            inner,
            font=FONT_BODY,
            relief="flat",
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
            padx=12,
            pady=6,
            command=on_browse,
        )
        self._browse_btn.grid(row=2, column=2, pady=(8, 0))

        self._chat_title_label = tk.Label(inner, bg=BG_CARD, fg=TEXT_SECONDARY, font=FONT_CAPTION)
        self._chat_title_label.grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.chat_title = tk.StringVar()
        tk.Entry(
            inner,
            textvariable=self.chat_title,
            font=FONT_BODY,
            relief="flat",
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
        ).grid(row=3, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=(8, 0), ipady=6)

        self._row_list_summary = 4
        self._row_list = 5
        self._row_preview_label = 6
        self._row_preview = 7
        self._row_buttons = 6
        self._row_status = 7

        self._list_summary = tk.Label(inner, bg=BG_CARD, fg=TEXT_SECONDARY, font=FONT_CAPTION)
        self._list_summary.grid(row=self._row_list_summary, column=0, columnspan=3, sticky="w", pady=(8, 0))

        self._list_frame = tk.Frame(inner, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        self._list_frame.grid(row=self._row_list, column=0, columnspan=3, sticky="nsew", pady=(6, 0))
        self._list_frame.columnconfigure(0, weight=1)
        self._list_frame.rowconfigure(0, weight=1)

        self.file_list = tk.Listbox(
            self._list_frame,
            height=10,
            font=FONT_BODY,
            relief="flat",
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
            selectbackground=ACCENT,
            highlightthickness=0,
            borderwidth=0,
            activestyle="none",
        )
        self.file_list.grid(row=0, column=0, sticky="nsew")
        self._list_scroll = ttk.Scrollbar(
            self._list_frame,
            orient="vertical",
            command=self.file_list.yview,
        )
        self._list_scroll.grid(row=0, column=1, sticky="ns")
        self.file_list.configure(yscrollcommand=self._list_scroll.set)

        self._conversation_list = ConversationCheckboxList(
            self._list_frame,
            on_row_select=on_chat_select,
            on_checked_change=on_chat_check_change,
        )
        self._conversation_list.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self._conversation_list.grid_remove()

        self._chat_preview_label = tk.Label(inner, bg=BG_CARD, fg=TEXT_SECONDARY, font=FONT_CAPTION)
        self._preview_frame = tk.Frame(inner, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        self._chat_preview = tk.Text(
            self._preview_frame,
            height=8,
            font=FONT_CAPTION,
            wrap="word",
            relief="flat",
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
            highlightthickness=0,
            borderwidth=0,
        )
        self._chat_preview.grid(row=0, column=0, sticky="nsew")
        self._preview_scroll = ttk.Scrollbar(
            self._preview_frame,
            orient="vertical",
            command=self._chat_preview.yview,
        )
        self._preview_scroll.grid(row=0, column=1, sticky="ns")
        self._chat_preview.configure(yscrollcommand=self._preview_scroll.set, state="disabled")
        self._preview_frame.columnconfigure(0, weight=1)
        self._preview_frame.rowconfigure(0, weight=1)
        bind_vertical_mousewheel(self._chat_preview, self._on_preview_mousewheel)
        bind_vertical_mousewheel(self._preview_frame, self._on_preview_mousewheel)
        bind_vertical_mousewheel(self._preview_scroll, self._on_preview_mousewheel)
        bind_vertical_mousewheel(self.file_list, self._on_file_list_mousewheel)
        bind_vertical_mousewheel(self._list_scroll, self._on_file_list_mousewheel)
        self._chat_preview_visible = False

        self._btn_row = tk.Frame(inner, bg=BG_CARD)
        self._btn_row.grid(row=self._row_buttons, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self._btn_row.columnconfigure(0, weight=1)
        self._btn_row.columnconfigure(1, weight=1)

        self._export_btn = tk.Button(
            self._btn_row,
            font=FONT_BODY,
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
            activebackground=BG_DISABLED,
            activeforeground=TEXT_PRIMARY,
            relief="flat",
            padx=16,
            pady=10,
            cursor="hand2",
            command=on_export,
        )
        self._export_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self._upload_btn = tk.Button(
            self._btn_row,
            font=FONT_BODY,
            bg=ACCENT,
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief="flat",
            padx=16,
            pady=10,
            cursor="hand2",
            command=on_send,
        )
        self._upload_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self._status = tk.Label(inner, text="", bg=BG_CARD, fg=TEXT_MUTED, font=FONT_CAPTION, wraplength=640)
        self._status.grid(row=self._row_status, column=0, columnspan=3, sticky="w", pady=(8, 0))

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
        self._authenticated = False
        self._folder_row_visible = True
        self._upload_mode = False

        inner.columnconfigure(1, weight=1)
        self._inner.rowconfigure(self._row_list, weight=3)
        self.bind("<Configure>", self._on_panel_configure)
        self.apply_texts()
        self.set_authenticated(False)

    def set_authenticated(self, authenticated: bool) -> None:
        """Toggle grey overlay until MindGraph credentials are verified."""
        self._authenticated = authenticated
        if authenticated:
            self._overlay.place_forget()
            return
        self._overlay_label.configure(text=self._i18n.translate("send.overlay"))
        self._overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._overlay.lift()
        self.set_export_enabled(False)
        self.set_upload_enabled(False)
        self.set_controls_enabled(False)

    def apply_texts(self) -> None:
        """Refresh labels for the active locale."""
        self._title.configure(text=self._i18n.translate("send.title"))
        self._platform_label.configure(text=self._i18n.translate("send.platform"))
        self._wechat_btn.configure(text=self._i18n.translate("send.wechat"))
        self._dingtalk_btn.configure(text=self._i18n.translate("send.dingtalk"))
        self._wecom_btn.configure(text=self._i18n.translate("send.wecom"))
        self._folder_label.configure(text=self._i18n.translate("send.folder"))
        self._browse_btn.configure(text=self._i18n.translate("send.browse"))
        self._chat_title_label.configure(text=self._i18n.translate("send.chat_title"))
        self._chat_preview_label.configure(text=self._i18n.translate("send.chat_preview"))
        if not self.chat_title.get().strip():
            self.chat_title.set(self._i18n.translate("send.default_title"))
        self._apply_action_button_texts()

    def set_upload_mode(self, enabled: bool) -> None:
        """Switch export label and show live chat preview when connected to WeChat."""
        self._upload_mode = enabled
        self._apply_action_button_texts()
        if enabled:
            self.file_list.grid_remove()
            self._list_scroll.grid_remove()
            self._conversation_list.grid()
            self._show_chat_preview()
        else:
            self._conversation_list.grid_remove()
            self.file_list.grid(row=0, column=0, sticky="nsew")
            self._list_scroll.grid(row=0, column=1, sticky="ns")
            self._hide_chat_preview()
        self._sync_conversation_heights()

    def _show_chat_preview(self) -> None:
        if self._chat_preview_visible:
            return
        self._chat_preview_visible = True
        self._row_buttons = 8
        self._row_status = 9
        self._inner.rowconfigure(self._row_preview, weight=2)
        self._chat_preview_label.grid(
            row=self._row_preview_label,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(10, 0),
        )
        self._preview_frame.grid(
            row=self._row_preview,
            column=0,
            columnspan=3,
            sticky="nsew",
            pady=(6, 0),
        )
        self._btn_row.grid(row=self._row_buttons, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self._status.grid(row=self._row_status, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def _hide_chat_preview(self) -> None:
        if not self._chat_preview_visible:
            return
        self._chat_preview_visible = False
        self._row_buttons = 6
        self._row_status = 7
        self._inner.rowconfigure(self._row_preview, weight=0)
        self._chat_preview_label.grid_remove()
        self._preview_frame.grid_remove()
        self._btn_row.grid(row=self._row_buttons, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self._status.grid(row=self._row_status, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.clear_chat_preview()

    def _on_preview_mousewheel(self, event: tk.Event) -> str | None:
        units = wheel_scroll_units(event)
        if units:
            self._chat_preview.yview_scroll(units, "units")
        return "break"

    def _on_file_list_mousewheel(self, event: tk.Event) -> str | None:
        units = wheel_scroll_units(event)
        if units:
            self.file_list.yview_scroll(units, "units")
        return "break"

    def _on_panel_configure(self, event: tk.Event) -> None:
        if event.widget is not self:
            return
        self.after_idle(self._sync_conversation_heights)

    def _sync_conversation_heights(self) -> None:
        try:
            panel_height = self.winfo_height()
        except tk.TclError:
            return
        if panel_height < 120:
            return
        preview_reserve = 180 if self._chat_preview_visible else 0
        chrome = 280 + preview_reserve
        list_pixels = max(panel_height - chrome, 140)
        list_lines = max(10, list_pixels // 22)
        self.file_list.configure(height=list_lines)
        self._conversation_list.set_canvas_height(list_pixels)
        if self._chat_preview_visible:
            preview_pixels = max(panel_height - chrome - list_lines * 22, 100)
            preview_lines = max(6, preview_pixels // 18)
            self._chat_preview.configure(height=preview_lines)

    def set_list_summary(self, text: str) -> None:
        """Show conversation / file count above the list."""
        self._list_summary.configure(text=text)

    def clear_list_summary(self) -> None:
        """Clear the conversation / file count line."""
        self._list_summary.configure(text="")

    def set_chat_preview(self, text: str) -> None:
        """Show formatted message lines for the selected live chat."""
        self._chat_preview.configure(state="normal")
        self._chat_preview.delete("1.0", tk.END)
        if text:
            self._chat_preview.insert("1.0", text)
        self._chat_preview.configure(state="disabled")

    def clear_chat_preview(self) -> None:
        """Clear the live chat message preview."""
        self.set_chat_preview("")

    def _apply_action_button_texts(self) -> None:
        export_key = "send.button_export" if self._upload_mode else "send.button_export_open"
        self._export_btn.configure(text=self._i18n.translate(export_key))
        self._upload_btn.configure(text=self._i18n.translate("send.button_upload"))
        self._export_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._upload_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def set_folder_row_visible(self, visible: bool) -> None:
        """Show or hide the manual export folder row."""
        if visible == self._folder_row_visible:
            return
        self._folder_row_visible = visible
        if visible:
            self._folder_label.grid()
            self._folder_entry.grid()
            self._browse_btn.grid()
            return
        self._folder_label.grid_remove()
        self._folder_entry.grid_remove()
        self._browse_btn.grid_remove()

    def set_status(self, text: str, *, error: bool = False) -> None:
        """Show upload status or error under the send panel."""
        color = "#dc2626" if error else TEXT_MUTED
        self._status.configure(text=text, fg=color)

    def set_export_enabled(self, enabled: bool) -> None:
        """Enable or disable the export / open-folder button."""
        state = tk.NORMAL if enabled else tk.DISABLED
        self._export_btn.configure(state=state)

    def set_upload_enabled(self, enabled: bool) -> None:
        """Enable or disable the upload button."""
        state = tk.NORMAL if enabled else tk.DISABLED
        self._upload_btn.configure(state=state)

    def set_controls_enabled(self, enabled: bool) -> None:
        """Enable folder browse and file list when authenticated."""
        state = tk.NORMAL if enabled else tk.DISABLED
        self._browse_btn.configure(state=state)
        browse_state = "normal" if enabled else "disabled"
        self.file_list.configure(state=browse_state)
        self._conversation_list.set_enabled(enabled)

    def set_chat_rows(self, labels: List[str]) -> None:
        """Populate live conversation rows with checkboxes."""
        self._conversation_list.set_rows(labels)

    def clear_chat_rows(self) -> None:
        """Clear live conversation checkbox rows."""
        self._conversation_list.clear()

    def get_checked_chat_indices(self) -> List[int]:
        """Return indices of checked live conversations."""
        return self._conversation_list.get_checked_indices()

    def get_selected_chat_index(self) -> Optional[int]:
        """Return the conversation row selected for preview."""
        return self._conversation_list.get_selected_index()

    def format_file_row(self, title: str, message_count: int) -> str:
        """Localized list row for an export preview."""
        return self._i18n.translate("send.file_row", title=title, count=message_count)

    def format_chat_row(self, title: str, *, is_group: bool, time_label: str) -> str:
        """Localized list row for a live WeChat session."""
        group_suffix = self._i18n.translate("send.chat_group_suffix") if is_group else ""
        return self._i18n.translate(
            "send.chat_row",
            title=title,
            group=group_suffix,
            time=time_label,
        )
