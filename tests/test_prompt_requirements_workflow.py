"""Integration tests for prompt requirements in the diagram workflow."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from agents.core.prompt_requirements import ParsedRequirements
from agents.core.workflow import agent_graph_workflow_with_styles


@pytest.mark.asyncio
async def test_workflow_extracts_requirements_and_passes_structure_mode() -> None:
    parsed = ParsedRequirements(
        structure_mode="fixed",
        central="北京三日游计划",
        fixed_nodes={"children": ["衣", "食", "住", "行"]},
        diagram_type="mind_map",
    )

    captured: dict[str, Any] = {}

    async def fake_generate(*args: Any, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"spec": {"topic": "北京三日游计划", "children": [{"text": "衣", "children": []}]}}

    with patch(
        "agents.core.workflow.extract_prompt_requirements",
        new=AsyncMock(return_value=parsed),
    ):
        with patch(
            "agents.core.workflow._generate_spec_with_agent",
            new=AsyncMock(side_effect=fake_generate),
        ):
            result = await agent_graph_workflow_with_styles(
                "生成一个北京三日游计划，四个分支，衣食住行四个方面",
                language="zh",
                forced_diagram_type="mind_map",
                model="qwen",
            )

    assert result["success"] is True
    assert result["structure_mode"] == "fixed"
    assert result["topics"] == ["北京三日游计划"]
    assert captured.get("structure_mode") == "fixed"
    assert captured.get("fixed_nodes") == {"children": ["衣", "食", "住", "行"]}


@pytest.mark.asyncio
async def test_workflow_requirements_phase_emitted_when_streaming() -> None:
    phases: list[str] = []

    async def phase_emit(event: str) -> None:
        phases.append(event)

    parsed = ParsedRequirements(
        structure_mode="free",
        central="光合作用",
        diagram_type="mind_map",
    )

    async def fake_generate(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"spec": {"topic": "光合作用", "children": [{"text": "光", "children": []}]}}

    async def fake_extract(*_args: Any, **kwargs: Any) -> ParsedRequirements:
        emit = kwargs.get("phase_emit")
        if emit is not None:
            await emit("requirements")
        return parsed

    with patch(
        "agents.core.workflow.extract_prompt_requirements",
        new=AsyncMock(side_effect=fake_extract),
    ):
        with patch(
            "agents.core.workflow._generate_spec_with_agent",
            new=AsyncMock(side_effect=fake_generate),
        ):
            await agent_graph_workflow_with_styles(
                "光合作用",
                language="zh",
                forced_diagram_type="mind_map",
                model="qwen",
                phase_emit=phase_emit,
            )

    assert "requirements" in phases
