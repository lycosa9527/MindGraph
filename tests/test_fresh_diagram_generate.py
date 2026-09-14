"""Kitty fresh-diagram auto_complete command resolution."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.agent_loop.fresh_diagram_generate import (
    is_fresh_diagram,
    resolve_fresh_diagram_commands,
)
from services.kitty.agent_loop.loop import run_typed_agent_loop
from services.kitty.routing.outcomes import RouteOutcome
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from tests.typing_helpers import mock_await_args


def _fresh_context(*, phase: str = "create") -> dict:
    return {
        "one_sentence_phase": phase,
        "diagram_type": "mind_map",
        "diagram_data": {
            "center": {"text": "中心主题"},
            "children": [],
            "nodes": [{"id": "topic", "type": "topic", "text": "中心主题"}],
        },
    }


def _filled_context() -> dict:
    return {
        "one_sentence_phase": "edit",
        "diagram_type": "mind_map",
        "diagram_data": {
            "center": {"text": "Cars"},
            "children": [{"text": "历史"}],
            "nodes": [
                {"id": "topic", "type": "topic", "text": "Cars"},
                {"id": "uid-hist", "text": "历史"},
            ],
        },
    }


def test_is_fresh_when_create_or_no_branches() -> None:
    """Create phase and empty children count as fresh."""
    assert is_fresh_diagram(_fresh_context()) is True
    assert is_fresh_diagram({"diagram_data": {}}) is True
    assert is_fresh_diagram(_filled_context()) is False


def test_fresh_photosynthesis_dispatches_level_and_autocomplete() -> None:
    """小学水平 + topic on a new map becomes set_content_level then auto_complete."""
    commands = resolve_fresh_diagram_commands(
        "画一个小学水平的光合作用思维导图",
        _fresh_context(),
        "zh",
    )
    assert commands is not None
    assert commands[0]["action"] == "set_content_level"
    assert commands[0]["level"] == "primary"
    assert commands[1]["action"] == "auto_complete"
    assert commands[1]["topic"] == "光合作用"
    assert "is_learning_sheet" not in commands[1]


def test_fresh_learning_sheet_marks_autocomplete() -> None:
    """半成品 is stripped from the topic and forwarded as a command flag."""
    commands = resolve_fresh_diagram_commands("茶叶半成品", _fresh_context(), "zh")
    assert commands is not None
    assert len(commands) == 1
    assert commands[0]["action"] == "auto_complete"
    assert commands[0]["topic"] == "茶叶"
    assert commands[0]["is_learning_sheet"] is True


def test_fresh_explain_does_not_autocomplete() -> None:
    """Explain stays on the edit/explain path."""
    assert resolve_fresh_diagram_commands("解释这个节点", _fresh_context(), "zh") is None


def test_filled_map_does_not_full_regenerate() -> None:
    """A map with branches does not full-map auto_complete from a generate sentence."""
    assert (
        resolve_fresh_diagram_commands(
            "画一个小学水平的光合作用思维导图",
            _filled_context(),
            "zh",
        )
        is None
    )


def test_preference_only_on_fresh_map_skips_generate() -> None:
    """专业内容改成小学 without a topic does not auto_complete."""
    assert resolve_fresh_diagram_commands("专业内容改成小学", _fresh_context(), "zh") is None


@pytest.mark.asyncio
async def test_loop_fresh_map_auto_completes_with_topic() -> None:
    """Fresh create-phase loop dispatches auto_complete with the extracted topic."""
    context = _fresh_context()
    context["interaction_language"] = "zh"
    ws = MagicMock()
    vid = create_voice_session(
        user_id="1",
        diagram_session_id="scope-fresh-ac",
        diagram_type="mind_map",
    )
    voice_sessions[vid]["context"] = context
    chat_mock = AsyncMock()
    ac_sent = AsyncMock(return_value=True)
    pref_sent = AsyncMock(return_value=True)
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", chat_mock),
            patch("services.kitty.agent_loop.tools.send_kitty_ws_action", ac_sent),
            patch("services.kitty.agent_loop.preference_tools.send_kitty_ws_action", pref_sent),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.preference_tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch(
                "services.kitty.agent_loop.tools.fanout_voice_command_from_session",
                new=AsyncMock(),
            ),
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
            result = await run_typed_agent_loop(
                ws,
                vid,
                "画一个小学水平的光合作用思维导图",
                dict(context),
            )
        assert result.outcome == RouteOutcome.EXECUTED
        assert result.reason == "fresh_diagram"
        assert result.action == "auto_complete"
        chat_mock.assert_not_awaited()
        assert pref_sent.await_count == 1
        assert ac_sent.await_count == 1
        ac_payload = mock_await_args(ac_sent)[2]
        assert ac_payload["params"]["topic"] == "光合作用"
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("utterance", "topic", "sheet"),
    (
        ("比较猫和狗", "比较猫和狗", False),
        ("茶叶半成品", "茶叶", True),
    ),
)
async def test_loop_fresh_plain_topic_is_not_blocked_by_grounding(
    utterance: str,
    topic: str,
    sheet: bool,
) -> None:
    """A generate sentence without 思维导图 still auto_completes on a blank map."""
    context = _fresh_context()
    context["interaction_language"] = "zh"
    ws = MagicMock()
    vid = create_voice_session(
        user_id="1",
        diagram_session_id=f"scope-fresh-{topic}",
        diagram_type="mind_map",
    )
    voice_sessions[vid]["context"] = context
    ac_sent = AsyncMock(return_value=True)
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", new=AsyncMock()),
            patch("services.kitty.agent_loop.tools.send_kitty_ws_action", ac_sent),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.fanout_voice_command_from_session", new=AsyncMock()),
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
            result = await run_typed_agent_loop(ws, vid, utterance, dict(context))
        assert result.outcome == RouteOutcome.EXECUTED
        assert result.reason == "fresh_diagram"
        params = mock_await_args(ac_sent)[2]["params"]
        assert params["topic"] == topic
        if sheet:
            assert params.get("is_learning_sheet") is True
    finally:
        voice_sessions.pop(vid, None)
