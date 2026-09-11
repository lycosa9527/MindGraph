"""Pre-LLM fast path for obvious single-intent structural edits."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.agent_hub.diagram_spine.types import DiagramCommandResult
from services.diagram_edit.convert import legacy_command_to_diagram_edit
from services.diagram_edit.effects import build_expected_effect
from services.diagram_edit.types import ToolResult
from services.kitty.agent_loop.loop import (
    AGENT_LOOP_MODEL,
    _is_fast_structural_command,
    run_typed_agent_loop,
)
from services.kitty.routing.outcomes import RouteOutcome, RouteResult
from services.kitty.routing.one_sentence_edit_heuristics import (
    heuristic_one_sentence_edit_command,
    normalize_edit_label,
)
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


def test_normalize_edit_label_peels_asr_wrappers() -> None:
    """Quoted span is the name; 这个 after it is spoken glue, not a regex special case."""
    assert normalize_edit_label("“新分支测试”这个") == "新分支测试"
    assert normalize_edit_label("“反思与研究能力”") == "反思与研究能力"
    assert normalize_edit_label("教师专业发展量表这个") == "教师专业发展量表"
    assert normalize_edit_label("Mechanism") == "Mechanism"
    assert normalize_edit_label("「食」") == "食"
    assert normalize_edit_label("市场部") == "市场部"


def test_fast_structural_allows_valued_add_without_follow_ups() -> None:
    """Named add/delete/rename without 补全 is the allowlist."""
    add_cmd = heuristic_one_sentence_edit_command("加一个市场部的分支")
    assert add_cmd is not None
    assert _is_fast_structural_command(add_cmd, "加一个市场部的分支") is True
    again = heuristic_one_sentence_edit_command("再加一个市场部的分支")
    assert again is not None
    assert _is_fast_structural_command(again, "再加一个市场部的分支") is True
    fill_cmd = heuristic_one_sentence_edit_command("添加一个市场部的分支并补全")
    if fill_cmd is not None:
        assert _is_fast_structural_command(fill_cmd, "添加一个市场部的分支并补全") is False
    compound = heuristic_one_sentence_edit_command("主题改成运动，再添加一个跑步的分支")
    if compound is not None:
        assert _is_fast_structural_command(compound, "主题改成运动，再添加一个跑步的分支") is False


def test_fast_structural_rename_and_delete_this_branch() -> None:
    """Catalog phrases 把X改成Y / 删除X这个分支 skip the LLM."""
    rename = heuristic_one_sentence_edit_command("把地理区位改成要点提纲")
    assert rename is not None
    assert rename == {
        "action": "update_node",
        "target": "地理区位",
        "new_text": "要点提纲",
        "confidence": 0.92,
    }
    assert _is_fast_structural_command(rename, "把地理区位改成要点提纲") is True
    delete = heuristic_one_sentence_edit_command("删除地理区位这个分支")
    assert delete is not None
    assert delete == {
        "action": "delete_node",
        "target": "地理区位",
        "confidence": 0.92,
    }
    quoted = heuristic_one_sentence_edit_command("删除“反思与研究能力”这个分支。")
    assert quoted == {
        "action": "delete_node",
        "target": "反思与研究能力",
        "confidence": 0.92,
    }
    add_quoted = heuristic_one_sentence_edit_command("添加“新分支测试”这个分支")
    assert add_quoted == {
        "action": "add_node",
        "target": "新分支测试",
        "confidence": 0.92,
    }
    add_then_fill = heuristic_one_sentence_edit_command("添加“教师专业发展量表”这个分支并补完")
    if add_then_fill is not None:
        assert _is_fast_structural_command(add_then_fill, "添加“教师专业发展量表”这个分支并补完") is False
    complete_quoted = heuristic_one_sentence_edit_command("补全“Mechanism”这个分支")
    assert complete_quoted == {
        "action": "auto_complete_branch",
        "target": "Mechanism",
        "confidence": 0.95,
    }
    rename_quoted = heuristic_one_sentence_edit_command("把“Boundary”改成测试名称")
    assert rename_quoted == {
        "action": "update_node",
        "target": "Boundary",
        "new_text": "测试名称",
        "confidence": 0.92,
    }
    assert _is_fast_structural_command(delete, "删除地理区位这个分支") is True
    center = heuristic_one_sentence_edit_command("主题改成茶叶导学")
    assert center is not None
    assert center.get("action") == "update_center"


def test_stacked_jobs_are_not_fast_structural() -> None:
    """改主题并补完 is not a regex plan — the tool loop owns the task list."""
    spoken = "把主题改成教师专业发展，并自动补完这幅思维导图。"
    command = heuristic_one_sentence_edit_command(spoken)
    if command is not None:
        assert _is_fast_structural_command(command, spoken) is False
    swallowed = {
        "action": "update_center",
        "target": "教师专业发展，并自动补完这幅思维导图",
        "confidence": 0.92,
    }
    assert _is_fast_structural_command(swallowed, spoken) is False
    assert AGENT_LOOP_MODEL == "qwen3.8-flash"


def test_rename_heuristic_maps_new_text_not_old_target() -> None:
    """把X改成Y must apply Y; target stays the identity (X)."""
    rename = heuristic_one_sentence_edit_command("把地理区位改成要点提纲")
    assert rename is not None
    cmd = legacy_command_to_diagram_edit(
        rename,
        scope="scope-rename",
        diagram_type="mindmap",
    )
    assert cmd is not None
    assert cmd.args.get("node_identifier") == "地理区位"
    assert cmd.args.get("new_text") == "要点提纲"
    effect = build_expected_effect(cmd, {"nodes": [{"id": "n1", "text": "地理区位"}]})
    assert effect.text == "要点提纲"


@pytest.mark.asyncio
async def test_fast_structural_add_skips_llm() -> None:
    """Obvious add_node does not call chat_raw."""
    context = _edit_context()
    ws = MagicMock()
    vid = create_voice_session(
        user_id="1",
        diagram_session_id="scope-fast-add",
        diagram_type="mind_map",
    )
    voice_sessions[vid]["context"] = context
    voice_sessions[vid]["active_panel"] = "one_sentence"
    chat_mock = AsyncMock()
    bus_mock = AsyncMock(
        return_value=DiagramCommandResult(
            tool_result=ToolResult(
                status="applied",
                mutation_id="mut-fast",
                revision=2,
                applied_ops=[{"op": "add_node", "node_id": "uid-mkt", "text": "市场部"}],
            ),
            hub_revision=2,
        )
    )
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", chat_mock),
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", bus_mock),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
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
            patch(
                "services.kitty.agent_loop.loop.fanout_voice_phase_from_session",
                new=AsyncMock(),
            ),
        ):
            result = await run_typed_agent_loop(ws, vid, "加一个市场部的分支", dict(context))
        assert result.outcome == RouteOutcome.EXECUTED
        assert result.reason == "fast_structural"
        assert result.action == "add_node"
        chat_mock.assert_not_awaited()
        bus_mock.assert_awaited_once()
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_fast_preference_skips_llm() -> None:
    """专业内容 / 启用中文编号 stay on fast_preference and never call chat_raw."""
    context = _edit_context()
    ws = MagicMock()
    vid = create_voice_session(
        user_id="1",
        diagram_session_id="scope-fast-pref",
        diagram_type="mind_map",
    )
    voice_sessions[vid]["context"] = context
    voice_sessions[vid]["active_panel"] = "one_sentence"
    chat_mock = AsyncMock()
    ws_mock = AsyncMock(return_value=True)
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", chat_mock),
            patch("services.kitty.agent_loop.preference_tools.send_kitty_ws_action", ws_mock),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.preference_tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch(
                "services.kitty.agent_loop.preference_tools.fanout_voice_command_from_session",
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
            patch(
                "services.kitty.agent_loop.loop.fanout_voice_phase_from_session",
                new=AsyncMock(),
            ),
        ):
            level = await run_typed_agent_loop(ws, vid, "专业内容改成小学", dict(context))
            numbering = await run_typed_agent_loop(ws, vid, "启用中文编号", dict(context))
        assert level.outcome == RouteOutcome.EXECUTED
        assert level.reason == "fast_preference"
        assert level.action == "set_content_level"
        assert numbering.outcome == RouteOutcome.EXECUTED
        assert numbering.reason == "fast_preference"
        assert numbering.action == "set_branch_numbering"
        chat_mock.assert_not_awaited()
        assert ws_mock.await_count == 2
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_fast_preference_ws_failure_does_not_call_llm() -> None:
    """A failed canvas send is FAILED, not a reason to ask Qwen."""
    context = _edit_context()
    ws = MagicMock()
    vid = create_voice_session(
        user_id="1",
        diagram_session_id="scope-fast-pref-fail",
        diagram_type="mind_map",
    )
    voice_sessions[vid]["context"] = context
    voice_sessions[vid]["active_panel"] = "one_sentence"
    chat_mock = AsyncMock()
    ws_mock = AsyncMock(return_value=False)
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", chat_mock),
            patch("services.kitty.agent_loop.preference_tools.send_kitty_ws_action", ws_mock),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.preference_tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch(
                "services.kitty.agent_loop.preference_tools.fanout_voice_command_from_session",
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
            patch(
                "services.kitty.agent_loop.loop.fanout_voice_phase_from_session",
                new=AsyncMock(),
            ),
        ):
            result = await run_typed_agent_loop(ws, vid, "专业内容改成小学", dict(context))
        assert result.outcome == RouteOutcome.FAILED
        assert result.action == "set_content_level"
        chat_mock.assert_not_awaited()
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_stacked_jobs_call_qwen38_flash() -> None:
    """改主题并补完 skips fast_structural and plans tools with qwen3.8-flash."""
    context = _edit_context()
    ws = MagicMock()
    vid = create_voice_session(
        user_id="1",
        diagram_session_id="scope-stacked-agent",
        diagram_type="mind_map",
    )
    voice_sessions[vid]["context"] = context
    voice_sessions[vid]["active_panel"] = "one_sentence"
    chat_mock = AsyncMock(return_value={"content": "好", "tool_calls": []})
    clarify = AsyncMock(
        return_value=RouteResult(outcome=RouteOutcome.EXECUTED, reason="intent_clarify", action="clarify")
    )
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", chat_mock),
            patch("services.kitty.agent_loop.loop._offer_intent_clarify", clarify),
            patch("services.kitty.agent_loop.loop.load_kitty_live_context", new=AsyncMock(return_value=None)),
            patch(
                "services.kitty.agent_loop.loop.throttled_refresh_voice_context_from_library",
                new=AsyncMock(),
            ),
            patch(
                "services.kitty.agent_loop.loop.live_spec_newer_than_library",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "services.kitty.agent_loop.loop.fanout_voice_phase_from_session",
                new=AsyncMock(),
            ),
        ):
            result = await run_typed_agent_loop(
                ws,
                vid,
                "把主题改成教师专业发展，并自动补完这幅思维导图。",
                dict(context),
            )
        assert result.reason != "fast_structural"
        chat_mock.assert_awaited()
        assert chat_mock.await_args is not None
        assert chat_mock.await_args.kwargs["model"] == "qwen3.8-flash"
    finally:
        voice_sessions.pop(vid, None)
