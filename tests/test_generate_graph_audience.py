"""generate_graph router uses shared prompt prepare for NL 专业程度."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.requests.requests_diagram import GenerateRequest
from routers.api.diagram_generation import _prepare_generate_graph


@pytest.mark.asyncio
async def test_prepare_generate_graph_merges_nl_audience() -> None:
    """Landing-style prompt 小学水平 becomes the canvas audience block."""
    req = GenerateRequest.model_validate({"prompt": "光合作用，小学水平", "language": "zh"})
    request = MagicMock()
    request.headers = {"Accept-Language": "zh"}
    request.state = MagicMock()

    with (
        patch(
            "routers.api.diagram_generation.check_endpoint_rate_limit",
            new=AsyncMock(),
        ),
        patch(
            "routers.api.diagram_generation.assert_collab_blocks_canvas_ai",
            new=AsyncMock(),
        ),
    ):
        prepared = await _prepare_generate_graph(
            req,
            request,
            None,
            None,
            endpoint_path="/api/generate_graph",
        )

    prompt = str(prepared["prompt"])
    assert "光合作用" in prompt
    topic_part = prompt.split("【用户要求】", maxsplit=1)[0]
    assert "小学水平" not in topic_part
    assert "请按「小学」专业程度生成内容。" in prompt
    assert prepared["generation_instructions"] is not None
    assert "小学" in str(prepared["generation_instructions"])
    assert prepared["workflow_kwargs"]["user_prompt"] == prompt
    assert prepared["is_learning_sheet"] is False
    assert prepared["workflow_kwargs"]["is_learning_sheet"] is False


@pytest.mark.asyncio
async def test_prepare_generate_graph_keeps_learning_sheet_after_strip() -> None:
    """半成品 is stripped from the topic but still forwarded as a workflow flag."""
    req = GenerateRequest.model_validate({"prompt": "茶叶半成品", "language": "zh"})
    request = MagicMock()
    request.headers = {"Accept-Language": "zh"}
    request.state = MagicMock()

    with (
        patch(
            "routers.api.diagram_generation.check_endpoint_rate_limit",
            new=AsyncMock(),
        ),
        patch(
            "routers.api.diagram_generation.assert_collab_blocks_canvas_ai",
            new=AsyncMock(),
        ),
    ):
        prepared = await _prepare_generate_graph(
            req,
            request,
            None,
            None,
            endpoint_path="/api/generate_graph",
        )

    prompt = str(prepared["prompt"])
    assert "茶叶" in prompt
    assert "半成品" not in prompt
    assert prepared["is_learning_sheet"] is True
    assert prepared["workflow_kwargs"]["is_learning_sheet"] is True
    assert prepared["workflow_kwargs"]["user_prompt"] == prompt
