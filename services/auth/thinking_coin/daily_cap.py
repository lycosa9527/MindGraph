"""Daily earn cap across task rewards."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.thinking_coin import ThinkingCoinLedger
from services.auth.thinking_coin.dates import beijing_day_utc_bounds
from services.auth.thinking_coin.task_registry import get_daily_earn_cap
from utils.auth.thinking_coin_config import (
    LEDGER_CASE,
    LEDGER_DAILY_CHECKIN,
    LEDGER_REFERRAL,
    LEDGER_TASK,
)

_DAILY_EARN_REASONS = frozenset(
    {
        LEDGER_DAILY_CHECKIN,
        LEDGER_TASK,
        LEDGER_REFERRAL,
        LEDGER_CASE,
    }
)


async def daily_earn_total_today(db: AsyncSession, user_id: int) -> int:
    """Sum of positive task earn credits for the current Beijing day."""
    day_start, day_end = beijing_day_utc_bounds()
    total = (
        await db.execute(
            select(func.coalesce(func.sum(ThinkingCoinLedger.delta), 0)).where(
                ThinkingCoinLedger.user_id == user_id,
                ThinkingCoinLedger.delta > 0,
                ThinkingCoinLedger.reason.in_(tuple(_DAILY_EARN_REASONS)),
                ThinkingCoinLedger.created_at >= day_start,
                ThinkingCoinLedger.created_at < day_end,
            )
        )
    ).scalar_one()
    return int(total)


async def daily_earn_cap_blocks(
    db: AsyncSession,
    user_id: int,
    amount: int,
) -> bool:
    """True when crediting amount would exceed the configured daily earn cap."""
    if amount <= 0:
        return True
    cap = await get_daily_earn_cap(db)
    if cap <= 0:
        return False
    earned = await daily_earn_total_today(db, user_id)
    return earned + amount > cap
