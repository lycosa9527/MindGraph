"""Tests for fixed-structure (Case 2) support on thinking-map agents."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from agents.core.fixed_structure import (
    extract_part_names,
    fixed_labels_from_nodes,
    validate_fixed_labels,
)
from agents.thinking_maps.brace_map_agent import BraceMapAgent
from agents.thinking_maps.flow_map_agent import FlowMapAgent
from agents.thinking_maps.tree_map_agent import TreeMapAgent
from prompts import get_prompt


def test_fixed_structure_prompts_registered() -> None:
    """Fixed-structure prompt keys exist for tree, brace, and flow maps."""
    assert get_prompt("tree_map_agent", "zh", "fixed_children")
    assert get_prompt("brace_map_agent", "en", "fixed_parts")
    assert get_prompt("flow_map_agent", "zh", "fixed_steps")


def test_validate_fixed_labels_order_and_count() -> None:
    """Fixed label validation enforces count and order."""
    ok, _ = validate_fixed_labels(["A", "B"], ["A", "B"], "steps")
    assert ok is True
    ok, msg = validate_fixed_labels(["A"], ["A", "B"], "steps")
    assert ok is False
    assert "Expected 2" in msg
    ok, msg = validate_fixed_labels(["B", "A"], ["A", "B"], "steps")
    assert ok is False
    assert "Steps 1" in msg


def test_extract_part_names_from_mixed_shapes() -> None:
    """Part name extraction accepts strings and dict nodes."""
    assert extract_part_names(["引擎", "底盘"]) == ["引擎", "底盘"]
    assert extract_part_names([{"name": "引擎"}, {"text": "底盘"}]) == ["引擎", "底盘"]


def test_fixed_labels_from_nodes() -> None:
    """fixed_labels_from_nodes normalizes and skips empty entries."""
    assert fixed_labels_from_nodes({"children": [" 衣 ", "", "食"]}, "children") == ["衣", "食"]
    assert fixed_labels_from_nodes(None, "children") is None


@pytest.mark.asyncio
async def test_tree_map_agent_uses_fixed_children_prompt() -> None:
    """Tree map Case 2 selects fixed_children prompt and validates output."""
    captured: dict[str, Any] = {}

    def fake_get_prompt(_diagram_type: str, _language: str, prompt_type: str) -> str:
        captured["prompt_type"] = prompt_type
        return "system {topic}"

    async def fake_dispatch(**_kwargs: Any) -> str:
        return (
            '{"topic":"动物","dimension":"分类","children":['
            '{"text":"哺乳动物","children":[{"text":"猫"}]},'
            '{"text":"鸟类","children":[{"text":"鹰"}]}'
            '],"alternative_dimensions":[]}'
        )

    agent = TreeMapAgent(model="qwen")
    with patch("agents.thinking_maps.tree_map_agent.get_prompt", side_effect=fake_get_prompt):
        with patch(
            "agents.thinking_maps.tree_map_agent.dispatch_llm_chat",
            new=AsyncMock(side_effect=fake_dispatch),
        ):
            result = await agent.generate_graph(
                "动物分类",
                "zh",
                structure_mode="fixed",
                fixed_nodes={"children": ["哺乳动物", "鸟类"]},
            )

    assert captured.get("prompt_type") == "fixed_children"
    assert result["success"] is True


@pytest.mark.asyncio
async def test_tree_map_agent_rejects_wrong_fixed_labels() -> None:
    """Tree map validation fails when category labels do not match."""
    agent = TreeMapAgent(model="qwen")
    spec = {
        "topic": "动物",
        "dimension": "分类",
        "children": [
            {"text": "鱼类", "children": []},
            {"text": "鸟类", "children": []},
        ],
        "alternative_dimensions": [],
    }
    ok, msg = agent.validate_output(spec, fixed_category_labels=["哺乳动物", "鸟类"])
    assert ok is False
    assert "Categories 1" in msg


@pytest.mark.asyncio
async def test_brace_map_agent_uses_fixed_parts_prompt() -> None:
    """Brace map Case 2 selects fixed_parts prompt and validates output."""
    captured: dict[str, Any] = {}

    def fake_get_prompt(_diagram_type: str, _language: str, prompt_type: str) -> str:
        captured["prompt_type"] = prompt_type
        return "system {topic}"

    async def fake_dispatch(**_kwargs: Any) -> str:
        return (
            '{"whole":"汽车","dimension":"组成","parts":['
            '{"name":"引擎","subparts":[{"name":"活塞"}]},'
            '{"name":"底盘","subparts":[{"name":"悬挂"}]}'
            '],"alternative_dimensions":[]}'
        )

    agent = BraceMapAgent(model="qwen")
    with patch("agents.thinking_maps.brace_map_agent.get_prompt", side_effect=fake_get_prompt):
        with patch(
            "agents.thinking_maps.brace_map_agent.dispatch_llm_chat",
            new=AsyncMock(side_effect=fake_dispatch),
        ):
            result = await agent.generate_graph(
                "汽车",
                "zh",
                structure_mode="fixed",
                fixed_nodes={"parts": ["引擎", "底盘"]},
            )

    assert captured.get("prompt_type") == "fixed_parts"
    assert result["success"] is True


@pytest.mark.asyncio
async def test_flow_map_agent_uses_fixed_steps_prompt() -> None:
    """Flow map Case 2 selects fixed_steps prompt and validates output."""
    captured: dict[str, Any] = {}

    def fake_get_prompt(_diagram_type: str, _language: str, prompt_type: str) -> str:
        captured["prompt_type"] = prompt_type
        return "system {topic}"

    async def fake_dispatch(**_kwargs: Any) -> str:
        return '{"title":"制作咖啡","steps":["磨豆","萃取","打奶泡"]}'

    agent = FlowMapAgent(model="qwen")
    with patch("agents.thinking_maps.flow_map_agent.get_prompt", side_effect=fake_get_prompt):
        with patch(
            "agents.thinking_maps.flow_map_agent.dispatch_llm_chat",
            new=AsyncMock(side_effect=fake_dispatch),
        ):
            result = await agent.generate_graph(
                "制作咖啡",
                "zh",
                structure_mode="fixed",
                fixed_nodes={"steps": ["磨豆", "萃取", "打奶泡"]},
            )

    assert captured.get("prompt_type") == "fixed_steps"
    assert result["success"] is True


@pytest.mark.asyncio
async def test_flow_map_agent_rejects_wrong_step_order() -> None:
    """Flow map validation fails when step order does not match."""
    agent = FlowMapAgent(model="qwen")
    spec = {"title": "制作咖啡", "steps": ["萃取", "磨豆"]}
    ok, msg = agent.validate_output(spec, fixed_step_labels=["磨豆", "萃取"])
    assert ok is False
    assert "Steps 1" in msg
