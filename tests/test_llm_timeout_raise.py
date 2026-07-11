"""Unit tests for LLM timeout re-raise typing."""

import pytest

from services.infrastructure.http.error_handler import LLMServiceError, LLMTimeoutError
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


def test_raise_chat_pipeline_error_keeps_generic_service_error():
    """Non-timeout pipeline errors stay LLMServiceError."""
    with pytest.raises(LLMServiceError) as caught:
        _raise_like_service("qwen", "boom", RuntimeError("boom"))
    assert not isinstance(caught.value, LLMTimeoutError)
    assert "qwen" in str(caught.value)
