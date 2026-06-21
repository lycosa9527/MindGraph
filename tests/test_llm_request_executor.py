"""LLM request executor — doubao no-retry and per-attempt timeout for others."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.infrastructure.http.error_handler import LLMServiceError
from services.llm.llm_request_executor import LLMRequestExecutor
from services.llm.llm_utils import LLMUtils


def test_is_no_retry_model_doubao_only() -> None:
    """Doubao / ark-doubao skip retry; kimi still retries."""
    assert LLMUtils.is_no_retry_model("doubao", "ark-doubao") is True
    assert LLMUtils.is_no_retry_model("kimi", "ark-kimi") is False
    assert LLMUtils.is_no_retry_model("qwen", "qwen") is False


@pytest.mark.asyncio
async def test_execute_chat_request_doubao_single_attempt_no_retry() -> None:
    """Doubao uses one attempt only (no with_retry)."""
    client = AsyncMock()
    client.async_chat_completion = AsyncMock(side_effect=asyncio.TimeoutError())

    with patch(
        "services.llm.llm_request_executor.error_handler.with_retry",
        new_callable=AsyncMock,
    ) as mock_retry:
        with pytest.raises(asyncio.TimeoutError):
            await LLMRequestExecutor.execute_chat_request(
                client=client,
                messages=[{"role": "user", "content": "hi"}],
                rate_limiter=None,
                timeout=0.05,
                model="doubao",
                actual_model="ark-doubao",
            )
        mock_retry.assert_not_called()


@pytest.mark.asyncio
async def test_execute_chat_request_qwen_uses_retry() -> None:
    """Non-doubao models delegate to with_retry."""
    client = AsyncMock()
    client.chat_completion = AsyncMock(return_value={"content": "ok", "usage": {}})

    with patch(
        "services.llm.llm_request_executor.error_handler.with_retry",
        new_callable=AsyncMock,
        return_value={"content": "ok", "usage": {}},
    ) as mock_retry:
        with patch(
            "services.llm.llm_request_executor.error_handler.validate_response",
            return_value={"content": "ok", "usage": {}},
        ):
            result = await LLMRequestExecutor.execute_chat_request(
                client=client,
                messages=[{"role": "user", "content": "hi"}],
                rate_limiter=None,
                timeout=30.0,
                model="qwen",
                actual_model="qwen",
            )
        mock_retry.assert_awaited_once()
        assert result["content"] == "ok"


@pytest.mark.asyncio
async def test_execute_chat_request_qwen_propagates_retry_failure() -> None:
    """with_retry failures bubble up for non-doubao models."""
    client = MagicMock()

    with patch(
        "services.llm.llm_request_executor.error_handler.with_retry",
        new_callable=AsyncMock,
        side_effect=LLMServiceError("all attempts failed"),
    ):
        with pytest.raises(LLMServiceError):
            await LLMRequestExecutor.execute_chat_request(
                client=client,
                messages=[{"role": "user", "content": "hi"}],
                rate_limiter=None,
                timeout=30.0,
                model="qwen",
                actual_model="qwen",
            )
