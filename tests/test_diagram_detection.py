"""Tests for LLM diagram type detection parsing and unclear-intent defaults."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agents.core.diagram_detection import _extract_diagram_type_from_llm_response
from agents.core.prompt_requirements import ParsedRequirements
from agents.core.workflow import agent_graph_workflow_with_styles


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("mind_map", "mind_map"),
        ("tree_map", "tree_map"),
        ("  flow_map  ", "flow_map"),
        ("mindmap", "mind_map"),
        ("The answer is bubble_map.", "bubble_map"),
        ("unclear", "unclear"),
        ("", None),
        ("not_a_real_type", None),
    ],
)
def test_extract_diagram_type_from_llm_response(raw: str, expected: str | None) -> None:
    """Parse diagram type tokens from raw LLM detection output."""
    assert _extract_diagram_type_from_llm_response(raw) == expected


@pytest.mark.asyncio
async def test_workflow_unclear_detection_still_generates_mind_map() -> None:
    """Unclear detection clarity still proceeds with the detected mind map type."""
    detection = {
        "diagram_type": "mind_map",
        "clarity": "unclear",
        "has_topic": True,
    }
    parsed = ParsedRequirements(
        structure_mode="free",
        central="光合作用",
        diagram_type="mind_map",
    )

    with patch(
        "agents.core.workflow._detect_diagram_type_from_prompt",
        new=AsyncMock(return_value=detection),
    ):
        with patch(
            "agents.core.workflow.extract_prompt_requirements",
            new=AsyncMock(return_value=parsed),
        ):
            with patch(
                "agents.core.workflow._generate_spec_with_agent",
                new=AsyncMock(return_value={"spec": {"topic": "光合作用", "children": []}}),
            ):
                result = await agent_graph_workflow_with_styles(
                    "光合作用",
                    language="zh",
                    model="qwen",
                )

    assert result["success"] is True
    assert result["diagram_type"] == "mind_map"


@pytest.mark.asyncio
async def test_workflow_forced_type_skips_detection() -> None:
    """Forced diagram type bypasses LLM detection entirely."""
    detect_mock = AsyncMock()
    parsed = ParsedRequirements(
        structure_mode="fixed",
        central="北京三日游计划",
        fixed_nodes={"children": ["衣", "食", "住", "行"]},
        diagram_type="mind_map",
    )

    with patch(
        "agents.core.workflow._detect_diagram_type_from_prompt",
        new=detect_mock,
    ):
        with patch(
            "agents.core.workflow.extract_prompt_requirements",
            new=AsyncMock(return_value=parsed),
        ):
            with patch(
                "agents.core.workflow._generate_spec_with_agent",
                new=AsyncMock(return_value={"spec": {"topic": "北京三日游计划", "children": []}}),
            ):
                result = await agent_graph_workflow_with_styles(
                    "北京三日游计划，四个分支：衣、食、住、行",
                    language="zh",
                    forced_diagram_type="mind_map",
                    model="qwen",
                )

    detect_mock.assert_not_called()
    assert result["success"] is True
    assert result["structure_mode"] == "fixed"
