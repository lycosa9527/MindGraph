"""Unit tests for single-owner hosted workshop teardown."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from services.online_collab.lifecycle.online_collab_single_owner_session import (
    stop_other_owner_online_collabs,
)


@pytest.mark.asyncio
async def test_stop_other_calls_stop_online_collab_per_candidate() -> None:
    stops: list[tuple[str, int]] = []

    async def _fake_stop(diagram_id: str, uid: int) -> bool:
        stops.append((diagram_id, uid))
        return True

    fake_sess = AsyncMock()

    fake_result = MagicMock()
    fake_result.all.return_value = [
        ("dia-a", "AB1-CD2"),
        ("dia-whitespace-only", "   "),
        ("dia-b", "YZ3-ZY4"),
    ]

    fake_sess.execute = AsyncMock(return_value=fake_result)

    context = AsyncMock()

    async def _enter_sess(*_a, **_k):
        return fake_sess

    context.__aenter__.side_effect = _enter_sess
    context.__aexit__.return_value = None

    with (
        patch(
            "services.online_collab.lifecycle.online_collab_single_owner_session"
            ".AsyncSessionLocal",
            return_value=context,
        ),
        patch(
            "services.online_collab.core.online_collab_lifecycle.stop_online_collab_impl",
            side_effect=_fake_stop,
        ),
    ):
        n = await stop_other_owner_online_collabs(
            owner_user_id=42,
            except_diagram_id="target-diagram",
        )

    assert n == 2
    assert stops == [
        ("dia-a", 42),
        ("dia-b", 42),
    ]


@pytest.mark.asyncio
async def test_stop_other_returns_zero_on_listing_error() -> None:
    fake_sess = AsyncMock()
    fake_sess.execute = AsyncMock(side_effect=SQLAlchemyError("db down"))

    context = AsyncMock()

    async def _enter(*_a, **_k):
        return fake_sess

    context.__aenter__.side_effect = _enter
    context.__aexit__.return_value = None

    async def _never_stop(_d: str, _u: int) -> bool:
        raise AssertionError("stop should not run")

    with (
        patch(
            "services.online_collab.lifecycle.online_collab_single_owner_session"
            ".AsyncSessionLocal",
            return_value=context,
        ),
        patch(
            "services.online_collab.core.online_collab_lifecycle.stop_online_collab_impl",
            side_effect=_never_stop,
        ),
    ):
        n = await stop_other_owner_online_collabs(
            owner_user_id=1,
            except_diagram_id="x",
        )
    assert n == 0
