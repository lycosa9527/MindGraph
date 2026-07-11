"""Tests for Kitty acknowledgment template library and delivery."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.ack.ack_emit import emit_user_ack
from services.kitty.ack.ack_library import (
    render_ack,
    render_ack_for_command,
    render_ack_for_diagram_update,
    render_low_confidence_ack,
)
from services.kitty.ack.ack_phrase_pool import ack_pool_lines
from services.kitty.ack.ack_slots import slots_from_command
from tests.typing_helpers import mock_await_args


def test_render_update_node_progress_zh() -> None:
    """Rename progress ack includes old and new labels."""
    text = render_ack(
        "diagram.update_node.progress",
        {"old_text": "食", "new_text": "小吃"},
        lang="zh",
        variant_index=0,
    )
    assert text == "好的，正在把「食」改为「小吃」…"


def test_render_update_node_progress_rotates_variants() -> None:
    """Progress acks can pick alternate human-like wording."""
    text = render_ack(
        "diagram.update_node.progress",
        {"old_text": "食", "new_text": "小吃"},
        lang="zh",
        variant_index=1,
    )
    assert text == "嗯，把「食」改成「小吃」…"
    assert len(ack_pool_lines("diagram.update_node.progress", "zh")) >= 8


def test_render_update_node_done_zh() -> None:
    """Rename done ack uses past tense."""
    text = render_ack(
        "diagram.update_node.done",
        {"old_text": "食", "new_text": "小吃"},
        lang="zh",
        variant_index=0,
    )
    assert text.startswith("已将「食」改为「小吃」。")
    assert "还需要改别的吗" in text


def test_render_ack_for_command_update_node_progress() -> None:
    """Router command maps to progress template."""
    command = {
        "action": "update_node",
        "node_identifier": "食",
        "target": "小吃",
        "confidence": 0.95,
    }
    text = render_ack_for_command(
        "update_node",
        command,
        {},
        lang="zh",
        variant_index=0,
    )
    assert text == "好的，正在把「食」改为「小吃」…"


def test_render_ack_for_command_update_center_done() -> None:
    """Topic update done ack."""
    command = {"action": "update_center", "target": "猫屎咖啡"}
    text = render_ack_for_command(
        "update_center",
        command,
        {},
        lang="zh",
        phase="done",
        variant_index=0,
    )
    assert text == "主题已更新为「猫屎咖啡」。"


def test_render_low_confidence_echo_back() -> None:
    """Low confidence uses echo-back clarify template."""
    command = {
        "action": "update_node",
        "node_identifier": "衣",
        "target": "穿搭",
    }
    text = render_low_confidence_ack(command, lang="zh")
    assert "衣" in text
    assert "穿搭" in text


def test_slots_from_command_extracts_identifiers() -> None:
    """Slot builder captures node_identifier and target."""
    slots = slots_from_command(
        "update_node",
        {"node_identifier": "A", "target": "B"},
        {},
    )
    assert slots["old_text"] == "A"
    assert slots["new_text"] == "B"


def test_slots_from_command_resolves_branch_label() -> None:
    """Branch label is resolved from diagram_data when branch_index is set."""
    session = {
        "diagram_data": {
            "children": [
                {"text": "历史", "children": []},
            ],
        },
    }
    slots = slots_from_command(
        "add_node",
        {"target": "唐朝", "branch_index": 0, "child_index": 1},
        session,
    )
    assert slots["branch_label"] == "历史"
    assert slots["target"] == "唐朝"


def test_render_ack_for_diagram_update_with_command() -> None:
    """WS diagram_update summary uses done-phase template when command present."""
    command = {
        "action": "update_node",
        "node_identifier": "食",
        "target": "小吃",
    }
    text = render_ack_for_diagram_update(
        "update_nodes",
        [{"node_id": "n1", "new_text": "小吃"}],
        lang="zh",
        command=command,
        session_context={},
        variant_index=0,
    )
    assert text.startswith("已将「食」改为「小吃」。")
    assert "还需要改别的吗" in text


def test_render_add_branch_progress_zh() -> None:
    """Mind map branch add uses branch-specific progress ack."""
    command = {"action": "add_node", "target": "历史"}
    session = {
        "diagram_type": "mindmap",
        "conversation_history": [{"role": "user", "content": "添加一个历史分支"}],
    }
    text = render_ack_for_command(
        "add_node",
        command,
        session,
        lang="zh",
        variant_index=0,
    )
    assert text == "好的，正在添加「历史」分支…"


def test_render_ack_empty_slots_clears_placeholders() -> None:
    """Empty slots must not leave literal ``{target}`` in the UI string."""
    text = render_ack("diagram.add_node.progress", {}, lang="zh", variant_index=0)
    assert "{target}" not in text
    assert text == "好的，正在添加「」…"


def test_render_ack_for_command_missing_target_clears_placeholder() -> None:
    """add_node without target still formats progress (no raw braces)."""
    text = render_ack_for_command(
        "add_node",
        {"action": "add_node"},
        {},
        lang="zh",
        variant_index=0,
    )
    assert "{target}" not in text
    assert "正在添加" in text


def test_render_add_branch_done_zh() -> None:
    """Diagram update completion uses branch-specific done ack."""
    command = {"action": "add_node", "target": "历史"}
    session = {
        "diagram_type": "mindmap",
        "conversation_history": [{"role": "user", "content": "添加一个历史分支"}],
    }
    text = render_ack_for_diagram_update(
        "add_nodes",
        [{"text": "历史"}],
        lang="zh",
        command=command,
        session_context=session,
        variant_index=0,
    )
    assert text == "「历史」分支已添加，正在自动补全…"


def test_render_add_child_with_branch_label() -> None:
    """Child add under a named branch uses branch-aware progress ack."""
    command = {"action": "add_node", "target": "唐朝", "branch_index": 0, "child_index": 1}
    session = {
        "diagram_type": "mindmap",
        "diagram_data": {"children": [{"text": "历史", "children": []}]},
        "conversation_history": [{"role": "user", "content": "在历史分支下添加唐朝"}],
    }
    progress = render_ack_for_command(
        "add_node",
        command,
        session,
        lang="zh",
        variant_index=0,
    )
    done = render_ack_for_command(
        "add_node",
        command,
        session,
        lang="zh",
        phase="done",
        variant_index=0,
    )
    assert progress == "好的，正在向「历史」分支添加「唐朝」…"
    assert done == "「唐朝」已添加到「历史」分支。"


def test_render_delete_node_progress_and_done() -> None:
    """Plain delete uses target in progress and done acks."""
    command = {"action": "delete_node", "target": "饮食"}
    progress = render_ack_for_command(
        "delete_node",
        command,
        {},
        lang="zh",
        variant_index=0,
    )
    done = render_ack_for_command(
        "delete_node",
        command,
        {},
        lang="zh",
        phase="done",
        variant_index=0,
    )
    assert progress == "好的，正在删除「饮食」…"
    assert done.startswith("「饮食」已删除。")
    assert "还需要改别的吗" in done


def test_render_delete_branch_progress_and_done() -> None:
    """Mind map branch delete mentions branch in ack."""
    command = {"action": "delete_node", "target": "历史"}
    session = {
        "diagram_type": "mindmap",
        "conversation_history": [{"role": "user", "content": "删除历史分支"}],
    }
    progress = render_ack_for_command(
        "delete_node",
        command,
        session,
        lang="zh",
        variant_index=0,
    )
    done = render_ack_for_command(
        "delete_node",
        command,
        session,
        lang="zh",
        phase="done",
        variant_index=0,
    )
    assert progress == "好的，正在删除「历史」分支…"
    assert done.startswith("「历史」分支已删除。")
    assert "还需要改别的吗" in done


def test_render_delete_child_with_branch_label() -> None:
    """Child delete under a branch uses branch-aware ack."""
    command = {"action": "delete_node", "branch_index": 0, "child_index": 1}
    session = {
        "diagram_type": "mindmap",
        "diagram_data": {"children": [{"text": "历史", "children": [{"text": "唐朝"}]}]},
    }
    progress = render_ack_for_command(
        "delete_node",
        command,
        session,
        lang="zh",
        variant_index=0,
    )
    done = render_ack_for_command(
        "delete_node",
        command,
        session,
        lang="zh",
        phase="done",
        variant_index=0,
    )
    assert progress == "好的，正在删除「历史」分支下的子项…"
    assert done == "「历史」分支下的子项已删除。"


@pytest.mark.asyncio
async def test_emit_user_ack_sends_text_chunk() -> None:
    """emit_user_ack always delivers text_chunk for text clients."""
    ws = MagicMock()
    send_mock = AsyncMock(return_value=True)
    speak_mock = AsyncMock()
    with (
        patch("services.kitty.ack.ack_emit.safe_websocket_send", send_mock),
        patch("services.kitty.ack.ack_emit.speak_kitty_final_reply", speak_mock),
        patch(
            "services.kitty.ack.ack_emit.persist_one_sentence_turn_from_voice_session",
            new=AsyncMock(),
        ),
    ):
        ok = await emit_user_ack(ws, "voice-test-1", "好的，正在处理…")
        await asyncio.sleep(0)
    assert ok is True
    send_mock.assert_awaited_once()
    payload = mock_await_args(send_mock)[1]
    assert payload["type"] == "text_chunk"
    assert payload["text"] == "好的，正在处理…"
    assert payload["reply_kind"] == "final"
    speak_mock.assert_awaited()


@pytest.mark.asyncio
async def test_emit_user_ack_progress_also_speaks() -> None:
    """Progress acks speak in parallel with chat text."""
    ws = MagicMock()
    speak_mock = AsyncMock()
    send_mock = AsyncMock(return_value=True)
    with (
        patch("services.kitty.ack.ack_emit.safe_websocket_send", send_mock),
        patch("services.kitty.ack.ack_emit.speak_kitty_final_reply", speak_mock),
        patch(
            "services.kitty.ack.ack_emit.persist_one_sentence_turn_from_voice_session",
            new=AsyncMock(),
        ),
    ):
        await emit_user_ack(
            ws,
            "voice-test-progress",
            "好的，正在添加「品牌」分支…",
            reply_kind="progress",
        )
        await asyncio.sleep(0)
    speak_mock.assert_awaited_once()
    assert speak_mock.await_args is not None
    assert speak_mock.await_args.args[2] == "好的，正在添加「品牌」分支…"
    progress_payload = mock_await_args(send_mock)[1]
    assert progress_payload["reply_kind"] == "progress"


@pytest.mark.asyncio
async def test_emit_user_ack_includes_clarify_options() -> None:
    """Clarify acks carry structured options for one-sentence choice buttons."""
    ws = MagicMock()
    send_mock = AsyncMock(return_value=True)
    with (
        patch("services.kitty.ack.ack_emit.safe_websocket_send", send_mock),
        patch("services.kitty.ack.ack_emit.speak_kitty_final_reply", new=AsyncMock()),
        patch(
            "services.kitty.ack.ack_emit.persist_one_sentence_turn_from_voice_session",
            new=AsyncMock(),
        ),
    ):
        await emit_user_ack(
            ws,
            "voice-clarify",
            "你是想：\n1) A\n2) B\n请回复序号或选项内容。",
            one_sentence_action="clarify_options",
            clarify_question="你是想：",
            clarify_options=["第一个 地理位置", "第二个 地理位置"],
        )
        await asyncio.sleep(0)
    payload = mock_await_args(send_mock)[1]
    assert payload["clarify_question"] == "你是想："
    assert payload["clarify_options"] == ["第一个 地理位置", "第二个 地理位置"]
    assert payload["action"] == "clarify_options"
