"""Kitty one-sentence 节点解释 (explain_node) catalog and fast path."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.agent_loop.loop import run_typed_agent_loop
from services.kitty.routing.one_sentence_edit_heuristics import (
    heuristic_one_sentence_edit_command,
    is_fast_explain_command,
)
from services.kitty.routing.outcomes import RouteOutcome
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from tests.typing_helpers import mock_await_args


def _edit_context() -> Dict[str, Any]:
    return {
        "interaction_language": "zh",
        "one_sentence_phase": "edit",
        "active_panel": "one_sentence",
        "diagram_type": "mind_map",
        "diagram_data": {
            "center": {"text": "茶叶"},
            "children": [{"id": "uid-cn", "text": "中国"}],
            "nodes": [
                {"id": "topic", "text": "茶叶"},
                {"id": "uid-cn", "text": "中国"},
            ],
        },
    }


def test_heuristic_explain_and_intro_phrases() -> None:
    """解释 / 介绍 / explain map to explain_node with the named branch."""
    explain = heuristic_one_sentence_edit_command("解释一下中国")
    assert explain is not None
    assert explain == {"action": "explain_node", "target": "中国", "confidence": 0.95}
    assert is_fast_explain_command(explain) is True
    intro = heuristic_one_sentence_edit_command("介绍一下中国这个分支")
    assert intro == {"action": "explain_node", "target": "中国", "confidence": 0.95}
    english = heuristic_one_sentence_edit_command("explain China")
    assert english == {"action": "explain_node", "target": "China", "confidence": 0.95}
    deictic = heuristic_one_sentence_edit_command("解释一下这个节点")
    assert deictic == {"action": "explain_node", "confidence": 0.9}
    intro_this = heuristic_one_sentence_edit_command("介绍这个节点")
    assert intro_this == {"action": "explain_node", "confidence": 0.9}
    assert heuristic_one_sentence_edit_command("介绍下这个节点") == {
        "action": "explain_node",
        "confidence": 0.9,
    }
    assert heuristic_one_sentence_edit_command("把这个节点介绍一下") == {
        "action": "explain_node",
        "confidence": 0.9,
    }
    assert heuristic_one_sentence_edit_command("介绍一下这张导图") is None


@pytest.mark.asyncio
async def test_fast_explain_opens_node_explanation() -> None:
    """Named 解释 skips the LLM and sends explain_node to the canvas."""
    context = _edit_context()
    ws = MagicMock()
    vid = create_voice_session(
        user_id="1",
        diagram_session_id="scope-fast-explain",
        diagram_type="mind_map",
    )
    voice_sessions[vid]["context"] = context
    voice_sessions[vid]["active_panel"] = "one_sentence"
    chat_mock = AsyncMock()
    ws_mock = AsyncMock(return_value=True)
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", chat_mock),
            patch("services.kitty.agent_loop.explain_tools.send_kitty_ws_action", ws_mock),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.explain_tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch(
                "services.kitty.agent_loop.explain_tools.fanout_voice_command_from_session",
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
            result = await run_typed_agent_loop(ws, vid, "解释一下中国", dict(context))
        assert result.outcome == RouteOutcome.EXECUTED
        assert result.reason == "fast_explain"
        assert result.action == "explain_node"
        chat_mock.assert_not_awaited()
        ws_mock.assert_awaited_once()
        payload = mock_await_args(ws_mock)[2]
        assert payload.get("action") == "explain_node"
        assert payload.get("params", {}).get("node_id") == "uid-cn"
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_fast_intro_this_node_uses_selection() -> None:
    """介绍这个节点 opens 节点解释 for the current selection."""
    context = _edit_context()
    context["selected_nodes"] = ["uid-cn"]
    diagram = context["diagram_data"]
    assert isinstance(diagram, dict)
    diagram["selected_nodes"] = ["uid-cn"]
    ws = MagicMock()
    vid = create_voice_session(
        user_id="1",
        diagram_session_id="scope-fast-intro-this",
        diagram_type="mind_map",
    )
    voice_sessions[vid]["context"] = context
    voice_sessions[vid]["active_panel"] = "one_sentence"
    chat_mock = AsyncMock()
    ws_mock = AsyncMock(return_value=True)
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", chat_mock),
            patch("services.kitty.agent_loop.explain_tools.send_kitty_ws_action", ws_mock),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.explain_tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch(
                "services.kitty.agent_loop.explain_tools.fanout_voice_command_from_session",
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
            result = await run_typed_agent_loop(ws, vid, "介绍这个节点", dict(context))
        assert result.outcome == RouteOutcome.EXECUTED
        assert result.reason == "fast_explain"
        assert result.action == "explain_node"
        chat_mock.assert_not_awaited()
        payload = mock_await_args(ws_mock)[2]
        assert payload.get("action") == "explain_node"
        assert payload.get("params", {}).get("node_id") == "uid-cn"
    finally:
        voice_sessions.pop(vid, None)
