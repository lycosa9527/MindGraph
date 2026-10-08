"""DashScope windows that must not share another model's provider quota."""

from __future__ import annotations

from typing import Optional

from services.infrastructure.rate_limiting.rate_limiter import DashscopeRateLimiter


class _DashscopeModelLimiters:
    """Process holder so chat routing can see the Qwen windows."""

    def __init__(self) -> None:
        self.qwen: Optional[DashscopeRateLimiter] = None
        self.qwen38: Optional[DashscopeRateLimiter] = None


_STATE = _DashscopeModelLimiters()


def set_dashscope_model_limiters(
    qwen: Optional[DashscopeRateLimiter],
    qwen38: Optional[DashscopeRateLimiter],
) -> None:
    """Install the Qwen limiters created during LLM service startup."""
    _STATE.qwen = qwen
    _STATE.qwen38 = qwen38


def qwen_rate_limiter() -> Optional[DashscopeRateLimiter]:
    """qwen3.6-flash window, or None when DashScope limiting is off."""
    return _STATE.qwen


def qwen38_rate_limiter() -> Optional[DashscopeRateLimiter]:
    """qwen3.8-flash window, or None when DashScope limiting is off."""
    return _STATE.qwen38
