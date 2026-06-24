"""Tests for auto-complete generate_graph SSE stream and LLM phase dispatch."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from agents.core.llm_spec_stream import dispatch_llm_chat
from agents.mind_maps.mind_map_agent import MindMapAgent
from models import GenerateRequest
from models.common import DiagramType, LLMModel
from routers.api.diagram_generation import _build_workflow_kwargs, _stream_generate_graph_events


async def _fake_chat_stream(**_kwargs: Any):
    yield {"type": "token", "content": "{"}
    yield {"type": "token", "content": '"topic": "T"'}
    yield {"type": "token", "content": "}"}


@pytest.mark.asyncio
async def test_dispatch_llm_chat_emits_waiting_then_streaming() -> None:
    """Streaming chat emits waiting then streaming phase events."""
    phases: list[str] = []

    async def phase_emit(event: str) -> None:
        phases.append(event)

    with patch(
        "agents.core.llm_spec_stream.llm_service.chat_stream",
        side_effect=_fake_chat_stream,
    ):
        result = await dispatch_llm_chat(
            phase_emit=phase_emit,
            prompt="test",
            model="qwen",
        )

    assert phases == ["waiting", "streaming"]
    assert result == '{"topic": "T"}'


@pytest.mark.asyncio
async def test_dispatch_llm_chat_without_phase_emit_uses_blocking_chat() -> None:
    """Without phase_emit, dispatch uses blocking chat instead of stream."""
    with patch(
        "agents.core.llm_spec_stream.llm_service.chat",
        new=AsyncMock(return_value='{"topic": "X"}'),
    ) as mock_chat:
        result = await dispatch_llm_chat(
            phase_emit=None,
            prompt="test",
            model="qwen",
        )

    mock_chat.assert_awaited_once()
    assert result == '{"topic": "X"}'


@pytest.mark.asyncio
async def test_dispatch_llm_chat_strips_phase_emit_from_llm_kwargs() -> None:
    """phase_emit is not forwarded to the underlying LLM client."""
    captured: dict[str, Any] = {}

    async def fake_stream(**kwargs: Any):
        captured.update(kwargs)
        yield {"type": "token", "content": "ok"}

    async def phase_emit(_event: str) -> None:
        return None

    with patch(
        "agents.core.llm_spec_stream.llm_service.chat_stream",
        side_effect=fake_stream,
    ):
        await dispatch_llm_chat(
            phase_emit=phase_emit,
            prompt="test",
            model="qwen",
            user_id=1,
        )

    assert "phase_emit" not in captured
    assert captured.get("user_id") == 1


@pytest.mark.asyncio
async def test_mind_map_agent_passes_phase_emit_to_dispatch() -> None:
    """MindMapAgent forwards phase_emit through dispatch_llm_chat."""
    phases: list[str] = []

    async def phase_emit(event: str) -> None:
        phases.append(event)

    async def fake_dispatch(**kwargs: Any) -> str:
        emit = kwargs.get("phase_emit")
        assert emit is not None
        await emit("waiting")
        await emit("streaming")
        return '{"topic":"T","children":[{"text":"A","children":[]}]}'

    agent = MindMapAgent(model="qwen")
    with patch(
        "agents.mind_maps.mind_map_agent.dispatch_llm_chat",
        new=AsyncMock(side_effect=fake_dispatch),
    ):
        result = await agent.generate_graph(
            "photosynthesis",
            "en",
            phase_emit=phase_emit,
        )

    assert result["success"] is True
    assert phases == ["waiting", "streaming"]


@pytest.mark.asyncio
async def test_mind_map_agent_uses_fixed_children_prompt_for_case2() -> None:
    """Fixed children structure selects the fixed_children prompt template."""
    captured: dict[str, Any] = {}

    def fake_get_prompt(_diagram_type: str, _language: str, prompt_type: str) -> str:
        captured["prompt_type"] = prompt_type
        return "system prompt"

    async def fake_dispatch(**_kwargs: Any) -> str:
        return (
            '{"topic":"北京三日游计划","children":['
            '{"text":"衣","children":[]},'
            '{"text":"食","children":[]},'
            '{"text":"住","children":[]},'
            '{"text":"行","children":[]}'
            "]}"
        )

    agent = MindMapAgent(model="qwen")
    with patch("agents.mind_maps.mind_map_agent.get_prompt", side_effect=fake_get_prompt):
        with patch(
            "agents.mind_maps.mind_map_agent.dispatch_llm_chat",
            new=AsyncMock(side_effect=fake_dispatch),
        ):
            result = await agent.generate_graph(
                "北京三日游计划",
                "zh",
                structure_mode="fixed",
                fixed_nodes={"children": ["衣", "食", "住", "行"]},
            )

    assert captured.get("prompt_type") == "fixed_children"
    assert result["success"] is True


@pytest.mark.asyncio
async def test_stream_generate_graph_events_phase_order() -> None:
    """Autocomplete SSE stream emits accepted, waiting, streaming, then complete."""
    prepared = {
        "lang": "en",
        "prompt": "photosynthesis",
        "request_id": "gen_test",
        "llm_model": "qwen",
        "language": "en",
        "user_id": None,
        "organization_id": None,
        "request_type": "autocomplete",
        "endpoint_path": "/api/generate_graph/stream",
        "req": None,
        "current_user": None,
        "workflow_kwargs": {"user_prompt": "photosynthesis", "language": "en", "model": "qwen"},
    }

    async def fake_workflow(**kwargs: Any) -> dict[str, Any]:
        assert kwargs.get("user_prompt") == "photosynthesis"
        phase_emit = kwargs.get("phase_emit")
        assert phase_emit is not None
        await phase_emit("waiting")
        await phase_emit("streaming")
        return {
            "success": True,
            "spec": {"topic": "Photosynthesis", "children": [{"text": "Light", "children": []}]},
            "diagram_type": "mindmap",
            "language": "en",
        }

    async def fake_finalize(result: dict[str, Any], _prepared: dict[str, Any]) -> dict[str, Any]:
        result["llm_model"] = _prepared["llm_model"]
        result["request_id"] = _prepared["request_id"]
        return result

    events: list[dict[str, Any]] = []
    with patch(
        "routers.api.diagram_generation.run_generate_pipeline",
        new=AsyncMock(side_effect=fake_workflow),
    ):
        with patch(
            "routers.api.diagram_generation._finalize_generate_graph_result",
            new=AsyncMock(side_effect=fake_finalize),
        ):
            async for chunk in _stream_generate_graph_events(prepared):
                if chunk.startswith("data: "):
                    events.append(json.loads(chunk.removeprefix("data: ").strip()))

    assert events[0]["event"] == "accepted"
    assert [e["event"] for e in events[1:-1]] == ["waiting", "streaming"]
    assert events[-1]["event"] == "complete"
    assert events[-1]["success"] is True
    assert events[-1]["diagram_type"] == "mindmap"


def test_build_workflow_kwargs_uses_user_prompt_not_prompt() -> None:
    """Workflow kwargs use user_prompt and omit the raw prompt field."""
    req = GenerateRequest.model_validate(
        {
            "prompt": "circle topic",
            "diagram_type": DiagramType.CIRCLE_MAP,
            "language": "zh",
            "llm": LLMModel.QWEN,
            "request_type": "autocomplete",
        }
    )
    prepared = {
        "prompt": "circle topic",
        "language": "zh",
        "llm_model": "qwen",
        "user_id": 3,
        "organization_id": None,
        "request_type": "autocomplete",
        "endpoint_path": "/api/generate_graph/stream",
    }
    kwargs = _build_workflow_kwargs(req, prepared)
    assert kwargs["user_prompt"] == "circle topic"
    assert "prompt" not in kwargs
    assert kwargs["forced_diagram_type"] == "circle_map"
    assert kwargs["model"] == "qwen"
