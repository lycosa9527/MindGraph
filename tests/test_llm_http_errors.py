"""Shared LLM → HTTP mapping for API routes."""

from __future__ import annotations

import pytest

from services.infrastructure.http.error_handler import (
    LLMAccessDeniedError,
    LLMContentFilterError,
    LLMProviderError,
    LLMRateLimitError,
    LLMServiceError,
    LLMTimeoutError,
    attach_llm_user_message,
    error_handler,
)
from services.infrastructure.http.llm_http_errors import (
    CONTENT_FILTER_ERROR_TYPE,
    http_exception_for_llm_error,
    is_llm_content_filter_detail,
    should_record_http_exception,
)
from services.llm.error_parsers.dashscope_error_parser import parse_and_raise_dashscope_error


def _detail_map(detail: object) -> dict[str, str]:
    """HTTPException.detail is str | list in stubs; content-filter uses a dict."""
    assert isinstance(detail, dict)
    return {str(key): str(value) for key, value in detail.items()}


def test_access_denied_maps_to_502() -> None:
    """Provider API key / access failures are upstream 502, not client 401/403."""
    exc = http_exception_for_llm_error(LLMAccessDeniedError("Invalid API-key provided."))
    assert exc.status_code == 502
    assert "Invalid API-key" in str(exc.detail)


def test_rate_limit_maps_to_429() -> None:
    """Provider throttle becomes HTTP 429."""
    exc = http_exception_for_llm_error(LLMRateLimitError("throttled"))
    assert exc.status_code == 429


def test_timeout_maps_to_504() -> None:
    """Upstream timeout becomes HTTP 504."""
    exc = http_exception_for_llm_error(LLMTimeoutError("timed out"))
    assert exc.status_code == 504


def test_content_filter_maps_to_400() -> None:
    """Content-filter refusals become HTTP 400 with a stable error_type."""
    exc = http_exception_for_llm_error(LLMContentFilterError("filtered"))
    assert exc.status_code == 400
    detail = _detail_map(exc.detail)
    assert detail["error_type"] == CONTENT_FILTER_ERROR_TYPE
    assert "filtered" in detail["message"]


def test_wrapped_retry_content_filter_maps_to_400() -> None:
    """Retry leftovers still map to 400 so they are not collected as 502."""
    wrapped = LLMServiceError(
        "All 3 attempts failed. Last error: Content filter: Input text data may contain inappropriate content."
    )
    exc = http_exception_for_llm_error(wrapped)
    assert exc.status_code == 400
    assert _detail_map(exc.detail)["error_type"] == CONTENT_FILTER_ERROR_TYPE


def test_attach_preserves_content_filter_type() -> None:
    """DashScope attach must not wrap LLMContentFilterError into LLMProviderError."""
    original = LLMContentFilterError("Content filter: blocked")
    attached = attach_llm_user_message(original, "请修改输入内容")
    assert isinstance(attached, LLMContentFilterError)
    assert attached.user_message == "请修改输入内容"
    mapped = http_exception_for_llm_error(attached)
    assert mapped.status_code == 400
    assert _detail_map(mapped.detail)["error_type"] == CONTENT_FILTER_ERROR_TYPE


def test_attach_still_sets_provider_user_message() -> None:
    """Provider errors keep their type and gain user_message."""
    original = LLMProviderError("upstream", provider="dashscope", error_code="Throttling")
    attached = attach_llm_user_message(original, "请稍后重试")
    assert isinstance(attached, LLMProviderError)
    assert attached is original
    assert attached.user_message == "请稍后重试"


def test_content_filter_http_is_not_recorded() -> None:
    """Safety refusals must not enter admin error collection."""
    assert should_record_http_exception(400, {"error_type": CONTENT_FILTER_ERROR_TYPE}) is False
    assert (
        should_record_http_exception(
            502,
            "All 3 attempts failed. Last error: Content filter: Input text data may contain inappropriate content.",
        )
        is False
    )
    assert should_record_http_exception(502, "Qwen API timeout") is True
    assert should_record_http_exception(502, "输入可能包含不当内容，请修改输入内容") is False
    assert is_llm_content_filter_detail("Generation failed: Content filter: blocked") is True


@pytest.mark.asyncio
async def test_with_retry_does_not_retry_content_filter() -> None:
    """Content-filter refusals are deterministic — one attempt only."""
    calls = {"n": 0}

    async def boom() -> None:
        calls["n"] += 1
        raise LLMContentFilterError("Content filter: blocked")

    with pytest.raises(LLMContentFilterError):
        await error_handler.with_retry(boom)
    assert calls["n"] == 1


def test_dashscope_parse_raises_content_filter_type() -> None:
    """DataInspectionFailed stays LLMContentFilterError after attach."""
    with pytest.raises(LLMContentFilterError) as caught:
        parse_and_raise_dashscope_error(
            400,
            '{"code":"DataInspectionFailed","message":"Input text data may contain inappropriate content."}',
            {
                "code": "DataInspectionFailed",
                "message": "Input text data may contain inappropriate content.",
            },
        )
    assert "inappropriate" in str(caught.value).lower()
    assert caught.value.user_message
    mapped = http_exception_for_llm_error(caught.value)
    assert mapped.status_code == 400
    assert _detail_map(mapped.detail)["error_type"] == CONTENT_FILTER_ERROR_TYPE
