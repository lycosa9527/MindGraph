"""Resolve earn-task metadata for ledger API rows."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.thinking_coin import ThinkingCoinEarnTask, ThinkingCoinLedger


def collect_earn_task_ids(rows: list[ThinkingCoinLedger]) -> list[int]:
    """Collect unique earn-task ids referenced by ledger rows."""
    ids: list[int] = []
    seen: set[int] = set()
    for row in rows:
        if row.ref_type != "earn_task" or not row.ref_id:
            continue
        try:
            task_id = int(str(row.ref_id).strip())
        except ValueError:
            continue
        if task_id in seen:
            continue
        seen.add(task_id)
        ids.append(task_id)
    return ids


async def load_earn_tasks_by_ids(
    db: AsyncSession,
    task_ids: list[int],
) -> dict[int, ThinkingCoinEarnTask]:
    """Batch-load earn tasks for ledger enrichment."""
    if not task_ids:
        return {}
    rows = (await db.execute(select(ThinkingCoinEarnTask).where(ThinkingCoinEarnTask.id.in_(task_ids)))).scalars().all()
    return {int(row.id): row for row in rows}
