"""Non-blocking toast notifications for the desktop UI."""

from __future__ import annotations

import tkinter as tk
from typing import Literal, Optional

from file_reader.theme import FONT_BODY

Kind = Literal["info", "success", "error"]

_COLORS: dict[Kind, tuple[str, str]] = {
    "info": ("#1e40af", "#eff6ff"),
    "success": ("#047857", "#ecfdf5"),
    "error": ("#b91c1c", "#fef2f2"),
}


class NotificationBar(tk.Frame):
    """Slide-down banner at the bottom of the window."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, bg="#ffffff", height=0)
        self.pack_propagate(False)
        self._label = tk.Label(
            self,
            text="",
            font=FONT_BODY,
            anchor="w",
            padx=16,
            pady=10,
        )
        self._label.pack(fill="both", expand=True)
        self._after_id: Optional[str] = None
        self.pack_forget()

    def show(self, message: str, *, kind: Kind = "info", duration_ms: int = 6000) -> None:
        """Display a message; auto-hide after duration_ms (0 = stay visible)."""
        fg, bg = _COLORS.get(kind, _COLORS["info"])
        self.configure(bg=bg)
        self._label.configure(text=message, fg=fg, bg=bg)
        self.pack(fill="x", side="bottom")
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None
        if duration_ms > 0:
            self._after_id = self.after(duration_ms, self.hide)

    def hide(self) -> None:
        """Dismiss the banner."""
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None
        self.pack_forget()
