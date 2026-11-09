"""Content mind map generation retries once when the first spec is invalid."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest

from agents.mind_maps.web_content_mind_map_agent import WebContentMindMapAgent


def _spec(branch_count: int) -> Dict[str, Any]:
    return {
        "topic": "Course",
        "children": [{"text": f"Section {idx}", "children": [{"text": f"Point {idx}"}]} for idx in range(branch_count)],
    }


async def _passthrough(spec: Dict[str, Any]) -> Dict[str, Any]:
    return spec


@pytest.mark.asyncio
async def test_invalid_first_spec_is_retried_with_feedback() -> None:
    """Too many main branches triggers one retry that carries the validation message."""
    agent = WebContentMindMapAgent(model="express")
    llm = AsyncMock(side_effect=[(_spec(46), None), (_spec(6), None)])
    with (
        patch.object(agent, "_spec_from_extracted_content", llm),
        patch.object(agent, "enhance_spec", _passthrough),
    ):
        result = await agent.generate_from_page_content(
            page_content="text",
            language="en",
            source_kind="document",
        )
    assert result["success"] is True
    assert len(result["spec"]["children"]) == 6
    assert llm.await_count == 2
    retry_instructions = llm.await_args_list[1].kwargs["generation_instructions"]
    assert "Main branches must be 4 to 8 (got 46)" in retry_instructions


@pytest.mark.asyncio
async def test_second_invalid_spec_reports_retry_error() -> None:
    """When the retry is also invalid, the error names the retry's problem."""
    agent = WebContentMindMapAgent(model="express")
    llm = AsyncMock(side_effect=[(_spec(46), None), (_spec(2), None)])
    with patch.object(agent, "_spec_from_extracted_content", llm):
        result = await agent.generate_from_page_content(
            page_content="text",
            language="zh",
            source_kind="document",
        )
    assert result["success"] is False
    assert "got 2" in result["error"]
    assert "上一次生成未通过校验" in llm.await_args_list[1].kwargs["generation_instructions"]
