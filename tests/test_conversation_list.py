"""Unit tests for conversation checkbox list helpers."""

from __future__ import annotations

import tkinter as tk

from file_reader.chat.conversation_list import ConversationCheckboxList


def test_conversation_checkbox_list_empty_until_checked() -> None:
    """New rows start unchecked; selection index stays unset."""
    root = tk.Tk()
    root.withdraw()
    panel = ConversationCheckboxList(
        root,
        on_row_select=lambda _index: None,
        on_checked_change=lambda: None,
    )
    assert panel.get_checked_indices() == []
    assert panel.get_selected_index() is None
    panel.set_rows(["Alice · yesterday", "Bob · today"])
    assert panel.get_checked_indices() == []
    panel.clear()
    assert panel.get_checked_indices() == []
    root.destroy()
