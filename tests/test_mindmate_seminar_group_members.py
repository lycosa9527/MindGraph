"""Closed seminar membership id normalization."""

from services.features.mindmate_seminar.group_members import (
    normalize_group_member_ids,
    pending_seminar_invites_statement,
)


def test_normalize_group_member_ids_keeps_owner_and_caps() -> None:
    """The host is always first, duplicates drop out, and the room cap holds."""
    assert normalize_group_member_ids(5, [5, 0, 9, 9, 2], 3) == [5, 9, 2]


def test_pending_seminar_invites_statement_joins_from_membership() -> None:
    """The invite list starts at the member row so the owner and school joins compile."""
    sql = str(pending_seminar_invites_statement(3).compile(compile_kwargs={"literal_binds": True}))
    assert "FROM mindmate_seminar_members JOIN mindmate_seminar_sessions" in sql
    assert "JOIN users ON users.id = mindmate_seminar_sessions.owner_user_id" in sql
    assert "LEFT OUTER JOIN organizations ON organizations.id = mindmate_seminar_sessions.organization_id" in sql
    assert "mindmate_seminar_members.user_id = 3" in sql
    assert "mindmate_seminar_members.accepted IS false" in sql
    assert "mindmate_seminar_sessions.ended_at IS NULL" in sql
    assert "ORDER BY mindmate_seminar_members.joined_at" in sql
