"""Persistent bottom status bar with visual state indicators."""

from __future__ import annotations

import tkinter as tk
from typing import Literal, Optional

from file_reader.theme import BORDER, FONT_BODY, FONT_CAPTION

StatusKind = Literal[
    "offline",
    "connecting",
    "connected",
    "waiting",
    "ready",
    "sending",
    "success",
    "warning",
    "error",
]

_DOT: dict[StatusKind, str] = {
    "offline": "#94a3b8",
    "connecting": "#2563eb",
    "connected": "#059669",
    "waiting": "#d97706",
    "ready": "#059669",
    "sending": "#2563eb",
    "success": "#059669",
    "warning": "#d97706",
    "error": "#dc2626",
}

_BG: dict[StatusKind, str] = {
    "offline": "#f8fafc",
    "connecting": "#eff6ff",
    "connected": "#ecfdf5",
    "waiting": "#fffbeb",
    "ready": "#ecfdf5",
    "sending": "#eff6ff",
    "success": "#ecfdf5",
    "warning": "#fffbeb",
    "error": "#fef2f2",
}

_FG: dict[StatusKind, str] = {
    "offline": "#475569",
    "connecting": "#1e40af",
    "connected": "#047857",
    "waiting": "#b45309",
    "ready": "#047857",
    "sending": "#1e40af",
    "success": "#047857",
    "warning": "#b45309",
    "error": "#b91c1c",
}


class StatusDock(tk.Frame):
    """Bottom dock: colored dot + primary / secondary status lines."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, bg="#ffffff", highlightbackground=BORDER, highlightthickness=1)
        self._kind: StatusKind = "offline"
        self._context_kind: StatusKind = "offline"
        self._context_primary = ""
        self._context_secondary = ""
        self._flash_after: Optional[str] = None

        self._row = tk.Frame(self, bg="#ffffff", padx=16, pady=12)
        self._row.pack(fill="x")

        self._dot = tk.Canvas(self._row, width=12, height=12, bg="#ffffff", highlightthickness=0)
        self._dot.pack(side="left", padx=(0, 12), pady=4)
        self._dot_id = self._dot.create_oval(2, 2, 10, 10, fill=_DOT["offline"], outline="")

        text_col = tk.Frame(self._row, bg="#ffffff")
        text_col.pack(side="left", fill="x", expand=True)

        self._primary = tk.Label(
            text_col,
            text="",
            font=(FONT_BODY[0], 10, "bold"),
            anchor="w",
            justify="left",
        )
        self._primary.pack(fill="x")

        self._secondary = tk.Label(
            text_col,
            text="",
            font=FONT_CAPTION,
            anchor="w",
            justify="left",
            wraplength=720,
        )
        self._secondary.pack(fill="x", pady=(2, 0))

    def set_context(self, kind: StatusKind, primary: str, secondary: str = "") -> None:
        """Update the persistent status shown when no flash is active."""
        self._context_kind = kind
        self._context_primary = primary.strip()
        self._context_secondary = secondary.strip()
        if self._flash_after is None:
            self._apply(kind, self._context_primary, self._context_secondary)

    def flash(
        self,
        kind: StatusKind,
        primary: str,
        secondary: str = "",
        duration_ms: int = 5000,
    ) -> None:
        """Temporarily override the dock, then restore the last context."""
        if self._flash_after is not None:
            self.after_cancel(self._flash_after)
            self._flash_after = None
        self._apply(kind, primary.strip(), secondary.strip())
        if duration_ms > 0:
            self._flash_after = self.after(duration_ms, self._restore_context)

    def persist(self, kind: StatusKind, primary: str, secondary: str = "") -> None:
        """Set context and display immediately (sticky; no auto-revert)."""
        if self._flash_after is not None:
            self.after_cancel(self._flash_after)
            self._flash_after = None
        self.set_context(kind, primary, secondary)

    def _restore_context(self) -> None:
        self._flash_after = None
        self._apply(self._context_kind, self._context_primary, self._context_secondary)

    def _apply(self, kind: StatusKind, primary: str, secondary: str) -> None:
        self._kind = kind
        dot = _DOT.get(kind, _DOT["offline"])
        bg = _BG.get(kind, _BG["offline"])
        fg = _FG.get(kind, _FG["offline"])

        self.configure(bg=bg)
        self._row.configure(bg=bg)
        for child in self._row.winfo_children():
            if isinstance(child, tk.Frame):
                child.configure(bg=bg)
                for sub in child.winfo_children():
                    if isinstance(sub, tk.Label):
                        sub.configure(bg=bg, fg=fg if sub is self._primary else _muted_fg(kind))
            elif isinstance(child, tk.Canvas):
                child.configure(bg=bg)

        self._dot.configure(bg=bg)
        self._dot.itemconfigure(self._dot_id, fill=dot)
        self._primary.configure(text=primary, bg=bg, fg=fg)
        self._secondary.configure(
            text=secondary,
            bg=bg,
            fg=_muted_fg(kind),
        )


def _muted_fg(kind: StatusKind) -> str:
    if kind == "error":
        return "#991b1b"
    if kind in ("waiting", "warning"):
        return "#92400e"
    if kind in ("connected", "ready", "success"):
        return "#065f46"
    if kind in ("connecting", "sending"):
        return "#1e3a8a"
    return "#64748b"
