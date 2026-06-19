"""Per-user daily LLM token cap (Beijing calendar day).

Enforcement uses a Redis counter; admin views may reconcile with ``token_usage`` DB sums.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.messages import Language, Messages
from models.domain.token_usage import TokenUsage
from services.infrastructure.http.error_handler import UserDailyTokenCapExceededError
from services.redis.cache.redis_user_daily_token import get_daily_usage, record_tracked_daily_tokens
from services.utils.error_types import DATABASE_ERRORS
from utils.auth.token_stats_queries import get_beijing_today_start_utc
from utils.auth.user_daily_token_config import daily_token_cap

logger = logging.getLogger(__name__)


def daily_token_limit_message(lang: Language, cap: int | None = None) -> str:
    """Localized user-facing message when the daily token cap is reached."""
    limit = cap if cap is not None else daily_token_cap()
    return Messages.error("daily_token_limit_reached", lang, limit)


def daily_token_quota_fields(used_today: int) -> dict[str, int]:
    """Admin payload fields for daily token budget."""
    cap = daily_token_cap()
    if cap <= 0:
        return {
            "token_daily_cap": 0,
            "token_used_today": used_today,
            "token_remaining_today": 0,
        }
    return {
        "token_daily_cap": cap,
        "token_used_today": used_today,
        "token_remaining_today": max(0, cap - used_today),
    }


async def resolve_daily_usage(user_id: int, db_fallback: Optional[int] = None) -> int:
    """Best-effort today usage: max(Redis counter, optional DB fallback)."""
    redis_used = await get_daily_usage(user_id)
    if db_fallback is None:
        return redis_used
    return max(redis_used, db_fallback)


async def fetch_db_daily_usage_by_user(
    db: AsyncSession,
    user_ids: Sequence[int],
) -> dict[int, int]:
    """Sum successful ``token_usage`` rows since Beijing midnight for each user."""
    if not user_ids:
        return {}
    today_start = get_beijing_today_start_utc()
    try:
        rows = (
            await db.execute(
                select(
                    TokenUsage.user_id,
                    sa_func.coalesce(sa_func.sum(TokenUsage.total_tokens), 0).label("total"),
                )
                .where(
                    TokenUsage.user_id.in_(tuple(int(uid) for uid in user_ids)),
                    TokenUsage.success.is_(True),
                    TokenUsage.created_at >= today_start,
                )
                .group_by(TokenUsage.user_id)
            )
        ).all()
        return {int(row.user_id): int(row.total or 0) for row in rows}
    except DATABASE_ERRORS as exc:
        logger.debug("[UserDailyToken] DB daily usage query failed: %s", exc)
        return {}


async def resolve_daily_usage_map(
    db: AsyncSession,
    user_ids: Sequence[int],
) -> dict[int, int]:
    """Today usage per user for admin lists (max of Redis and DB)."""
    db_map = await fetch_db_daily_usage_by_user(db, user_ids)
    resolved: dict[int, int] = {}
    for uid in user_ids:
        user_id = int(uid)
        resolved[user_id] = await resolve_daily_usage(user_id, db_map.get(user_id, 0))
    return resolved


async def assert_user_daily_token_budget(
    user_id: Optional[int],
    estimated_tokens: int = 0,
    lang: Language = "en",
) -> None:
    """Raise ``UserDailyTokenCapExceededError`` when the daily cap would be exceeded."""
    if user_id is None:
        return
    cap = daily_token_cap()
    if cap <= 0:
        return
    used = await get_daily_usage(user_id)
    projected = used + max(0, estimated_tokens)
    if projected > cap:
        message = daily_token_limit_message(lang, cap)
        raise UserDailyTokenCapExceededError(cap=cap, used=used, user_message=message)


async def record_user_daily_tokens(user_id: Optional[int], tokens: int) -> None:
    """Increment the Redis daily counter after a tracked LLM call."""
    await record_tracked_daily_tokens(user_id, tokens)
