"""Tests for mind map branch sub-graph expansion."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from agents.core.workflow import agent_graph_workflow_with_styles, _generate_spec_with_agent
from agents.mind_maps.mind_map_agent import MindMapAgent, build_mind_map_branch_expand_user_message
from prompts.ai_content_level import merge_generation_instructions


def test_build_branch_expand_user_message_includes_topic_and_reference_branches():
    """Branch expand prompt should include central topic and sibling branches."""
    message = build_mind_map_branch_expand_user_message(
        expand_branch="Light",
        mind_map_topic="Photosynthesis",
        reference_branches=["Calvin cycle"],
        existing_branch_children=["Chlorophyll"],
        parent_branch="",
        language="zh",
    )
    assert "中心主题：Photosynthesis" in message
    assert "要扩展的分支：Light" in message
    assert "图中其他分支（参考）：Calvin cycle" in message
    assert "该分支已有子节点（勿重复）：Chlorophyll" in message
    assert "直接子节点" in message


def test_build_branch_expand_user_message_appends_global_audience_instructions():
    """Subgraph expand must keep the canvas 专业程度 block on the LLM user message."""
    message = build_mind_map_branch_expand_user_message(
        expand_branch="Light",
        mind_map_topic="Photosynthesis",
        reference_branches=[],
        existing_branch_children=[],
        parent_branch="",
        language="zh",
        generation_instructions="小学短句，具体可感知",
    )
    assert message.endswith("小学短句，具体可感知")
    assert "要扩展的分支：Light" in message


def test_build_branch_expand_user_message_appends_rag_after_audience():
    """RAG context trails the 专业程度 block on the single user message."""
    message = build_mind_map_branch_expand_user_message(
        expand_branch="Light",
        mind_map_topic="Photosynthesis",
        reference_branches=[],
        existing_branch_children=[],
        parent_branch="",
        language="zh",
        generation_instructions="小学短句，具体可感知",
        rag_context_block="相关背景知识（来自用户的知识库）：\n叶绿素",
    )
    audience_at = message.find("小学短句，具体可感知")
    rag_at = message.find("叶绿素")
    assert audience_at != -1
    assert rag_at != -1
    assert audience_at < rag_at


def test_build_branch_expand_user_message_uses_nested_wording_for_child_nodes():
    """Nested anchors should ask for direct sub-node children only."""
    message = build_mind_map_branch_expand_user_message(
        expand_branch="Dynasties",
        mind_map_topic="History",
        reference_branches=[],
        existing_branch_children=[],
        parent_branch="Ancient",
        language="zh",
    )
    assert "上级分支：Ancient" in message
    assert "直接下级节点" in message


def test_validate_branch_expand_output_accepts_valid_children():
    """Accept specs with at least two sub-branches under the expanded branch."""
    agent = MindMapAgent(model="qwen")
    spec = {
        "topic": "Light reactions",
        "children": [
            {"id": "a", "text": "Photosystem II"},
            {"id": "b", "text": "Electron transport"},
        ],
    }
    ok, msg = agent.validate_branch_expand_output(spec, "Light reactions")
    assert ok is True
    assert msg == "Valid branch expand specification"


def test_validate_branch_expand_output_rejects_too_few_children():
    """Reject branch expand output with fewer than two sub-branches."""
    agent = MindMapAgent(model="qwen")
    spec = {
        "topic": "Light reactions",
        "children": [{"id": "a", "text": "Only one"}],
    }
    ok, msg = agent.validate_branch_expand_output(spec, "Light reactions")
    assert ok is False
    assert "At least two" in msg


def test_validate_branch_expand_output_rejects_wrong_topic():
    """Reject when topic label does not match the branch being expanded."""
    agent = MindMapAgent(model="qwen")
    spec = {
        "topic": "Wrong label",
        "children": [
            {"id": "a", "text": "One"},
            {"id": "b", "text": "Two"},
        ],
    }
    ok, msg = agent.validate_branch_expand_output(spec, "Light reactions")
    assert ok is False
    assert "expanded branch" in msg


@pytest.mark.asyncio
async def test_generate_graph_branch_expand_keeps_global_audience_in_llm_prompt() -> None:
    """Router-merged 专业程度 text must reach the branch-expand LLM user prompt."""
    captured: dict[str, str] = {}

    async def fake_dispatch(**kwargs: Any) -> dict[str, Any]:
        prompt = kwargs.get("prompt")
        captured["prompt"] = str(prompt or "")
        return {
            "topic": "Light",
            "children": [
                {"id": "a", "text": "Photosystem II"},
                {"id": "b", "text": "Electron transport"},
            ],
        }

    user_prompt = merge_generation_instructions(
        "中心主题：Photosynthesis\n要扩展的分支：Light",
        "小学短句，具体可感知",
        "zh",
    )
    agent = MindMapAgent(model="qwen")
    with patch(
        "agents.mind_maps.mind_map_agent.dispatch_llm_chat",
        new=AsyncMock(side_effect=fake_dispatch),
    ):
        result = await agent.generate_graph(
            user_prompt,
            "zh",
            expand_branch="Light",
            mind_map_topic="Photosynthesis",
        )

    assert result.get("success") is True
    assert "要扩展的分支：Light" in captured["prompt"]
    assert "小学短句，具体可感知" in captured["prompt"]


@pytest.mark.asyncio
async def test_generate_graph_branch_expand_uses_explicit_generation_instructions() -> None:
    """First-class generation_instructions reach the LLM without a merged prompt suffix."""
    captured: dict[str, str] = {}

    async def fake_dispatch(**kwargs: Any) -> dict[str, Any]:
        captured["prompt"] = str(kwargs.get("prompt") or "")
        return {
            "topic": "Light",
            "children": [
                {"id": "a", "text": "Photosystem II"},
                {"id": "b", "text": "Electron transport"},
            ],
        }

    agent = MindMapAgent(model="qwen")
    with patch(
        "agents.mind_maps.mind_map_agent.dispatch_llm_chat",
        new=AsyncMock(side_effect=fake_dispatch),
    ):
        result = await agent.generate_graph(
            "中心主题：Photosynthesis\n要扩展的分支：Light",
            "zh",
            expand_branch="Light",
            mind_map_topic="Photosynthesis",
            generation_instructions="请按「小学」专业程度生成内容。",
        )

    assert result.get("success") is True
    assert "请按「小学」专业程度生成内容。" in captured["prompt"]
    assert "【用户要求】" not in captured["prompt"]


@pytest.mark.asyncio
async def test_generate_spec_with_agent_forwards_branch_expand_audience() -> None:
    """Workflow helper must pass audience and RAG as agent kwargs, not rebuild the prompt."""
    captured: dict[str, Any] = {}

    async def fake_generate_graph(_prompt: str, _language: str, **kwargs: Any) -> dict[str, Any]:
        captured["prompt"] = _prompt
        captured.update(kwargs)
        return {
            "success": True,
            "spec": {
                "topic": "Light",
                "children": [
                    {"id": "a", "text": "Photosystem II"},
                    {"id": "b", "text": "Electron transport"},
                ],
            },
        }

    with patch("agents.core.workflow.MindMapAgent") as mock_agent_cls:
        mock_agent_cls.return_value.generate_graph = AsyncMock(side_effect=fake_generate_graph)
        await _generate_spec_with_agent(
            "中心主题：Photosynthesis\n要扩展的分支：Light",
            "mind_map",
            "zh",
            expand_branch="Light",
            mind_map_topic="Photosynthesis",
            generation_instructions="请按「小学」专业程度生成内容。",
            rag_context_block="相关背景知识（来自用户的知识库）：\n叶绿素",
        )

    assert captured["expand_branch"] == "Light"
    assert captured["generation_instructions"] == "请按「小学」专业程度生成内容。"
    assert captured["rag_context_block"] == "相关背景知识（来自用户的知识库）：\n叶绿素"


@pytest.mark.asyncio
async def test_workflow_branch_expand_keeps_audience_on_llm_prompt() -> None:
    """Live HTTP path: request generation_instructions must appear on the LLM user message."""
    captured: dict[str, str] = {}

    async def fake_dispatch(**kwargs: Any) -> dict[str, Any]:
        captured["prompt"] = str(kwargs.get("prompt") or "")
        return {
            "topic": "Light",
            "children": [
                {"id": "a", "text": "Photosystem II"},
                {"id": "b", "text": "Electron transport"},
            ],
        }

    with patch(
        "agents.mind_maps.mind_map_agent.dispatch_llm_chat",
        new=AsyncMock(side_effect=fake_dispatch),
    ):
        result = await agent_graph_workflow_with_styles(
            "中心主题：Photosynthesis\n要扩展的分支：Light",
            language="zh",
            forced_diagram_type="mind_map",
            expand_branch="Light",
            mind_map_topic="Photosynthesis",
            generation_instructions="请按「小学」专业程度生成内容。",
        )

    assert result.get("success") is True
    assert "要扩展的分支：Light" in captured["prompt"]
    assert "请按「小学」专业程度生成内容。" in captured["prompt"]
