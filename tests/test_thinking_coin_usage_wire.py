"""Tests for thinking coin LLM budget gate."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from services.auth.thinking_coin import usage_wire as usage_wire_mod
from services.infrastructure.http.error_handler import ThinkingCoinInsufficientError


class _FakeDbSession:
    """Minimal async session stub for usage_wire unit tests."""

    async def __aenter__(self):
        return AsyncMock()

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

    async def locked_assert_fail(*_args, **_kwargs) -> int:
        raise ThinkingCoinInsufficientError(balance=2, cost=6, user_message="low")

    monkeypatch.setattr(usage_wire_mod, "thinking_coins_apply_to_user", always_apply)
    monkeypatch.setattr(usage_wire_mod, "open_async_session", _FakeDbSession)
    monkeypatch.setattr(usage_wire_mod, "_assert_balance_with_lock", locked_assert_fail)

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
    monkeypatch.setattr(usage_wire_mod, "_assert_balance_with_lock", AsyncMock(return_value=6))

    result = await usage_wire_mod.assert_thinking_coin_llm_budget(99, 1, "mindmate")
    assert result is True
