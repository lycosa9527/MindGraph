"""Unit tests for Maite LLM adapter and session event bus."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from services.llm.llm_utils import stream_enable_thinking
from services.maite.events.bus import (
    MaiteEvent,
    get_maite_session_event_bus,
    remove_maite_session_event_bus,
)
from services.maite.events.kinds import MaiteEventKind
from services.maite.llm.adapter import MaiteLLMAdapter
from services.maite.llm.router import route


@pytest.mark.asyncio
async def test_maite_llm_adapter_complete_passes_tracking_kwargs():
    """Adapter must call llm_service.chat with maite_learning request_type."""
    adapter = MaiteLLMAdapter()
    with patch(
        "services.maite.llm.adapter.llm_service.chat",
        new_callable=AsyncMock,
        return_value='{"ok": true}',
    ) as chat_mock:
        result = await adapter.complete(
            system_prompt="sys",
            user_prompt="user",
            user_id=7,
            organization_id=3,
            endpoint_path="/api/maite/mentor/decompose",
            task_type="mentor_decompose",
        )
    assert result == '{"ok": true}'
    assert chat_mock.await_args is not None
    kwargs = chat_mock.await_args.kwargs
    assert kwargs["request_type"] == "maite_learning"
    assert kwargs["user_id"] == 7
    assert kwargs["organization_id"] == 3
    assert kwargs["use_knowledge_base"] is False
    assert kwargs["system_message"] == "sys"
    assert kwargs["prompt"] == "user"
    assert "messages" not in kwargs


def test_stream_enable_thinking_off_for_qwen3():
    """qwen3.7-* must not enable DashScope thinking on streams."""
    assert stream_enable_thinking("qwen3.7-plus") is False
    assert stream_enable_thinking("qwen3.7-flash") is False
    assert stream_enable_thinking("qwen") is False


def test_maite_route_ocr_requires_vision():
    """OCR task routes to vision prompt on qwen3.7-flash."""
    resolved = route("ocr_extract", has_image=True)
    assert resolved.prompt_id == "ocr_extract"
    assert resolved.requires_vision is True
    assert resolved.model == "qwen3.7-flash"


def test_maite_route_diagnosis_stays_text():
    """Diagnosis stays on text model even when image was used earlier."""
    resolved = route("diagnosis_auto", has_image=True)
    assert resolved.requires_vision is False


@pytest.mark.asyncio
async def test_maite_session_event_bus_emit_and_handler():
    """Session bus delivers events to async handlers."""
    key = "test-maite-bus"
    remove_maite_session_event_bus(key)
    bus = get_maite_session_event_bus(key)
    seen: list[MaiteEventKind] = []

    async def handler(event: MaiteEvent) -> None:
        seen.append(event.kind)

    bus.add_handler(handler)
    await bus.start()
    await bus.emit(MaiteEvent(kind="practice_dirty", session_key=key, payload={"n": 1}))
    await asyncio.sleep(0.05)
    await bus.stop()
    remove_maite_session_event_bus(key)
    assert "practice_dirty" in seen
