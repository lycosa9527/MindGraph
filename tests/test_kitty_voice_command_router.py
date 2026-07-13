"""Tests for Kitty command router and diagram spec sync."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.diagram.diagram_spec_sync import sync_diagram_data_to_spec_shape
from services.kitty.diagram.diagram_utils import is_paragraph_text
from services.kitty.omni.tools import omni_function_call_to_command
from services.agent_hub.diagram_spine.types import DiagramCommandResult
from services.diagram_edit.types import ToolResult
from services.kitty.routing.command_router import (
    RouteOutcome,
    route_omni_function_call,
    route_voice_command,
)
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from tests.typing_helpers import mock_await_args, mock_await_kwargs


def test_sync_circle_map_children_to_context() -> None:
    """Test sync circle map children to context."""
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
    """Test sync bubble map attributes."""
    data = {
        "center": {"text": "Dog"},
        "children": [{"text": "loyal"}, {"text": "furry"}],
    }
    out = sync_diagram_data_to_spec_shape("bubble_map", data)
    assert out["attributes"] == [{"text": "loyal"}, {"text": "furry"}]


def test_omni_add_node_function_call() -> None:
    """Test omni add node function call."""
    cmd = omni_function_call_to_command("add_node", '{"text": "apple", "position": 1}')
    assert cmd["action"] == "add_node"
    assert cmd["target"] == "apple"
    assert cmd["node_index"] == 1


def test_omni_update_center_double_bubble() -> None:
    """Test omni update center double bubble."""
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
    """Test is paragraph text short commands."""
    assert is_paragraph_text(text) is is_paragraph


@pytest.mark.asyncio
async def test_route_omni_function_call_open_panel() -> None:
    """Test route omni function call open panel."""
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
    """Test omni open desktop canvas mindmap zh."""
    cmd = omni_function_call_to_command(
        "open_desktop_canvas",
        '{"diagram_type": "思维导图", "target": "运动会"}',
    )
    assert cmd["action"] == "open_desktop_canvas"
    assert cmd["diagram_type"] == "mindmap"
    assert cmd["target"] == "运动会"
    assert cmd["confidence"] >= 0.9


def test_omni_open_desktop_canvas_double_bubble() -> None:
    """Test omni open desktop canvas double bubble."""
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
    """Voice open_desktop_canvas creates a library draft then open_library_diagram."""
    ws = MagicMock()
    vid = create_voice_session(user_id="42", diagram_session_id="scope_test", diagram_type="circle_map")
    voice_sessions[vid]["context"] = {"diagram_data": {"children": [], "center": {"text": ""}}}

    enqueue_mock = AsyncMock(return_value=True)
    drain_mock = AsyncMock()
    wake_mock = AsyncMock()
    ack_mock = AsyncMock(return_value=True)
    save_mock = AsyncMock(return_value="lib-draft-001")
    focus_mock = AsyncMock(return_value=("lib-draft-001", 1_700_000_000))
    notify_mock = AsyncMock()
    ingress_mock = AsyncMock()
    mgr = MagicMock()
    mgr.set_desktop_focus = focus_mock
    mgr.begin_ingress = ingress_mock

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
                "services.kitty.routing.open_desktop_canvas.try_save_diagram_to_library",
                save_mock,
            ),
            patch(
                "services.kitty.routing.open_desktop_canvas.enqueue_kitty_desktop_action",
                enqueue_mock,
            ),
            patch(
                "services.kitty.routing.open_desktop_canvas.mark_kitty_desktop_action_explicit_drain",
                drain_mock,
            ),
            patch(
                "services.kitty.routing.open_desktop_canvas.publish_kitty_desktop_action_pending",
                wake_mock,
            ),
            patch(
                "services.kitty.routing.open_desktop_canvas.emit_user_ack",
                ack_mock,
            ),
            patch(
                "services.kitty.routing.open_desktop_canvas.notify_kitty_desktop_focus_changed",
                notify_mock,
            ),
            patch(
                "services.kitty.routing.open_desktop_canvas.get_kitty_session_manager",
                return_value=mgr,
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
        save_mock.assert_awaited_once()
        save_kwargs = mock_await_kwargs(save_mock)
        assert save_kwargs["title"] == "运动会"
        assert save_kwargs["diagram_type"] == "mindmap"
        assert save_kwargs["spec"] == {"topic": "运动会", "children": []}
        drain_mock.assert_awaited_once()
        enqueue_mock.assert_awaited_once()
        payload = mock_await_args(enqueue_mock)[1]
        assert payload["kind"] == "open_library_diagram"
        assert payload["diagram_library_id"] == "lib-draft-001"
        assert payload["title"] == "运动会"
        wake_mock.assert_awaited_once_with(42)
        focus_mock.assert_awaited_once_with(42, "lib-draft-001")
        notify_mock.assert_awaited_once()
        ingress_mock.assert_awaited_once()
        ingress_kwargs = mock_await_kwargs(ingress_mock)
        assert ingress_kwargs["source"] == "ui_create"
        assert ingress_kwargs["scope"] == "lib-draft-001"
        assert voice_sessions[vid]["diagram_session_id"] == "lib-draft-001"
        ack_mock.assert_awaited()
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_route_omni_function_call_inline_recommendations_selected() -> None:
    """Test route omni function call inline recommendations selected."""
    ws = MagicMock()
    vid = create_voice_session(user_id="7", diagram_session_id="scope_test", diagram_type="mindmap")
    voice_sessions[vid]["context"] = {
        "diagram_data": {
            "children": [{"id": "branch-l-1-0", "text": "Sports"}],
        },
        "selected_nodes": ["branch-l-1-0"],
    }

    send_mock = AsyncMock(return_value=True)
    ack_mock = AsyncMock(return_value=True)

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
                "services.kitty.routing.command_router.send_kitty_ws_action",
                send_mock,
            ),
            patch(
                "services.kitty.routing.command_router.emit_user_ack",
                ack_mock,
            ),
            patch(
                "services.kitty.routing.command_router.fanout_voice_command_from_session",
                new=AsyncMock(),
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
        payload = mock_await_args(send_mock)[2]
        assert payload["action"] == "start_inline_recommendations"
        assert payload["params"]["node_id"] == "branch-l-1-0"
        ack_mock.assert_awaited()
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_route_update_node_emits_success_ack() -> None:
    """Diagram update success emits templated user acknowledgment."""
    ws = MagicMock()
    vid = create_voice_session(user_id="7", diagram_session_id="lib-ack-1", diagram_type="mind_map")
    voice_sessions[vid]["context"] = {
        "interaction_language": "zh",
        "diagram_data": {
            "children": [{"id": "branch-0", "text": "食"}],
            "center": {"text": "北京三日游"},
        },
    }
    ack_mock = AsyncMock(return_value=True)

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
                "services.kitty.routing.command_router.parse_voice_intent_with_tools",
                new=AsyncMock(
                    return_value={
                        "action": "update_node",
                        "node_identifier": "食",
                        "target": "小吃",
                        "confidence": 0.95,
                    }
                ),
            ),
            patch(
                "services.kitty.routing.command_router.apply_kitty_legacy_diagram_command",
                new=AsyncMock(
                    return_value=DiagramCommandResult(
                        tool_result=ToolResult(
                            status="applied",
                            mutation_id="legacy-mut",
                            revision=0,
                        ),
                        hub_revision=0,
                    )
                ),
            ),
            patch(
                "services.kitty.routing.command_router.emit_user_ack",
                ack_mock,
            ),
            patch(
                "services.kitty.routing.command_router.redis_user_cache.get_by_id",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await route_voice_command(
                ws,
                vid,
                "把食改成小吃",
                dict(voice_sessions[vid]["context"]),
                is_text_message=True,
                from_voice=False,
            )

        assert result.outcome == RouteOutcome.EXECUTED
        ack_mock.assert_awaited_once()
        ack_text = mock_await_args(ack_mock)[2]
        # Rotating phrase pools may omit old_text; new label is always present.
        assert "小吃" in ack_text
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_route_low_confidence_diagram_emits_clarify_ack() -> None:
    """Low-confidence diagram intent emits echo-back clarify ack."""
    ws = MagicMock()
    vid = create_voice_session(user_id="8", diagram_session_id="lib-ack-2", diagram_type="mind_map")
    voice_sessions[vid]["context"] = {
        "interaction_language": "zh",
        "diagram_data": {"children": [], "center": {"text": "Topic"}},
    }
    ack_mock = AsyncMock(return_value=True)

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
                "services.kitty.routing.command_router.parse_voice_intent_with_tools",
                new=AsyncMock(
                    return_value={
                        "action": "update_node",
                        "node_identifier": "食",
                        "target": "小吃",
                        "confidence": 0.2,
                    }
                ),
            ),
            patch(
                "services.kitty.routing.command_router.emit_user_ack",
                ack_mock,
            ),
            patch(
                "services.kitty.routing.command_router.redis_user_cache.get_by_id",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await route_voice_command(
                ws,
                vid,
                "把食改成小吃",
                dict(voice_sessions[vid]["context"]),
                is_text_message=True,
                from_voice=False,
            )

        assert result.outcome == RouteOutcome.FAILED
        assert result.reason == "low_confidence_diagram"
        ack_mock.assert_awaited_once()
        ack_text = mock_await_args(ack_mock)[2]
        assert "食" in ack_text
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_route_open_desktop_canvas_fishbone_emits_unsupported_ack() -> None:
    """Rejected fishbone desktop open emits in-development ack with mind map alternative."""
    ws = MagicMock()
    vid = create_voice_session(user_id="9", diagram_session_id="scope-fish", diagram_type="mind_map")
    voice_sessions[vid]["context"] = {"interaction_language": "zh", "diagram_data": {"children": []}}
    ack_mock = AsyncMock(return_value=True)

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
                "services.kitty.routing.command_router.emit_user_ack",
                ack_mock,
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
                '{"diagram_type": "fishbone", "target": "质量问题"}',
                dict(voice_sessions[vid]["context"]),
            )

        assert result.outcome == RouteOutcome.FAILED
        assert result.reason == "unsupported_diagram_type"
        ack_mock.assert_awaited_once()
        ack_text = mock_await_args(ack_mock)[2]
        assert "鱼骨" in ack_text or "开发" in ack_text
        assert "思维导图" in ack_text
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_route_unsupported_diagram_type_from_text() -> None:
    """Parser-routed unsupported diagram intent emits templated fallback."""
    ws = MagicMock()
    vid = create_voice_session(user_id="10", diagram_session_id="scope-fish-2", diagram_type="mind_map")
    voice_sessions[vid]["context"] = {"interaction_language": "zh", "diagram_data": {"children": []}}
    ack_mock = AsyncMock(return_value=True)

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
                "services.kitty.routing.command_router.parse_voice_intent_with_tools",
                new=AsyncMock(
                    return_value={
                        "action": "unsupported_diagram_type",
                        "requested_label": "鱼骨图",
                        "confidence": 0.85,
                    }
                ),
            ),
            patch(
                "services.kitty.routing.command_router.emit_user_ack",
                ack_mock,
            ),
            patch(
                "services.kitty.routing.command_router.redis_user_cache.get_by_id",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await route_voice_command(
                ws,
                vid,
                "帮我画一张鱼骨图",
                dict(voice_sessions[vid]["context"]),
                is_text_message=True,
                from_voice=False,
            )

        assert result.outcome == RouteOutcome.FAILED
        assert result.reason == "unsupported_diagram_type"
        ack_mock.assert_awaited_once()
        ack_text = mock_await_args(ack_mock)[2]
        assert "思维导图" in ack_text
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_route_unknown_action_text_emits_not_understood_ack() -> None:
    """Unknown structured action on text path clarifies supported node edits."""
    ws = MagicMock()
    vid = create_voice_session(user_id="11", diagram_session_id="scope-unk", diagram_type="mind_map")
    voice_sessions[vid]["context"] = {"interaction_language": "zh", "diagram_data": {"children": []}}
    ack_mock = AsyncMock(return_value=True)

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
                "services.kitty.routing.command_router.parse_voice_intent_with_tools",
                new=AsyncMock(
                    return_value={
                        "action": "rotate_canvas",
                        "confidence": 0.9,
                    }
                ),
            ),
            patch(
                "services.kitty.routing.command_router.emit_user_ack",
                ack_mock,
            ),
            patch(
                "services.kitty.routing.command_router.redis_user_cache.get_by_id",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await route_voice_command(
                ws,
                vid,
                "旋转画布",
                dict(voice_sessions[vid]["context"]),
                is_text_message=True,
                from_voice=False,
            )

        assert result.outcome == RouteOutcome.FAILED
        assert result.reason == "action_not_understood"
        ack_mock.assert_awaited_once()
        ack_text = mock_await_args(ack_mock)[2]
        assert "节点" in ack_text
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_route_voice_command_from_voice_skips_turbo() -> None:
    """Test route voice command from voice skips turbo."""
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
    """Test route voice select node syncs hub and fanout."""
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
                "services.kitty.routing.command_router.load_kitty_live_context",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "services.kitty.routing.command_router.throttled_refresh_voice_context_from_library",
                new=AsyncMock(return_value=None),
            ),
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
        payload = mock_await_args(send_mock)[1]
        assert payload["action"] == "select_node"
        assert payload["params"]["node_id"] == "context-0"
    finally:
        voice_sessions.pop(vid, None)
