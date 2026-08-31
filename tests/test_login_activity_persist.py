"""Login activity_log persist for all roles; teacher-usage stays teacher-only."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routers.auth.helpers import _log_login_and_compute_stats, track_user_activity
from tests.typing_helpers import as_user


@pytest.mark.asyncio
async def test_non_teacher_login_persists_without_usage_stats() -> None:
    """School managers get a login row but no teacher-usage recompute."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    with patch(
        "routers.auth.helpers.compute_and_upsert_user_usage_stats_async",
        new_callable=AsyncMock,
    ) as compute:
        with patch("routers.auth.helpers.user_rls_session") as session_cm:
            await _log_login_and_compute_stats(9, db, "school_admin")
    db.add.assert_called_once()
    db.commit.assert_awaited()
    compute.assert_not_called()
    session_cm.assert_not_called()


@pytest.mark.asyncio
async def test_teacher_login_persists_and_recomputes_usage() -> None:
    """Teachers still recompute usage stats after the login row commits."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    stats_session = object()

    class _Ctx:
        async def __aenter__(self):
            return stats_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    with patch(
        "routers.auth.helpers.compute_and_upsert_user_usage_stats_async",
        new_callable=AsyncMock,
    ) as compute:
        with patch("routers.auth.helpers.user_rls_session", return_value=_Ctx()):
            await _log_login_and_compute_stats(3, db, "teacher")
    compute.assert_awaited_once()


@pytest.mark.asyncio
async def test_track_user_activity_logs_non_teacher_login() -> None:
    """track_user_activity persists login for non-teacher roles when db is passed."""
    user = SimpleNamespace(id=4, role="school_admin", phone="13800000001", name="Mgr")
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    with patch("routers.auth.helpers.get_activity_tracker") as tracker_factory:
        tracker_factory.return_value.start_session = AsyncMock()
        with patch("routers.auth.helpers.track_module_activity", new_callable=AsyncMock):
            with patch(
                "routers.auth.helpers.compute_and_upsert_user_usage_stats_async",
                new_callable=AsyncMock,
            ) as compute:
                await track_user_activity(as_user(user), "login", {"method": "password"}, None, db)
    db.add.assert_called_once()
    compute.assert_not_called()
