"""Scrollable conversation list with per-row checkboxes."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional

from file_reader.mousewheel import bind_vertical_mousewheel, bind_vertical_mousewheel_tree, wheel_scroll_units
from file_reader.theme import ACCENT, BG_CARD, BG_MUTED, FONT_BODY, TEXT_PRIMARY


class ConversationCheckboxList(tk.Frame):
    """Live chat rows: checkbox for batch actions, label click for preview."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        on_row_select: Callable[[int], None],
        on_checked_change: Callable[[], None],
    ) -> None:
        super().__init__(master, bg=BG_CARD, highlightthickness=0)
        self._on_row_select = on_row_select
        self._on_checked_change = on_checked_change
        self._enabled = True
        self._selected_index: Optional[int] = None
        self._row_vars: List[tk.BooleanVar] = []
        self._row_labels: List[tk.Label] = []
        self._row_frames: List[tk.Frame] = []

        self._canvas = tk.Canvas(
            self,
            bg=BG_MUTED,
            highlightthickness=0,
            borderwidth=0,
        )
        self._scroll = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._inner = tk.Frame(self._canvas, bg=BG_MUTED)
        self._window_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._canvas.configure(yscrollcommand=self._scroll.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._scroll.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        bind_vertical_mousewheel(self._canvas, self._on_mousewheel)
        bind_vertical_mousewheel(self._inner, self._on_mousewheel)
        bind_vertical_mousewheel(self._scroll, self._on_mousewheel)
        bind_vertical_mousewheel(self, self._on_mousewheel)

    def _on_inner_configure(self, _event: object) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self._canvas.itemconfigure(self._window_id, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        units = wheel_scroll_units(event)
        if units:
            self._canvas.yview_scroll(units, "units")
        return "break"

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable row interaction."""
        self._enabled = enabled
        state = tk.NORMAL if enabled else tk.DISABLED
        for row_frame in self._row_frames:
            for child in row_frame.winfo_children():
                if isinstance(child, tk.Checkbutton):
                    child.configure(state=state)
                elif isinstance(child, tk.Label):
                    child.configure(state=state)

    def clear(self) -> None:
        """Remove all conversation rows."""
        for row_frame in self._row_frames:
            row_frame.destroy()
        self._row_vars.clear()
        self._row_labels.clear()
        self._row_frames.clear()
        self._selected_index = None
        self._canvas.yview_moveto(0)

    def set_rows(self, labels: List[str]) -> None:
        """Replace rows with new labels (all unchecked)."""
        self.clear()
        for index, label in enumerate(labels):
            var = tk.BooleanVar(value=False)
            row = tk.Frame(self._inner, bg=BG_MUTED)
            row.pack(fill="x", anchor="w")

            check = tk.Checkbutton(
                row,
                variable=var,
                bg=BG_MUTED,
                activebackground=BG_MUTED,
                highlightthickness=0,
                borderwidth=0,
                command=self._on_checked_change,
            )
            check.pack(side="left", padx=(4, 2), pady=2)

            text = tk.Label(
                row,
                text=label,
                bg=BG_MUTED,
                fg=TEXT_PRIMARY,
                font=FONT_BODY,
                anchor="w",
                justify="left",
                cursor="hand2",
            )
            text.pack(side="left", fill="x", expand=True, padx=(0, 6), pady=4)
            text.bind("<Button-1>", lambda _event, idx=index: self._select_row(idx))
            bind_vertical_mousewheel_tree(row, self._on_mousewheel)

            self._row_vars.append(var)
            self._row_labels.append(text)
            self._row_frames.append(row)
        self.set_enabled(self._enabled)

    def get_checked_indices(self) -> List[int]:
        """Return indices of checked conversations."""
        return [index for index, var in enumerate(self._row_vars) if var.get()]

    def get_selected_index(self) -> Optional[int]:
        """Return the row highlighted for message preview."""
        return self._selected_index

    def _select_row(self, index: int) -> None:
        if not self._enabled or index < 0 or index >= len(self._row_frames):
            return
        self._selected_index = index
        for row_index, label in enumerate(self._row_labels):
            if row_index == index:
                label.configure(bg=ACCENT, fg="#ffffff")
                self._row_frames[row_index].configure(bg=ACCENT)
            else:
                label.configure(bg=BG_MUTED, fg=TEXT_PRIMARY)
                self._row_frames[row_index].configure(bg=BG_MUTED)
        self._on_row_select(index)

    def set_canvas_height(self, pixels: int) -> None:
        """Set visible list height in pixels."""
        self._canvas.configure(height=max(pixels, 140))
