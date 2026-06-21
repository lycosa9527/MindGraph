"""Daily check-in and signup grant."""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization, User
from models.domain.thinking_coin import ThinkingCoinCheckin, ThinkingCoinLedger
from services.auth.thinking_coin.dates import beijing_date_today
from services.auth.thinking_coin.eligibility import user_eligible_for_thinking_coins
from services.auth.thinking_coin.daily_cap import daily_earn_cap_blocks
from services.auth.thinking_coin.monthly_cap import task_monthly_cap_reached
from services.auth.thinking_coin.task_registry import get_signup_grant, get_task_by_slug
from services.auth.thinking_coin.wallet_service import (
    credit_wallet,
    get_balance,
    get_or_create_wallet,
    safe_commit,
)
from utils.auth.thinking_coin_config import LEDGER_DAILY_CHECKIN, LEDGER_SIGNUP_GRANT, SLUG_DAILY_CHECKIN

logger = logging.getLogger(__name__)


async def _already_checked_in(db: AsyncSession, user_id: int, activity_date: date) -> bool:
    row = (
        await db.execute(
            select(ThinkingCoinCheckin.id).where(
                ThinkingCoinCheckin.user_id == user_id,
                ThinkingCoinCheckin.checkin_date == activity_date,
            )
        )
    ).scalar_one_or_none()
    return row is not None


async def ensure_wallet_bootstrap(
    db: AsyncSession,
    user: User,
    org: Organization | None,
) -> tuple[int, bool]:
    """Create wallet and signup grant once. Returns (balance, checkin_credited_today)."""
    if not user_eligible_for_thinking_coins(user, org):
        return 0, False

    user_id = int(user.id)
    await get_or_create_wallet(db, user_id)

    existing_grant = (
        await db.execute(
            select(ThinkingCoinLedger.id).where(
                ThinkingCoinLedger.user_id == user_id,
                ThinkingCoinLedger.reason == LEDGER_SIGNUP_GRANT,
            )
        )
    ).scalar_one_or_none()
    if existing_grant is None:
        grant = await get_signup_grant(db)
        await credit_wallet(db, user_id, grant, LEDGER_SIGNUP_GRANT)

    checkin_amount = await try_daily_checkin(db, user, org)
    balance = await get_balance(db, user_id)
    await safe_commit(db)
    return balance, checkin_amount > 0


async def try_daily_checkin(
    db: AsyncSession,
    user: User,
    org: Organization | None,
) -> int:
    """Idempotent daily check-in credit; returns coins credited (0 if already done)."""
    if not user_eligible_for_thinking_coins(user, org):
        return 0

    task = await get_task_by_slug(db, SLUG_DAILY_CHECKIN)
    if task is None or not task.is_active:
        return 0

    activity_date = beijing_date_today()
    user_id = int(user.id)
    if await _already_checked_in(db, user_id, activity_date):
        return 0
    if await task_monthly_cap_reached(db, user_id, task):
        return 0

    reward = int(task.reward_amount)
    if await daily_earn_cap_blocks(db, user_id, reward):
        return 0

    db.add(ThinkingCoinCheckin(user_id=user_id, checkin_date=activity_date))
    await credit_wallet(
        db,
        user_id,
        reward,
        LEDGER_DAILY_CHECKIN,
        ref_type="earn_task",
        ref_id=str(task.id),
    )
    return reward


async def is_checkin_completed_today(db: AsyncSession, user_id: int) -> bool:
    """Whether user already checked in today."""
    return await _already_checked_in(db, user_id, beijing_date_today())
