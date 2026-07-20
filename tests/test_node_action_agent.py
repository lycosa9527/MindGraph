"""Tests for NodeActionAgent LLM routing."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from services.infrastructure.http.error_handler import LLMTimeoutError
from services.kitty.routing.node_action_agent import (
    ONE_SENTENCE_EDIT_DASHSCOPE_MODEL,
    parse_node_action_intent,
)


@pytest.mark.asyncio
async def test_agent_complete_existing_branch() -> None:
    """补全中国这个分支 → auto_complete_branch when branch exists on canvas."""
    chat_raw = AsyncMock(
        return_value={
            "tool_calls": [
                {
                    "function": {
                        "name": "node_action.auto_complete_branch",
                        "arguments": json.dumps({"target": "中国"}),
                    }
                }
            ],
        }
    )
    ctx = {
        "language": "zh",
        "diagram_data": {
            "center": {"text": "茶叶"},
            "children": [{"text": "中国", "id": "n1"}],
        },
    }
    with (
        patch("services.kitty.routing.node_action_agent.llm_service.chat_raw", chat_raw),
        patch(
            "services.kitty.routing.node_action_agent.get_session_memory",
        ) as mem,
    ):
        mem.return_value.summarize_for_parser.return_value = ""
        cmd = await parse_node_action_intent(
            "补全中国这个分支",
            voice_session_id="voice_test",
            diagram_type="mindmap",
            session_context=ctx,
        )

    assert cmd is not None
    assert cmd["action"] == "auto_complete_branch"
    assert cmd["target"] == "中国"
    assert cmd.get("node_id") == "n1"
    assert chat_raw.await_args is not None
    kwargs = chat_raw.await_args.kwargs
    assert kwargs["model"] == ONE_SENTENCE_EDIT_DASHSCOPE_MODEL
    assert "dashscope_model" not in kwargs
    assert "中国" in kwargs["prompt"]


@pytest.mark.asyncio
async def test_agent_add_new_branch() -> None:
    """增加一个中国的分支 → add_node for a new branch label."""
    chat_raw = AsyncMock(
        return_value={
            "tool_calls": [
                {
                    "function": {
                        "name": "diagram.add_node",
                        "arguments": json.dumps({"text": "中国"}),
                    }
                }
            ],
        }
    )
    with (
        patch("services.kitty.routing.node_action_agent.llm_service.chat_raw", chat_raw),
        patch(
            "services.kitty.routing.node_action_agent.get_session_memory",
        ) as mem,
    ):
        mem.return_value.summarize_for_parser.return_value = ""
        cmd = await parse_node_action_intent(
            "增加一个中国的分支",
            voice_session_id="voice_test",
            diagram_type="mindmap",
            session_context={"language": "zh", "diagram_data": {"center": {"text": "茶叶"}}},
        )

    assert cmd is not None
    assert cmd["action"] == "add_node"
    assert cmd["target"] == "中国"


@pytest.mark.asyncio
async def test_agent_clarify_when_ambiguous() -> None:
    """Ambiguous intent returns clarify_options with at least two choices."""
    options = [
        {"label": "补全「中国」分支", "action": "auto_complete_branch", "target": "中国"},
        {"label": "新增「中国」分支", "action": "add_node", "target": "中国"},
    ]
    chat_raw = AsyncMock(
        return_value={
            "tool_calls": [
                {
                    "function": {
                        "name": "node_action.clarify_options",
                        "arguments": json.dumps({"question": "你是想：", "options": options}),
                    }
                }
            ],
        }
    )
    with (
        patch("services.kitty.routing.node_action_agent.llm_service.chat_raw", chat_raw),
        patch(
            "services.kitty.routing.node_action_agent.get_session_memory",
        ) as mem,
    ):
        mem.return_value.summarize_for_parser.return_value = ""
        cmd = await parse_node_action_intent(
            "中国",
            voice_session_id="voice_test",
            diagram_type="mindmap",
            session_context={"language": "zh", "diagram_data": {"center": {"text": "茶叶"}}},
        )

    assert cmd is not None
    assert cmd["action"] == "clarify_options"
    assert len(cmd.get("options", [])) >= 2


@pytest.mark.asyncio
async def test_agent_timeout_returns_none() -> None:
    """LLM failure returns None so caller can use heuristic fallback."""
    with (
        patch(
            "services.kitty.routing.node_action_agent.llm_service.chat_raw",
            new=AsyncMock(side_effect=LLMTimeoutError("timeout")),
        ),
        patch(
            "services.kitty.routing.node_action_agent.get_session_memory",
        ) as mem,
    ):
        mem.return_value.summarize_for_parser.return_value = ""
        cmd = await parse_node_action_intent(
            "补全中国这个分支",
            voice_session_id="voice_test",
            diagram_type="mindmap",
        )

    assert cmd is None


@pytest.mark.asyncio
async def test_agent_update_center_and_auto_complete_two_tools() -> None:
    """Two tool calls become update_center + auto_complete follow-up."""
    chat_raw = AsyncMock(
        return_value={
            "tool_calls": [
                {
                    "function": {
                        "name": "diagram.update_center",
                        "arguments": json.dumps({"new_text": "小学新课标"}),
                    }
                },
                {
                    "function": {
                        "name": "node_action.auto_complete",
                        "arguments": "{}",
                    }
                },
            ],
        }
    )
    with (
        patch("services.kitty.routing.node_action_agent.llm_service.chat_raw", chat_raw),
        patch(
            "services.kitty.routing.node_action_agent.get_session_memory",
        ) as mem,
    ):
        mem.return_value.summarize_for_parser.return_value = ""
        cmd = await parse_node_action_intent(
            "主题改成小学新课标，并自动补完",
            voice_session_id="voice_test",
            diagram_type="mindmap",
            session_context={"language": "zh", "diagram_data": {"center": {"text": "中心主题"}}},
        )

    assert cmd is not None
    assert cmd["action"] == "update_center"
    assert cmd["target"] == "小学新课标"
    follow = cmd.get("follow_up_actions")
    assert isinstance(follow, list)
    assert len(follow) == 1
    assert follow[0]["action"] == "auto_complete"
    assert chat_raw.await_args is not None
    assert chat_raw.await_args.kwargs["model"] == ONE_SENTENCE_EDIT_DASHSCOPE_MODEL
    assert chat_raw.await_args.kwargs["timeout"] == 10.0


@pytest.mark.asyncio
async def test_agent_attaches_autocomplete_when_user_asks_but_model_returns_one() -> None:
    """Safety net: single update_center still chains auto_complete from user text."""
    chat_raw = AsyncMock(
        return_value={
            "tool_calls": [
                {
                    "function": {
                        "name": "diagram.update_center",
                        "arguments": json.dumps({"new_text": "小学新课标"}),
                    }
                },
            ],
        }
    )
    with (
        patch("services.kitty.routing.node_action_agent.llm_service.chat_raw", chat_raw),
        patch(
            "services.kitty.routing.node_action_agent.get_session_memory",
        ) as mem,
    ):
        mem.return_value.summarize_for_parser.return_value = ""
        cmd = await parse_node_action_intent(
            "主题改成小学新课标，并自动补完。",
            voice_session_id="voice_test",
            diagram_type="mindmap",
            session_context={"language": "zh", "diagram_data": {"center": {"text": "中心主题"}}},
        )

    assert cmd is not None
    assert cmd["action"] == "update_center"
    follow = cmd.get("follow_up_actions")
    assert isinstance(follow, list)
    assert follow[0]["action"] == "auto_complete"


@pytest.mark.asyncio
async def test_agent_attaches_branch_autocomplete_for_add_node() -> None:
    """add_node + 补全 attaches auto_complete_branch with the same label."""
    chat_raw = AsyncMock(
        return_value={
            "tool_calls": [
                {
                    "function": {
                        "name": "diagram.add_node",
                        "arguments": json.dumps({"text": "中国"}),
                    }
                },
            ],
        }
    )
    with (
        patch("services.kitty.routing.node_action_agent.llm_service.chat_raw", chat_raw),
        patch(
            "services.kitty.routing.node_action_agent.get_session_memory",
        ) as mem,
    ):
        mem.return_value.summarize_for_parser.return_value = ""
        cmd = await parse_node_action_intent(
            "添加一个中国的分支并补全",
            voice_session_id="voice_test",
            diagram_type="mindmap",
            session_context={"language": "zh", "diagram_data": {"center": {"text": "茶叶"}}},
        )

    assert cmd is not None
    assert cmd["action"] == "add_node"
    assert cmd["target"] == "中国"
    follow = cmd.get("follow_up_actions")
    assert isinstance(follow, list)
    assert follow[0]["action"] == "auto_complete_branch"
    assert follow[0]["target"] == "中国"


@pytest.mark.asyncio
async def test_agent_multi_add_node_tool_calls_merge_in_order() -> None:
    """Multiple add_node tool calls become primary + structural follow-ups."""
    chat_raw = AsyncMock(
        return_value={
            "tool_calls": [
                {
                    "function": {
                        "name": "diagram.update_center",
                        "arguments": json.dumps({"new_text": "学生运动"}),
                    }
                },
                {
                    "function": {
                        "name": "diagram.add_node",
                        "arguments": json.dumps({"text": "跑步"}),
                    }
                },
                {
                    "function": {
                        "name": "diagram.add_node",
                        "arguments": json.dumps({"text": "跳跃"}),
                    }
                },
            ],
        }
    )
    with (
        patch("services.kitty.routing.node_action_agent.llm_service.chat_raw", chat_raw),
        patch(
            "services.kitty.routing.node_action_agent.get_session_memory",
        ) as mem,
    ):
        mem.return_value.summarize_for_parser.return_value = ""
        cmd = await parse_node_action_intent(
            "主题改成学生运动，添加跑步和跳跃分支",
            voice_session_id="voice_test",
            diagram_type="mindmap",
            session_context={"language": "zh", "diagram_data": {"center": {"text": "主题"}}},
        )

    assert cmd is not None
    assert cmd["action"] == "update_center"
    assert cmd["target"] == "学生运动"
    follow = cmd.get("follow_up_actions")
    assert isinstance(follow, list)
    assert [item.get("action") for item in follow] == ["add_node", "add_node"]
    assert [item.get("target") for item in follow] == ["跑步", "跳跃"]
    assert chat_raw.await_args is not None
    system = chat_raw.await_args.kwargs["system_message"]
    assert "多个" in system or "MULTIPLE" in system
    assert "不要在 add_node 之间" in system or "Do NOT call" in system
    assert "whole-map" in system or "整图" in system
