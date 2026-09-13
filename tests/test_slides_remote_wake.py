"""Slide-remote Redis pub/sub wake and local WebSocket delivery."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.websockets import WebSocketState

from services.features.slides_remote.constants import COMMAND_PENDING_TYPE, SNAPSHOT_TYPE
from services.features.slides_remote.wake_fanout import (
    publish_slides_command_pending,
    slides_command_pending_payload,
    slides_snapshot_frame,
    slides_wake_channel,
    user_id_from_wake_channel,
)
from services.features.slides_remote.wake_listener import dispatch_slides_wake_message
from services.features.slides_remote.ws_manager import SlidesRemoteWsManager
from services.features.slides_remote.ws_ttl import run_desktop_session_touch


def test_wake_payload_and_channel() -> None:
    """Desktop sockets listen on a per-user channel for command-pending."""
    assert COMMAND_PENDING_TYPE in slides_command_pending_payload()
    assert slides_wake_channel(3) == "slide_remote:user:3:wake"
    assert user_id_from_wake_channel("slide_remote:user:3:wake") == 3
    assert user_id_from_wake_channel("other:user:3:wake") is None
    frame = slides_snapshot_frame({"state": "idle", "session_id": ""})
    assert SNAPSHOT_TYPE in frame
    assert '"state": "idle"' in frame or '"state":"idle"' in frame


@pytest.mark.asyncio
async def test_publish_slides_command_pending() -> None:
    """Enqueue wake is a Redis PUBLISH, not another HTTP poll."""
    redis = AsyncMock()
    with patch(
        "services.features.slides_remote.wake_fanout.get_async_redis",
        return_value=redis,
    ):
        await publish_slides_command_pending(7)
    redis.publish.assert_awaited_once_with(
        "slide_remote:user:7:wake",
        slides_command_pending_payload(),
    )


@pytest.mark.asyncio
async def test_publish_slides_command_pending_without_redis() -> None:
    """Missing Redis is a no-op; the command stays in the list until a drain."""
    with patch(
        "services.features.slides_remote.wake_fanout.get_async_redis",
        return_value=None,
    ):
        await publish_slides_command_pending(7)


@pytest.mark.asyncio
async def test_dispatch_wake_sends_to_local_sockets() -> None:
    """The worker that holds the desktop socket pushes one frame."""
    with patch("services.features.slides_remote.wake_listener.slides_remote_ws_manager") as manager:
        manager.send_to_user = AsyncMock(return_value=1)
        sent = await dispatch_slides_wake_message(
            "slide_remote:user:9:wake",
            slides_command_pending_payload(),
        )
    manager.send_to_user.assert_awaited_once_with(9, slides_command_pending_payload())
    assert sent == 1


@pytest.mark.asyncio
async def test_ws_manager_skips_disconnected() -> None:
    """Only CONNECTED sockets receive the wake frame."""
    manager = SlidesRemoteWsManager()
    live = MagicMock()
    live.client_state = WebSocketState.CONNECTED
    live.send_text = AsyncMock()
    dead = MagicMock()
    dead.client_state = WebSocketState.DISCONNECTED
    dead.send_text = AsyncMock()
    manager.connect(4, live)
    manager.connect(4, dead, watch=True)
    delivered = await manager.send_to_user(4, slides_command_pending_payload())
    assert delivered == 1
    assert manager.desktop_count(4) == 1
    live.send_text.assert_awaited_once()
    dead.send_text.assert_not_called()
    manager.disconnect(4, live)
    assert manager.desktop_count(4) == 0


@pytest.mark.asyncio
async def test_desktop_ttl_touch_runs_once_when_stopped() -> None:
    """TTL loop must not spin after the desktop socket closes."""
    stop = asyncio.Event()
    stop.set()
    with patch(
        "services.features.slides_remote.ws_ttl.touch_session",
        new=AsyncMock(return_value=True),
    ) as touch:
        await run_desktop_session_touch(8, stop)
    touch.assert_awaited_once_with(8)
