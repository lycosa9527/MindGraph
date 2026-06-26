"""Paginated ledger queries."""

from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.thinking_coin import ThinkingCoinLedger


async def fetch_ledger_page(
    db: AsyncSession,
    user_id: int,
    *,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[ThinkingCoinLedger], int]:
    """Return ledger rows and total count."""
    safe_page = max(1, page)
    safe_limit = min(max(1, limit), 100)
    offset = (safe_page - 1) * safe_limit

    count_stmt = select(func.count()).select_from(ThinkingCoinLedger).where(ThinkingCoinLedger.user_id == user_id)
    total = int((await db.execute(count_stmt)).scalar_one())

    rows = (
        (
            await db.execute(
                select(ThinkingCoinLedger)
                .where(ThinkingCoinLedger.user_id == user_id)
                .order_by(desc(ThinkingCoinLedger.created_at), desc(ThinkingCoinLedger.id))
                .offset(offset)
                .limit(safe_limit)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), total
