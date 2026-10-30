"""Unread seminar lines ignore the viewer's own messages and ended rooms."""

from __future__ import annotations

from services.features.mindmate_seminar.unread_summary import message_is_unread, rooms_from_counts


def test_own_user_line_is_not_unread() -> None:
    """A message this person sent does not light the badge."""
    assert message_is_unread("user", 7, 7, 4, 1) is False


def test_assistant_line_after_the_cursor_is_unread() -> None:
    """MindMate replies count even though the sender is not another teacher."""
    assert message_is_unread("assistant", None, 7, 5, 4) is True


def test_other_person_and_missing_cursor() -> None:
    """Someone else's line counts, and a missing cursor treats every line as unseen."""
    assert message_is_unread("user", 8, 7, 2, None) is True
    assert message_is_unread("user", 8, 7, 2, 2) is False


def test_rooms_drop_empty_and_sort_by_newest() -> None:
    """Ended rooms never appear in the session list, so they cannot enter this summary."""
    summary = rooms_from_counts(
        [
            {"session_id": "old", "code": "AAA-BBB", "title": "Old"},
            {"session_id": "new", "code": "CCC-DDD", "title": "New"},
            {"session_id": "quiet", "code": "EEE-FFF", "title": "Quiet"},
        ],
        {"old": (1, 3), "new": (2, 9), "quiet": (0, 8)},
    )
    assert summary["unread_count"] == 3
    assert [room["code"] for room in summary["rooms"]] == ["CCC-DDD", "AAA-BBB"]
