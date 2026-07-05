"""MindMate collab automated stop_session uses system RLS."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.features.mindmate_collab.manager import MindmateCollabManager


@pytest.mark.asyncio
async def test_stop_session_idle_uses_system_rls_not_owner_actor() -> None:
    """Idle/zombie/expired stops load the row with system RLS (owner actor may be 0)."""
    mgr = MindmateCollabManager()
    session = MagicMock()
    session.id = "sess-idle"
    session.code = "ABC-DEF"
    session.organization_id = 3
    session.visibility = "network"
    session.ended_at = None
    session.owner_user_id = 99

    fake_sess = AsyncMock()
    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = session
    fake_sess.execute = AsyncMock(return_value=fake_result)

    system_ctx = AsyncMock()
    system_ctx.__aenter__.return_value = fake_sess
    system_ctx.__aexit__.return_value = None

    with (
        patch(
            "services.features.mindmate_collab.manager.system_rls_session",
            return_value=system_ctx,
        ) as system_rls_mock,
        patch(
            "services.features.mindmate_collab.manager.abort_dify_stream",
            AsyncMock(),
        ),
        patch(
            "services.features.mindmate_collab.manager.get_async_redis",
            return_value=None,
        ),
        patch(
            "services.features.mindmate_collab.manager.broadcast_to_all",
            AsyncMock(),
        ),
    ):
        ok = await mgr.stop_session("sess-idle", 0, reason="idle")

    assert ok is True
    assert system_rls_mock.call_count >= 2
