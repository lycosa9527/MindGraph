"""Tests for daily login coin expiry at Beijing midnight."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.auth.thinking_coin import wallet_service as wallet_mod
from utils.auth.thinking_coin_config import LEDGER_DAILY_EXPIRE


def _wallet(
    *,
    balance: int,
    daily_balance: int = 0,
    daily_balance_date: date | None = None,
    user_id: int = 1,
) -> MagicMock:
    wallet = MagicMock()
    wallet.user_id = user_id
    wallet.balance = balance
    wallet.daily_balance = daily_balance
    wallet.daily_balance_date = daily_balance_date
    return wallet


@pytest.mark.asyncio
async def test_expire_stale_daily_balance_clears_unused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unused daily login coins are removed after Beijing day rollover."""
    today = date(2026, 8, 5)
    yesterday = today - timedelta(days=1)
    monkeypatch.setattr(wallet_mod, "beijing_date_today", lambda: today)

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.info = {}
    wallet = _wallet(balance=225, daily_balance=25, daily_balance_date=yesterday)
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=wallet)))

    result = await wallet_mod.get_or_create_wallet(db, 1)
    assert result is wallet
    assert wallet.balance == 200
    assert wallet.daily_balance == 0
    assert wallet.daily_balance_date == today
    assert db.info.get("thinking_coin_daily_expired") == 25
    ledger = db.add.call_args.args[0]
    assert ledger.reason == LEDGER_DAILY_EXPIRE
    assert ledger.delta == -25


@pytest.mark.asyncio
async def test_credit_daily_tags_same_day_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Check-in credits increase daily_balance for today."""
    today = date(2026, 8, 5)
    monkeypatch.setattr(wallet_mod, "beijing_date_today", lambda: today)

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    wallet = _wallet(balance=200, daily_balance=0, daily_balance_date=None)
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=wallet)))

    balance = await wallet_mod.credit_wallet(db, 1, 25, "daily_checkin", daily=True)
    assert balance == 225
    assert wallet.daily_balance == 25
    assert wallet.daily_balance_date == today


@pytest.mark.asyncio
async def test_debit_consumes_daily_bucket_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AI spend draws from daily login coins before persistent balance."""
    today = date(2026, 8, 5)
    monkeypatch.setattr(wallet_mod, "beijing_date_today", lambda: today)

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    wallet = _wallet(balance=225, daily_balance=25, daily_balance_date=today)
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=wallet)))

    balance = await wallet_mod.debit_wallet(db, 1, 10, "ai_spend")
    assert balance == 215
    assert wallet.daily_balance == 15


@pytest.mark.asyncio
async def test_same_day_wallet_does_not_expire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Daily coins for the current Beijing day remain available."""
    today = date(2026, 8, 5)
    monkeypatch.setattr(wallet_mod, "beijing_date_today", lambda: today)

    db = AsyncMock()
    db.flush = AsyncMock()
    db.info = {}
    wallet = _wallet(balance=225, daily_balance=25, daily_balance_date=today)
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=wallet)))

    await wallet_mod.get_or_create_wallet(db, 1)
    assert wallet.balance == 225
    assert wallet.daily_balance == 25
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_debit_ignores_daily_bucket_without_today_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Orphan daily_balance without today's date is not spent as daily."""
    today = date(2026, 8, 5)
    monkeypatch.setattr(wallet_mod, "beijing_date_today", lambda: today)

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.info = {}
    wallet = _wallet(balance=100, daily_balance=25, daily_balance_date=None)
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=wallet)))

    balance = await wallet_mod.debit_wallet(db, 1, 10, "ai_spend")
    assert balance == 90
    assert wallet.daily_balance == 0
    assert wallet.balance == 90


@pytest.mark.asyncio
async def test_commit_wallet_changes_when_expiry_marked() -> None:
    """Expiry marker forces a commit even when no earn/spend occurred."""
    db = AsyncMock()
    db.info = {"thinking_coin_daily_expired": 25}
    db.commit = AsyncMock()

    await wallet_mod.commit_wallet_changes(db, force=False)
    db.commit.assert_awaited_once()
    assert "thinking_coin_daily_expired" not in db.info


@pytest.mark.asyncio
async def test_expire_marks_session_for_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stale daily expiry records amount on the session for caller commit."""
    today = date(2026, 8, 5)
    yesterday = today - timedelta(days=1)
    monkeypatch.setattr(wallet_mod, "beijing_date_today", lambda: today)

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.info = {}
    wallet = _wallet(balance=225, daily_balance=25, daily_balance_date=yesterday)
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=wallet)))

    await wallet_mod.get_or_create_wallet(db, 1)
    assert db.info.get("thinking_coin_daily_expired") == 25
