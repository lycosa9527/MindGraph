"""Tests for wallet row locking and debit safety."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from services.auth.thinking_coin import usage_wire as usage_wire_mod
from services.auth.thinking_coin import wallet_service as wallet_mod
from services.infrastructure.http.error_handler import ThinkingCoinInsufficientError


@pytest.mark.asyncio
async def test_get_or_create_wallet_uses_for_update() -> None:
    """Wallet pre-flight locks the row to prevent TOCTOU races."""
    db = AsyncMock()
    wallet = MagicMock()
    wallet.balance = 12
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=wallet)))

    result = await wallet_mod.get_or_create_wallet(db, 42)
    assert result is wallet
    stmt = db.execute.await_args.args[0]
    compiled = str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).upper()
    assert "FOR UPDATE" in compiled


@pytest.mark.asyncio
async def test_assert_llm_budget_raises_when_balance_low(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-flight budget check fails when locked balance is too low."""
    monkeypatch.setenv("FEATURE_THINKING_COINS", "true")

    async def always_apply(*_args, **_kwargs) -> bool:
        return True

    class _FakeDbSession:
        async def __aenter__(self):
            return AsyncMock()

        async def __aexit__(self, *_exc):
            return False

    async def locked_assert_fail(*_args, **_kwargs) -> int:
        raise ThinkingCoinInsufficientError(balance=2, cost=6, user_message="low")

    monkeypatch.setattr(usage_wire_mod, "thinking_coins_apply_to_user", always_apply)
    monkeypatch.setattr(usage_wire_mod, "open_async_session", _FakeDbSession)
    monkeypatch.setattr(usage_wire_mod, "_assert_balance_with_lock", locked_assert_fail)

    with pytest.raises(ThinkingCoinInsufficientError) as exc_info:
        await usage_wire_mod.assert_thinking_coin_llm_budget(9, 1, "node_palette", lang="en")

    assert exc_info.value.balance == 2
    assert exc_info.value.cost == 6


@pytest.mark.asyncio
async def test_debit_wallet_serial_failure_on_insufficient() -> None:
    """Second debit fails when balance was consumed by first debit."""
    db = AsyncMock()
    wallet = MagicMock()
    wallet.balance = 8
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=wallet)))
    db.add = MagicMock()
    db.flush = AsyncMock()

    balance = await wallet_mod.debit_wallet(db, 1, 6, "ai_spend")
    assert balance == 2
    assert wallet.balance == 2

    with pytest.raises(ValueError, match="insufficient_thinking_coins"):
        await wallet_mod.debit_wallet(db, 1, 6, "ai_spend")
