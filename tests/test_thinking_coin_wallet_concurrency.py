"""Tests for wallet row locking and debit safety."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from services.auth.thinking_coin import usage_wire as usage_wire_mod
from services.auth.thinking_coin import wallet_service as wallet_mod
from services.infrastructure.http.error_handler import ThinkingCoinInsufficientError


@pytest.mark.asyncio
async def test_get_or_create_wallet_uses_for_update() -> None:
    """Wallet pre-flight locks the row to prevent TOCTOU races."""
    db = AsyncMock()
    wallet = MagicMock()
    wallet.user_id = 42
    wallet.balance = 12
    wallet.daily_balance = 0
    wallet.daily_balance_date = None
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


class _PgError(Exception):
    """Stand-in for a psycopg error that carries a SQLSTATE."""

    def __init__(self, sqlstate: str) -> None:
        super().__init__(sqlstate)
        self.sqlstate = sqlstate


class _Savepoint:
    """Async savepoint that rolls back when the nested flush raises."""

    async def __aenter__(self) -> "_Savepoint":
        return self

    async def __aexit__(self, exc_type, _exc, _tb) -> bool:
        return False


@pytest.mark.asyncio
async def test_get_or_create_wallet_reloads_after_unique_violation() -> None:
    """A concurrent insert on the wallet primary key is re-read instead of failing the request."""
    db = AsyncMock()
    existing = MagicMock()
    existing.user_id = 6470
    existing.balance = 0
    existing.daily_balance = 0
    existing.daily_balance_date = None
    missing = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    found = MagicMock(scalar_one_or_none=MagicMock(return_value=existing))
    db.execute = AsyncMock(side_effect=[missing, found])
    db.begin_nested = MagicMock(return_value=_Savepoint())
    db.add = MagicMock()
    db.flush = AsyncMock(
        side_effect=IntegrityError("INSERT", {"user_id": 6470}, _PgError("23505")),
    )

    result = await wallet_mod.get_or_create_wallet(db, 6470)

    assert result is existing
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_get_or_create_wallet_reraises_non_unique_integrity_error() -> None:
    """A check-constraint failure is not treated as a lost insert race."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    db.begin_nested = MagicMock(return_value=_Savepoint())
    db.add = MagicMock()
    db.flush = AsyncMock(
        side_effect=IntegrityError("INSERT", {"user_id": 1}, _PgError("23514")),
    )

    with pytest.raises(IntegrityError):
        await wallet_mod.get_or_create_wallet(db, 1)

    assert db.execute.await_count == 1


@pytest.mark.asyncio
async def test_assert_llm_budget_raises_when_balance_low(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-flight budget check fails when locked balance is too low."""
    monkeypatch.setenv("FEATURE_THINKING_COINS", "true")

    async def always_apply(*_args, **_kwargs) -> bool:
        return True

    class _FakeDbSession:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return AsyncMock()

        async def __aexit__(self, *_exc):
            return False

    async def locked_assert_fail(*_args, **_kwargs) -> int:
        raise ThinkingCoinInsufficientError(balance=2, cost=6, user_message="low")

    monkeypatch.setattr(usage_wire_mod, "thinking_coins_apply_to_user", always_apply)
    monkeypatch.setattr(usage_wire_mod, "user_rls_session", _FakeDbSession)
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
    wallet.user_id = 1
    wallet.balance = 8
    wallet.daily_balance = 0
    wallet.daily_balance_date = None
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=wallet)))
    db.add = MagicMock()
    db.flush = AsyncMock()

    balance = await wallet_mod.debit_wallet(db, 1, 6, "ai_spend")
    assert balance == 2
    assert wallet.balance == 2

    with pytest.raises(ValueError, match="insufficient_thinking_coins"):
        await wallet_mod.debit_wallet(db, 1, 6, "ai_spend")
