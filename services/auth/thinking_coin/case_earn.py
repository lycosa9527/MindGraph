"""Credit thinking coins when a case is approved."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.thinking_coin import ThinkingCoinLedger
from services.auth.thinking_coin.daily_cap import daily_earn_cap_blocks
from services.auth.thinking_coin.dates import beijing_month_utc_bounds
from services.auth.thinking_coin.task_registry import load_active_tasks
from services.auth.thinking_coin.wallet_service import credit_wallet
from utils.auth.thinking_coin_config import (
    LEDGER_CASE,
    SLUG_PUBLISH_CASE,
    feature_thinking_coins_enabled,
)
from utils.db.rls_context import RlsContext, apply_rls_context_async


async def _already_credited_for_case(db: AsyncSession, user_id: int, case_id: str) -> bool:
    row = (
        await db.execute(
            select(ThinkingCoinLedger.id).where(
                ThinkingCoinLedger.user_id == user_id,
                ThinkingCoinLedger.reason == LEDGER_CASE,
                ThinkingCoinLedger.ref_type == "showcase_post",
                ThinkingCoinLedger.ref_id == case_id,
            )
        )
    ).scalar_one_or_none()
    return row is not None


async def _monthly_case_rewards(db: AsyncSession, user_id: int) -> int:
    month_start, month_end = beijing_month_utc_bounds()
    count = (
        await db.execute(
            select(func.count())
            .select_from(ThinkingCoinLedger)
            .where(
                ThinkingCoinLedger.user_id == user_id,
                ThinkingCoinLedger.reason == LEDGER_CASE,
                ThinkingCoinLedger.delta > 0,
                ThinkingCoinLedger.created_at >= month_start,
                ThinkingCoinLedger.created_at < month_end,
            )
        )
    ).scalar_one()
    return int(count)


async def try_publish_case_earn(
    db: AsyncSession,
    user_id: int,
    case_id: str,
) -> tuple[int, str | None]:
    """Credit publish_case reward once per approved case (monthly cap applies)."""
    if not feature_thinking_coins_enabled():
        return 0, None

    if await _already_credited_for_case(db, user_id, case_id):
        return 0, SLUG_PUBLISH_CASE

    tasks = await load_active_tasks(db)
    task = next((t for t in tasks if t.slug == SLUG_PUBLISH_CASE and t.is_active), None)
    if task is None:
        return 0, None

    if task.monthly_cap is not None:
        used = await _monthly_case_rewards(db, user_id)
        if used >= int(task.monthly_cap):
            return 0, task.slug

    amount = int(task.reward_amount)
    if await daily_earn_cap_blocks(db, user_id, amount):
        return 0, task.slug

    await credit_wallet(
        db,
        user_id,
        amount,
        LEDGER_CASE,
        ref_type="showcase_post",
        ref_id=case_id,
    )
    return amount, task.slug


async def try_publish_case_earn_as_author(
    db: AsyncSession,
    author_id: int,
    case_id: str,
    *,
    restore_ctx: RlsContext,
) -> tuple[int, str | None]:
    """Credit under the author's RLS, then restore the caller's context.

    Admin review runs in panel mode; wallet RLS is owner-or-system only, so the
    credit must execute as the author (same transaction, savepoint-isolated).
    """
    org_id = (
        await db.execute(select(User.organization_id).where(User.id == author_id))
    ).scalar_one_or_none()
    await apply_rls_context_async(db, RlsContext.for_celery_user(author_id, org_id))
    try:
        async with db.begin_nested():
            return await try_publish_case_earn(db, author_id, case_id)
    finally:
        await apply_rls_context_async(db, restore_ctx)
