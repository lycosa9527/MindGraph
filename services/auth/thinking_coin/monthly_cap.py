"""Monthly earn caps per task."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.thinking_coin import ThinkingCoinEarnTask, ThinkingCoinLedger
from services.auth.thinking_coin.dates import beijing_month_utc_bounds


async def monthly_earn_count_for_task(db: AsyncSession, user_id: int, task_id: int) -> int:
    """Count positive earn ledger rows for a task in the current Beijing month."""
    month_start, month_end = beijing_month_utc_bounds()
    count = (
        await db.execute(
            select(func.count())
            .select_from(ThinkingCoinLedger)
            .where(
                ThinkingCoinLedger.user_id == user_id,
                ThinkingCoinLedger.ref_type == "earn_task",
                ThinkingCoinLedger.ref_id == str(task_id),
                ThinkingCoinLedger.delta > 0,
                ThinkingCoinLedger.created_at >= month_start,
                ThinkingCoinLedger.created_at < month_end,
            )
        )
    ).scalar_one()
    return int(count)


async def task_monthly_cap_reached(
    db: AsyncSession,
    user_id: int,
    task: ThinkingCoinEarnTask,
) -> bool:
    """True when the task has a monthly cap and the user reached it."""
    if task.monthly_cap is None:
        return False
    used = await monthly_earn_count_for_task(db, user_id, int(task.id))
    return used >= int(task.monthly_cap)
