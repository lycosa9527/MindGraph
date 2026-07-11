"""Mock integration tests: one-sentence edit → Bus → combined ack → canvas path."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.agent_hub.diagram_spine.types import DiagramCommandResult
from services.diagram_edit.ack import complete_mutation_ack_from_client
from services.diagram_edit.executor import execute_diagram_edit_from_legacy
from services.diagram_edit.pending import register_pending, reset_pending_state_for_tests
from services.diagram_edit.transport.kitty_ws import OUTBOUND_EXTRAS_KEY, verified_edit_extras_pending
from services.diagram_edit.types import ToolResult
from services.kitty.diagram.diagram_execute import execute_diagram_update
from services.kitty.routing.command_router import RouteOutcome, route_voice_command
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from tests.typing_helpers import mock_await_args, mock_await_kwargs


def _mindmap_edit_context() -> dict:
    return {
        "one_sentence_phase": "edit",
        "active_panel": "one_sentence",
        "interaction_language": "zh",
        "diagram_data": {
            "center": {"text": "Cars"},
            "children": [],
        },
    }


def _applied_bus_result(
    revision: int = 2,
    *,
    node_id: str | None = "branch-r-1-0",
) -> DiagramCommandResult:
    applied_ops = [{"op": "add_node", "text": "DIY", "node_id": node_id}] if node_id else []
    return DiagramCommandResult(
        tool_result=ToolResult(
            status="applied",
            mutation_id="edit-mut-1",
            revision=revision,
            applied_ops=applied_ops,
        ),
        hub_revision=revision,
    )


@pytest.mark.asyncio
async def test_one_sentence_add_node_routes_through_verified_bus() -> None:
    """Edit-phase text add_node uses Bus; branch auto-complete starts after verify with node_id."""
    ws = MagicMock()
    vid = create_voice_session(user_id="1", diagram_session_id="scope-os-add", diagram_type="mind_map")
    voice_sessions[vid]["context"] = _mindmap_edit_context()
    ack_mock = AsyncMock(return_value=True)
    hub_sync_mock = AsyncMock()
    call_order: list[str] = []

    async def _bus_side_effect(*_args, **_kwargs):
        call_order.append("bus")
        return _applied_bus_result()

    async def _branch_ac_side_effect(*_args, **_kwargs):
        call_order.append("auto_complete_branch")
        return True

    bus_mock = AsyncMock(side_effect=_bus_side_effect)
    branch_ac_mock = AsyncMock(side_effect=_branch_ac_side_effect)

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
                "services.kitty.routing.command_router.parse_one_sentence_edit_intent",
                new=AsyncMock(
                    return_value={
                        "action": "add_node",
                        "target": "DIY",
                        "confidence": 0.95,
                    }
                ),
            ),
            patch(
                "services.kitty.routing.command_router.apply_kitty_legacy_diagram_command",
                bus_mock,
            ),
            patch(
                "services.kitty.routing.command_router.try_sync_voice_diagram_to_hub",
                hub_sync_mock,
            ),
            patch(
                "services.kitty.routing.command_router.emit_auto_complete_branch",
                new=AsyncMock(),
            ) as emit_branch_mock,
            patch(
                "services.kitty.routing.command_router.emit_user_ack",
                ack_mock,
            ),
            patch(
                "services.kitty.routing.command_router.maybe_start_background_branch_autocomplete",
                branch_ac_mock,
            ),
            patch(
                "services.kitty.routing.command_router.redis_user_cache.get_by_id",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await route_voice_command(
                ws,
                vid,
                "增加一个DIY分支",
                dict(voice_sessions[vid]["context"]),
                is_text_message=True,
                from_voice=False,
            )

        assert result.outcome == RouteOutcome.EXECUTED
        assert result.action == "add_node"
        bus_mock.assert_awaited_once()
        assert bus_mock.await_args is not None
        call_kwargs = bus_mock.await_args.kwargs
        assert call_kwargs["verify_required"] is True
        assert call_kwargs["scope"] == "scope-os-add"
        hub_sync_mock.assert_not_awaited()
        branch_ac_mock.assert_awaited_once()
        assert branch_ac_mock.await_args is not None
        assert branch_ac_mock.await_args.kwargs.get("node_id") == "branch-r-1-0"
        emit_branch_mock.assert_not_awaited()
        assert "auto_complete_branch" in call_order
        assert "bus" in call_order
        assert call_order.index("bus") < call_order.index("auto_complete_branch")
        assert voice_sessions[vid].get("pending_branch_autocomplete") is None
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_one_sentence_update_node_routes_through_verified_bus() -> None:
    """Edit-phase update_node uses verified Bus path."""
    ws = MagicMock()
    vid = create_voice_session(user_id="2", diagram_session_id="scope-os-upd", diagram_type="mindmap")
    voice_sessions[vid]["context"] = _mindmap_edit_context()
    bus_mock = AsyncMock(return_value=_applied_bus_result(3))

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
                "services.kitty.routing.command_router.parse_one_sentence_edit_intent",
                new=AsyncMock(
                    return_value={
                        "action": "update_node",
                        "node_identifier": "分支1",
                        "target": "改装",
                        "confidence": 0.92,
                    }
                ),
            ),
            patch(
                "services.kitty.routing.command_router.apply_kitty_legacy_diagram_command",
                bus_mock,
            ),
            patch(
                "services.kitty.routing.command_router.emit_user_ack",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "services.kitty.routing.command_router.redis_user_cache.get_by_id",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await route_voice_command(
                ws,
                vid,
                "把分支1改成改装",
                dict(voice_sessions[vid]["context"]),
                is_text_message=True,
                from_voice=False,
            )

        assert result.outcome == RouteOutcome.EXECUTED
        assert result.action == "update_node"
        assert bus_mock.await_args is not None
        assert bus_mock.await_args.kwargs["verify_required"] is True
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_one_sentence_update_center_then_auto_complete_follow_up() -> None:
    """Compound intent updates topic first, then fires auto_complete with topic."""
    ws = MagicMock()
    vid = create_voice_session(
        user_id="2b",
        diagram_session_id="scope-os-center-ac",
        diagram_type="mindmap",
    )
    voice_sessions[vid]["context"] = _mindmap_edit_context()
    call_order: list[str] = []

    async def _bus_side_effect(*_args, **_kwargs):
        call_order.append("bus")
        return _applied_bus_result(4)

    async def _send_side_effect(_ws, message, *_args, **_kwargs):
        if isinstance(message, dict) and message.get("action") == "auto_complete":
            call_order.append("auto_complete")
        return True

    bus_mock = AsyncMock(side_effect=_bus_side_effect)
    send_mock = AsyncMock(side_effect=_send_side_effect)
    fanout_mock = AsyncMock()

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
                "services.kitty.routing.command_router.parse_one_sentence_edit_intent",
                new=AsyncMock(
                    return_value={
                        "action": "update_center",
                        "target": "小学新课标",
                        "confidence": 0.95,
                        "follow_up_actions": [
                            {"action": "auto_complete", "confidence": 0.95},
                        ],
                    }
                ),
            ),
            patch(
                "services.kitty.routing.command_router.apply_kitty_legacy_diagram_command",
                bus_mock,
            ),
            patch(
                "services.kitty.routing.command_router.safe_websocket_send",
                send_mock,
            ),
            patch(
                "services.kitty.routing.command_router.fanout_voice_command_from_session",
                fanout_mock,
            ),
            patch(
                "services.kitty.routing.command_router.emit_user_ack",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "services.kitty.routing.command_router.redis_user_cache.get_by_id",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await route_voice_command(
                ws,
                vid,
                "主题改成小学新课标，并自动补完",
                dict(voice_sessions[vid]["context"]),
                is_text_message=True,
                from_voice=False,
            )

        assert result.outcome == RouteOutcome.EXECUTED
        assert result.action == "update_center"
        bus_mock.assert_awaited_once()
        fanout_mock.assert_awaited()
        auto_sends = [
            call
            for call in send_mock.await_args_list
            if len(call.args) >= 2 and isinstance(call.args[1], dict) and call.args[1].get("action") == "auto_complete"
        ]
        assert auto_sends, "expected auto_complete websocket action"
        auto_msg = auto_sends[0].args[1]
        assert auto_msg.get("params", {}).get("topic") == "小学新课标"
        assert "auto_complete" in call_order
        assert "bus" in call_order
        # Topic mutation must finish before whole-map fill (avoids stale_revision).
        assert call_order.index("bus") < call_order.index("auto_complete")
        assert fanout_mock.await_args is not None
        fanout_kwargs = fanout_mock.await_args.kwargs
        assert fanout_kwargs.get("params", {}).get("topic") == "小学新课标"
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_one_sentence_delete_node_routes_through_verified_bus() -> None:
    """Edit-phase delete_node uses verified Bus path."""
    ws = MagicMock()
    vid = create_voice_session(user_id="3", diagram_session_id="scope-os-del", diagram_type="mind_map")
    voice_sessions[vid]["context"] = _mindmap_edit_context()
    bus_mock = AsyncMock(return_value=_applied_bus_result())

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
                "services.kitty.routing.command_router.parse_one_sentence_edit_intent",
                new=AsyncMock(
                    return_value={
                        "action": "delete_node",
                        "node_identifier": "DIY",
                        "confidence": 0.9,
                    }
                ),
            ),
            patch(
                "services.kitty.routing.command_router.apply_kitty_legacy_diagram_command",
                bus_mock,
            ),
            patch(
                "services.kitty.routing.command_router.emit_user_ack",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "services.kitty.routing.command_router.redis_user_cache.get_by_id",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await route_voice_command(
                ws,
                vid,
                "删除DIY分支",
                dict(voice_sessions[vid]["context"]),
                is_text_message=True,
                from_voice=False,
            )

        assert result.outcome == RouteOutcome.EXECUTED
        assert result.action == "delete_node"
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_one_sentence_action_none_fails_not_conversational() -> None:
    """Edit mode action:none returns FAILED — never conversational fallback."""
    ws = MagicMock()
    vid = create_voice_session(user_id="4", diagram_session_id="scope-os-none", diagram_type="mind_map")
    voice_sessions[vid]["context"] = _mindmap_edit_context()
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
                "services.kitty.routing.command_router.parse_one_sentence_edit_intent",
                new=AsyncMock(return_value={"action": "none", "confidence": 0.0}),
            ),
            patch(
                "services.kitty.routing.command_router.apply_kitty_legacy_diagram_command",
                new=AsyncMock(),
            ) as bus_mock,
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
                "你觉得怎么样",
                dict(voice_sessions[vid]["context"]),
                is_text_message=True,
                from_voice=False,
            )

        assert result.outcome == RouteOutcome.FAILED
        assert result.reason == "edit_not_parsed"
        bus_mock.assert_not_awaited()
        ack_mock.assert_awaited_once()
        ack_kwargs = mock_await_kwargs(ack_mock)
        assert ack_kwargs.get("one_sentence_outcome") == "failed"
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_one_sentence_client_reported_failure_skips_duplicate_ack() -> None:
    """hub_persist_failed is already shown by FE — BE must not emit a second text_chunk."""
    ws = MagicMock()
    vid = create_voice_session(user_id="5", diagram_session_id="scope-os-fail", diagram_type="mind_map")
    voice_sessions[vid]["context"] = _mindmap_edit_context()
    fail_result = DiagramCommandResult(
        tool_result=ToolResult(
            status="failed",
            mutation_id="fail-mut",
            error_code="hub_persist_failed",
        ),
        hub_revision=1,
    )
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
                "services.kitty.routing.command_router.parse_one_sentence_edit_intent",
                new=AsyncMock(
                    return_value={
                        "action": "add_node",
                        "target": "DIY",
                        "confidence": 0.95,
                    }
                ),
            ),
            patch(
                "services.kitty.routing.command_router.apply_kitty_legacy_diagram_command",
                new=AsyncMock(return_value=fail_result),
            ),
            patch(
                "services.kitty.routing.command_router.emit_auto_complete_branch",
                new=AsyncMock(),
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
                "增加一个DIY分支",
                dict(voice_sessions[vid]["context"]),
                is_text_message=True,
                from_voice=False,
            )

        assert result.outcome == RouteOutcome.FAILED
        assert result.reason == "hub_persist_failed"
        # Progress ack may fire before Bus; do not emit a second failure ack.
        outcomes = [call.kwargs.get("one_sentence_outcome") for call in ack_mock.await_args_list]
        assert "failed" not in outcomes
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_one_sentence_ack_timeout_emits_diagram_failure_ack() -> None:
    """Server-side ack_timeout still emits execute_failed (FE may not have messaged)."""
    ws = MagicMock()
    vid = create_voice_session(user_id="55", diagram_session_id="scope-os-timeout", diagram_type="mind_map")
    voice_sessions[vid]["context"] = _mindmap_edit_context()
    fail_result = DiagramCommandResult(
        tool_result=ToolResult(
            status="failed",
            mutation_id="timeout-mut",
            error_code="ack_timeout",
        ),
        hub_revision=1,
    )
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
                "services.kitty.routing.command_router.parse_one_sentence_edit_intent",
                new=AsyncMock(
                    return_value={
                        "action": "add_node",
                        "target": "DIY",
                        "confidence": 0.95,
                    }
                ),
            ),
            patch(
                "services.kitty.routing.command_router.apply_kitty_legacy_diagram_command",
                new=AsyncMock(return_value=fail_result),
            ),
            patch(
                "services.kitty.routing.command_router.emit_auto_complete_branch",
                new=AsyncMock(),
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
                "增加一个DIY分支",
                dict(voice_sessions[vid]["context"]),
                is_text_message=True,
                from_voice=False,
            )

        assert result.outcome == RouteOutcome.FAILED
        assert result.reason == "ack_timeout"
        ack_kwargs = mock_await_kwargs(ack_mock)
        assert ack_kwargs.get("one_sentence_outcome") == "failed"
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_executor_applied_only_with_hub_persist_ok() -> None:
    """Combined ack with hub_persist_ok yields applied ToolResult."""
    reset_pending_state_for_tests()
    ws = MagicMock()
    vid = "voice-combined-ok"
    voice_sessions[vid] = {
        "user_id": "1",
        "diagram_session_id": "scope-combined",
        "diagram_type": "mindmap",
        "_hub_scope_revision": 4,
        "context": _mindmap_edit_context(),
    }
    mutation_holder: list[str] = []

    async def fake_dispatch(*_args, **_kwargs) -> bool:
        return True

    def capture_register(mid: str, *_args, **_kwargs):
        mutation_holder.append(mid)
        return register_pending(mid, vid)

    try:
        with (
            patch("services.diagram_edit.executor._ensure_handlers"),
            patch("services.diagram_edit.executor.dispatch_tool", side_effect=fake_dispatch),
            patch(
                "services.kitty.infra.scope.kitty_scope_access.user_may_access_kitty_scope",
                new=AsyncMock(return_value=True),
            ),
            patch("services.diagram_edit.executor.register_pending", side_effect=capture_register),
        ):
            exec_task = asyncio.create_task(
                execute_diagram_edit_from_legacy(
                    ws,
                    vid,
                    {"action": "add_node", "target": "DIY", "confidence": 0.95},
                    dict(voice_sessions[vid]["context"]),
                    scope="scope-combined",
                    diagram_type="mindmap",
                    user_id=1,
                    ack_timeout_sec=1.0,
                    require_hub_persist=True,
                )
            )
            for _ in range(50):
                if mutation_holder:
                    break
                await asyncio.sleep(0.01)
            assert mutation_holder
            complete_mutation_ack_from_client(
                {
                    "mutation_id": mutation_holder[0],
                    "verified": True,
                    "hub_persist_ok": True,
                    "hub_revision": 5,
                    "evidence": {
                        "nodes": [
                            {"id": "topic", "type": "topic", "text": "Cars"},
                            {"id": "branch-r-1-0", "text": "DIY"},
                        ],
                        "connections": [{"source": "topic", "target": "branch-r-1-0"}],
                    },
                }
            )
            result = await exec_task

        assert result.status == "applied"
        assert result.revision == 5
        assert voice_sessions[vid]["_hub_scope_revision"] == 5
    finally:
        voice_sessions.pop(vid, None)
        reset_pending_state_for_tests()


def test_verified_edit_extras_pending_detects_mutation_id() -> None:
    """verified_edit_extras_pending is true only for non-blank mutation_id."""
    vid = create_voice_session(user_id="91", diagram_session_id="scope-v", diagram_type="mindmap")
    try:
        assert verified_edit_extras_pending(vid) is False
        voice_sessions[vid][OUTBOUND_EXTRAS_KEY] = {"mutation_id": "mut-1"}
        assert verified_edit_extras_pending(vid) is True
        voice_sessions[vid][OUTBOUND_EXTRAS_KEY] = {"mutation_id": "  "}
        assert verified_edit_extras_pending(vid) is False
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_execute_diagram_update_skips_hub_sync_when_verified_extras() -> None:
    """Verified mutation_id extras must skip server try_sync (Pinia client owns Hub)."""
    ws = MagicMock()
    vid = create_voice_session(user_id="92", diagram_session_id="scope-skip", diagram_type="mindmap")
    voice_sessions[vid]["context"] = {
        "diagram_data": {"center": {"text": "Cars"}, "children": []},
    }
    voice_sessions[vid][OUTBOUND_EXTRAS_KEY] = {
        "mutation_id": "mut-verified",
        "expected_effect": {"op": "add_branch", "text": "DIY"},
    }
    hub_sync = AsyncMock()

    try:
        with (
            patch(
                "services.kitty.diagram.diagram_execute.voice_apply_add_node_action",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "services.kitty.diagram.diagram_execute.emit_diagram_mutated",
                new=AsyncMock(),
            ),
            patch(
                "services.kitty.diagram.diagram_execute.try_sync_voice_diagram_to_hub",
                hub_sync,
            ),
            patch(
                "services.kitty.diagram.diagram_execute.sync_diagram_data_to_spec_shape",
            ),
        ):
            ok = await execute_diagram_update(
                ws,
                vid,
                "add_node",
                {"action": "add_node", "target": "DIY"},
                voice_sessions[vid]["context"],
            )
        assert ok is True
        hub_sync.assert_not_awaited()
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_execute_diagram_update_hub_syncs_legacy_without_extras() -> None:
    """Legacy path without mutation_id extras still server-syncs Hub."""
    ws = MagicMock()
    vid = create_voice_session(user_id="93", diagram_session_id="scope-legacy", diagram_type="circle_map")
    voice_sessions[vid]["context"] = {
        "diagram_data": {"center": {"text": "Topic"}, "children": []},
    }
    hub_sync = AsyncMock()

    try:
        with (
            patch(
                "services.kitty.diagram.diagram_execute.voice_apply_add_node_action",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "services.kitty.diagram.diagram_execute.emit_diagram_mutated",
                new=AsyncMock(),
            ),
            patch(
                "services.kitty.diagram.diagram_execute.try_sync_voice_diagram_to_hub",
                hub_sync,
            ),
            patch(
                "services.kitty.diagram.diagram_execute.sync_diagram_data_to_spec_shape",
            ),
        ):
            ok = await execute_diagram_update(
                ws,
                vid,
                "add_node",
                {"action": "add_node", "target": "Node"},
                voice_sessions[vid]["context"],
            )
        assert ok is True
        hub_sync.assert_awaited_once_with(vid)
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_one_sentence_clarify_options_emits_numbered_ack() -> None:
    """Edit-phase clarify_options emits numbered options and arms pending pick."""
    ws = MagicMock()
    vid = create_voice_session(user_id="1", diagram_session_id="scope-os-clarify", diagram_type="mind_map")
    voice_sessions[vid]["context"] = _mindmap_edit_context()
    ack_mock = AsyncMock(return_value=True)

    clarify_cmd = {
        "action": "clarify_options",
        "confidence": 0.85,
        "question": "你是想：",
        "options": ["补全「中国」分支", "新增「中国」分支"],
        "option_commands": [
            {"action": "auto_complete_branch", "target": "中国"},
            {"action": "add_node", "target": "中国"},
        ],
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
                "services.kitty.routing.command_router.parse_one_sentence_edit_intent",
                new=AsyncMock(return_value=clarify_cmd),
            ),
            patch(
                "services.kitty.routing.command_router.emit_user_ack",
                ack_mock,
            ),
        ):
            result = await route_voice_command(
                ws,
                vid,
                "中国",
                dict(voice_sessions[vid]["context"]),
                is_text_message=True,
                from_voice=False,
            )

        assert result.outcome == RouteOutcome.EXECUTED
        assert result.action == "clarify_options"
        ack_mock.assert_awaited_once()
        ack_text = mock_await_args(ack_mock)[2]
        assert "1)" in ack_text
        assert "2)" in ack_text
        assert voice_sessions[vid].get("pending_clarify_options") is not None
    finally:
        voice_sessions.pop(vid, None)
