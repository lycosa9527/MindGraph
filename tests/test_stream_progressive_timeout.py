"""stream_progressive must surface provider timeouts and not leak tasks."""

from __future__ import annotations

import asyncio
import gc
from typing import Any
from unittest.mock import MagicMock

import pytest

from services.infrastructure.http.error_handler import LLMTimeoutError, UserDailyTokenCapExceededError
from services.llm.llm_multi_service import LLMMultiService


def _capture_unretrieved(loop: asyncio.AbstractEventLoop) -> list[str]:
    leaked: list[str] = []

    def _handler(_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
        leaked.append(str(context.get("message", "")))

    loop.set_exception_handler(_handler)
    return leaked


def _llm_with_stream(stream: Any) -> MagicMock:
    llm_service = MagicMock()
    llm_service.load_balancer = None
    llm_service.chat_stream = stream
    return llm_service


async def _timeout_then_ok_stream(**kwargs: object):
    if kwargs.get("model") == "deepseek":
        raise LLMTimeoutError("DeepSeek streaming timeout")
    yield {"type": "token", "content": "ok"}


def _blocking_stream(cancelled: asyncio.Event):
    async def _stream(**_kwargs: object):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
        yield {"type": "token", "content": "ok"}

    return _stream


@pytest.mark.asyncio
async def test_stream_progressive_timeout_emits_error_and_finishes() -> None:
    """A DeepSeek LLMTimeoutError becomes an error event; the other model still completes."""
    llm_service = _llm_with_stream(_timeout_then_ok_stream)
    loop = asyncio.get_running_loop()
    leaked = _capture_unretrieved(loop)
    chunks: list[dict[str, Any]] = []
    try:
        async for chunk in LLMMultiService(llm_service).stream_progressive(
            prompt="hello",
            models=["deepseek", "qwen"],
        ):
            chunks.append(chunk)
        gc.collect()
    finally:
        loop.set_exception_handler(None)

    errors = [item for item in chunks if item.get("event") == "error"]
    completes = [item for item in chunks if item.get("event") == "complete"]
    assert len(errors) == 1
    assert errors[0]["llm"] == "deepseek"
    assert "timeout" in str(errors[0]["error"]).lower()
    assert len(completes) == 1
    assert completes[0]["llm"] == "qwen"
    assert not any("never retrieved" in message for message in leaked)


@pytest.mark.asyncio
async def test_stream_progressive_close_cancels_inflight_task() -> None:
    """Leaving the stream cancels the provider task instead of orphaning it."""
    cancelled = asyncio.Event()
    llm_service = _llm_with_stream(_blocking_stream(cancelled))
    loop = asyncio.get_running_loop()
    leaked = _capture_unretrieved(loop)

    async def _consume() -> None:
        async for _chunk in LLMMultiService(llm_service).stream_progressive(
            prompt="hello",
            models=["deepseek"],
        ):
            break

    consumer = asyncio.create_task(_consume())
    try:
        await asyncio.sleep(0.05)
        consumer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consumer
        await asyncio.wait_for(cancelled.wait(), timeout=2)
        gc.collect()
    finally:
        loop.set_exception_handler(None)

    assert cancelled.is_set()
    assert not any("never retrieved" in message for message in leaked)


@pytest.mark.asyncio
async def test_generate_multi_timeout_is_per_model_failure() -> None:
    """A provider timeout fails that model and lets the others return."""
    llm_service = _llm_with_stream(_timeout_then_ok_stream)
    llm_service.chat = _chat_by_model
    llm_service.performance_tracker.can_call_model.return_value = True

    results = await LLMMultiService(llm_service).generate_multi(
        prompt="hello",
        models=["deepseek", "qwen"],
    )

    assert results["deepseek"]["success"] is False
    assert "timeout" in str(results["deepseek"]["error"]).lower()
    assert results["qwen"]["success"] is True
    assert results["qwen"]["response"] == "ok"


@pytest.mark.asyncio
async def test_generate_multi_user_limit_propagates() -> None:
    """A daily cap is not stored as a per-model provider failure."""
    llm_service = _llm_with_stream(_timeout_then_ok_stream)
    cap = UserDailyTokenCapExceededError(cap=1, used=1, user_message="limit")

    async def _chat(**_kwargs: object) -> str:
        raise cap

    llm_service.chat = _chat
    llm_service.performance_tracker.can_call_model.return_value = True

    with pytest.raises(UserDailyTokenCapExceededError):
        await LLMMultiService(llm_service).generate_multi(prompt="hello", models=["qwen"])


async def _chat_by_model(**kwargs: object) -> str:
    if kwargs.get("model") == "deepseek":
        raise LLMTimeoutError("DeepSeek API timeout")
    return "ok"
