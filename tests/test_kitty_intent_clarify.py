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
    restore_pending_intent_slot,
    rewrite_valueless_edit_to_followup,
)
from services.kitty.agent_loop.loop import run_typed_agent_loop
from services.kitty.routing.outcomes import RouteOutcome
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
async def test_restore_pending_intent_slot_from_store() -> None:
    """Reconnect can re-arm a follow-up slot from Redis."""
    session: dict = {"user_id": "4", "diagram_session_id": "scope-slot"}
    with patch(
        "services.kitty.agent_loop.intent_clarify.load_pending_intent_slot_payload",
        new=AsyncMock(return_value={"action": "add_node", "followup": "要添加哪条分支？"}),
    ):
        assert await restore_pending_intent_slot(session) is True
    assert session[PENDING_INTENT_SLOT_KEY]["action"] == "add_node"


def test_rewrite_nameless_add_to_followup() -> None:
    """Clarify pick of add_node without a label asks for the branch name."""
    rewritten = rewrite_valueless_edit_to_followup(
        {"action": "add_node", "confidence": 0.9, "parent_ref": "品牌", "side": "right"},
        lang="zh",
    )
    assert rewritten["action"] == "ask_followup"
    assert rewritten["slot_action"] == "add_node"
    assert rewritten["followup"] == "要添加哪条分支？"
    assert rewritten["parent_ref"] == "品牌"
    assert rewritten["side"] == "right"
    named = rewrite_valueless_edit_to_followup(
        {"action": "add_node", "target": "罗技"},
        lang="zh",
    )
    assert named["action"] == "add_node"
    assert named["target"] == "罗技"
    fill = rewrite_valueless_edit_to_followup({"action": "auto_complete_branch"}, lang="zh")
    assert fill["action"] == "ask_followup"
    assert fill["slot_action"] == "auto_complete_branch"
    delete = rewrite_valueless_edit_to_followup({"action": "delete_node"}, lang="zh")
    assert delete["action"] == "ask_followup"
    assert delete["slot_action"] == "delete_node"


def test_intent_slot_keeps_parent_and_side() -> None:
    """Child-placement follow-up still lands under the chosen parent."""
    session: dict = {}
    assert arm_pending_intent_slot(
        session,
        {"slot_action": "add_node", "parent_ref": "品牌", "side": "left"},
    )
    filled = consume_pending_intent_slot(session, "罗技")
    assert filled == {
        "action": "add_node",
        "confidence": 0.9,
        "target": "罗技",
        "parent_ref": "品牌",
        "side": "left",
    }


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


@pytest.mark.asyncio
async def test_unnamed_add_asks_for_name_without_llm() -> None:
    """「添加一个自定义的分支」 asks for the name instead of a placement quiz."""
    context = _mindmap_context()
    result, vid, chat_mock, bus_mock = await _run_loop(
        "添加一个自定义的分支",
        context=context,
        chat_side_effect=[_text_reply("不应走到模型")],
        bus_side_effect=[],
    )
    try:
        assert result.action == "ask_followup"
        assert result.reason == "heuristic"
        chat_mock.assert_not_awaited()
        bus_mock.assert_not_awaited()
        slot = voice_sessions[vid].get(PENDING_INTENT_SLOT_KEY)
        assert isinstance(slot, dict)
        assert slot.get("action") == "add_node"
    finally:
        voice_sessions.pop(vid, None)


@pytest.mark.asyncio
async def test_clarify_pick_nameless_add_asks_for_name() -> None:
    """Pick of 添加新顶级分支 without a label asks for the branch, then adds it."""
    context = _mindmap_context()
    ws = MagicMock()
    vid = create_voice_session(user_id="1", diagram_session_id="scope-nameless", diagram_type="mind_map")
    voice_sessions[vid]["context"] = context
    voice_sessions[vid]["active_panel"] = "one_sentence"
    voice_sessions[vid]["pending_clarify_options"] = {
        "question": "请告诉我您想添加的具体内容和位置？",
        "options": ["添加新顶级分支", "在现有分支下添加子节点", "补全某个分支的子节点"],
        "option_commands": [
            {"action": "add_node", "confidence": 0.9},
            {"action": "add_node", "confidence": 0.9},
            {"action": "auto_complete_branch", "confidence": 0.9},
        ],
    }
    bus_mock = AsyncMock(return_value=_applied(revision=3, node_id="uid-ship", op="add_node"))
    try:
        with (
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", bus_mock),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch(
                "services.kitty.routing.pending_clarify_options.emit_user_ack",
                new=AsyncMock(return_value=True),
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
            patch(
                "services.kitty.agent_loop.tools.maybe_start_background_branch_autocomplete",
                new=AsyncMock(return_value=True),
            ),
        ):
            picked = await run_typed_agent_loop(ws, vid, "1", dict(context))
            assert picked.action == "ask_followup"
            bus_mock.assert_not_awaited()
            slot = voice_sessions[vid].get(PENDING_INTENT_SLOT_KEY)
            assert isinstance(slot, dict)
            assert slot.get("action") == "add_node"
            applied = await run_typed_agent_loop(ws, vid, "配送", dict(context))
        assert applied.outcome == RouteOutcome.EXECUTED
        assert applied.action == "add_node"
        command = mock_await_args(bus_mock)[2]
        assert command.get("action") == "add_node"
        assert command.get("target") == "配送"
    finally:
        voice_sessions.pop(vid, None)
