"""Shared LLM → HTTP mapping for API routes."""

from __future__ import annotations

from services.infrastructure.http.error_handler import (
    LLMAccessDeniedError,
    LLMContentFilterError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from services.infrastructure.http.llm_http_errors import http_exception_for_llm_error


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
    """Content-filter refusals become HTTP 400."""
    exc = http_exception_for_llm_error(LLMContentFilterError("filtered"))
    assert exc.status_code == 400
