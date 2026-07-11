"""Tests for background branch auto-complete after add + legacy yes/no consume."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.routing.pending_branch_autocomplete import (
    PENDING_BRANCH_AUTOCOMPLETE_KEY,
    arm_pending_branch_autocomplete,
    classify_branch_autocomplete_offer_reply,
    clear_pending_branch_autocomplete,
    get_pending_branch_autocomplete,
    maybe_start_background_branch_autocomplete,
    try_consume_pending_branch_autocomplete,
)
from services.kitty.session.runtime_state import voice_sessions


def test_classify_branch_autocomplete_offer_reply() -> None:
    """Classify accept/decline/other replies for branch autocomplete offers."""
    assert classify_branch_autocomplete_offer_reply("好的") == "accept"
    assert classify_branch_autocomplete_offer_reply("需要") == "accept"
    assert classify_branch_autocomplete_offer_reply("yes") == "accept"
    assert classify_branch_autocomplete_offer_reply("不用") == "decline"
    assert classify_branch_autocomplete_offer_reply("no") == "decline"
    assert classify_branch_autocomplete_offer_reply("增加一个历史分支") == "other"


def test_arm_pending_branch_autocomplete_for_mindmap_branch() -> None:
    """Arm pending autocomplete after a top-level mindmap branch add."""
    session: dict = {}
    command = {"action": "add_node", "target": "中国"}
    ctx = {
        "diagram_type": "mindmap",
        "conversation_history": [{"role": "user", "content": "增加一个中国的分支"}],
    }
    assert arm_pending_branch_autocomplete(session, command, ctx) is True
    assert get_pending_branch_autocomplete(session) == {"target": "中国"}


def test_arm_pending_branch_autocomplete_skips_child_add() -> None:
    """Do not arm pending autocomplete for nested child adds."""
    session: dict = {}
    command = {"action": "add_node", "target": "唐朝", "branch_index": 0, "child_index": 1}
    ctx = {
        "diagram_type": "mindmap",
        "conversation_history": [{"role": "user", "content": "在历史分支下添加唐朝"}],
    }
    assert arm_pending_branch_autocomplete(session, command, ctx) is False
    assert get_pending_branch_autocomplete(session) is None


@pytest.mark.asyncio
async def test_maybe_start_background_branch_autocomplete_emits_without_pending() -> None:
    """Background autocomplete emits auto_complete_branch without arming pending."""
    session: dict = {}
    command = {"action": "add_node", "target": "罗技", "node_id": "n-logitech"}
    ctx = {
        "diagram_type": "mindmap",
        "interaction_language": "zh",
        "conversation_history": [{"role": "user", "content": "增加一个罗技分支"}],
    }
    websocket = MagicMock()
    with (
        patch(
            "services.kitty.routing.pending_branch_autocomplete.safe_websocket_send",
            new_callable=AsyncMock,
        ) as send_mock,
        patch(
            "services.kitty.routing.pending_branch_autocomplete.fanout_voice_command_from_session",
            new_callable=AsyncMock,
        ) as fanout_mock,
        patch(
            "services.kitty.routing.pending_branch_autocomplete.emit_user_ack",
            new_callable=AsyncMock,
        ) as ack_mock,
    ):
        started = await maybe_start_background_branch_autocomplete(
            websocket,
            "bg-branch-ac",
            command,
            ctx,
            command_text="增加一个罗技分支",
            node_id="branch-r-1-12",
        )
    assert started is True
    assert get_pending_branch_autocomplete(session) is None
    send_mock.assert_awaited()
    assert send_mock.await_args is not None
    sent = send_mock.await_args.args[1]
    assert sent["action"] == "auto_complete_branch"
    assert sent["params"]["node_label"] == "罗技"
    assert sent["params"]["node_id"] == "branch-r-1-12"
    fanout_mock.assert_awaited()
    ack_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_maybe_start_background_branch_autocomplete_skips_child_add() -> None:
    """Background autocomplete is skipped for nested child adds."""
    command = {"action": "add_node", "target": "唐朝", "branch_index": 0, "child_index": 1}
    ctx = {
        "diagram_type": "mindmap",
        "conversation_history": [{"role": "user", "content": "在历史分支下添加唐朝"}],
    }
    websocket = MagicMock()
    with patch(
        "services.kitty.routing.pending_branch_autocomplete.safe_websocket_send",
        new_callable=AsyncMock,
    ) as send_mock:
        started = await maybe_start_background_branch_autocomplete(
            websocket,
            "bg-branch-skip",
            command,
            ctx,
        )
    assert started is False
    send_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_try_consume_accept_sends_auto_complete_branch_action() -> None:
    """Accepting a pending offer sends auto_complete_branch and progress ack."""
    voice_session_id = "pending-branch-accept"
    voice_sessions[voice_session_id] = {
        PENDING_BRANCH_AUTOCOMPLETE_KEY: {"target": "中国"},
        "context": {"interaction_language": "zh"},
    }
    websocket = MagicMock()
    with (
        patch(
            "services.kitty.routing.pending_branch_autocomplete.safe_websocket_send",
            new_callable=AsyncMock,
        ) as send_mock,
        patch(
            "services.kitty.routing.pending_branch_autocomplete.fanout_voice_command_from_session",
            new_callable=AsyncMock,
        ) as fanout_mock,
        patch(
            "services.kitty.routing.pending_branch_autocomplete.emit_user_ack",
            new_callable=AsyncMock,
        ) as ack_mock,
        patch(
            "services.kitty.routing.pending_branch_autocomplete.get_session_memory",
        ) as memory_mock,
    ):
        memory_mock.return_value = MagicMock()
        action = await try_consume_pending_branch_autocomplete(
            websocket,
            voice_session_id,
            "好的",
            {"interaction_language": "zh"},
        )
    assert action == "auto_complete_branch"
    assert get_pending_branch_autocomplete(voice_sessions[voice_session_id]) is None
    send_mock.assert_awaited()
    assert send_mock.await_args is not None
    sent = send_mock.await_args.args[1]
    assert sent["action"] == "auto_complete_branch"
    assert sent["params"]["node_label"] == "中国"
    fanout_mock.assert_awaited()
    ack_mock.assert_awaited()
    assert ack_mock.await_args is not None
    ack_kwargs = ack_mock.await_args.kwargs
    assert ack_kwargs.get("one_sentence_outcome") == "pending"
    assert ack_kwargs.get("reply_kind") == "progress"
    clear_pending_branch_autocomplete(voice_sessions[voice_session_id])
    voice_sessions.pop(voice_session_id, None)


@pytest.mark.asyncio
async def test_try_consume_decline_clears_without_action() -> None:
    """Declining a pending offer clears state without emitting an action."""
    voice_session_id = "pending-branch-decline"
    voice_sessions[voice_session_id] = {
        PENDING_BRANCH_AUTOCOMPLETE_KEY: {"target": "中国"},
        "context": {"interaction_language": "zh"},
    }
    websocket = MagicMock()
    with (
        patch(
            "services.kitty.routing.pending_branch_autocomplete.safe_websocket_send",
            new_callable=AsyncMock,
        ) as send_mock,
        patch(
            "services.kitty.routing.pending_branch_autocomplete.emit_user_ack",
            new_callable=AsyncMock,
        ) as ack_mock,
        patch(
            "services.kitty.routing.pending_branch_autocomplete.get_session_memory",
        ) as memory_mock,
    ):
        memory_mock.return_value = MagicMock()
        action = await try_consume_pending_branch_autocomplete(
            websocket,
            voice_session_id,
            "不用",
            {"interaction_language": "zh"},
        )
    assert action == "decline_branch_autocomplete"
    assert get_pending_branch_autocomplete(voice_sessions[voice_session_id]) is None
    send_mock.assert_not_awaited()
    ack_mock.assert_awaited()
    voice_sessions.pop(voice_session_id, None)
