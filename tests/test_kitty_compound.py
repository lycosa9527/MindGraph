"""Stacked edits go to the tool loop; placeholder rename still applies in order."""

from __future__ import annotations

from contextlib import ExitStack
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.agent_hub.diagram_spine.types import DiagramCommandResult
from services.diagram_edit.types import ToolResult
from services.kitty.agent_loop.compound import take_placeholder_rename_plan
from services.kitty.agent_loop.intent_clarify import PENDING_INTENT_SLOT_KEY
from services.kitty.agent_loop.loop import AGENT_LOOP_MODEL, run_typed_agent_loop
from services.kitty.routing.outcomes import RouteOutcome, RouteResult
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions


def _edit_context() -> dict:
    return {
        "interaction_language": "zh",
        "one_sentence_phase": "edit",
        "active_panel": "one_sentence",
        "diagram_type": "mind_map",
        "diagram_data": {
            "center": {"text": "Cars"},
            "children": [{"id": "uid-hist", "text": "历史"}],
            "nodes": [
                {"id": "topic", "text": "Cars"},
                {"id": "uid-hist", "text": "历史"},
            ],
        },
    }


def _tool_reply(name: str, arguments: str, call_id: str) -> Dict[str, Any]:
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


def _text_reply(text: str = "好") -> Dict[str, Any]:
    return {"content": text}


def _applied(*, revision: int, node_id: str = "", op: str = "add_node") -> DiagramCommandResult:
    applied_ops = [{"op": op, "node_id": node_id}] if node_id else [{"op": op}]
    return DiagramCommandResult(
        tool_result=ToolResult(
            status="applied",
            mutation_id=f"mut-{revision}",
            revision=revision,
            applied_ops=applied_ops,
        ),
        hub_revision=revision,
    )


def _failed(*, revision: int = 1) -> DiagramCommandResult:
    return DiagramCommandResult(
        tool_result=ToolResult(status="failed", mutation_id="", revision=revision, applied_ops=[]),
        hub_revision=revision,
    )


def _loop_patches(
    *,
    chat_mock: AsyncMock,
    bus_mock: AsyncMock,
    interrupt: Optional[AsyncMock] = None,
) -> tuple:
    return (
        patch("services.kitty.agent_loop.loop.llm_service.chat_raw", chat_mock),
        patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", bus_mock),
        patch("services.kitty.agent_loop.compound.emit_user_ack", new=AsyncMock(return_value=True)),
        patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
        patch(
            "services.kitty.agent_loop.tools.interrupt_kitty_tts",
            interrupt if interrupt is not None else AsyncMock(),
        ),
        patch(
            "services.kitty.agent_loop.tools.maybe_start_background_branch_autocomplete",
            new=AsyncMock(return_value=False),
        ),
        patch("services.kitty.agent_loop.loop.persist_armed_intent_slot", new=AsyncMock()),
        patch("services.kitty.agent_loop.loop.clear_pending_intent_slot_async", new=AsyncMock()),
        patch("services.kitty.agent_loop.loop.load_kitty_live_context", new=AsyncMock(return_value=None)),
        patch(
            "services.kitty.agent_loop.loop.throttled_refresh_voice_context_from_library",
            new=AsyncMock(),
        ),
        patch(
            "services.kitty.agent_loop.loop.live_spec_newer_than_library",
            new=AsyncMock(return_value=True),
        ),
        patch("services.kitty.agent_loop.loop.fanout_voice_phase_from_session", new=AsyncMock()),
    )


def test_placeholder_rename_plan_maps_listed_names() -> None:
    """Armed node ids become ordered update_node steps."""
    session = {PENDING_INTENT_SLOT_KEY: {"action": "update_node", "node_ids": ["uid-p1", "uid-p2"]}}
    plan = take_placeholder_rename_plan(session, "光反应、暗反应")
    assert plan is not None
    assert plan.kind == "rename"
    assert [step.get("new_text") for step in plan.steps] == ["光反应", "暗反应"]
    assert PENDING_INTENT_SLOT_KEY not in session


@pytest.mark.asyncio
async def test_stacked_named_jobs_call_qwen38_flash() -> None:
    """改主题再加分支 is planned by qwen3.8-flash, not a regex stack."""
    ctx = _edit_context()
    ws = MagicMock()
    vid = create_voice_session(
        user_id="1",
        diagram_session_id="scope-compound-llm",
        diagram_type="mind_map",
    )
    voice_sessions[vid]["context"] = ctx
    voice_sessions[vid]["active_panel"] = "one_sentence"
    chat_mock = AsyncMock(
        side_effect=[
            _tool_reply("diagram.update_center", '{"new_text":"运动"}', "call_c"),
            _tool_reply("diagram.add_node", '{"text":"跑步"}', "call_a"),
            _text_reply("好"),
        ]
    )
    bus_mock = AsyncMock(
        side_effect=[
            _applied(revision=2, op="update_center"),
            _applied(revision=3, node_id="uid-run", op="add_node"),
        ]
    )
    try:
        with ExitStack() as stack:
            for patcher in _loop_patches(chat_mock=chat_mock, bus_mock=bus_mock):
                stack.enter_context(patcher)
            result = await run_typed_agent_loop(
                ws,
                vid,
                "主题改成运动，再添加一个跑步的分支",
                dict(ctx),
            )
        assert result.outcome == RouteOutcome.EXECUTED
        assert result.reason != "fast_structural"
        assert chat_mock.await_count >= 1
        assert chat_mock.await_args is not None
        assert chat_mock.await_args.kwargs["model"] == AGENT_LOOP_MODEL
        assert bus_mock.await_count == 2
        assert bus_mock.await_args_list[0].args[2].get("target") == "运动"
        assert bus_mock.await_args_list[1].args[2].get("target") == "跑步"
    finally:
        voice_sessions.pop(vid, None)


