"""Tests for thinking coin LLM budget gate."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from services.auth.thinking_coin import usage_wire as usage_wire_mod
from services.infrastructure.http.error_handler import ThinkingCoinInsufficientError


class _FakeDbSession:
    """Minimal async session stub for usage_wire unit tests."""

    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_exc):
        return False


@pytest.mark.asyncio
async def test_assert_skips_when_feature_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-eligible callers fall through to daily token cap."""
    monkeypatch.delenv("FEATURE_THINKING_COINS", raising=False)
    result = await usage_wire_mod.assert_thinking_coin_llm_budget(1, 1, "mindmate")
    assert result is False


@pytest.mark.asyncio
async def test_assert_raises_when_balance_too_low(monkeypatch: pytest.MonkeyPatch) -> None:
    """Insufficient balance raises ThinkingCoinInsufficientError."""
    monkeypatch.setenv("FEATURE_THINKING_COINS", "true")

    async def always_apply(*_args, **_kwargs) -> bool:
        return True

    monkeypatch.setattr(usage_wire_mod, "thinking_coins_apply_to_user", always_apply)
    monkeypatch.setattr(usage_wire_mod, "open_async_session", _FakeDbSession)
    monkeypatch.setattr(usage_wire_mod, "get_cost_for_request_type", AsyncMock(return_value=6))
    monkeypatch.setattr(usage_wire_mod, "get_balance", AsyncMock(return_value=2))

    with pytest.raises(ThinkingCoinInsufficientError) as exc_info:
        await usage_wire_mod.assert_thinking_coin_llm_budget(99, 1, "mindmate", lang="zh")

    assert exc_info.value.balance == 2
    assert exc_info.value.cost == 6


@pytest.mark.asyncio
async def test_assert_passes_when_balance_covers_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sufficient balance returns True (skip daily token cap)."""
    monkeypatch.setenv("FEATURE_THINKING_COINS", "true")

    async def always_apply(*_args, **_kwargs) -> bool:
        return True

    monkeypatch.setattr(usage_wire_mod, "thinking_coins_apply_to_user", always_apply)
    monkeypatch.setattr(usage_wire_mod, "open_async_session", _FakeDbSession)
    monkeypatch.setattr(usage_wire_mod, "get_cost_for_request_type", AsyncMock(return_value=6))
    monkeypatch.setattr(usage_wire_mod, "get_balance", AsyncMock(return_value=100))

    result = await usage_wire_mod.assert_thinking_coin_llm_budget(99, 1, "mindmate")
    assert result is True
