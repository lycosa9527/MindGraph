"""Typed Kitty agent loop: observe-act retry, clarify, identity, step cap."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.agent_hub.diagram_spine.types import DiagramCommandResult
from services.diagram_edit.types import ErrorCode, ToolResult
from services.infrastructure.http.error_handler import ThinkingCoinInsufficientError
from services.kitty.agent_loop.loop import MAX_TOOL_ROUNDS, run_typed_agent_loop
from services.kitty.agent_loop.tools import leftover_live_key
from services.kitty.routing.command_router import RouteOutcome, route_omni_function_call
from services.kitty.routing.one_sentence_edit_helpers import should_use_verified_diagram_edit
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from tests.typing_helpers import mock_await_args, mock_await_kwargs


def _mindmap_context(*, edit: bool = True, leftover_alias: bool = False) -> Dict[str, Any]:
    node: Dict[str, Any] = {"id": "uid-hist", "text": "历史"}
    if leftover_alias:
        node["data"] = {"mindMapLegacyId": "branch-r-1-0"}
    context: Dict[str, Any] = {
        "interaction_language": "zh",
        "diagram_data": {
            "center": {"text": "Cars"},
            "children": [dict(node)],
            "nodes": [
                {"id": "topic", "text": "Cars"},
                dict(node),
            ],
        },
    }
    if edit:
        context["one_sentence_phase"] = "edit"
        context["active_panel"] = "one_sentence"
    return context


def _tool_reply(name: str, arguments: str, call_id: str = "call_1") -> Dict[str, Any]:
    return {
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        ],
    }


def _text_reply(text: str = "好的") -> Dict[str, Any]:
    return {"content": text}


def _applied(*, revision: int, node_id: Optional[str] = None, op: str = "add_node") -> DiagramCommandResult:
    applied_ops = [{"op": op, "node_id": node_id}] if node_id else []
    return DiagramCommandResult(
        tool_result=ToolResult(
            status="applied",
            mutation_id=f"mut-{revision}",
            revision=revision,
            applied_ops=applied_ops,
        ),
        hub_revision=revision,
    )


def _failed(error_code: ErrorCode, *, revision: int = 1) -> DiagramCommandResult:
    return DiagramCommandResult(
        tool_result=ToolResult(
            status="failed",
            mutation_id="mut-fail",
            revision=revision,
            error_code=error_code,
        ),
        hub_revision=revision,
    )


def _messages_at(chat_mock: AsyncMock, index: int) -> List[Dict[str, Any]]:
    call = chat_mock.await_args_list[index]
    messages = call.kwargs.get("messages")
    assert isinstance(messages, list)
    return messages


async def _run_loop(
    text: str,
    *,
    context: Dict[str, Any],
    chat_side_effect: Any,
    bus_side_effect: Any,
    diagram_type: str = "mind_map",
) -> tuple[Any, str, AsyncMock, AsyncMock]:
    ws = MagicMock()
    vid = create_voice_session(user_id="1", diagram_session_id="scope-loop", diagram_type=diagram_type)
    voice_sessions[vid]["context"] = context
    if context.get("active_panel"):
        voice_sessions[vid]["active_panel"] = context.get("active_panel")
    chat_mock = AsyncMock(side_effect=chat_side_effect)
    bus_mock = AsyncMock(side_effect=bus_side_effect)
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", chat_mock),
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", bus_mock),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_auto_complete_branch", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.send_kitty_ws_action", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.loop.load_kitty_live_context", new=AsyncMock(return_value=None)),
            patch(
                "services.kitty.agent_loop.loop.throttled_refresh_voice_context_from_library",
                new=AsyncMock(),
            ),
            patch(
                "services.kitty.agent_loop.loop.live_spec_newer_than_library",
                new=AsyncMock(return_value=True),
            ),
        ):
            result = await run_typed_agent_loop(ws, vid, text, dict(context))
        return result, vid, chat_mock, bus_mock
    except Exception:
        voice_sessions.pop(vid, None)
        raise


@pytest.mark.asyncio
async def test_verify_failed_is_observed_then_retried() -> None:
    """Step 1 verify_failed is a role=tool row; the model retries to applied."""
    context = _mindmap_context()
    result, vid, chat_mock, bus_mock = await _run_loop(
        "把历史改成史记",
        context=context,
        chat_side_effect=[
            _tool_reply("diagram.update_node", '{"node_identifier":"历史","new_text":"史记"}', "call_a"),
            _tool_reply("diagram.update_node", '{"node_identifier":"历史","new_text":"史记"}', "call_b"),
            _text_reply("已改好"),
        ],
        bus_side_effect=[
            _failed("verify_failed", revision=2),
            _applied(revision=3, node_id="uid-hist", op="update_node"),
        ],
    )
    try:
        assert result.outcome == RouteOutcome.EXECUTED
        assert bus_mock.await_count == 2
        assert chat_mock.await_count == 3
        second = _messages_at(chat_mock, 1)
        tool_rows = [row for row in second if row.get("role") == "tool"]
        assert tool_rows
        assert tool_rows[0]["tool_call_id"] == "call_a"
        assert "verify_failed" in tool_rows[0]["content"]
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_clarify_options_stops_without_mutate() -> None:
    """Ambiguous intent stops the loop after clarify_options."""
    context = _mindmap_context()
    clarify_args = json.dumps(
        {
            "question": "你是想：",
            "options": [
                {"label": "补全「历史」", "action": "auto_complete_branch", "target": "历史"},
                {"label": "删除「历史」", "action": "delete_node", "target": "历史"},
            ],
        },
        ensure_ascii=False,
    )
    result, vid, chat_mock, bus_mock = await _run_loop(
        "历史",
        context=context,
        chat_side_effect=[_tool_reply("node_action.clarify_options", clarify_args)],
        bus_side_effect=[],
    )
    try:
        assert result.outcome == RouteOutcome.EXECUTED
        assert result.action == "clarify_options"
        assert chat_mock.await_count == 1
        bus_mock.assert_not_awaited()
        pending = voice_sessions[vid].get("pending_clarify_options")
        assert isinstance(pending, dict)
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_multi_step_includes_first_tool_result_and_revision() -> None:
    """改主题再加分支: second LLM call sees first apply + new revision."""
    context = _mindmap_context()
    result, vid, chat_mock, bus_mock = await _run_loop(
        "改主题再加分支",
        context=context,
        chat_side_effect=[
            _tool_reply("diagram.update_center", '{"new_text":"运动"}', "call_center"),
            _tool_reply("diagram.add_node", '{"text":"跑步"}', "call_add"),
            _text_reply("完成"),
        ],
        bus_side_effect=[
            _applied(revision=2, op="update_center"),
            _applied(revision=3, node_id="uid-run", op="add_node"),
        ],
    )
    try:
        assert result.outcome == RouteOutcome.EXECUTED
        assert bus_mock.await_count == 2
        second = _messages_at(chat_mock, 1)
        tool_rows = [row for row in second if row.get("role") == "tool"]
        assert tool_rows
        assert '"revision": 2' in tool_rows[0]["content"]
        assert '"status": "applied"' in tool_rows[0]["content"]
        add_cmd = bus_mock.await_args_list[1].args[2]
        assert add_cmd["action"] == "add_node"
        assert add_cmd.get("target") == "跑步"
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_general_typed_delete_uses_verified_bus() -> None:
    """General typed mindmap delete_node uses Bus without one-sentence panel."""
    context = _mindmap_context(edit=False)
    result, vid, chat_mock, bus_mock = await _run_loop(
        "删除历史",
        context=context,
        chat_side_effect=[
            _tool_reply("diagram.delete_node", '{"node_identifier":"历史"}', "call_del"),
            _text_reply("已删除"),
        ],
        bus_side_effect=[_applied(revision=6, node_id="uid-hist", op="delete_node")],
    )
    try:
        assert result.outcome == RouteOutcome.EXECUTED
        assert result.action == "delete_node"
        assert chat_mock.await_count == 2
        kwargs = mock_await_kwargs(bus_mock)
        assert kwargs["verify_required"] is True
        command = mock_await_args(bus_mock)[2]
        assert command.get("node_id") == "uid-hist"
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_text_without_tools_after_apply_is_ack() -> None:
    """Text with no tools after a successful apply ends the turn (no done tool)."""
    context = _mindmap_context()
    result, vid, chat_mock, bus_mock = await _run_loop(
        "主题改成茶叶",
        context=context,
        chat_side_effect=[
            _tool_reply("diagram.update_center", '{"new_text":"茶叶"}', "call_c"),
            _text_reply("主题已改成茶叶"),
        ],
        bus_side_effect=[_applied(revision=2, op="update_center")],
    )
    try:
        assert result.outcome == RouteOutcome.EXECUTED
        assert result.reason == "text_stop"
        assert bus_mock.await_count == 1
        assert chat_mock.await_count == 2
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_add_node_next_call_uses_created_node_id() -> None:
    """After add_node applied, the next tool must target created_node_ids."""
    context = _mindmap_context()
    created = "uid-created-branch"
    result, vid, _chat_mock, bus_mock = await _run_loop(
        "加一个历史分支再补全",
        context=context,
        chat_side_effect=[
            _tool_reply("diagram.add_node", '{"text":"历史"}', "call_add"),
            _tool_reply(
                "node_action.auto_complete_branch",
                json.dumps({"node_id": created, "target": "历史"}, ensure_ascii=False),
                "call_ac",
            ),
            _text_reply("好了"),
        ],
        bus_side_effect=[_applied(revision=2, node_id=created, op="add_node")],
    )
    try:
        assert result.outcome == RouteOutcome.EXECUTED
        assert bus_mock.await_count == 1
        first = bus_mock.await_args_list[0].args[2]
        assert first["action"] == "add_node"
        assert first.get("node_id") is None
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_leftover_branch_id_rejected_as_live_key() -> None:
    """update/delete/auto_complete_branch reject leftover branch-* without alias."""
    context = _mindmap_context()
    assert leftover_live_key({"action": "update_node", "node_id": "branch-r-1-0"}, context) == "branch-r-1-0"
    assert leftover_live_key({"action": "delete_node", "node_id": "branch-r-1-0"}, context) == "branch-r-1-0"
    assert leftover_live_key({"action": "auto_complete_branch", "node_id": "branch-r-1-0"}, context) == "branch-r-1-0"

    result, vid, _chat_mock, bus_mock = await _run_loop(
        "改那个节点",
        context=context,
        chat_side_effect=[
            _tool_reply("diagram.update_node", '{"node_identifier":"branch-r-1-0","new_text":"史记"}'),
            _text_reply("需要确认节点"),
        ],
        bus_side_effect=[],
    )
    try:
        bus_mock.assert_not_awaited()
        assert result.outcome in {RouteOutcome.EXECUTED, RouteOutcome.FAILED}
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_leftover_branch_id_allowed_only_as_alias() -> None:
    """Leftover branch-* may resolve through mindMapLegacyId to a UUID."""
    context = _mindmap_context(leftover_alias=True)
    assert leftover_live_key({"action": "update_node", "node_id": "branch-r-1-0"}, context) is None
    result, vid, _chat_mock, bus_mock = await _run_loop(
        "把那个分支改成史记",
        context=context,
        chat_side_effect=[
            _tool_reply("diagram.update_node", '{"node_identifier":"branch-r-1-0","new_text":"史记"}'),
            _text_reply("已改"),
        ],
        bus_side_effect=[_applied(revision=4, node_id="uid-hist", op="update_node")],
    )
    try:
        assert result.outcome == RouteOutcome.EXECUTED
        command = mock_await_args(bus_mock)[2]
        assert command.get("node_id") == "uid-hist"
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_step_cap_stops_after_five_rounds() -> None:
    """Five tool rounds then stop; no sixth LLM call."""
    context = _mindmap_context()
    replies = [
        _tool_reply("diagram.update_center", '{"new_text":"运动"}', f"call_{index}") for index in range(MAX_TOOL_ROUNDS)
    ]
    applies = [_applied(revision=index + 2, op="update_center") for index in range(MAX_TOOL_ROUNDS)]
    result, vid, chat_mock, bus_mock = await _run_loop(
        "改主题",
        context=context,
        chat_side_effect=replies,
        bus_side_effect=applies,
    )
    try:
        assert chat_mock.await_count == MAX_TOOL_ROUNDS
        assert bus_mock.await_count == MAX_TOOL_ROUNDS
        assert result.reason == "step_cap"
        assert result.outcome == RouteOutcome.EXECUTED
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_general_typed_text_without_tools_is_chat() -> None:
    """Outside edit mode, text-without-tools is the conversational reply."""
    context = _mindmap_context(edit=False)
    result, vid, chat_mock, bus_mock = await _run_loop(
        "这张图讲的是什么",
        context=context,
        chat_side_effect=[_text_reply("这是一张关于汽车的思维导图。")],
        bus_side_effect=[],
    )
    try:
        assert result.outcome == RouteOutcome.EXECUTED
        assert result.reason == "text_stop"
        bus_mock.assert_not_awaited()
        assert chat_mock.await_count == 1
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_route_omni_function_call_stays_one_shot() -> None:
    """Retired Omni path does not enter the typed agent loop."""
    ws = MagicMock()
    vid = create_voice_session(user_id="1", diagram_session_id="scope-omni", diagram_type="circle_map")
    context = {"diagram_data": {"children": [], "center": {"text": ""}}}
    voice_sessions[vid]["context"] = context
    try:
        with (
            patch("services.kitty.agent_loop.loop.run_typed_agent_loop", new=AsyncMock()) as loop_mock,
            patch(
                "services.kitty.routing.command_router.safe_websocket_send",
                new=AsyncMock(return_value=True),
            ),
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
                context,
            )
        loop_mock.assert_not_awaited()
        assert result.outcome == RouteOutcome.EXECUTED
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_heuristics_are_last_resort_after_empty_tools() -> None:
    """Edit-mode heuristics run only after the LLM returns no tools."""
    context = _mindmap_context()
    result, vid, chat_mock, bus_mock = await _run_loop(
        "添加一个饮品分析的分支",
        context=context,
        chat_side_effect=[_text_reply("")],
        bus_side_effect=[_applied(revision=2, node_id="uid-drink", op="add_node")],
    )
    try:
        assert chat_mock.await_count == 1
        assert bus_mock.await_count == 1
        assert result.reason == "heuristic"
        assert result.outcome == RouteOutcome.EXECUTED
        command = mock_await_args(bus_mock)[2]
        assert command.get("action") == "add_node"
        assert command.get("target") == "饮品分析"
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_thinking_coins_do_not_run_heuristics() -> None:
    """Budget failure must not pretend the edit applied via regex."""
    context = _mindmap_context()
    result, vid, chat_mock, bus_mock = await _run_loop(
        "添加一个饮品分析的分支",
        context=context,
        chat_side_effect=ThinkingCoinInsufficientError(0, 15),
        bus_side_effect=[],
    )
    try:
        assert result.outcome == RouteOutcome.FAILED
        assert result.reason == "thinking_coins"
        chat_mock.assert_awaited()
        bus_mock.assert_not_awaited()
    finally:
        voice_sessions.pop(vid, None)


def test_verified_edit_is_all_typed_mindmap() -> None:
    """Typed mindmap structural ops use verified Bus even outside one-sentence."""
    context = {"one_sentence_phase": "create"}
    assert should_use_verified_diagram_edit(context, None, "mind_map", is_text_message=True) is True
    assert should_use_verified_diagram_edit(context, None, "mind_map", is_text_message=False) is False
    assert should_use_verified_diagram_edit(context, None, "circle_map", is_text_message=True) is False
