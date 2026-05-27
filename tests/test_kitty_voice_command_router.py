"""Tests for Kitty command router and diagram spec sync."""

from __future__ import annotations

import pytest

from services.kitty.diagram.diagram_spec_sync import sync_diagram_data_to_spec_shape
from services.kitty.omni.tools import omni_function_call_to_command


def test_sync_circle_map_children_to_context() -> None:
    data = {
        "center": {"text": "Cars"},
        "children": [
            {"id": "context_0", "text": "wheels"},
            {"id": "context_1", "text": "engine"},
        ],
    }
    out = sync_diagram_data_to_spec_shape("circle_map", data)
    assert out["topic"] == "Cars"
    assert out["context"] == ["wheels", "engine"]


def test_sync_bubble_map_attributes() -> None:
    data = {
        "center": {"text": "Dog"},
        "children": [{"text": "loyal"}, {"text": "furry"}],
    }
    out = sync_diagram_data_to_spec_shape("bubble_map", data)
    assert out["attributes"] == [{"text": "loyal"}, {"text": "furry"}]


def test_omni_add_node_function_call() -> None:
    cmd = omni_function_call_to_command("add_node", '{"text": "apple", "position": 1}')
    assert cmd["action"] == "add_node"
    assert cmd["target"] == "apple"
    assert cmd["node_index"] == 1


def test_omni_update_center_double_bubble() -> None:
    cmd = omni_function_call_to_command(
        "update_center",
        '{"left": "Apples", "right": "Pears"}',
    )
    assert cmd["action"] == "update_center"
    assert cmd["left"] == "Apples"
    assert cmd["right"] == "Pears"


@pytest.mark.parametrize(
    "text,is_paragraph",
    [
        ("add node apple", False),
        ("hello", False),
    ],
)
def test_is_paragraph_text_short_commands(text: str, is_paragraph: bool) -> None:
    from services.kitty.diagram.diagram_utils import is_paragraph_text

    assert is_paragraph_text(text) is is_paragraph


@pytest.mark.asyncio
async def test_route_omni_function_call_open_panel() -> None:
    from unittest.mock import AsyncMock, MagicMock, patch

    from services.kitty.routing.command_router import RouteOutcome, route_omni_function_call
    from services.kitty.session.runtime_state import voice_sessions
    from services.kitty.session.ops import create_voice_session

    ws = MagicMock()
    vid = create_voice_session(user_id="1", diagram_session_id="scope_test", diagram_type="circle_map")
    voice_sessions[vid]["context"] = {"diagram_data": {"children": [], "center": {"text": ""}}}

    try:
        with (
            patch(
                "services.kitty.routing.command_router.safe_websocket_send",
                new=AsyncMock(return_value=True),
            ) as send_mock,
            patch(
                "services.kitty.routing.command_router.redis_user_cache.get_by_id",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await route_omni_function_call(
                ws,
                vid,
                "open_panel",
                '{"panel_name": "mindmate"}',
                dict(voice_sessions[vid]["context"]),
            )
        assert result.outcome == RouteOutcome.EXECUTED
        send_mock.assert_awaited()
    finally:
        voice_sessions.pop(vid, None)


def test_omni_open_desktop_canvas_mindmap_zh() -> None:
    cmd = omni_function_call_to_command(
        "open_desktop_canvas",
        '{"diagram_type": "思维导图", "target": "运动会"}',
    )
    assert cmd["action"] == "open_desktop_canvas"
    assert cmd["diagram_type"] == "mindmap"
    assert cmd["target"] == "运动会"
    assert cmd["confidence"] >= 0.9


def test_omni_open_desktop_canvas_double_bubble() -> None:
    cmd = omni_function_call_to_command(
        "open_desktop_canvas",
        '{"diagram_type": "double_bubble_map", "left": "苹果", "right": "梨"}',
    )
    assert cmd["action"] == "open_desktop_canvas"
    assert cmd["diagram_type"] == "double_bubble_map"
    assert cmd["left"] == "苹果"
    assert cmd["right"] == "梨"


@pytest.mark.asyncio
async def test_route_omni_function_call_open_desktop_canvas() -> None:
    from unittest.mock import AsyncMock, MagicMock, patch

    from services.kitty.routing.command_router import RouteOutcome, route_omni_function_call
    from services.kitty.session.runtime_state import voice_sessions
    from services.kitty.session.ops import create_voice_session

    ws = MagicMock()
    vid = create_voice_session(user_id="42", diagram_session_id="scope_test", diagram_type="circle_map")
    voice_sessions[vid]["context"] = {"diagram_data": {"children": [], "center": {"text": ""}}}

    enqueue_mock = AsyncMock(return_value=True)
    wake_mock = AsyncMock()
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
                "services.kitty.routing.command_router.enqueue_kitty_desktop_action",
                enqueue_mock,
            ),
            patch(
                "services.kitty.routing.command_router.publish_kitty_desktop_action_pending",
                wake_mock,
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
                "open_desktop_canvas",
                '{"diagram_type": "mindmap", "target": "运动会"}',
                dict(voice_sessions[vid]["context"]),
            )
        assert result.outcome == RouteOutcome.EXECUTED
        enqueue_mock.assert_awaited_once()
        payload = enqueue_mock.await_args.args[1]
        assert payload["kind"] == "open_canvas"
        assert payload["diagram_type"] == "mindmap"
        assert payload["topic"] == "运动会"
        wake_mock.assert_awaited_once_with(42)
        omni_mock.create_response.assert_awaited()
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_route_omni_function_call_inline_recommendations_selected() -> None:
    from unittest.mock import AsyncMock, MagicMock, patch

    from services.kitty.routing.command_router import RouteOutcome, route_omni_function_call
    from services.kitty.session.runtime_state import voice_sessions
    from services.kitty.session.ops import create_voice_session

    ws = MagicMock()
    vid = create_voice_session(user_id="7", diagram_session_id="scope_test", diagram_type="mindmap")
    voice_sessions[vid]["context"] = {
        "diagram_data": {
            "children": [{"id": "branch-l-1-0", "text": "Sports"}],
        },
        "selected_nodes": ["branch-l-1-0"],
    }

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
                "start_inline_recommendations",
                "{}",
                dict(voice_sessions[vid]["context"]),
            )
        assert result.outcome == RouteOutcome.EXECUTED
        send_mock.assert_awaited()
        payload = send_mock.await_args.args[1]
        assert payload["action"] == "start_inline_recommendations"
        assert payload["params"]["node_id"] == "branch-l-1-0"
        omni_mock.create_response.assert_awaited()
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_route_voice_command_from_voice_skips_turbo() -> None:
    from unittest.mock import MagicMock

    from services.kitty.routing.command_router import RouteOutcome, route_voice_command

    ws = MagicMock()
    result = await route_voice_command(
        ws,
        "voice_nonexistent",
        "add node apple",
        {"diagram_data": {"children": []}},
        is_text_message=False,
        from_voice=True,
    )
    assert result.outcome == RouteOutcome.CONVERSATIONAL_FALLBACK


