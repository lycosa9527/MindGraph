"""30-day live cap and a joiner leaving without ending the seminar."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.domain.mindmate_seminar import MindmateSeminarMember, MindmateSeminarSession
from services.features.mindmate_seminar.config import MINDMATE_COLLAB_MAX_LIVE_SECONDS
from services.features.mindmate_seminar.seminar_leave import leave_live_seminar
from services.features.mindmate_seminar.seminar_ttl import (
    expire_overdue_live_seminars,
    seminar_past_max_live_age,
)


def test_seminar_past_max_live_age_uses_utc_for_naive_start() -> None:
    """Exactly 30 days is overdue; a day-old room and a naive started_at stay open."""
    now = datetime(2026, 10, 27, 8, 0, tzinfo=UTC)
    assert MINDMATE_COLLAB_MAX_LIVE_SECONDS == 30 * 24 * 60 * 60
    started = now - timedelta(seconds=MINDMATE_COLLAB_MAX_LIVE_SECONDS)
    assert seminar_past_max_live_age(started, now) is True
    assert seminar_past_max_live_age(started + timedelta(seconds=1), now) is False
    assert seminar_past_max_live_age(now - timedelta(hours=24), now) is False
    assert seminar_past_max_live_age(started.replace(tzinfo=None), now) is True


def _system_db(db: AsyncMock) -> AsyncMock:
    ctx = AsyncMock()
    ctx.__aenter__.return_value = db
    ctx.__aexit__.return_value = None
    return ctx


@pytest.mark.asyncio
async def test_expire_overdue_live_seminars_stops_with_expired_reason() -> None:
    """The sweep asks stop_session to close each overdue live row."""
    fake_db = AsyncMock()
    fake_result = MagicMock()
    fake_result.scalars.return_value.all.return_value = ["old-sess"]
    fake_db.execute = AsyncMock(return_value=fake_result)
    manager = MagicMock()
    manager.stop_session = AsyncMock(return_value=True)
    with (
        patch(
            "services.features.mindmate_seminar.seminar_ttl.system_rls_session",
            return_value=_system_db(fake_db),
        ),
        patch(
            "services.features.mindmate_seminar.seminar_ttl.get_mindmate_seminar_manager",
            return_value=manager,
        ),
    ):
        stopped = await expire_overdue_live_seminars()
    manager.stop_session.assert_awaited_once_with("old-sess", 0, reason="expired")
    assert stopped == 1


@pytest.mark.asyncio
async def test_leave_live_seminar_rejects_owner() -> None:
    """The owner ends the room; leave is only for joiners."""
    session = MagicMock()
    session.ended_at = None
    session.owner_user_id = 3
    fake_db = AsyncMock()
    fake_db.get = AsyncMock(return_value=session)
    with patch(
        "services.features.mindmate_seminar.seminar_leave.system_rls_session",
        return_value=_system_db(fake_db),
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
            "services.features.mindmate_seminar.seminar_leave.get_mindmate_seminar_manager",
            return_value=manager,
        ),
    ):
        result = await leave_live_seminar(4, "sess-1")
    assert result == "ok"
    assert member.left_at is not None
    manager.remove_participant.assert_awaited_once_with("ABC-DEF", 4)
