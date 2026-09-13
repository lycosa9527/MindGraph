"""Kitty write-path fanout: live_context, conversation turn, session snapshot."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.kitty.infra.control.kitty_event_push import (
    SESSION_SNAPSHOT_RELAY_ALL,
    conversation_turn_ws_body,
    handle_conversation_turn_relay,
    handle_live_context_relay,
    handle_session_snapshot_relay,
    live_context_ws_body,
    notify_kitty_conversation_turn,
    notify_kitty_live_context_changed,
    notify_kitty_session_snapshot_changed,
    session_snapshot_ws_body,
)
from tests.typing_helpers import mock_await_args, mock_await_kwargs


def test_live_context_ws_body_matches_get_shape() -> None:
    """Mobile payload matches GET /live_context."""
    body = live_context_ws_body(
        "lib-1",
        {
            "updated_at": 9,
            "diagram_type": "mindmap",
            "active_panel": "none",
            "diagram_data": {"nodes": []},
            "selected_nodes": ["topic"],
            "selected_llm_model": "qwen",
        },
    )
    assert body["type"] == "live_context_update"
    assert body["ok"] is True
    assert body["scope"] == "lib-1"
    assert body["updated_at"] == 9
    assert body["selected_nodes"] == ["topic"]


def test_conversation_turn_ws_body_is_compact() -> None:
    """Peer turn carries persisted fields only."""
    body = conversation_turn_ws_body(
        "lib-1",
        {
            "turn_id": "t1",
            "role": "kitty",
            "content": "已加上",
            "request_id": "r1",
            "source": "ui_edit",
            "noise": "drop",
        },
    )
    assert body["type"] == "conversation_turn"
    assert body["turn"]["turn_id"] == "t1"
    assert "noise" not in body["turn"]


def test_session_snapshot_ws_body() -> None:
    """Session Manager DTO is nested under session."""
    body = session_snapshot_ws_body({"requested_scope": "lib-a", "canvas_owner_present": True})
    assert body["type"] == "session_snapshot"
    assert body["session"]["canvas_owner_present"] is True


@pytest.mark.asyncio
async def test_notify_live_context_pushes_mobile_and_relays() -> None:
    """PUT notify fans the GET payload to mobile sockets and control relay."""
    live = {"updated_at": 3, "diagram_type": "mindmap", "diagram_data": {}}
    with (
        patch(
            "services.kitty.infra.control.kitty_event_push.send_kitty_ws_json",
            AsyncMock(return_value=1),
        ) as send,
        patch(
            "services.kitty.infra.control.kitty_event_push._publish_relay",
            AsyncMock(return_value=True),
        ) as relay,
    ):
        await notify_kitty_live_context_changed(3, "lib-1", live)
    send.assert_awaited()
    assert mock_await_kwargs(send)["lanes"] == frozenset({"mobile"})
    relay.assert_awaited()
    assert mock_await_args(relay)[0] == "live_context_update"


@pytest.mark.asyncio
async def test_notify_conversation_turn_excludes_writer_lane() -> None:
    """Desktop-sourced turns skip desktop sockets."""
    turn = {"turn_id": "t1", "role": "user", "content": "加分支", "source": "ui_edit"}
    with (
        patch(
            "services.kitty.infra.control.kitty_event_push.send_kitty_ws_json",
            AsyncMock(return_value=1),
        ) as send,
        patch(
            "services.kitty.infra.control.kitty_event_push._publish_relay",
            AsyncMock(return_value=True),
        ),
    ):
        await notify_kitty_conversation_turn(3, "lib-1", turn)
    assert mock_await_kwargs(send)["exclude_lanes"] == frozenset({"desktop"})


@pytest.mark.asyncio
async def test_notify_conversation_turn_asr_reaches_mobile() -> None:
    """Desktop ASR ingress is not a mobile persist source — do not drop the phone."""
    turn = {"turn_id": "t2", "role": "user", "content": "加分支", "source": "asr"}
    with (
        patch(
            "services.kitty.infra.control.kitty_event_push.send_kitty_ws_json",
            AsyncMock(return_value=1),
        ) as send,
        patch(
            "services.kitty.infra.control.kitty_event_push._publish_relay",
            AsyncMock(return_value=True),
        ),
    ):
        await notify_kitty_conversation_turn(3, "lib-1", turn)
    assert mock_await_kwargs(send)["exclude_lanes"] is None


@pytest.mark.asyncio
async def test_notify_session_snapshot_without_scope_uses_local() -> None:
    """Focus clear still relays when a local Kitty socket has a scope."""
    with (
        patch(
            "services.kitty.infra.control.kitty_event_push.iter_local_kitty_scopes",
            return_value=["lib-a"],
        ),
        patch(
            "services.kitty.infra.control.kitty_event_push._push_session_snapshots_local",
            AsyncMock(return_value=1),
        ),
        patch(
            "services.kitty.infra.control.kitty_event_push._publish_relay",
            AsyncMock(return_value=True),
        ) as relay,
    ):
        await notify_kitty_session_snapshot_changed(3, None)
    assert mock_await_kwargs(relay)["scope"] == "lib-a"


@pytest.mark.asyncio
async def test_notify_session_snapshot_without_local_still_relays() -> None:
    """HTTP worker with no Kitty sockets still wakes other workers on focus clear."""
    with (
        patch(
            "services.kitty.infra.control.kitty_event_push.iter_local_kitty_scopes",
            return_value=[],
        ),
        patch(
            "services.kitty.infra.control.kitty_event_push._push_session_snapshots_local",
            AsyncMock(return_value=0),
        ),
        patch(
            "services.kitty.infra.control.kitty_event_push._publish_relay",
            AsyncMock(return_value=True),
        ) as relay,
    ):
        await notify_kitty_session_snapshot_changed(3, None)
    assert mock_await_kwargs(relay)["scope"] == SESSION_SNAPSHOT_RELAY_ALL


@pytest.mark.asyncio
async def test_notify_session_snapshot_rebuilds_per_scope() -> None:
    """Canvas-owner change rebuilds the snapshot for local sockets."""
    with (
        patch(
            "services.kitty.infra.control.kitty_event_push._push_session_snapshots_local",
            AsyncMock(return_value=1),
        ) as push,
        patch(
            "services.kitty.infra.control.kitty_event_push._publish_relay",
            AsyncMock(return_value=True),
        ) as relay,
    ):
        await notify_kitty_session_snapshot_changed(3, "lib-a")
    push.assert_awaited_once()
    relay.assert_awaited()
    assert mock_await_args(relay)[0] == "session_snapshot"


@pytest.mark.asyncio
async def test_live_context_relay_skips_origin() -> None:
    """Origin worker does not double-send."""
    with (
        patch(
            "services.kitty.infra.control.kitty_event_push.get_kitty_control_instance_id",
            return_value="here",
        ),
        patch(
            "services.kitty.infra.control.kitty_event_push._auth_ok",
            return_value=True,
        ),
    ):
        ok = await handle_live_context_relay({"user_id": 3, "scope": "lib-1", "origin": "here"})
    assert ok is False


@pytest.mark.asyncio
async def test_conversation_turn_relay_sends() -> None:
    """Relayed turn is pushed to local peer sockets."""
    with (
        patch(
            "services.kitty.infra.control.kitty_event_push.get_kitty_control_instance_id",
            return_value="here",
        ),
        patch(
            "services.kitty.infra.control.kitty_event_push._auth_ok",
            return_value=True,
        ),
        patch(
            "services.kitty.infra.control.kitty_event_push.send_kitty_ws_json",
            AsyncMock(return_value=1),
        ) as send,
    ):
        ok = await handle_conversation_turn_relay(
            {
                "user_id": 3,
                "scope": "lib-1",
                "origin": "other",
                "turn": {"turn_id": "t1", "role": "kitty", "content": "好"},
                "exclude_lane": "desktop",
            }
        )
    assert ok is True
    assert mock_await_kwargs(send)["exclude_lanes"] == frozenset({"desktop"})


@pytest.mark.asyncio
async def test_session_snapshot_relay_rebuilds() -> None:
    """Relayed snapshot rebuilds from Redis SoT on this worker."""
    with (
        patch(
            "services.kitty.infra.control.kitty_event_push.get_kitty_control_instance_id",
            return_value="here",
        ),
        patch(
            "services.kitty.infra.control.kitty_event_push._auth_ok",
            return_value=True,
        ),
        patch(
            "services.kitty.infra.control.kitty_event_push._push_session_snapshots_local",
            AsyncMock(return_value=2),
        ) as push,
    ):
        ok = await handle_session_snapshot_relay({"user_id": 3, "scope": "lib-a", "origin": "other"})
    assert ok is True
    push.assert_awaited_once()
