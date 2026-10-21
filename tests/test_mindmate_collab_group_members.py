"""Closed seminar membership stays open until the first invited row exists."""

from services.features.mindmate_collab.group_members import (
    closed_group_allows,
    normalize_group_member_ids,
)


def test_open_room_allows_any_joiner() -> None:
    """An empty membership list keeps the previous school-wide join rule."""
    assert closed_group_allows([], 4, 1) is True


def test_closed_room_allows_invited_teacher_and_owner() -> None:
    """Checked colleagues and the host can enter. The rest of the school cannot."""
    assert closed_group_allows([1, 8, 9], 8, 1) is True
    assert closed_group_allows([8, 9], 1, 1) is True
    assert closed_group_allows([1, 8], 3, 1) is False


def test_normalize_group_member_ids_keeps_owner_and_caps() -> None:
    """The host is always first, duplicates drop out, and the room cap holds."""
    assert normalize_group_member_ids(5, [5, 0, 9, 9, 2], 3) == [5, 9, 2]
