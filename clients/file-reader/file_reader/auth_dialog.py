"""Modal credential dialog for MindGraph file-reader."""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from file_reader.i18n import I18n
from file_reader.theme import BG_APP
from file_reader.widgets import AuthPanel


class AuthDialog:
    """Toplevel window hosting the connect-account form."""

    def __init__(
        self,
        root: tk.Tk,
        i18n: I18n,
        *,
        on_connect: Callable[[], None],
        on_clear: Callable[[], None],
    ) -> None:
        self._root = root
        self._i18n = i18n
        self._on_connect = on_connect
        self._on_clear = on_clear
        self._top: Optional[tk.Toplevel] = None
        self._panel: Optional[AuthPanel] = None

    @property
    def panel(self) -> AuthPanel:
        """Return the embedded auth form (creates the dialog if needed)."""
        if self._panel is None:
            self._ensure_window()
        assert self._panel is not None
        return self._panel

    def show(self) -> None:
        """Open or raise the credential dialog."""
        self._ensure_window()
        assert self._top is not None
        self._top.deiconify()
        self._top.lift()
        self._top.focus_force()

    def is_open(self) -> bool:
        """True when the dialog window exists and is visible."""
        return self._top is not None and bool(self._top.winfo_exists()) and self._top.state() != "withdrawn"

    def set_values(self, server_url: str, api_token: str, phone: str) -> None:
        """Populate form fields."""
        self.panel.set_values(server_url, api_token, phone)

    def get_values(self) -> tuple[str, str, str]:
        """Read server, token, phone from the form."""
        return self.panel.get_values()

    def set_status(self, text: str, *, error: bool = False) -> None:
        """Show helper or error text under the form."""
        self.panel.set_status(text, error=error)

    def set_busy(self, busy: bool) -> None:
        """Disable connect while a request is in flight."""
        self.panel.set_busy(busy)

    def _ensure_window(self) -> None:
        if self._top is not None and self._top.winfo_exists():
            return

        top = tk.Toplevel(self._root)
        top.title(self._i18n.translate("auth.title"))
        top.configure(bg=BG_APP)
        top.resizable(False, False)
        top.transient(self._root)
        top.protocol("WM_DELETE_WINDOW", self._on_close)

        pad = tk.Frame(top, bg=BG_APP, padx=16, pady=16)
        pad.pack(fill="both", expand=True)

        panel = AuthPanel(pad, self._i18n, on_connect=self._on_connect, on_clear=self._on_clear)
        panel.pack(fill="x")

        self._top = top
        self._panel = panel

        top.update_idletasks()
        root_x = self._root.winfo_rootx()
        root_y = self._root.winfo_rooty()
        root_w = self._root.winfo_width()
        dialog_w = top.winfo_width()
        top.geometry(f"+{root_x + max(0, (root_w - dialog_w) // 2)}+{root_y + 72}")

    def close(self) -> None:
        """Hide the credential dialog."""
        self._on_close()

    def _on_close(self) -> None:
        if self._top is not None and self._top.winfo_exists():
            self._top.withdraw()
