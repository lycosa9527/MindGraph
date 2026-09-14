"""Training presence refresh while SSE / watch sockets stay open."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.features.training.connection_lease import (
    refresh_org_connection_lease,
    refresh_user_connection_lease,
)
from services.features.training.session_store import TrainingSessionError


@pytest.mark.asyncio
async def test_org_lease_heartbeats_owner_and_teacher_row() -> None:
    """Keepalive must stamp both the hosted room and an existing rail row."""
    with (
        patch(
            "services.features.training.connection_lease.heartbeat",
            new_callable=AsyncMock,
        ) as beat,
        patch(
            "services.features.training.connection_lease.refresh_activity_lease",
            new_callable=AsyncMock,
        ) as activity,
    ):
        await refresh_org_connection_lease(8, 3)
    beat.assert_awaited_once_with(8, 3)
    activity.assert_awaited_once_with(8, 3)


@pytest.mark.asyncio
async def test_org_lease_ignores_non_owner_heartbeat() -> None:
    """Teachers on the org stream must not raise when they are not the host."""
    with (
        patch(
            "services.features.training.connection_lease.heartbeat",
            new_callable=AsyncMock,
            side_effect=TrainingSessionError("not_owner", "no"),
        ) as beat,
        patch(
            "services.features.training.connection_lease.refresh_activity_lease",
            new_callable=AsyncMock,
        ) as activity,
    ):
        await refresh_org_connection_lease(8, 9)
    beat.assert_awaited_once_with(8, 9)
    activity.assert_awaited_once_with(8, 9)


@pytest.mark.asyncio
async def test_user_lease_follows_instructor_pointer() -> None:
    """Waiting phone / watch sockets refresh the hosted school, not a guess."""
    with (
        patch(
            "services.features.training.connection_lease.get_instructor_pointer",
            new_callable=AsyncMock,
            return_value={"org_id": 12, "session_id": "s1"},
        ),
        patch(
            "services.features.training.connection_lease.heartbeat",
            new_callable=AsyncMock,
        ) as beat,
    ):
        await refresh_user_connection_lease(4)
    beat.assert_awaited_once_with(12, 4)


@pytest.mark.asyncio
async def test_user_lease_noops_without_pointer() -> None:
    """No hosted room means keepalive is a no-op."""
    with (
        patch(
            "services.features.training.connection_lease.get_instructor_pointer",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "services.features.training.connection_lease.heartbeat",
            new_callable=AsyncMock,
        ) as beat,
    ):
        await refresh_user_connection_lease(4)
    beat.assert_not_awaited()
