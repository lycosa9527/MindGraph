"""Node palette logs a low thinking-coin balance as info, not an API fault."""

from __future__ import annotations

import logging

from routers.node_palette_streaming import _palette_llm_error_log
from services.infrastructure.http.error_handler import (
    LLMServiceError,
    ThinkingCoinInsufficientError,
    UserDailyTokenCapExceededError,
)


def test_thinking_coin_shortfall_is_info() -> None:
    """A trial user who cannot pay is an expected limit, not a service error."""
    error_type, level = _palette_llm_error_log(ThinkingCoinInsufficientError(balance=3, cost=4))
    assert error_type == "thinking_coin_insufficient"
    assert level == logging.INFO


def test_daily_token_cap_is_info() -> None:
    """The daily token cap uses the same expected-limit log level."""
    error_type, level = _palette_llm_error_log(UserDailyTokenCapExceededError(cap=100, used=100))
    assert error_type == "daily_token_cap"
    assert level == logging.INFO


def test_provider_failure_stays_error() -> None:
    """An unclassified LLM failure still logs at error."""
    error_type, level = _palette_llm_error_log(LLMServiceError("provider down"))
    assert error_type == "service_error"
    assert level == logging.ERROR
