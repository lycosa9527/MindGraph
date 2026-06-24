"""Integration tests for typed generate_graph SSE events."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from agents.core.generate_events import GenerateGraphEvent
from routers.api.diagram_generation import _stream_generate_graph_events


@pytest.mark.asyncio
async def test_stream_emits_detecting_requirements_progress_and_complete() -> None:
    """SSE stream emits detecting, requirements, progress, and complete events."""
    prepared = {
        "lang": "en",
        "prompt": "classify animals",
        "request_id": "gen_events",
        "llm_model": "qwen",
        "language": "en",
        "user_id": None,
        "organization_id": None,
        "request_type": "diagram_generation",
        "endpoint_path": "/api/generate_graph/stream",
        "req": None,
        "current_user": None,
        "http_request": None,
        "workflow_kwargs": {"user_prompt": "classify animals", "language": "en", "model": "qwen"},
    }

    async def fake_pipeline(**kwargs: Any) -> dict[str, Any]:
        event_emit = kwargs.get("event_emit")
        phase_emit = kwargs.get("phase_emit")
        assert event_emit is not None
        await event_emit(GenerateGraphEvent(event="detecting", model="qwen"))
        if phase_emit is not None:
            await phase_emit("requirements")
        await event_emit(
            GenerateGraphEvent(
                event="progress",
                topic="Animals",
                diagram_type="tree_map",
                model="qwen",
            )
        )
        if phase_emit is not None:
            await phase_emit("waiting")
            await phase_emit("streaming")
        return {
            "success": True,
            "spec": {"topic": "Animals", "children": [{"text": "Fish", "children": []}]},
            "diagram_type": "tree_map",
            "language": "en",
        }

    async def fake_finalize(result: dict[str, Any], _prepared: dict[str, Any]) -> dict[str, Any]:
        result["llm_model"] = _prepared["llm_model"]
        result["request_id"] = _prepared["request_id"]
        return result

    events: list[dict[str, Any]] = []
    with patch(
        "routers.api.diagram_generation.run_generate_pipeline",
        new=AsyncMock(side_effect=fake_pipeline),
    ):
        with patch(
            "routers.api.diagram_generation._finalize_generate_graph_result",
            new=AsyncMock(side_effect=fake_finalize),
        ):
            async for chunk in _stream_generate_graph_events(prepared):
                if chunk.startswith("data: "):
                    events.append(json.loads(chunk.removeprefix("data: ").strip()))

    event_names = [event["event"] for event in events]
    assert event_names[0] == "accepted"
    assert "detecting" in event_names
    assert "requirements" in event_names
    progress = next(event for event in events if event["event"] == "progress")
    assert progress["topic"] == "Animals"
    assert progress["diagram_type"] == "tree_map"
    assert "waiting" in event_names
    assert "streaming" in event_names
    assert events[-1]["event"] == "complete"
    assert events[-1]["success"] is True


@pytest.mark.asyncio
async def test_stream_cancel_event_set_on_disconnect() -> None:
    """Disconnecting the SSE client sets the pipeline cancel event."""
    prepared = {
        "lang": "en",
        "prompt": "topic",
        "request_id": "gen_cancel",
        "llm_model": "qwen",
        "language": "en",
        "user_id": None,
        "organization_id": None,
        "request_type": "diagram_generation",
        "endpoint_path": "/api/generate_graph/stream",
        "req": None,
        "current_user": None,
        "http_request": None,
        "workflow_kwargs": {"user_prompt": "topic", "language": "en", "model": "qwen"},
    }

    captured_cancel: asyncio.Event | None = None
    pipeline_started = asyncio.Event()

    async def slow_pipeline(**kwargs: Any) -> dict[str, Any]:
        nonlocal captured_cancel
        captured_cancel = kwargs.get("cancel_event")
        pipeline_started.set()
        await asyncio.sleep(10)
        return {"success": True, "spec": {"topic": "T"}, "diagram_type": "mindmap", "language": "en"}

    with patch(
        "routers.api.diagram_generation.run_generate_pipeline",
        new=AsyncMock(side_effect=slow_pipeline),
    ):
        with patch(
            "routers.api.diagram_generation._finalize_generate_graph_result",
            new=AsyncMock(side_effect=lambda result, _prepared: result),
        ):
            gen = _stream_generate_graph_events(prepared)
            first = await gen.__anext__()
            assert "accepted" in first
            await asyncio.wait_for(pipeline_started.wait(), timeout=2.0)
            await gen.aclose()

    assert captured_cancel is not None
    assert captured_cancel.is_set()
