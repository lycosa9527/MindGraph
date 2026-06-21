"""Tests for thinking coin wallet credit/debit."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.auth.thinking_coin import wallet_service as wallet_mod


@pytest.mark.asyncio
async def test_debit_wallet_raises_when_insufficient() -> None:
    """Debit fails when balance is below amount."""
    db = AsyncMock()
    wallet = MagicMock()
    wallet.balance = 3
    db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=wallet))
    )

    with pytest.raises(ValueError, match="insufficient_thinking_coins"):
        await wallet_mod.debit_wallet(db, 1, 6, "ai_spend")


@pytest.mark.asyncio
async def test_credit_wallet_skips_non_positive_amount() -> None:
    """Zero or negative credit is a no-op."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    balance = await wallet_mod.credit_wallet(db, 9, 0, "task_reward")
    assert balance == 0
