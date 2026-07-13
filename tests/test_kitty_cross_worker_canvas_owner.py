"""Simulate Kitty mobile + desktop on different Uvicorn workers via Redis fanout.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.diagram_edit.ack import complete_mutation_ack_from_client, configure_mutation_ack_relay
from services.diagram_edit.pending import (
    detach_pending_for_tests,
    new_mutation_id,
    reattach_pending_for_tests,
    register_pending,
    reset_pending_state_for_tests,
)
from services.kitty.context.messaging import send_kitty_diagram_update, send_kitty_ws_action
from services.kitty.infra.control.kitty_canvas_owner_relay import (
    handle_mutation_ack_relay,
    publish_mutation_ack_relay,
)
from services.kitty.infra.control.kitty_control_fanout import (
    handle_kitty_control_dispatch,
    parse_kitty_control_envelope,
)
from services.kitty.infra.desktop.kitty_desktop_focus_push import (
    publish_desktop_focus_relay,
    push_kitty_desktop_focus_to_local_mobile,
)
from services.kitty.infra.desktop.kitty_desktop_wake_fanout import (
    publish_kitty_canvas_action,
    publish_kitty_desktop_action_pending,
    publish_kitty_diagram_update,
)
from services.kitty.session.canvas_owner import find_canvas_owner_websocket
from tests.typing_helpers import mock_await_args

class _FakeRedisPubSub:
    """In-memory pub/sub that delivers to every subscribed handler (multi-worker)."""

    def __init__(self) -> None:
        """Init channel map."""
        self.channels: Dict[str, List[Any]] = {}

    async def publish(self, channel: str, payload: str) -> int:
        """Publish payload to all handlers on channel."""
        handlers = list(self.channels.get(channel, []))
        for handler in handlers:
            await handler(payload)
        return len(handlers)

    def subscribe(self, channel: str, handler: Any) -> None:
        """Subscribe handler to channel."""
        self.channels.setdefault(channel, []).append(handler)


@pytest.mark.asyncio
async def test_cross_worker_canvas_action_reaches_desktop_via_redis_sse() -> None:
    """
    Worker A (mobile) cannot see Worker B's canvas_owner WS; Redis desktop_wake
    still publishes canvas_action for the browser SSE listener.
    """
    redis = _FakeRedisPubSub()
    delivered: List[Dict[str, Any]] = []

    async def on_wake(payload: str) -> None:
        delivered.append(json.loads(payload))

    redis.subscribe("kitty:desktop_wake:7", on_wake)

    with patch(
        "services.kitty.infra.desktop.kitty_desktop_wake_fanout.get_async_redis",
        return_value=redis,
    ):
        ok = await publish_kitty_canvas_action(
            7,
            "lib-cross-worker",
            {
                "type": "action",
                "action": "auto_complete_branch",
                "params": {"node_label": "中国", "node_id": "branch-r-1-6"},
            },
        )

    assert ok is True
    assert len(delivered) == 1
    assert delivered[0]["type"] == "canvas_action"
    assert delivered[0]["action"] == "auto_complete_branch"
    assert delivered[0]["scope"] == "lib-cross-worker"
    assert delivered[0]["params"]["node_id"] == "branch-r-1-6"


@pytest.mark.asyncio
async def test_cross_worker_verified_diagram_update_sse_includes_mutation_id() -> None:
    """Verified edit SSE keeps mutation_id so desktop owner can apply + ack."""
    redis = _FakeRedisPubSub()
    delivered: List[Dict[str, Any]] = []

    async def on_wake(payload: str) -> None:
        delivered.append(json.loads(payload))

    redis.subscribe("kitty:desktop_wake:7", on_wake)

    with patch(
        "services.kitty.infra.desktop.kitty_desktop_wake_fanout.get_async_redis",
        return_value=redis,
    ):
        await publish_kitty_diagram_update(
            7,
            "lib-cross-worker",
            {
                "type": "diagram_update",
                "action": "add_nodes",
                "updates": {"nodes": [{"text": "江苏"}]},
                "mutation_id": "mut-cross-1",
                "expected_effect": {"kind": "add_nodes"},
            },
        )

    assert len(delivered) == 1
    assert delivered[0]["mutation_id"] == "mut-cross-1"
    assert delivered[0]["expected_effect"] == {"kind": "add_nodes"}


@pytest.mark.asyncio
async def test_cross_worker_mutation_ack_completes_pending_on_other_worker() -> None:
    """
    Worker A waits on a pending future; Worker B receives the client ack on its
    Kitty WS (no local pending) and Redis-relays so Worker A completes.
    """
    reset_pending_state_for_tests()
    redis = _FakeRedisPubSub()
    mutation_id = new_mutation_id()

    fut = register_pending(mutation_id, "voice-worker-a")
    # Simulate process isolation: pending future lives only on worker A.
    detached = detach_pending_for_tests(mutation_id)
    assert detached is fut

    async def worker_a_control_listener(raw: str) -> None:
        envelope = parse_kitty_control_envelope(raw)
        assert envelope is not None
        reattach_pending_for_tests(mutation_id, fut, voice_session_id="voice-worker-a")
        await handle_mutation_ack_relay(envelope)

    redis.subscribe("mg:kitty:control", worker_a_control_listener)
    configure_mutation_ack_relay(publish=publish_mutation_ack_relay)

    with patch(
        "services.kitty.infra.control.kitty_canvas_owner_relay.get_async_redis",
        return_value=redis,
    ):
        matched_on_b = complete_mutation_ack_from_client(
            {
                "mutation_id": mutation_id,
                "verified": True,
                "created_node_ids": ["branch-r-1-9"],
            },
            allow_relay=True,
        )
        assert matched_on_b is False
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    assert fut.done()
    ack = fut.result()
    assert ack.verified is True
    assert ack.created_node_ids == ["branch-r-1-9"]


@pytest.mark.asyncio
async def test_find_canvas_owner_misses_other_worker_session() -> None:
    """Process-local registry cannot see the desktop owner on another worker."""
    worker_a_sessions = {
        "vs-mobile": {
            "user_id": 7,
            "diagram_session_id": "lib-x",
            "_kitty_client_lane": "mobile",
            "_client_websocket": MagicMock(name="mobile_ws"),
        }
    }
    with patch(
        "services.kitty.session.canvas_owner.voice_sessions",
        worker_a_sessions,
    ):
        assert find_canvas_owner_websocket(7, "lib-x") is None

    owner_ws = MagicMock(name="desktop_ws")
    worker_b_sessions = {
        "vs-desktop": {
            "user_id": 7,
            "diagram_session_id": "lib-x",
            "_kitty_canvas_owner": True,
            "_client_websocket": owner_ws,
        }
    }
    with patch(
        "services.kitty.session.canvas_owner.voice_sessions",
        worker_b_sessions,
    ):
        assert find_canvas_owner_websocket(7, "lib-x") is owner_ws


@pytest.mark.asyncio
async def test_mobile_send_falls_back_to_sse_when_owner_not_local() -> None:
    """End-to-end messaging path: local miss → Redis canvas_action publish."""
    ingress_ws = MagicMock()
    message = {
        "type": "action",
        "action": "auto_complete",
        "params": {},
    }
    with (
        patch(
            "services.kitty.context.messaging.find_canvas_owner_websocket",
            return_value=None,
        ),
        patch(
            "services.kitty.context.messaging.require_aligned_for_verified_edit",
            AsyncMock(return_value=MagicMock(ok=True, error_code=None, message="")),
        ),
        patch(
            "services.kitty.context.messaging.publish_kitty_canvas_action",
            AsyncMock(return_value=True),
        ) as sse,
        patch(
            "services.kitty.context.messaging.voice_sessions",
            {
                "vs-mobile": {
                    "user_id": 3,
                    "diagram_session_id": "lib-js",
                    "_kitty_client_lane": "mobile",
                }
            },
        ),
    ):
        ok = await send_kitty_ws_action(ingress_ws, "vs-mobile", message)

    assert ok is True
    sse.assert_awaited_once()


@pytest.mark.asyncio
async def test_verified_send_without_local_owner_still_publishes_sse() -> None:
    """add_node cross-worker: chat-only WS + diagram_update SSE with mutation_id."""
    ingress_ws = MagicMock()
    message = {
        "type": "diagram_update",
        "action": "add_nodes",
        "updates": {"nodes": [{"text": "江苏"}]},
        "mutation_id": "mut-js",
        "user_summary": "已添加",
    }
    with (
        patch(
            "services.kitty.context.messaging.safe_websocket_send",
            AsyncMock(return_value=True),
        ) as safe_send,
        patch(
            "services.kitty.context.messaging.publish_kitty_diagram_update",
            AsyncMock(),
        ) as fanout,
        patch(
            "services.kitty.context.messaging.find_canvas_owner_websocket",
            return_value=None,
        ),
        patch(
            "services.kitty.context.messaging.require_aligned_for_verified_edit",
            AsyncMock(return_value=MagicMock(ok=True, error_code=None, message="")),
        ),
        patch(
            "services.kitty.context.messaging.voice_sessions",
            {
                "vs-mobile": {
                    "user_id": 3,
                    "diagram_session_id": "lib-js",
                    "_kitty_client_lane": "mobile",
                }
            },
        ),
        patch(
            "services.kitty.context.messaging.fanout_voice_command_from_session",
            AsyncMock(),
        ),
    ):
        ok = await send_kitty_diagram_update(ingress_ws, "vs-mobile", message)

    assert ok is True
    fanout.assert_awaited_once()
    assert mock_await_args(fanout)[2]["mutation_id"] == "mut-js"
    _ws, chat = mock_await_args(safe_send)
    # Chat-only mobile frame still carries mutation_id for Session Manager correlation.
    assert chat.get("mutation_id") == "mut-js"
    assert chat.get("updates") == {}
    assert chat.get("user_summary") == "已添加"


@pytest.mark.asyncio
async def test_cross_worker_desktop_action_pending_reaches_sse() -> None:
    """Enqueue wake is Redis pub/sub — any worker's SSE listener can drain via LPOP."""
    redis = _FakeRedisPubSub()
    delivered: List[Dict[str, Any]] = []

    async def on_wake(payload: str) -> None:
        delivered.append(json.loads(payload))

    redis.subscribe("kitty:desktop_wake:11", on_wake)

    with patch(
        "services.kitty.infra.desktop.kitty_desktop_wake_fanout.get_async_redis",
        return_value=redis,
    ):
        await publish_kitty_desktop_action_pending(11)

    assert len(delivered) == 1
    assert delivered[0]["type"] == "desktop_action_pending"