def _slot_context() -> dict:
    context = _edit_context()
    diagram = context["diagram_data"]
    extra = [
        {"id": "uid-p1", "text": "新分支"},
        {"id": "uid-p2", "text": "新分支2"},
    ]
    diagram["children"] = list(diagram["children"]) + extra
    diagram["nodes"] = list(diagram["nodes"]) + extra
    return context


async def _run_with_slot(text: str, *, bus_side_effect: list) -> tuple[RouteResult, str, AsyncMock]:
    context = _slot_context()
    ws = MagicMock()
    vid = create_voice_session(
        user_id="1",
        diagram_session_id="scope-compound-slot",
        diagram_type="mind_map",
    )
    voice_sessions[vid]["context"] = context
    voice_sessions[vid]["active_panel"] = "one_sentence"
    voice_sessions[vid][PENDING_INTENT_SLOT_KEY] = {
        "action": "update_node",
        "node_ids": ["uid-p1", "uid-p2"],
    }
    bus_mock = AsyncMock(side_effect=bus_side_effect)
    finished = False
    try:
        with ExitStack() as stack:
            for patcher in _loop_patches(chat_mock=AsyncMock(), bus_mock=bus_mock):
                stack.enter_context(patcher)
            result = await run_typed_agent_loop(ws, vid, text, dict(context))
        finished = True
        return result, vid, bus_mock
    finally:
        if not finished:
            voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_placeholder_two_names_renames_both() -> None:
    """Two follow-up names rename both placeholders and clear the slot."""
    result, vid, bus_mock = await _run_with_slot(
        "光反应、暗反应",
        bus_side_effect=[
            _applied(revision=5, node_id="uid-p1", op="update_node"),
            _applied(revision=6, node_id="uid-p2", op="update_node"),
        ],
    )
    try:
        assert result.outcome == RouteOutcome.EXECUTED
        assert result.reason == "slot_rename"
        assert bus_mock.await_count == 2
        assert bus_mock.await_args_list[0].args[2].get("new_text") == "光反应"
        assert bus_mock.await_args_list[1].args[2].get("new_text") == "暗反应"
        assert PENDING_INTENT_SLOT_KEY not in voice_sessions[vid]
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_vague_one_name_keeps_slot() -> None:
    """One follow-up name renames the first placeholder and keeps the rest."""
    result, vid, bus_mock = await _run_with_slot(
        "光反应",
        bus_side_effect=[_applied(revision=5, node_id="uid-p1", op="update_node")],
    )
    try:
        assert result.outcome == RouteOutcome.EXECUTED
        assert bus_mock.await_count == 1
        slot = voice_sessions[vid].get(PENDING_INTENT_SLOT_KEY)
        assert isinstance(slot, dict)
        assert slot.get("node_ids") == ["uid-p2"]
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_mid_chain_fail_stops() -> None:
    """A failed mid-chain apply stops later tools and interrupts TTS."""
    interrupt = AsyncMock()
    ctx = _edit_context()
    ws = MagicMock()
    vid = create_voice_session(
        user_id="1",
        diagram_session_id="scope-compound-fail",
        diagram_type="mind_map",
    )
    voice_sessions[vid]["context"] = ctx
    voice_sessions[vid]["active_panel"] = "one_sentence"
    chat_mock = AsyncMock(
        side_effect=[
            _tool_reply("diagram.update_center", '{"new_text":"光合作用"}', "call_c"),
            _tool_reply("diagram.add_node", '{"text":"光反应"}', "call_a"),
        ]
    )
    bus_mock = AsyncMock(
        side_effect=[
            _applied(revision=2, op="update_center"),
            _failed(revision=2),
            _applied(revision=3, node_id="uid-x", op="add_node"),
        ]
    )
    try:
        with ExitStack() as stack:
            for patcher in _loop_patches(chat_mock=chat_mock, bus_mock=bus_mock, interrupt=interrupt):
                stack.enter_context(patcher)
            result = await run_typed_agent_loop(
                ws,
                vid,
                "主题改成光合作用，再加光反应、暗反应",
                dict(ctx),
            )
        assert result.outcome == RouteOutcome.FAILED
        assert bus_mock.await_count == 2
        interrupt.assert_awaited()
    finally:
        voice_sessions.pop(vid, None)
