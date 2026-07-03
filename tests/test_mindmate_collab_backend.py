"""MindMate collab manager unit tests (single-host rule)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.features.mindmate_collab.manager import MindmateCollabManager


@pytest.mark.asyncio
async def test_stop_hosted_sessions_for_user_stops_each_active_row() -> None:
    """Hosted-session cleanup invokes stop_session for every active owned row."""
    mgr = MindmateCollabManager()
    row_a = MagicMock(id="sess-a")
    row_b = MagicMock(id="sess-b")

    fake_sess = AsyncMock()
    fake_result = MagicMock()
    fake_result.scalars.return_value.all.return_value = [row_a, row_b]
    fake_sess.execute = AsyncMock(return_value=fake_result)

    context = AsyncMock()

    async def _enter(*_a, **_k):
        return fake_sess

    context.__aenter__.side_effect = _enter
    context.__aexit__.return_value = None

    stop_mock = AsyncMock(return_value=True)

    with (
        patch(
            "services.features.mindmate_collab.manager.user_rls_session",
            return_value=context,
        ),
        patch.object(mgr, "stop_session", stop_mock),
    ):
        count = await mgr.stop_hosted_sessions_for_user(42)

    assert count == 2
    assert stop_mock.await_count == 2
    stop_mock.assert_any_await("sess-a", 42, reason="single_host")
    stop_mock.assert_any_await("sess-b", 42, reason="single_host")


@pytest.mark.asyncio
async def test_session_payload_includes_owner_and_expiry() -> None:
    """Hosted session lookup exposes owner, participant count, and expiry."""
    mgr = MindmateCollabManager()
    session = MagicMock()
    session.id = "uuid-1"
    session.code = "ABC-DEF"
    session.title = "Room"
    session.visibility = "organization"
    session.owner_user_id = 7
    session.organization_id = 3
    session.expires_at = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)

    fake_sess = AsyncMock()
    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = session
    fake_sess.execute = AsyncMock(return_value=fake_result)
    context = AsyncMock()

    async def _enter(*_a, **_k):
        return fake_sess

    context.__aenter__.side_effect = _enter
    context.__aexit__.return_value = None

    with (
        patch(
            "services.features.mindmate_collab.manager.user_rls_session",
            return_value=context,
        ),
        patch.object(mgr, "participant_count", AsyncMock(return_value=4)),
    ):
        payload = await mgr.get_hosted_session(7)

    assert payload is not None
    assert payload["owner_user_id"] == 7
    assert payload["participant_count"] == 4
    assert payload["expires_at"].startswith("2026-07-03")
