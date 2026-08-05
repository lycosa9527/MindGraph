"""Wallet credit/debit and ledger writes."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.thinking_coin import ThinkingCoinLedger, ThinkingCoinWallet
from services.auth.thinking_coin.dates import beijing_date_today
from services.utils.error_types import DATABASE_ERRORS
from utils.auth.thinking_coin_config import LEDGER_DAILY_EXPIRE

logger = logging.getLogger(__name__)

_SESSION_EXPIRED_KEY = "thinking_coin_daily_expired"


def _mark_session_expired(db: AsyncSession, amount: int) -> None:
    if amount <= 0:
        return
    info = getattr(db, "info", None)
    if not isinstance(info, dict):
        return
    info[_SESSION_EXPIRED_KEY] = int(info.get(_SESSION_EXPIRED_KEY, 0)) + amount


def take_session_daily_expired(db: AsyncSession) -> int:
    """Return and clear expired-daily amount recorded on this session."""
    info = getattr(db, "info", None)
    if not isinstance(info, dict):
        return 0
    return int(info.pop(_SESSION_EXPIRED_KEY, 0) or 0)


def _clear_orphan_daily_bucket(wallet: ThinkingCoinWallet) -> bool:
    """Zero daily_balance when date is missing (corruption). Balance unchanged."""
    if wallet.daily_balance_date is not None:
        return False
    if int(wallet.daily_balance) <= 0:
        return False
    wallet.daily_balance = 0
    return True


def _expire_stale_daily_balance(db: AsyncSession, wallet: ThinkingCoinWallet) -> int:
    """Clear unused daily login coins after Beijing midnight. Returns expired amount."""
    today = beijing_date_today()
    daily_date = wallet.daily_balance_date
    if daily_date is None or daily_date >= today:
        return 0

    expired = min(int(wallet.daily_balance), int(wallet.balance))
    wallet.daily_balance = 0
    wallet.daily_balance_date = today
    if expired <= 0:
        return 0

    wallet.balance = int(wallet.balance) - expired
    db.add(
        ThinkingCoinLedger(
            user_id=int(wallet.user_id),
            delta=-expired,
            balance_after=int(wallet.balance),
            reason=LEDGER_DAILY_EXPIRE,
            ref_type="daily_balance",
            ref_id=str(daily_date),
        )
    )
    return expired


async def get_or_create_wallet(db: AsyncSession, user_id: int) -> ThinkingCoinWallet:
    """Fetch wallet row, creating with zero balance if missing. Expires stale daily coins."""
    wallet = (
        await db.execute(select(ThinkingCoinWallet).where(ThinkingCoinWallet.user_id == user_id).with_for_update())
    ).scalar_one_or_none()
    if wallet is None:
        wallet = ThinkingCoinWallet(
            user_id=user_id,
            balance=0,
            daily_balance=0,
            daily_balance_date=None,
        )
        db.add(wallet)
        await db.flush()
        return wallet

    orphan_cleared = _clear_orphan_daily_bucket(wallet)
    expired = _expire_stale_daily_balance(db, wallet)
    if orphan_cleared or expired > 0:
        await db.flush()
    if expired > 0:
        _mark_session_expired(db, expired)
    return wallet


async def get_balance(db: AsyncSession, user_id: int) -> int:
    """Current balance after lazy daily-login expiry (0 if no wallet)."""
    wallet = (
        await db.execute(select(ThinkingCoinWallet).where(ThinkingCoinWallet.user_id == user_id))
    ).scalar_one_or_none()
    if wallet is None:
        return 0
    if wallet.daily_balance_date is not None and wallet.daily_balance_date < beijing_date_today():
        wallet = await get_or_create_wallet(db, user_id)
    return int(wallet.balance)


async def get_daily_balance(db: AsyncSession, user_id: int) -> int:
    """Unused daily login coins for the current Beijing day (0 if none)."""
    wallet = (
        await db.execute(select(ThinkingCoinWallet).where(ThinkingCoinWallet.user_id == user_id))
    ).scalar_one_or_none()
    if wallet is None:
        return 0
    if wallet.daily_balance_date is not None and wallet.daily_balance_date < beijing_date_today():
        wallet = await get_or_create_wallet(db, user_id)
    if wallet.daily_balance_date != beijing_date_today():
        return 0
    return int(wallet.daily_balance)


async def credit_wallet(
    db: AsyncSession,
    user_id: int,
    amount: int,
    reason: str,
    *,
    ref_type: Optional[str] = None,
    ref_id: Optional[str] = None,
    daily: bool = False,
) -> int:
    """Credit coins; returns new balance.

    When ``daily`` is True, coins are tagged as same-day login reward and expire
    at the next Beijing midnight if unused.
    """
    if amount <= 0:
        return await get_balance(db, user_id)
    wallet = await get_or_create_wallet(db, user_id)
    wallet.balance = int(wallet.balance) + amount
    if daily:
        today = beijing_date_today()
        if wallet.daily_balance_date != today:
            wallet.daily_balance = 0
            wallet.daily_balance_date = today
        wallet.daily_balance = int(wallet.daily_balance) + amount
    db.add(
        ThinkingCoinLedger(
            user_id=user_id,
            delta=amount,
            balance_after=int(wallet.balance),
            reason=reason,
            ref_type=ref_type,
            ref_id=ref_id,
        )
    )
    await db.flush()
    return int(wallet.balance)


async def debit_wallet(
    db: AsyncSession,
    user_id: int,
    amount: int,
    reason: str,
    *,
    ref_type: Optional[str] = None,
    ref_id: Optional[str] = None,
) -> int:
    """Debit coins (daily login bucket first); raises ValueError if insufficient."""
    if amount <= 0:
        return await get_balance(db, user_id)
    wallet = await get_or_create_wallet(db, user_id)
    if int(wallet.balance) < amount:
        raise ValueError("insufficient_thinking_coins")

    today = beijing_date_today()
    from_daily = 0
    if wallet.daily_balance_date == today:
        from_daily = min(int(wallet.daily_balance), amount)
    if from_daily > 0:
        wallet.daily_balance = int(wallet.daily_balance) - from_daily
    wallet.balance = int(wallet.balance) - amount
    db.add(
        ThinkingCoinLedger(
            user_id=user_id,
            delta=-amount,
            balance_after=int(wallet.balance),
            reason=reason,
            ref_type=ref_type,
            ref_id=ref_id,
        )
    )
    await db.flush()
    return int(wallet.balance)


async def safe_commit(db: AsyncSession) -> None:
    """Commit thinking coin transaction."""
    try:
        await db.commit()
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error("[ThinkingCoin] commit failed: %s", exc, exc_info=True)
        raise
    finally:
        take_session_daily_expired(db)


async def commit_wallet_changes(db: AsyncSession, *, force: bool = False) -> None:
    """Commit when ``force`` or when lazy daily expiry dirtied this session."""
    expired = take_session_daily_expired(db)
    if force or expired > 0:
        await safe_commit(db)
