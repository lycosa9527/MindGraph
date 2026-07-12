"""Kitty cross-device sync: mobile UUID context, desktop fanout, hub merge."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.agent_hub.scope_lifecycle import MindGraphAgentHub
from services.kitty.context.messaging import send_kitty_diagram_update
from services.kitty.infra.desktop.kitty_desktop_wake_fanout import (
    publish_kitty_diagram_update,
    publish_kitty_selection_update,
)
from services.kitty.infra.desktop.kitty_selection_push import (
    normalize_kitty_selected_nodes,
    push_kitty_selection_to_mobile_scope,
)
from tests.typing_helpers import mock_await_args, mock_await_kwargs


@pytest.mark.asyncio
async def test_normalize_kitty_selected_nodes_dedupes() -> None:
    """Selection push normalizes and dedupes node ids."""
    assert normalize_kitty_selected_nodes(["a", " a ", "b", "a", "", 1]) == ["a", "b"]
    assert not normalize_kitty_selected_nodes(None)


@pytest.mark.asyncio
async def test_push_kitty_selection_to_mobile_scope_sends_ws() -> None:
    """Desktop selection PUT path notifies mobile WebSocket clients."""
    websocket = MagicMock()
    with (
        patch(
            "services.kitty.infra.desktop.kitty_selection_push.load_kitty_live_context",
            AsyncMock(return_value={"diagram_type": "mindmap", "diagram_data": {}}),
        ),
        patch(
            "services.kitty.infra.desktop.kitty_selection_push.upsert_kitty_redis_session",
            AsyncMock(return_value=123),
        ),
        patch(
            "services.kitty.infra.desktop.kitty_selection_push.safe_websocket_send",
            AsyncMock(return_value=True),
        ) as safe_send,
        patch(
            "services.kitty.infra.desktop.kitty_selection_push.active_websockets",
            {"lib-sel-1": [websocket]},
        ),
        patch(
            "services.kitty.infra.desktop.kitty_selection_push.voice_sessions",
            {
                "vs1": {
                    "user_id": 3,
                    "diagram_session_id": "lib-sel-1",
                    "context": {"selected_nodes": []},
                }
            },
        ),
    ):
        sent = await push_kitty_selection_to_mobile_scope("lib-sel-1", 3, ["n1", "n2"])

    assert sent == 1
    safe_send.assert_awaited_once()
    _ws, body = mock_await_args(safe_send)
    assert body["type"] == "selection_update"
    assert body["selected_nodes"] == ["n1", "n2"]


@pytest.mark.asyncio
async def test_publish_kitty_diagram_update_payload_shape() -> None:
    """Test publish kitty diagram update payload shape."""
    fake_redis = MagicMock()
    fake_redis.publish = AsyncMock()
    with patch(
        "services.kitty.infra.desktop.kitty_desktop_wake_fanout.get_async_redis",
        return_value=fake_redis,
    ):
        await publish_kitty_diagram_update(
            7,
            "lib-uuid-1",
            {
                "type": "diagram_update",
                "action": "add_nodes",
                "updates": [{"text": "node"}],
            },
        )

    fake_redis.publish.assert_awaited_once()
    channel, raw = mock_await_args(fake_redis.publish)
    assert "7" in channel
    body = json.loads(raw)
    assert body["type"] == "diagram_update"
    assert body["scope"] == "lib-uuid-1"
    assert body["action"] == "add_nodes"
    assert body["updates"] == [{"text": "node"}]


@pytest.mark.asyncio
async def test_publish_kitty_diagram_update_includes_mutation_id() -> None:
    """Verified WS edits must fan out mutation_id so desktop skips duplicate apply."""
    fake_redis = MagicMock()
    fake_redis.publish = AsyncMock()
    with patch(
        "services.kitty.infra.desktop.kitty_desktop_wake_fanout.get_async_redis",
        return_value=fake_redis,
    ):
        await publish_kitty_diagram_update(
            7,
            "lib-uuid-1",
            {
                "type": "diagram_update",
                "action": "add_nodes",
                "updates": [{"text": "node"}],
                "mutation_id": "mut-abc-123",
            },
        )

    fake_redis.publish.assert_awaited_once()
    _channel, raw = mock_await_args(fake_redis.publish)
    body = json.loads(raw)
    assert body["mutation_id"] == "mut-abc-123"


@pytest.mark.asyncio
async def test_publish_kitty_selection_update_payload_shape() -> None:
    """Test publish kitty selection update payload shape."""
    fake_redis = MagicMock()
    fake_redis.publish = AsyncMock()
    with (
        patch(
            "services.kitty.infra.desktop.kitty_desktop_wake_fanout.get_async_redis",
            return_value=fake_redis,
        ),
        patch(
            "services.kitty.infra.desktop.kitty_desktop_wake_fanout.publish_kitty_voice_command_log",
            AsyncMock(),
        ),
    ):
        await publish_kitty_selection_update(
            9,
            "lib-uuid-sel",
            ["context-0", "context-1"],
        )

    fake_redis.publish.assert_awaited_once()
    channel, raw = mock_await_args(fake_redis.publish)
    assert "9" in channel
    body = json.loads(raw)
    assert body["type"] == "selection_update"
    assert body["scope"] == "lib-uuid-sel"
    assert body["selected_nodes"] == ["context-0", "context-1"]


@pytest.mark.asyncio
async def test_send_kitty_diagram_update_fanouts_when_voice_session_known() -> None:
    """Test send kitty diagram update fanouts when voice session known."""
    websocket = MagicMock()
    message = {
        "type": "diagram_update",
        "action": "update_center",
        "updates": {"new_text": "Topic"},
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
            "services.kitty.context.messaging.voice_sessions",
            {
                "vs1": {
                    "user_id": 42,
                    "diagram_session_id": "lib-uuid-2",
                }
            },
        ),
        patch(
            "services.kitty.context.messaging.render_ack_for_diagram_update",
            return_value="摘要",
        ),
    ):
        ok = await send_kitty_diagram_update(websocket, "vs1", message)

    assert ok is True
    assert safe_send.await_count == 1
    sent_msg = mock_await_args(safe_send)[1]
    assert sent_msg["type"] == "diagram_update"
    assert sent_msg["action"] == "update_center"
    assert sent_msg["updates"] == {"new_text": "Topic"}
    fanout.assert_awaited_once_with(42, "lib-uuid-2", sent_msg)


@pytest.mark.asyncio
async def test_mobile_patch_context_prefers_library_when_delta_empty() -> None:
    """Test mobile patch context prefers library when delta empty."""
    hub = MindGraphAgentHub()
    sid = await hub.open_session(5, client_lane="mobile", source_module="kitty_test")
    await hub.bind_scope(sid, diagram_scope="lib-uuid-3", source_module="kitty_test")

    library_children = [{"id": "context-0", "index": 0, "text": "from-library"}]
    bootstrap_ctx = {
        "context": {
            "diagram_library_id": "lib-uuid-3",
            "diagram_data": {"children": library_children, "topic": "Library topic"},
            "selected_nodes": [],
        },
        "diagram_type": "circle_map",
        "active_panel": "none",
        "source": "library",
    }

    with (
        patch(
            "services.agent_hub.scope_lifecycle.resolve_mobile_open_bootstrap",
            AsyncMock(return_value=bootstrap_ctx),
        ),
        patch(
            "services.agent_hub.scope_lifecycle.merge_voice_context_with_library",
            AsyncMock(
                return_value=(
                    bootstrap_ctx["context"],
                    "circle_map",
                    "none",
                )
            ),
        ) as merge_lib,
        patch(
            "services.agent_hub.scope_lifecycle.upsert_kitty_redis_session",
            AsyncMock(return_value=999),
        ),
    ):
        out = await hub.apply_diagram_spec_mutation(
            hub_session_id=sid,
            diagram_scope="lib-uuid-3",
            mutation_cmd={
                "op": "patch_context",
                "context": {
                    "diagram_library_id": "lib-uuid-3",
                    "diagram_data": {},
                    "selected_nodes": [],
                },
                "diagram_type": "circle_map",
                "active_panel": "none",
            },
            source_module="kitty_test",
            expected_revision=0,
        )

    assert out["ok"] is True
    merge_lib.assert_awaited_once()
    assert mock_await_kwargs(merge_lib)["prefer_server_diagram_nodes"] is True
