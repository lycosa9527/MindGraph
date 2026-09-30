"""MindMate seminar read cursors move forward only."""

from __future__ import annotations

from datetime import UTC, datetime

from services.features.mindmate_collab.read_cursors import read_cursor_is_newer, serialize_read_cursor


def test_read_cursor_moves_forward_only() -> None:
    """A later line replaces the cursor. An older line does not."""
    assert read_cursor_is_newer(None, 4) is True
    assert read_cursor_is_newer(4, 9) is True
    assert read_cursor_is_newer(9, 9) is False
    assert read_cursor_is_newer(9, 3) is False
    assert read_cursor_is_newer(None, 0) is False
    assert read_cursor_is_newer(None, True) is False


def test_serialize_read_cursor_omits_blank_name() -> None:
    """The hover list uses the user id when no display name is stored."""
    stamp = datetime(2026, 9, 30, 8, 5, tzinfo=UTC)
    named = serialize_read_cursor(3, "Ada", 8, stamp)
    assert named["username"] == "Ada"
    assert named["last_read_message_id"] == 8
    blank = serialize_read_cursor(3, None, 8, stamp)
    assert "username" not in blank
