"""Stacked one-sentence edits: one office line, then ordered applies."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.agent_hub.diagram_spine.types import DiagramCommandResult
from services.diagram_edit.types import ToolResult
from services.kitty.agent_loop.compound import parse_compound_turn
from services.kitty.agent_loop.intent_clarify import PENDING_INTENT_SLOT_KEY
from services.kitty.agent_loop.loop import run_typed_agent_loop
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


def test_parse_topic_plus_one_named_add() -> None:
    """Greedy topic regex must not swallow the add clause."""
    plan = parse_compound_turn("主题改成运动，再添加一个跑步的分支")
    assert plan is not None
    assert plan.kind == "named"
    assert [(step["action"], step.get("target")) for step in plan.steps] == [
        ("update_center", "运动"),
        ("add_node", "跑步"),
    ]


def test_parse_topic_plus_two_named_adds() -> None:
    """Topic plus two listed names becomes three named steps."""
    plan = parse_compound_turn("主题改成光合作用，再加光反应、暗反应")
    assert plan is not None
    assert [step.get("target") for step in plan.steps] == ["光合作用", "光反应", "暗反应"]


def test_parse_count_plus_listed_names() -> None:
    """Count plus colon names is treated as a named stack, not placeholders."""
    plan = parse_compound_turn("再加两个分支：要点提纲、课堂练习")
    assert plan is not None
    assert plan.kind == "named"
    assert [step.get("target") for step in plan.steps] == ["要点提纲", "课堂练习"]


def test_parse_delete_then_add() -> None:
    """Delete-then-add and topic-then-删掉 stay ordered named steps."""
    plan = parse_compound_turn("删除历史这个分支，再加一个地理的分支")
    assert plan is not None
    assert [(step["action"], step.get("target")) for step in plan.steps] == [
        ("delete_node", "历史"),
        ("add_node", "地理"),
    ]
    spoken = parse_compound_turn("主题改成茶叶导学，然后删掉历史这个分支")
    assert spoken is not None
    assert [(step["action"], step.get("target")) for step in spoken.steps] == [
        ("update_center", "茶叶导学"),
        ("delete_node", "历史"),
    ]


def test_parse_vague_topic_and_count() -> None:
    """Topic plus unnamed count is vague: center only, placeholders later."""
    plan = parse_compound_turn("主题改成光合作用，再加两个分支")
    assert plan is not None
    assert plan.kind == "vague"
    assert plan.placeholder_count == 2
    assert plan.steps == [
        {"action": "update_center", "target": "光合作用", "confidence": 0.92},
    ]


def test_parse_vague_count_only() -> None:
    """Bare unnamed count is vague with no structural steps yet."""
    plan = parse_compound_turn("再加两个分支")
    assert plan is not None
    assert plan.kind == "vague"
    assert plan.placeholder_count == 2
    assert plan.steps == []


def test_parse_autocomplete_stays_out() -> None:
    """Autocomplete clauses must not be parsed as a compound stack."""
    assert parse_compound_turn("主题改成光合作用，并自动补全") is None
    assert parse_compound_turn("加一个市场部的分支并补全") is None


def test_parse_single_edit_stays_out() -> None:
    """A single edit or count-only add is not a compound turn."""
    assert parse_compound_turn("主题改成茶叶导学") is None
    assert parse_compound_turn("加五个分支") is None


async def _run_compound(
    text: str,
    *,
    bus_side_effect: list,
    acks: list[str],
    context: dict | None = None,
) -> tuple[RouteResult, str, AsyncMock]:
    ctx = context or _edit_context()
    ws = MagicMock()
    vid = create_voice_session(
        user_id="1",
        diagram_session_id="scope-compound",
        diagram_type="mind_map",
    )
    voice_sessions[vid]["context"] = ctx
    voice_sessions[vid]["active_panel"] = "one_sentence"
    chat_mock = AsyncMock()
    bus_mock = AsyncMock(side_effect=bus_side_effect)

    async def capture_ack(_ws, _vid, message, **_kwargs):
        acks.append(message)
        return True

    finished = False
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", chat_mock),
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", bus_mock),
            patch("services.kitty.agent_loop.compound.emit_user_ack", capture_ack),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.interrupt_kitty_tts", new=AsyncMock()),
            patch(
                "services.kitty.agent_loop.tools.maybe_start_background_branch_autocomplete",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "services.kitty.agent_loop.compound.persist_armed_intent_slot",
                new=AsyncMock(),
            ),
            patch(
                "services.kitty.agent_loop.loop.persist_armed_intent_slot",
                new=AsyncMock(),
            ),
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
        ):
            result = await run_typed_agent_loop(ws, vid, text, dict(ctx))
        finished = True
        return result, vid, bus_mock
    finally:
        if not finished:
            voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_named_compound_one_ack_no_llm() -> None:
    """Named stacks speak one done line and apply without calling Qwen."""
    acks: list[str] = []
    result, vid, bus_mock = await _run_compound(
        "主题改成运动，再添加一个跑步的分支",
        bus_side_effect=[
            _applied(revision=2, op="update_center"),
            _applied(revision=3, node_id="uid-run", op="add_node"),
        ],
        acks=acks,
    )
    try:
        assert result.outcome == RouteOutcome.EXECUTED
        assert result.reason == "fast_compound"
        assert bus_mock.await_count == 2
        assert len(acks) == 1
        assert "运动" in acks[0]
        assert "跑步" in acks[0]
        assert "运动，再添加" not in acks[0]
        center = bus_mock.await_args_list[0].args[2]
        assert center.get("target") == "运动"
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_vague_placeholders_then_two_names() -> None:
    """Vague count hangs placeholders and asks for names on the intent slot."""
    acks: list[str] = []
    result, vid, bus_mock = await _run_compound(
        "主题改成光合作用，再加两个分支",
        bus_side_effect=[
            _applied(revision=2, op="update_center"),
            _applied(revision=3, node_id="uid-p1", op="add_node"),
            _applied(revision=4, node_id="uid-p2", op="add_node"),
        ],
        acks=acks,
    )
    try:
        assert result.outcome == RouteOutcome.EXECUTED
        assert result.reason == "fast_compound_vague"
        assert bus_mock.await_count == 3
        assert bus_mock.await_args_list[0].args[2].get("target") == "光合作用"
        assert bus_mock.await_args_list[1].args[2].get("target") == "新分支"
        assert bus_mock.await_args_list[2].args[2].get("target") == "新分支2"
        assert len(acks) == 1
        assert "光合作用" in acks[0]
        assert "叫什么" in acks[0]
        slot = voice_sessions[vid].get(PENDING_INTENT_SLOT_KEY)
        assert isinstance(slot, dict)
        assert slot.get("node_ids") == ["uid-p1", "uid-p2"]
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_vague_slot_looks_up_label_when_apply_omits_id() -> None:
    """Mindmap apply without canvas ack has no node_id; use the live snapshot."""
    context = _edit_context()
    ws = MagicMock()
    vid = create_voice_session(
        user_id="1",
        diagram_session_id="scope-compound-lookup",
        diagram_type="mind_map",
    )
    voice_sessions[vid]["context"] = context
    voice_sessions[vid]["active_panel"] = "one_sentence"
    added = {"新分支": "uid-look-1", "新分支2": "uid-look-2"}

    async def apply_cmd(_ws, voice_id, command, session_context, **_kwargs):
        action = str(command.get("action") or "")
        if action == "add_node":
            label = str(command.get("target") or "")
            node_id = added[label]
            live = voice_sessions[voice_id]["context"]
            diagram = live["diagram_data"]
            row = {"id": node_id, "text": label}
            diagram["children"].append(row)
            diagram["nodes"].append(row)
            session_context["diagram_data"] = diagram
        return DiagramCommandResult(
            tool_result=ToolResult(
                status="applied",
                mutation_id="mut-look",
                revision=2,
                applied_ops=[{"op": action, "text": command.get("target")}],
            ),
            hub_revision=2,
        )

    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", new=AsyncMock()),
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", apply_cmd),
            patch("services.kitty.agent_loop.compound.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.compound.persist_armed_intent_slot", new=AsyncMock()),
            patch(
                "services.kitty.agent_loop.tools.maybe_start_background_branch_autocomplete",
                new=AsyncMock(return_value=False),
            ),
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
        ):
            result = await run_typed_agent_loop(
                ws,
                vid,
                "主题改成光合作用，再加两个分支",
                dict(context),
            )
        assert result.outcome == RouteOutcome.EXECUTED
        slot = voice_sessions[vid].get(PENDING_INTENT_SLOT_KEY)
        assert isinstance(slot, dict)
        assert slot.get("node_ids") == ["uid-look-1", "uid-look-2"]
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
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", new=AsyncMock()),
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", bus_mock),
            patch("services.kitty.agent_loop.compound.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
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
        ):
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
    """A failed mid-chain apply stops later steps and interrupts TTS."""
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
    bus_mock = AsyncMock(
        side_effect=[
            _applied(revision=2, op="update_center"),
            _failed(revision=2),
            _applied(revision=3, node_id="uid-x", op="add_node"),
        ]
    )
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", new=AsyncMock()),
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", bus_mock),
            patch("services.kitty.agent_loop.compound.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.interrupt_kitty_tts", interrupt),
            patch(
                "services.kitty.agent_loop.tools.maybe_start_background_branch_autocomplete",
                new=AsyncMock(return_value=False),
            ),
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
        ):
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
