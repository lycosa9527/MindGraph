"""Wallet credit/debit and ledger writes."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.thinking_coin import ThinkingCoinLedger, ThinkingCoinWallet
from services.utils.error_types import DATABASE_ERRORS

logger = logging.getLogger(__name__)


async def get_or_create_wallet(db: AsyncSession, user_id: int) -> ThinkingCoinWallet:
    """Fetch wallet row, creating with zero balance if missing."""
    wallet = (
        await db.execute(
            select(ThinkingCoinWallet)
            .where(ThinkingCoinWallet.user_id == user_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if wallet is not None:
        return wallet
    wallet = ThinkingCoinWallet(user_id=user_id, balance=0)
    db.add(wallet)
    await db.flush()
    return wallet


async def get_balance(db: AsyncSession, user_id: int) -> int:
    """Current balance (0 if no wallet)."""
    wallet = (
        await db.execute(select(ThinkingCoinWallet).where(ThinkingCoinWallet.user_id == user_id))
    ).scalar_one_or_none()
    return int(wallet.balance) if wallet is not None else 0


async def credit_wallet(
    db: AsyncSession,
    user_id: int,
    amount: int,
    reason: str,
    *,
    ref_type: Optional[str] = None,
    ref_id: Optional[str] = None,
) -> int:
    """Credit coins; returns new balance."""
    if amount <= 0:
        return await get_balance(db, user_id)
    wallet = await get_or_create_wallet(db, user_id)
    wallet.balance = int(wallet.balance) + amount
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
    """Debit coins; raises ValueError if insufficient."""
    if amount <= 0:
        return await get_balance(db, user_id)
    wallet = await get_or_create_wallet(db, user_id)
    if int(wallet.balance) < amount:
        raise ValueError("insufficient_thinking_coins")
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
