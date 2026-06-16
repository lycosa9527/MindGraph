"""Kitty cross-device sync: mobile UUID context, desktop fanout, hub merge."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.typing_helpers import mock_await_args, mock_await_kwargs
from services.kitty.context.messaging import send_kitty_diagram_update
from services.kitty.infra.desktop.kitty_desktop_wake_fanout import (
    publish_kitty_diagram_update,
    publish_kitty_selection_update,
)


@pytest.mark.asyncio
async def test_publish_kitty_diagram_update_payload_shape() -> None:
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
async def test_publish_kitty_selection_update_payload_shape() -> None:
    fake_redis = MagicMock()
    fake_redis.publish = AsyncMock()
    with patch(
        "services.kitty.infra.desktop.kitty_desktop_wake_fanout.get_async_redis",
        return_value=fake_redis,
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
            "services.kitty.infra.desktop.kitty_desktop_wake_fanout.publish_kitty_diagram_update",
            AsyncMock(),
        ) as fanout,
        patch(
            "services.kitty.session.runtime_state.voice_sessions",
            {
                "vs1": {
                    "user_id": 42,
                    "diagram_session_id": "lib-uuid-2",
                }
            },
        ),
    ):
        ok = await send_kitty_diagram_update(websocket, "vs1", message)

    assert ok is True
    safe_send.assert_awaited_once_with(websocket, message)
    fanout.assert_awaited_once_with(42, "lib-uuid-2", message)


@pytest.mark.asyncio
async def test_mobile_patch_context_prefers_library_when_delta_empty() -> None:
    from services.agent_hub.scope_lifecycle import MindGraphAgentHub

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
