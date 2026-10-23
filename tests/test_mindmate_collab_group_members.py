"""Closed seminar membership id normalization."""

from services.features.mindmate_collab.group_members import normalize_group_member_ids


def test_normalize_group_member_ids_keeps_owner_and_caps() -> None:
    """The host is always first, duplicates drop out, and the room cap holds."""
    assert normalize_group_member_ids(5, [5, 0, 9, 9, 2], 3) == [5, 9, 2]
