"""MindMate collab org session caps and duration presets."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.features.mindmate_collab.config import (
    MINDMATE_COLLAB_DEFAULT_DURATION,
    MINDMATE_COLLAB_MAX_ORG_CONCURRENT_SESSIONS,
)
from services.features.mindmate_collab.manager import MindmateCollabManager
from services.online_collab.lifecycle.online_collab_expiry import (
    DURATION_10H,
    compute_online_collab_expires_at,
    duration_allowed_for_visibility,
)


def test_default_duration_is_ten_hours() -> None:
    """MindMate collab defaults to a 10-hour session window."""
    assert MINDMATE_COLLAB_DEFAULT_DURATION == DURATION_10H


def test_ten_hour_preset_allowed_for_org_and_network() -> None:
    """10h is valid for both organization and network visibility."""
    assert duration_allowed_for_visibility("organization", DURATION_10H)
    assert duration_allowed_for_visibility("network", DURATION_10H)


def test_compute_expires_at_for_ten_hours() -> None:
    """10h preset adds exactly ten hours to the start instant."""
    start = datetime(2026, 7, 5, 8, 0, tzinfo=UTC)
    expires = compute_online_collab_expires_at(start, DURATION_10H)
    assert expires == datetime(2026, 7, 5, 18, 0)


def test_org_concurrent_cap_default_is_ten() -> None:
    """Each organization may host at most ten live org-visible rooms."""
    assert MINDMATE_COLLAB_MAX_ORG_CONCURRENT_SESSIONS == 10


@pytest.mark.asyncio
async def test_start_session_rejects_when_org_room_cap_reached() -> None:
    """start_session returns an error when the org already has ten live rooms."""
    mgr = MindmateCollabManager()
    user = MagicMock()
    user.organization_id = 99
    user.name = "Host"
    user.phone = None
    user.email = None

    fake_sess = AsyncMock()
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = user
    fake_sess.execute = AsyncMock(return_value=user_result)

    context = AsyncMock()

    async def _enter(*_a, **_k):
        return fake_sess

    context.__aenter__.side_effect = _enter
    context.__aexit__.return_value = None

    with (
        patch(
            "services.features.mindmate_collab.manager.get_async_redis",
            return_value=MagicMock(),
        ),
        patch(
            "services.features.mindmate_collab.manager.acquire_nx_lock",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.features.mindmate_collab.manager.release_nx_lock",
            AsyncMock(),
        ),
        patch.object(mgr, "stop_hosted_sessions_for_user", AsyncMock(return_value=0)),
        patch.object(
            mgr,
            "_count_live_org_sessions",
            AsyncMock(return_value=MINDMATE_COLLAB_MAX_ORG_CONCURRENT_SESSIONS),
        ),
        patch(
            "services.features.mindmate_collab.manager.user_rls_session",
            return_value=context,
        ),
    ):
        payload, error = await mgr.start_session(7, visibility="organization")

    assert payload is None
    assert error is not None
    assert "10" in error
    assert "concurrent seminar rooms" in error
