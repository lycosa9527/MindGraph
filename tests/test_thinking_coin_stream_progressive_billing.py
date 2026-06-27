"""Tests for stream_progressive single-debit billing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.llm.llm_multi_service import LLMMultiService
from utils.auth.thinking_coin_config import THINKING_COIN_MODE_BATCH_INNER


@pytest.mark.asyncio
async def test_stream_progressive_passes_batch_inner_to_chat_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inner LLM streams skip per-call thinking coin assert/settle."""
    llm_service = MagicMock()
    llm_service.load_balancer = None
    captured_modes: list[str] = []

    async def fake_chat_stream(**kwargs):
        captured_modes.append(str(kwargs.get("thinking_coin_mode")))
        yield {"type": "token", "content": "a"}
        yield {"type": "usage", "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}}

    llm_service.chat_stream = fake_chat_stream

    monkeypatch.setattr(
        "services.llm.llm_multi_service.assert_llm_usage_budget",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "services.llm.llm_multi_service.thinking_coins_apply_to_user",
        AsyncMock(return_value=False),
    )

    service = LLMMultiService(llm_service)
    chunks = []
    async for chunk in service.stream_progressive(
        prompt="hello",
        models=["qwen"],
        user_id=1,
        organization_id=2,
    ):
        chunks.append(chunk)

    assert captured_modes == [THINKING_COIN_MODE_BATCH_INNER]
    assert any(item.get("event") == "complete" for item in chunks)


@pytest.mark.asyncio
async def test_stream_progressive_yields_thinking_coins_footer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After batch settle, eligible users receive a thinking_coins SSE chunk."""
    from services.auth.thinking_coin.event_hub import ThinkingCoinMutation

    llm_service = MagicMock()
    llm_service.load_balancer = None

    async def fake_chat_stream(**_kwargs):
        yield {"type": "token", "content": "a"}
        yield {"type": "usage", "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}}

    llm_service.chat_stream = fake_chat_stream

    mutation = ThinkingCoinMutation(
        eligible=True,
        balance=88,
        credited=0,
        debited=6,
        task_slug=None,
    )

    monkeypatch.setattr(
        "services.llm.llm_multi_service.assert_llm_usage_budget",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "services.llm.llm_multi_service.thinking_coins_apply_to_user",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "services.llm.llm_multi_service.thinking_coin_post_llm_success_mutation",
        AsyncMock(return_value=mutation),
    )

    service = LLMMultiService(llm_service)
    chunks = []
    async for chunk in service.stream_progressive(
        prompt="hello",
        models=["qwen"],
        user_id=1,
        organization_id=2,
    ):
        chunks.append(chunk)

    coin_chunks = [item for item in chunks if item.get("event") == "thinking_coins"]
    assert len(coin_chunks) == 1
    assert coin_chunks[0]["thinking_coins"]["balance"] == 88
    assert coin_chunks[0]["thinking_coins"]["debited"] == 6
