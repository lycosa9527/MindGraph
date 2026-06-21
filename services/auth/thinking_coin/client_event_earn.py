"""Client-triggered daily earn tasks (share, export, learning sheet, etc.)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.thinking_coin import ThinkingCoinDailyActivity
from services.auth.thinking_coin.daily_cap import daily_earn_cap_blocks
from services.auth.thinking_coin.dates import beijing_date_today
from services.auth.thinking_coin.monthly_cap import task_monthly_cap_reached
from services.auth.thinking_coin.task_registry import load_active_tasks, task_client_event_key
from services.auth.thinking_coin.wallet_service import credit_wallet
from utils.auth.thinking_coin_config import HANDLER_CLIENT_EVENT, LEDGER_TASK


async def _event_done_today(
    db: AsyncSession,
    user_id: int,
    task_slug: str,
    activity_date: date,
) -> bool:
    row = (
        await db.execute(
            select(ThinkingCoinDailyActivity.id).where(
                ThinkingCoinDailyActivity.user_id == user_id,
                ThinkingCoinDailyActivity.task_slug == task_slug,
                ThinkingCoinDailyActivity.activity_date == activity_date,
            )
        )
    ).scalar_one_or_none()
    return row is not None


async def try_client_event_earn(
    db: AsyncSession,
    user_id: int,
    event_key: str,
) -> tuple[int, str | None]:
    """Credit client_event task once per day; returns (amount credited, task slug)."""
    normalized = (event_key or "").strip()
    if not normalized:
        return 0, None

    activity_date = beijing_date_today()
    tasks = await load_active_tasks(db)

    for task in tasks:
        if task.handler_key != HANDLER_CLIENT_EVENT:
            continue
        configured = task_client_event_key(task)
        if configured != normalized:
            continue
        if await _event_done_today(db, user_id, task.slug, activity_date):
            return 0, task.slug
        if await task_monthly_cap_reached(db, user_id, task):
            return 0, task.slug
        amount = int(task.reward_amount)
        if await daily_earn_cap_blocks(db, user_id, amount):
            return 0, task.slug
        db.add(
            ThinkingCoinDailyActivity(
                user_id=user_id,
                task_slug=task.slug,
                activity_date=activity_date,
            )
        )
        await credit_wallet(
            db,
            user_id,
            amount,
            LEDGER_TASK,
            ref_type="earn_task",
            ref_id=str(task.id),
        )
        return amount, task.slug

    return 0, None
