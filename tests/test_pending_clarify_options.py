"""Tests for pending clarify-options pick consumption."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.routing.pending_clarify_options import (
    arm_pending_clarify_options,
    classify_clarify_option_pick,
    get_pending_clarify_options,
    seed_target_from_clarify_command,
    try_consume_pending_clarify_options,
)


def test_classify_clarify_option_pick() -> None:
    """Numbered and ordinal replies map to option index."""
    assert classify_clarify_option_pick("1", 2) == 1
    assert classify_clarify_option_pick("第二个", 2) == 2
    assert classify_clarify_option_pick("好的第一个", 2) == 1
    assert classify_clarify_option_pick("随便聊聊", 2) is None


@pytest.mark.asyncio
async def test_try_consume_pending_clarify_options_returns_command() -> None:
    """Picking an option returns the stored legacy command."""
    session = {}
    command = {
        "action": "clarify_options",
        "options": ["补全「中国」", "新增「中国」"],
        "option_commands": [
            {"action": "auto_complete_branch", "target": "中国"},
            {"action": "add_node", "target": "中国"},
        ],
    }
    assert arm_pending_clarify_options(session, command) is True
    assert get_pending_clarify_options(session) is not None

    websocket = MagicMock()
    with (
        patch(
            "services.kitty.routing.pending_clarify_options.voice_sessions",
            {"voice_test": session},
        ),
        patch(
            "services.kitty.routing.pending_clarify_options.emit_user_ack",
            new=AsyncMock(),
        ),
        patch(
            "services.kitty.routing.pending_clarify_options.get_session_memory",
        ) as mem,
    ):
        mem.return_value.append_action_turn = MagicMock()
        picked = await try_consume_pending_clarify_options(
            websocket,
            "voice_test",
            "1",
            {"language": "zh"},
        )

    assert picked is not None
    assert picked["action"] == "auto_complete_branch"
    assert picked["target"] == "中国"
    assert get_pending_clarify_options(session) is None


def test_arm_backfills_missing_target_from_sibling() -> None:
    """Placement-only options inherit target from sibling option_commands."""
    session: dict = {}
    command = {
        "action": "clarify_options",
        "question": "「罗技」要添加到哪里？",
        "options": ["作为「品牌」的子节点", "作为新的顶级分支"],
        "option_commands": [
            {"action": "add_node", "target": "罗技", "parent_ref": "品牌"},
            {"action": "add_node"},
        ],
    }
    assert arm_pending_clarify_options(session, command) is True
    pending = get_pending_clarify_options(session)
    assert pending is not None
    assert pending.get("seed_target") == "罗技"
    cmds = pending.get("option_commands")
    assert isinstance(cmds, list)
    assert cmds[1]["target"] == "罗技"


def test_seed_target_ignores_placement_label_quotes() -> None:
    """「作为「品牌」的子节点」 must not seed target=品牌 when question/siblings lack it."""
    seed = seed_target_from_clarify_command(
        {
            "question": "",
            "options": ["作为「品牌」的子节点", "作为新的顶级分支"],
            "option_commands": [
                {"action": "add_node"},
                {"action": "add_node"},
            ],
        }
    )
    assert seed == ""


def test_seed_target_from_question_when_options_lack_target() -> None:
    """Question quote is the identity label when option_commands omit target."""
    seed = seed_target_from_clarify_command(
        {
            "question": "「罗技」要添加到哪里？",
            "options": ["作为「品牌」的子节点", "作为新的顶级分支"],
            "option_commands": [
                {"action": "add_node", "parent_ref": "品牌"},
                {"action": "add_node"},
            ],
        }
    )
    assert seed == "罗技"


@pytest.mark.asyncio
async def test_try_consume_backfills_target_on_pick() -> None:
    """Pick of a target-less add_node still returns seed_target."""
    session: dict = {}
    command = {
        "action": "clarify_options",
        "question": "「罗技」要添加到哪里？",
        "options": ["作为「品牌」的子节点", "作为新的顶级分支"],
        "option_commands": [
            {"action": "add_node", "target": "罗技", "parent_ref": "品牌"},
            {"action": "add_node"},
        ],
    }
    assert arm_pending_clarify_options(session, command) is True

    websocket = MagicMock()
    with (
        patch(
            "services.kitty.routing.pending_clarify_options.voice_sessions",
            {"voice_test": session},
        ),
        patch(
            "services.kitty.routing.pending_clarify_options.emit_user_ack",
            new=AsyncMock(),
        ),
        patch(
            "services.kitty.routing.pending_clarify_options.get_session_memory",
        ) as mem,
    ):
        mem.return_value.append_action_turn = MagicMock()
        picked = await try_consume_pending_clarify_options(
            websocket,
            "voice_test",
            "2",
            {"language": "zh"},
        )

    assert picked is not None
    assert picked["action"] == "add_node"
    assert picked["target"] == "罗技"
