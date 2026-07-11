"""Tests for one-sentence edit heuristics and intent parse wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.infrastructure.http.error_handler import LLMTimeoutError
from services.kitty.routing.intent_parser import parse_one_sentence_edit_intent
from services.kitty.routing.node_action_agent import ONE_SENTENCE_EDIT_DASHSCOPE_MODEL
from services.kitty.routing.one_sentence_edit_heuristics import (
    heuristic_one_sentence_edit_command,
)


@pytest.mark.parametrize(
    ("text", "action", "target"),
    [
        ("添加一个饮品分析的分支", "add_node", "饮品分析"),
        ("添加中国茶叶的分支", "add_node", "中国茶叶"),
        ("增加一个DIY分支", "add_node", "DIY"),
        ("添加分支 A.1", "add_node", "A.1"),
        ("添加分支A.1", "add_node", "A.1"),
        ("加一个分支叫历史", "add_node", "历史"),
        ("主题改成茶叶", "update_center", "茶叶"),
        ("change the topic to Specialty Coffee", "update_center", "Specialty Coffee"),
        ("删除饮品分析分支", "delete_node", "饮品分析"),
        ("delete the branch called Brewing Methods", "delete_node", "Brewing Methods"),
        ("add a branch called history", "add_node", "history"),
        ("add a branch A.1", "add_node", "A.1"),
        ("补全中国这个分支", "auto_complete_branch", "中国"),
        ("自动补全中国分支", "auto_complete_branch", "中国"),
        ("把中国分支补全", "auto_complete_branch", "中国"),
        ("complete the China branch", "auto_complete_branch", "China"),
        ("fill in 中国 branch", "auto_complete_branch", "中国"),
    ],
)
def test_heuristic_one_sentence_edit_phrases(text: str, action: str, target: str) -> None:
    """Clear structural phrases map without calling an LLM."""
    cmd = heuristic_one_sentence_edit_command(text)
    assert cmd is not None
    assert cmd["action"] == action
    assert cmd["target"] == target


def test_heuristic_whole_auto_complete() -> None:
    """Bare auto-complete maps to whole-diagram action."""
    cmd = heuristic_one_sentence_edit_command("自动补全")
    assert cmd is not None
    assert cmd["action"] == "auto_complete"
    assert "target" not in cmd


def test_heuristic_rejects_chitchat() -> None:
    """Non-edit chat does not match the heuristic."""
    assert heuristic_one_sentence_edit_command("你觉得怎么样") is None


@pytest.mark.asyncio
async def test_parse_complete_branch_uses_agent_first() -> None:
    """Agent is primary for 补全X分支; heuristic is not used when agent succeeds."""
    agent_cmd = {"action": "auto_complete_branch", "target": "中国", "confidence": 0.95}
    with (
        patch(
            "services.kitty.routing.intent_parser.parse_node_action_intent",
            new=AsyncMock(return_value=agent_cmd),
        ),
        patch(
            "services.kitty.routing.intent_parser.heuristic_one_sentence_edit_command",
        ) as heuristic,
    ):
        cmd = await parse_one_sentence_edit_intent(
            "补全中国这个分支",
            voice_session_id="voice_test",
            diagram_type="mindmap",
        )
    assert cmd["action"] == "auto_complete_branch"
    assert cmd["target"] == "中国"
    heuristic.assert_not_called()


@pytest.mark.asyncio
async def test_parse_one_sentence_edit_heuristic_fallback_on_agent_miss() -> None:
    """Heuristic runs only when the agent returns no tool match."""
    with (
        patch(
            "services.kitty.routing.intent_parser.parse_node_action_intent",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "services.kitty.routing.intent_parser.llm_service.chat_raw",
            new=AsyncMock(),
        ) as chat_raw,
    ):
        cmd = await parse_one_sentence_edit_intent(
            "添加一个饮品分析的分支",
            voice_session_id="voice_test",
            diagram_type="mindmap",
        )
    assert cmd["action"] == "add_node"
    assert cmd["target"] == "饮品分析"
    chat_raw.assert_not_awaited()


@pytest.mark.asyncio
async def test_parse_one_sentence_edit_agent_returns_clarify() -> None:
    """Agent clarify_options passes through without heuristic."""
    clarify = {
        "action": "clarify_options",
        "options": ["A", "B"],
        "option_commands": [{"action": "add_node"}, {"action": "auto_complete_branch"}],
        "confidence": 0.85,
    }
    with patch(
        "services.kitty.routing.intent_parser.parse_node_action_intent",
        new=AsyncMock(return_value=clarify),
    ):
        cmd = await parse_one_sentence_edit_intent(
            "中国",
            voice_session_id="voice_test",
            diagram_type="mindmap",
        )
    assert cmd["action"] == "clarify_options"
    assert len(cmd["options"]) == 2


@pytest.mark.asyncio
async def test_parse_one_sentence_edit_timeout_uses_heuristic() -> None:
    """LLM timeout falls back to regex heuristics for clear phrases."""
    with (
        patch(
            "services.kitty.routing.intent_parser.parse_node_action_intent",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "services.kitty.routing.intent_parser.llm_service.chat_raw",
            new=AsyncMock(side_effect=LLMTimeoutError("timeout")),
        ),
        patch(
            "services.kitty.routing.intent_parser.get_session_memory",
        ) as mem,
    ):
        mem.return_value.summarize_for_parser.return_value = ""
        cmd = await parse_one_sentence_edit_intent(
            "补全中国这个分支",
            voice_session_id="voice_test",
            diagram_type="mindmap",
        )
    assert cmd["action"] == "auto_complete_branch"
    assert cmd["target"] == "中国"


@pytest.mark.asyncio
async def test_parse_one_sentence_edit_timeout_returns_none_for_chitchat() -> None:
    """Agent miss + no heuristic match returns action none (caller acks)."""
    with patch(
        "services.kitty.routing.intent_parser.parse_node_action_intent",
        new=AsyncMock(return_value=None),
    ):
        cmd = await parse_one_sentence_edit_intent(
            "随便聊聊",
            voice_session_id="voice_test",
            diagram_type="mindmap",
        )
    assert cmd["action"] == "none"


def test_one_sentence_edit_dashscope_model_exported() -> None:
    """Intent parser re-exports the node-action DashScope model id."""
    assert ONE_SENTENCE_EDIT_DASHSCOPE_MODEL == "qwen3.6-flash"


def test_heuristic_update_center_then_auto_complete() -> None:
    """Compound 改主题+自动补完 maps to update_center with auto_complete follow-up."""
    cmd = heuristic_one_sentence_edit_command("主题改成小学新课标，并自动补完。")
    assert cmd is not None
    assert cmd["action"] == "update_center"
    assert cmd["target"] == "小学新课标"
    follow = cmd.get("follow_up_actions")
    assert isinstance(follow, list)
    assert len(follow) == 1
    assert follow[0]["action"] == "auto_complete"


def test_heuristic_update_center_then_auto_complete_en() -> None:
    """English compound topic change + auto-complete."""
    cmd = heuristic_one_sentence_edit_command("change the topic to New Curriculum and auto-complete")
    assert cmd is not None
    assert cmd["action"] == "update_center"
    assert cmd["target"] == "New Curriculum"
    follow = cmd.get("follow_up_actions")
    assert isinstance(follow, list)
    assert follow[0]["action"] == "auto_complete"


def test_heuristic_add_branch_then_auto_complete() -> None:
    """Compound 添加分支+补全 maps to add_node with auto_complete_branch follow-up."""
    cmd = heuristic_one_sentence_edit_command("添加一个中国的分支并补全")
    assert cmd is not None
    assert cmd["action"] == "add_node"
    assert cmd["target"] == "中国"
    follow = cmd.get("follow_up_actions")
    assert isinstance(follow, list)
    assert follow[0]["action"] == "auto_complete_branch"
    assert follow[0]["target"] == "中国"


def test_heuristic_add_branch_then_auto_complete_en() -> None:
    """English compound add branch + auto-complete."""
    cmd = heuristic_one_sentence_edit_command("add a branch called History and auto-complete it")
    assert cmd is not None
    assert cmd["action"] == "add_node"
    assert cmd["target"] == "History"
    follow = cmd.get("follow_up_actions")
    assert isinstance(follow, list)
    assert follow[0]["action"] == "auto_complete_branch"
    assert follow[0]["target"] == "History"
