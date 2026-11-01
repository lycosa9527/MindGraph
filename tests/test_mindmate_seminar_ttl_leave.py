"""A joiner leaves a live seminar without ending it."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.domain.mindmate_seminar import MindmateSeminarMember, MindmateSeminarSession
from services.features.mindmate_seminar.seminar_leave import leave_live_seminar


def _system_db(db: AsyncMock) -> AsyncMock:
    ctx = AsyncMock()
    ctx.__aenter__.return_value = db
    ctx.__aexit__.return_value = None
    return ctx


@pytest.mark.asyncio
async def test_leave_live_seminar_rejects_owner() -> None:
    """The owner ends the room; leave is only for joiners."""
    session = MagicMock()
    session.ended_at = None
    session.owner_user_id = 3
    fake_db = AsyncMock()
    fake_db.get = AsyncMock(return_value=session)
    with (
        patch(
            "services.features.mindmate_seminar.seminar_leave.system_rls_session",
            return_value=_system_db(fake_db),
        ),
        patch(
            "services.features.mindmate_seminar.seminar_leave.actor_is_seminar_leader",
            AsyncMock(return_value=True),
        ),
    ):
        result = await leave_live_seminar(3, "sess-1")
    assert result == "still_owner"


@pytest.mark.asyncio
async def test_leave_live_seminar_sets_left_at_for_joiner() -> None:
    """A joiner stays a member for the transcript, but is marked as having left."""
    session = MagicMock()
    session.ended_at = None
    session.owner_user_id = 9
    session.code = "ABC-DEF"
    member = MagicMock()
    member.left_at = None

    async def _get(model: object, _key: object) -> object:
        if model is MindmateSeminarSession:
            return session
        if model is MindmateSeminarMember:
            return member
        return None

    fake_db = AsyncMock()
    fake_db.get = AsyncMock(side_effect=_get)
    fake_db.commit = AsyncMock()
    manager = MagicMock()
    manager.remove_participant = AsyncMock()
    with (
        patch(
            "services.features.mindmate_seminar.seminar_leave.system_rls_session",
            return_value=_system_db(fake_db),
        ),
        patch(
            "services.features.mindmate_seminar.seminar_leave.actor_is_seminar_leader",
            AsyncMock(return_value=False),
        ),
        patch(
            "services.features.mindmate_seminar.seminar_leave.get_mindmate_seminar_manager",
            return_value=manager,
        ),
    ):
        result = await leave_live_seminar(4, "sess-1")
    assert result == "ok"
    assert member.left_at is not None
    manager.remove_participant.assert_awaited_once_with("ABC-DEF", 4)
