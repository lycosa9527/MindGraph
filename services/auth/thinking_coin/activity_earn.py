"""Activity earn after successful usage."""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.thinking_coin import ThinkingCoinDailyActivity
from services.auth.thinking_coin.dates import beijing_date_today
from services.auth.thinking_coin.daily_cap import daily_earn_cap_blocks
from services.auth.thinking_coin.monthly_cap import task_monthly_cap_reached
from services.auth.thinking_coin.task_registry import load_active_tasks, tasks_for_request_type
from services.auth.thinking_coin.wallet_service import credit_wallet
from utils.auth.thinking_coin_config import HANDLER_USAGE_DAILY, LEDGER_TASK

logger = logging.getLogger(__name__)


async def _activity_done_today(
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


async def try_daily_activity_earn(
    db: AsyncSession,
    user_id: int,
    request_type: str,
    *,
    is_learning_sheet: bool | None = None,
) -> list[dict[str, int | str]]:
    """Credit usage_daily tasks once per day; returns earn events for UI."""
    activity_date = beijing_date_today()
    tasks = await load_active_tasks(db)
    matched = tasks_for_request_type(
        tasks,
        request_type,
        is_learning_sheet=is_learning_sheet,
    )
    events: list[dict[str, int | str]] = []

    for task in matched:
        if task.handler_key != HANDLER_USAGE_DAILY:
            continue
        if await _activity_done_today(db, user_id, task.slug, activity_date):
            continue
        if await task_monthly_cap_reached(db, user_id, task):
            continue
        amount = int(task.reward_amount)
        if await daily_earn_cap_blocks(db, user_id, amount):
            continue
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
        events.append({"slug": task.slug, "amount": amount})
    return events


async def completed_usage_slugs_today(db: AsyncSession, user_id: int) -> set[str]:
    """Task slugs already earned today via usage_daily."""
    activity_date = beijing_date_today()
    rows = (
        (
            await db.execute(
                select(ThinkingCoinDailyActivity.task_slug).where(
                    ThinkingCoinDailyActivity.user_id == user_id,
                    ThinkingCoinDailyActivity.activity_date == activity_date,
                )
            )
        )
        .scalars()
        .all()
    )
    return set(rows)
