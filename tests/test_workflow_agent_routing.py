"""Tests for unified agent routing in diagram generation."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agents.core.agent_routing import resolve_agent_generate_route
from agents.core.workflow import _generate_spec_with_agent


def test_tree_map_fixed_children_routes_standard_with_structure_kwargs() -> None:
    route = resolve_agent_generate_route(
        diagram_type="tree_map",
        structure_mode="fixed",
        fixed_nodes={"children": ["衣", "食", "住", "行"]},
        fixed_dimension="分类",
        dimension_preference="分类方式",
    )
    assert route.mode == "standard"
    assert route.kwargs["structure_mode"] == "fixed"
    assert route.kwargs["fixed_nodes"]["children"] == ["衣", "食", "住", "行"]
    assert route.kwargs.get("dimension_preference") == "分类"
    assert route.kwargs.get("fixed_dimension") == "分类"


def test_brace_map_fixed_parts_routes_standard_with_structure_kwargs() -> None:
    route = resolve_agent_generate_route(
        diagram_type="brace_map",
        structure_mode="fixed",
        fixed_nodes={"parts": ["引擎", "底盘"]},
        fixed_dimension="组成",
    )
    assert route.mode == "standard"
    assert route.kwargs["structure_mode"] == "fixed"
    assert route.kwargs["fixed_nodes"]["parts"] == ["引擎", "底盘"]


def test_tree_map_dimension_only_without_fixed_lists_uses_dimension_branch() -> None:
    route = resolve_agent_generate_route(
        diagram_type="tree_map",
        structure_mode="free",
        fixed_dimension="栖息地",
    )
    assert route.mode == "tree_brace_fixed_dimension"
    assert route.kwargs["structure_mode"] == "free"
    assert route.kwargs["fixed_dimension"] == "栖息地"


@pytest.mark.asyncio
async def test_generate_spec_with_agent_passes_fixed_structure_to_tree_agent() -> None:
    captured: dict = {}

    async def fake_generate_graph(_prompt: str, _language: str, **kwargs) -> dict:
        captured.update(kwargs)
        return {
            "success": True,
            "spec": {"topic": "动物", "children": [{"text": "鱼类", "children": []}]},
        }

    with patch(
        "agents.core.workflow.TreeMapAgent",
    ) as mock_agent_cls:
        mock_agent_cls.return_value.generate_graph = AsyncMock(side_effect=fake_generate_graph)
        await _generate_spec_with_agent(
            "动物分类",
            "tree_map",
            "zh",
            structure_mode="fixed",
            fixed_nodes={"children": ["鱼类", "哺乳类"]},
            fixed_dimension="分类",
            dimension_preference="分类方式",
        )

    assert captured["structure_mode"] == "fixed"
    assert captured["fixed_nodes"]["children"] == ["鱼类", "哺乳类"]
    assert captured.get("dimension_preference") == "分类"
    assert captured.get("fixed_dimension") == "分类"
