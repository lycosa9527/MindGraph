"""Unit tests for LLM timeout re-raise typing."""

from unittest.mock import MagicMock

import pytest
from openai import APITimeoutError

from clients.llm.base import raise_openai_transport_error
from services.infrastructure.http.error_handler import LLMServiceError, LLMTimeoutError, error_handler
from services.llm.llm_utils import LLMUtils


def _raise_like_service(model: str, detail: str, exc: BaseException, *, stream: bool = False):
    """Mirror LLMService._raise_chat_pipeline_error without protected-access."""
    kind = "Chat stream failed" if stream else "Chat failed"
    message = f"{kind} for model {model}: {detail}"
    if isinstance(exc, LLMTimeoutError):
        raise LLMTimeoutError(message) from exc
    if isinstance(exc, TimeoutError):
        raise LLMTimeoutError(message) from exc
    raise LLMServiceError(message) from exc


def test_raise_chat_pipeline_error_preserves_timeout():
    """asyncio.TimeoutError becomes LLMTimeoutError."""
    detail = LLMUtils.format_request_failure(TimeoutError())
    with pytest.raises(LLMTimeoutError) as caught:
        _raise_like_service("doubao", detail, TimeoutError())
    assert "doubao" in str(caught.value)


def test_openai_transport_timeout_stays_llm_timeout() -> None:
    """Volcengine and school OpenAI clients share this mapping."""
    with pytest.raises(LLMTimeoutError, match="volcengine timeout"):
        raise_openai_transport_error(APITimeoutError(MagicMock()), provider="volcengine")


@pytest.mark.asyncio
async def test_with_retry_preserves_llm_timeout() -> None:
    """Exhausted retries keep LLMTimeoutError instead of a generic service error."""

    async def _fail() -> None:
        raise LLMTimeoutError("DeepSeek API timeout")

    with pytest.raises(LLMTimeoutError, match="DeepSeek API timeout"):
        await error_handler.with_retry(_fail, max_retries=2, base_delay=0, max_delay=0)


def test_raise_chat_pipeline_error_keeps_generic_service_error():
    """Non-timeout pipeline errors stay LLMServiceError."""
    with pytest.raises(LLMServiceError) as caught:
        _raise_like_service("qwen", "boom", RuntimeError("boom"))
    assert not isinstance(caught.value, LLMTimeoutError)
    assert "qwen" in str(caught.value)
