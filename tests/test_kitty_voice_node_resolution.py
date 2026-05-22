"""Tests for Kitty voice node reference resolution."""

from __future__ import annotations

import pytest

from services.kitty.diagram.diagram_utils import resolve_voice_node_reference
from services.kitty.omni.tools import omni_function_call_to_command


def test_resolve_voice_node_by_index_uses_child_id() -> None:
    ctx = {
        "diagram_data": {
            "children": [
                {"id": "branch-l-1-0", "text": "Sports"},
                {"id": "branch-r-1-1", "text": "Music"},
            ],
        },
        "selected_nodes": [],
    }
    out = resolve_voice_node_reference(ctx, "mindmap", node_index=0)
    assert out is not None
    assert out["node_id"] == "branch-l-1-0"
    assert out["node_label"] == "Sports"


def test_resolve_voice_node_by_text_match() -> None:
    ctx = {
        "diagram_data": {
            "children": [{"id": "context-0", "text": "Wheels"}],
        },
    }
    out = resolve_voice_node_reference(ctx, "circle_map", node_identifier="Wheel")
    assert out is not None
    assert out["node_id"] == "context-0"
    assert out["node_index"] == 0


def test_resolve_voice_node_falls_back_to_selected() -> None:
    ctx = {
        "diagram_data": {
            "children": [{"id": "bubble-1", "text": "Fast"}],
            "selected_nodes": ["bubble-1"],
        },
        "selected_nodes": ["bubble-1"],
    }
    out = resolve_voice_node_reference(ctx, "bubble_map", prefer_selected=True)
    assert out is not None
    assert out["node_id"] == "bubble-1"
    assert out["node_label"] == "Fast"


def test_omni_start_inline_recommendations_tool() -> None:
    cmd = omni_function_call_to_command(
        "start_inline_recommendations",
        '{"node_identifier": "第一个"}',
    )
    assert cmd["action"] == "start_inline_recommendations"
    assert cmd["node_identifier"] == "第一个"


def test_omni_explain_node_without_identifier() -> None:
    cmd = omni_function_call_to_command("explain_node", "{}")
    assert cmd["action"] == "explain_node"
    assert "node_identifier" not in cmd


def test_omni_add_node_with_recommendations_tool() -> None:
    cmd = omni_function_call_to_command("add_node_with_recommendations", "{}")
    assert cmd["action"] == "add_node_with_recommendations"
    assert cmd.get("target") is None

    cmd2 = omni_function_call_to_command(
        "add_node_with_recommendations",
        '{"text": "placeholder"}',
    )
    assert cmd2["target"] == "placeholder"


@pytest.mark.asyncio
async def test_route_omni_add_node_with_recommendations() -> None:
    from unittest.mock import AsyncMock, MagicMock, patch

    from services.kitty.routing.command_router import RouteOutcome, route_omni_function_call
    from services.kitty.session.runtime_state import voice_sessions
    from services.kitty.session.ops import create_voice_session

    ws = MagicMock()
    vid = create_voice_session(user_id="3", diagram_session_id="scope_test", diagram_type="bubble_map")
    voice_sessions[vid]["context"] = {"diagram_data": {"children": []}}

    send_mock = AsyncMock(return_value=True)
    omni_mock = AsyncMock()

    try:
        with (
            patch(
                "services.kitty.routing.command_router.load_kitty_live_context",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.kitty.routing.command_router.throttled_refresh_voice_context_from_library",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.kitty.routing.command_router.safe_websocket_send",
                send_mock,
            ),
            patch(
                "services.kitty.routing.command_router.get_session_omni_client",
                return_value=omni_mock,
            ),
            patch(
                "services.kitty.routing.command_router.redis_user_cache.get_by_id",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await route_omni_function_call(
                ws,
                vid,
                "add_node_with_recommendations",
                "{}",
                dict(voice_sessions[vid]["context"]),
            )
        assert result.outcome == RouteOutcome.EXECUTED
        payload = send_mock.await_args.args[1]
        assert payload["action"] == "add_node_with_recommendations"
        omni_mock.create_response.assert_awaited()
    finally:
        voice_sessions.pop(vid, None)


def test_omni_ask_mindmate_tool() -> None:
    cmd = omni_function_call_to_command(
        "ask_mindmate",
        '{"message": "什么是光合作用？"}',
    )
    assert cmd["action"] == "ask_mindmate"
    assert cmd["target"] == "什么是光合作用？"
