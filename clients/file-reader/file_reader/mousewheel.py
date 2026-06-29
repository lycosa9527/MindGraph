"""Mouse wheel scrolling helpers for Tk."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

WheelCallback = Callable[[tk.Event], str | None]


def wheel_scroll_units(event: tk.Event, *, direction: int = -1) -> int:
    """Return vertical scroll units from a wheel event (Windows or X11)."""
    delta = getattr(event, "delta", 0)
    if delta:
        return int(direction * (delta / 120))
    button = getattr(event, "num", None)
    if button == 4:
        return -3
    if button == 5:
        return 3
    return 0


def bind_vertical_mousewheel(widget: tk.Misc, callback: WheelCallback) -> None:
    """Bind vertical wheel events on a single widget."""
    widget.bind("<MouseWheel>", callback)
    widget.bind("<Button-4>", callback)
    widget.bind("<Button-5>", callback)


def bind_vertical_mousewheel_tree(widget: tk.Misc, callback: WheelCallback) -> None:
    """Bind vertical wheel events on a widget and all descendants."""
    bind_vertical_mousewheel(widget, callback)
    for child in widget.winfo_children():
        bind_vertical_mousewheel_tree(child, callback)