@pytest.mark.asyncio
async def test_cross_worker_desktop_focus_relay_pushes_mobile_ws() -> None:
    """
    Desktop PUT lands on worker A; mobile Kitty WS lives on worker B.
    Redis control ``desktop_focus`` must push ``desktop_focus_update`` on B.
    """
    redis = _FakeRedisPubSub()
    mobile_ws = MagicMock(name="mobile_ws_worker_b")
    worker_b_sessions = {
        "vs-mobile-b": {
            "user_id": 42,
            "diagram_session_id": "lib-focus",
            "_kitty_client_lane": "mobile",
            "_client_websocket": mobile_ws,
        }
    }

    async def worker_b_control_listener(raw: str) -> None:
        with patch(
            "services.kitty.infra.desktop.kitty_desktop_focus_push.voice_sessions",
            worker_b_sessions,
        ), patch(
            "services.kitty.infra.desktop.kitty_desktop_focus_push.safe_websocket_send",
            AsyncMock(return_value=True),
        ) as safe_send, patch(
            "services.kitty.infra.desktop.kitty_desktop_focus_push.get_kitty_control_instance_id",
            return_value="worker-b",
        ):
            await handle_kitty_control_dispatch(raw, local_instance="worker-b")
            safe_send.assert_awaited()
            _ws, body = mock_await_args(safe_send)
            assert body["type"] == "desktop_focus_update"
            assert body["diagram_library_id"] == "lib-focus-1"
            assert body["updated_at"] == 1_700_000_000

    redis.subscribe("mg:kitty:control", worker_b_control_listener)

    with (
        patch(
            "services.kitty.infra.desktop.kitty_desktop_focus_push.get_async_redis",
            return_value=redis,
        ),
        patch(
            "services.kitty.infra.desktop.kitty_desktop_focus_push.get_kitty_control_instance_id",
            return_value="worker-a",
        ),
        patch(
            "services.kitty.infra.desktop.kitty_desktop_focus_push.voice_sessions",
            {},
        ),
        patch(
            "services.kitty.infra.desktop.kitty_desktop_focus_push.safe_websocket_send",
            AsyncMock(return_value=True),
        ),
    ):
        # Same-worker push finds nothing on A.
        sent_local = await push_kitty_desktop_focus_to_local_mobile(
            42, "lib-focus-1", 1_700_000_000
        )
        assert sent_local == 0
        ok = await publish_desktop_focus_relay(42, "lib-focus-1", 1_700_000_000)
        assert ok is True
        await asyncio.sleep(0)
        await asyncio.sleep(0)
