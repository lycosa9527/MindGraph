"""HTTP handlers for the 演讲模式 watch clicker."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from models.domain.auth import User
from routers.api.slides_remote_routes import (
    CommandBody,
    SnapshotBody,
    active_session,
    close_session,
    pop_commands,
    post_command,
    publish_session,
)
from services.features.slides_remote.session_store import SlideRemoteError


def _user(user_id: int = 9) -> User:
    return cast(User, SimpleNamespace(id=user_id))


def _live() -> dict:
    return {
        "state": "live",
        "session_id": "sess-9",
        "diagram_id": "d1",
        "title": "主题",
        "slide_index": 0,
        "slide_count": 3,
        "traversal": "firstLevel",
        "autoplay": False,
        "can_prev": False,
        "can_next": True,
        "seq": 1,
    }


@pytest.mark.asyncio
async def test_publish_session_returns_public_view() -> None:
    """Desktop PUT writes the snapshot the watch will poll."""
    with patch(
        "routers.api.slides_remote_routes.upsert_session",
        new=AsyncMock(return_value=_live()),
    ) as upsert:
        body = SnapshotBody(diagram_id="d1", title="主题", slide_count=3, can_next=True)
        view = await publish_session(body, current_user=_user())
        upsert.assert_awaited_once()
        assert view["state"] == "live"
        assert view["session_id"] == "sess-9"
        assert view["can_next"] is True


@pytest.mark.asyncio
async def test_active_session_idle_when_missing() -> None:
    """Watch sees idle, not 404, when 演讲模式 is off."""
    with patch(
        "routers.api.slides_remote_routes.get_session",
        new=AsyncMock(return_value=None),
    ):
        view = await active_session(current_user=_user())
        assert view["state"] == "idle"
        assert view["session_id"] == ""


@pytest.mark.asyncio
async def test_post_command_not_found() -> None:
    """Clicks before a live room are 404."""
    with patch(
        "routers.api.slides_remote_routes.enqueue_command",
        new=AsyncMock(side_effect=SlideRemoteError("not_found", "No live slide session")),
    ):
        with pytest.raises(HTTPException) as exc:
            await post_command(CommandBody(action="next"), current_user=_user())
        assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_post_command_start_without_session() -> None:
    """Start from the watch library is accepted while idle."""
    with patch(
        "routers.api.slides_remote_routes.enqueue_command",
        new=AsyncMock(return_value={"action": "start", "diagram_id": "d9"}),
    ) as enqueue:
        view = await post_command(
            CommandBody(action="start", diagram_id="d9"),
            current_user=_user(),
        )
        enqueue.assert_awaited_once()
        assert view["ok"] is True
        assert view["command"]["diagram_id"] == "d9"


@pytest.mark.asyncio
async def test_post_command_start_needs_diagram() -> None:
    """Start without a library id is 400."""
    with patch(
        "routers.api.slides_remote_routes.enqueue_command",
        new=AsyncMock(side_effect=SlideRemoteError("bad_diagram", "Start needs a diagram")),
    ):
        with pytest.raises(HTTPException) as exc:
            await post_command(CommandBody(action="start"), current_user=_user())
        assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_pop_commands_and_end() -> None:
    """Desktop drain then end."""
    with patch(
        "routers.api.slides_remote_routes.drain_commands",
        new=AsyncMock(return_value=[{"id": "c1", "action": "quit"}]),
    ):
        body = await pop_commands(current_user=_user())
        assert body["items"][0]["action"] == "quit"
    with patch(
        "routers.api.slides_remote_routes.end_session",
        new=AsyncMock(),
    ) as ended:
        view = await close_session(current_user=_user())
        ended.assert_awaited_once()
        assert view["state"] == "ended"
