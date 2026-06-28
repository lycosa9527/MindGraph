"""Reusable UI widgets for the file-reader desktop app."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional

from file_reader.api_client import LiveSession, PackageItem, UserProfile
from file_reader.i18n import I18n
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
    """Dark header bar with MindGraph M logo and user avatar."""

    def __init__(self, master: tk.Misc, i18n: I18n) -> None:
        super().__init__(master, bg=BG_HEADER, height=56)
        self._i18n = i18n
        self.pack_propagate(False)

        logo_wrap = tk.Frame(self, bg=BG_HEADER)
        logo_wrap.pack(side="left", padx=(16, 10), pady=10)

        logo = tk.Canvas(logo_wrap, width=32, height=32, bg=BG_HEADER, highlightthickness=0)
        logo.pack(side="left")
        logo.create_rectangle(2, 2, 30, 30, fill="#1c1917", outline="#292524", width=1)
        logo.create_text(16, 17, text="M", fill=TEXT_ON_DARK, font=FONT_LOGO)

        titles = tk.Frame(logo_wrap, bg=BG_HEADER)
        titles.pack(side="left", padx=(8, 0))
        tk.Label(titles, text="MindGraph", bg=BG_HEADER, fg=TEXT_ON_DARK, font=FONT_TITLE).pack(anchor="w")

        self._avatar_frame = tk.Frame(self, bg=BG_HEADER)
        self._avatar_frame.pack(side="right", padx=16, pady=10)

        self._avatar_label = tk.Label(
            self._avatar_frame,
            text="👤",
            bg="#292524",
            fg=TEXT_ON_DARK,
            font=(FONT_BODY[0], 14),
            width=2,
            height=1,
            padx=4,
            pady=2,
        )
        self._avatar_label.pack(side="right")

        self._name_label = tk.Label(
            self._avatar_frame,
            bg=BG_HEADER,
            fg=TEXT_ON_DARK_MUTED,
            font=FONT_BODY,
        )
        self._name_label.pack(side="right", padx=(0, 10))
        self._profile: Optional[UserProfile] = None
        self.apply_texts()

    def apply_texts(self) -> None:
        """Refresh labels for the active locale."""
        if self._profile is None:
            self._name_label.configure(text=self._i18n.translate("header.not_signed_in"))

    def set_profile(self, profile: Optional[UserProfile]) -> None:
        """Update avatar and display name."""
        self._profile = profile
        if profile is None:
            self._avatar_label.configure(text="👤")
            self._name_label.configure(text=self._i18n.translate("header.not_signed_in"), fg=TEXT_ON_DARK_MUTED)
            return
        avatar = profile.avatar.strip() or "👤"
        display = profile.name.strip() or profile.phone
        self._avatar_label.configure(text=avatar[:2] if len(avatar) > 2 else avatar)
        self._name_label.configure(text=display, fg=TEXT_ON_DARK)


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
        self._entries: List[tk.Entry] = []
        for row_idx in range(1, 4):
            label = tk.Label(inner, bg=BG_CARD, fg=TEXT_SECONDARY, font=FONT_CAPTION)
            label.grid(row=row_idx, column=0, sticky="w", pady=4)
            self._field_labels.append(label)
            show = "*" if row_idx == 2 else ""
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
        for entry, value in zip(self._entries, (server_url, api_token, phone)):
            entry.delete(0, tk.END)
            entry.insert(0, value)

    def get_values(self) -> tuple[str, str, str]:
        """Read server, token, phone from the form."""
        return (
            self._entries[0].get().strip(),
            self._entries[1].get().strip(),
            self._entries[2].get().strip(),
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
        on_send: Callable[[], None],
        platform_var: tk.StringVar,
    ) -> None:
        super().__init__(master, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        self._i18n = i18n
        inner = tk.Frame(self, bg=BG_CARD, padx=16, pady=14)
        inner.pack(fill="both", expand=True)

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
        self._wechat_btn.pack(side="left", padx=(0, 12))
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
        self._dingtalk_btn.pack(side="left")

        self._folder_label = tk.Label(inner, bg=BG_CARD, fg=TEXT_SECONDARY, font=FONT_CAPTION)
        self._folder_label.grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.export_dir = tk.StringVar()
        tk.Entry(
            inner,
            textvariable=self.export_dir,
            font=FONT_BODY,
            relief="flat",
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
        ).grid(row=2, column=1, sticky="ew", padx=(8, 8), pady=(8, 0), ipady=6)
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

        self.file_list = tk.Listbox(
            inner,
            height=5,
            font=FONT_BODY,
            relief="flat",
            bg=BG_MUTED,
            fg=TEXT_PRIMARY,
            selectbackground=ACCENT,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.file_list.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(10, 0))

        self._send_btn = tk.Button(
            inner,
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
        self._send_btn.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(12, 0))

        self._status = tk.Label(inner, text="", bg=BG_CARD, fg=TEXT_MUTED, font=FONT_CAPTION, wraplength=640)
        self._status.grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))

        inner.columnconfigure(1, weight=1)
        inner.rowconfigure(4, weight=1)
        self.apply_texts()

    def apply_texts(self) -> None:
        """Refresh labels for the active locale."""
        self._title.configure(text=self._i18n.translate("send.title"))
        self._platform_label.configure(text=self._i18n.translate("send.platform"))
        self._wechat_btn.configure(text=self._i18n.translate("send.wechat"))
        self._dingtalk_btn.configure(text=self._i18n.translate("send.dingtalk"))
        self._folder_label.configure(text=self._i18n.translate("send.folder"))
        self._browse_btn.configure(text=self._i18n.translate("send.browse"))
        self._chat_title_label.configure(text=self._i18n.translate("send.chat_title"))
        if not self.chat_title.get().strip():
            self.chat_title.set(self._i18n.translate("send.default_title"))
        self._send_btn.configure(text=self._i18n.translate("send.button"))

    def set_status(self, text: str, *, error: bool = False) -> None:
        """Show upload status or error under the send panel."""
        color = "#dc2626" if error else TEXT_MUTED
        self._status.configure(text=text, fg=color)

    def set_send_enabled(self, enabled: bool) -> None:
        """Enable or disable the primary send button."""
        state = tk.NORMAL if enabled else tk.DISABLED
        self._send_btn.configure(state=state)

    def format_file_row(self, title: str, message_count: int) -> str:
        """Localized list row for an export preview."""
        return self._i18n.translate("send.file_row", title=title, count=message_count)
