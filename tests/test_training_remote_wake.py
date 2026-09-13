"""Training-remote Redis pub/sub wake and local WebSocket delivery."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.websockets import WebSocketState

from services.features.training.constants import SNAPSHOT_TYPE
from services.features.training.wake_fanout import (
    org_id_from_wake_channel,
    publish_training_snapshot_view,
    training_org_wake_channel,
    training_snapshot_frame,
    training_user_wake_channel,
    user_id_from_wake_channel,
)
from services.features.training.wake_listener import dispatch_training_wake_message
from services.features.training.ws_manager import TrainingRemoteWsManager


def test_wake_payload_and_channel() -> None:
    """Watch sockets listen on per-user and per-org channels."""
    assert training_user_wake_channel(3) == "training_remote:user:3:wake"
    assert training_org_wake_channel(9) == "training_remote:org:9:wake"
    assert user_id_from_wake_channel("training_remote:user:3:wake") == 3
    assert org_id_from_wake_channel("training_remote:org:9:wake") == 9
    assert user_id_from_wake_channel("slide_remote:user:3:wake") is None
    frame = training_snapshot_frame({"state": "none", "session_id": None})
    assert SNAPSHOT_TYPE in frame


@pytest.mark.asyncio
async def test_publish_training_snapshot_view() -> None:
    """Session change publishes to the instructor and the org channel."""
    redis = AsyncMock()
    with patch(
        "services.features.training.wake_fanout.get_async_redis",
        return_value=redis,
    ):
        await publish_training_snapshot_view(9, {"state": "live"}, instructor_id=3)
    assert redis.publish.await_count == 2
    channels = {call.args[0] for call in redis.publish.await_args_list}
    assert channels == {
        "training_remote:user:3:wake",
        "training_remote:org:9:wake",
    }


@pytest.mark.asyncio
async def test_dispatch_user_wake_sends_to_local_sockets() -> None:
    """The worker that holds the watch socket pushes one frame."""
    frame = training_snapshot_frame({"state": "none"})
    with patch("services.features.training.wake_listener.training_remote_ws_manager") as manager:
        manager.send_to_user = AsyncMock(return_value=1)
        sent = await dispatch_training_wake_message("training_remote:user:9:wake", frame)
    manager.send_to_user.assert_awaited_once_with(9, frame)
    assert sent == 1


@pytest.mark.asyncio
async def test_dispatch_org_wake_broadcasts() -> None:
    """Org channel updates every local training-remote socket."""
    frame = training_snapshot_frame({"state": "live", "org_id": 4})
    with patch("services.features.training.wake_listener.training_remote_ws_manager") as manager:
        manager.send_to_all = AsyncMock(return_value=2)
        sent = await dispatch_training_wake_message("training_remote:org:4:wake", frame)
    manager.send_to_all.assert_awaited_once_with(frame)
    assert sent == 2


@pytest.mark.asyncio
async def test_ws_manager_skips_disconnected() -> None:
    """Only CONNECTED sockets receive the snapshot frame."""
    manager = TrainingRemoteWsManager()
    live = MagicMock()
    live.client_state = WebSocketState.CONNECTED
    live.send_text = AsyncMock()
    dead = MagicMock()
    dead.client_state = WebSocketState.DISCONNECTED
    dead.send_text = AsyncMock()
    manager.connect(3, live)
    manager.connect(3, dead)
    sent = await manager.send_to_user(3, training_snapshot_frame({"state": "none"}))
    assert sent == 1
    live.send_text.assert_awaited_once()
    dead.send_text.assert_not_called()