@pytest.mark.asyncio
async def test_route_voice_select_node_syncs_hub_and_fanout() -> None:
    from unittest.mock import AsyncMock, MagicMock, patch

    from services.kitty.routing.command_router import RouteOutcome, route_voice_command
    from services.kitty.session.ops import create_voice_session
    from services.kitty.session.runtime_state import voice_sessions

    ws = MagicMock()
    vid = create_voice_session(user_id="42", diagram_session_id="lib-uuid-sel", diagram_type="circle_map")
    voice_sessions[vid]["context"] = {
        "diagram_data": {
            "children": [{"id": "context-0", "text": "Wheels"}],
            "center": {"text": "Cars"},
        },
        "selected_nodes": [],
    }

    try:
        with (
            patch(
                "services.kitty.routing.command_router.safe_websocket_send",
                new=AsyncMock(return_value=True),
            ) as send_mock,
            patch(
                "services.kitty.routing.command_router.parse_voice_intent_with_tools",
                new=AsyncMock(
                    return_value={
                        "action": "select_node",
                        "node_index": 0,
                        "confidence": 0.95,
                    }
                ),
            ),
            patch(
                "services.kitty.routing.command_router.redis_user_cache.get_by_id",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.kitty.routing.command_router.try_sync_voice_diagram_to_hub",
                new=AsyncMock(),
            ) as hub_sync,
            patch(
                "services.kitty.routing.command_router.publish_kitty_selection_update",
                new=AsyncMock(),
            ) as fanout,
        ):
            result = await route_voice_command(
                ws,
                vid,
                "select first node",
                dict(voice_sessions[vid]["context"]),
                is_text_message=True,
                from_voice=False,
            )

        assert result.outcome == RouteOutcome.EXECUTED
        hub_sync.assert_awaited_once_with(vid)
        fanout.assert_awaited_once_with(42, "lib-uuid-sel", ["context-0"])
        assert voice_sessions[vid]["context"]["selected_nodes"] == ["context-0"]
        send_mock.assert_awaited()
        payload = send_mock.await_args.args[1]
        assert payload["action"] == "select_node"
        assert payload["params"]["node_id"] == "context-0"
    finally:
        voice_sessions.pop(vid, None)
