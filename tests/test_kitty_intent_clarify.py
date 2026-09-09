"""Default Kitty clarify menu and follow-up slots."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.agent_loop.intent_clarify import (
    PENDING_INTENT_SLOT_KEY,
    arm_pending_intent_slot,
    consume_pending_intent_slot,
    default_intent_clarify_command,
    is_intent_slot_cancel,
)
from services.kitty.agent_loop.loop import run_typed_agent_loop
from services.kitty.routing.command_router import RouteOutcome
from services.kitty.routing.pending_clarify_options import classify_clarify_option_pick
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from tests.test_kitty_agent_loop import _applied, _mindmap_context, _run_loop, _text_reply
from tests.typing_helpers import mock_await_args


def test_default_clarify_without_selection() -> None:
    """Greeting-style menu: topic / add branch / auto-complete."""
    command = default_intent_clarify_command(lang="zh", session_context=_mindmap_context())
    assert command["action"] == "clarify_options"
    assert command["question"] == "想怎么改这张图？"
    assert command["options"] == ["改主题", "添加分支", "自动补全这张图"]
    actions = [item["action"] for item in command["option_commands"]]
    assert actions == ["ask_followup", "ask_followup", "auto_complete"]


def test_default_clarify_with_selection() -> None:
    """Selected node gets rename / delete / fill."""
    context = _mindmap_context()
    context["selected_nodes"] = ["uid-hist"]
    command = default_intent_clarify_command(lang="zh", session_context=context)
    assert "历史" in command["question"]
    assert command["options"] == ["改名称", "删除", "补全这个分支"]
    assert command["option_commands"][1]["action"] == "delete_node"
    assert command["option_commands"][1]["node_id"] == "uid-hist"


def test_classify_option_label() -> None:
    """Users can pick by chip text, not only 1/2/3."""
    labels = ["改主题", "添加分支", "自动补全这张图"]
    assert classify_clarify_option_pick("改主题", 3, labels) == 1
    assert classify_clarify_option_pick("添加分支", 3, labels) == 2
    assert classify_clarify_option_pick("随便聊聊", 3, labels) is None


def test_intent_slot_fill_and_cancel() -> None:
    """Next utterance becomes the armed edit; 取消 drops the slot."""
    session: dict = {}
    assert arm_pending_intent_slot(session, {"slot_action": "add_node", "followup": "要添加哪条分支？"})
    filled = consume_pending_intent_slot(session, "配送")
    assert filled == {"action": "add_node", "confidence": 0.9, "target": "配送"}
    assert PENDING_INTENT_SLOT_KEY not in session
    assert is_intent_slot_cancel("算了") is True
    session[PENDING_INTENT_SLOT_KEY] = {"action": "update_center"}
    assert consume_pending_intent_slot(session, "取消") is None
    assert PENDING_INTENT_SLOT_KEY not in session


@pytest.mark.asyncio
async def test_greeting_offers_short_suggestions() -> None:
    """你好 does not fail closed — it asks how to change the map."""
    context = _mindmap_context()
    result, vid, _chat, bus_mock = await _run_loop(
        "你好",
        context=context,
        chat_side_effect=[_text_reply("你好呀")],
        bus_side_effect=[],
    )
    try:
        assert result.outcome == RouteOutcome.EXECUTED
        assert result.reason == "intent_clarify"
        assert result.action == "clarify_options"
        bus_mock.assert_not_awaited()
        pending = voice_sessions[vid].get("pending_clarify_options")
        assert isinstance(pending, dict)
        assert "改主题" in pending.get("options", [])
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_vague_edit_offers_short_suggestions() -> None:
    """把这个改一下 asks for a short next step."""
    context = _mindmap_context()
    result, vid, _chat, bus_mock = await _run_loop(
        "把这个改一下",
        context=context,
        chat_side_effect=[_text_reply("")],
        bus_side_effect=[],
    )
    try:
        assert result.reason == "intent_clarify"
        assert result.action == "clarify_options"
        bus_mock.assert_not_awaited()
        pending = voice_sessions[vid].get("pending_clarify_options")
        assert isinstance(pending, dict)
        assert len(pending.get("options") or []) == 3
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_followup_slot_applies_add_node() -> None:
    """After 添加分支, the next line is the branch name."""
    context = _mindmap_context()
    ws = MagicMock()
    vid = create_voice_session(user_id="1", diagram_session_id="scope-slot", diagram_type="mind_map")
    voice_sessions[vid]["context"] = context
    voice_sessions[vid]["active_panel"] = "one_sentence"
    arm_pending_intent_slot(voice_sessions[vid], {"slot_action": "add_node"})
    bus_mock = AsyncMock(return_value=_applied(revision=3, node_id="uid-ship", op="add_node"))
    try:
        with (
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", bus_mock),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
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
            patch(
                "services.kitty.agent_loop.tools.maybe_start_background_branch_autocomplete",
                new=AsyncMock(return_value=True),
            ),
        ):
            result = await run_typed_agent_loop(ws, vid, "配送", dict(context))
        assert result.outcome == RouteOutcome.EXECUTED
        assert result.action == "add_node"
        command = mock_await_args(bus_mock)[2]
        assert command.get("action") == "add_node"
        assert command.get("target") == "配送"
    finally:
        voice_sessions.pop(vid, None)
