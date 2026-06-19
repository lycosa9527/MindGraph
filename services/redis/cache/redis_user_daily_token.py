"""Redis counter for per-user daily LLM token usage (Beijing calendar day).

Used for enforcing USER_DAILY_TOKEN_CAP before LLM calls. Fails open when Redis
is unavailable so teachers are not blocked by infra outages.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging

from services.redis import keys as _keys
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
from services.utils.error_types import REDIS_ERRORS
from utils.auth.user_daily_token_config import daily_token_cap
from utils.auth.token_stats_queries import beijing_date_key

logger = logging.getLogger(__name__)


def _usage_key(user_id: int) -> str:
    """Build Redis key for today's token total."""
    return _keys.USER_DAILY_TOKENS.format(user_id=user_id, beijing_date=beijing_date_key())


async def get_daily_usage(user_id: int) -> int:
    """Return tokens consumed today for ``user_id`` (0 if missing or Redis down)."""
    if not is_redis_available():
        return 0
    redis = get_async_redis()
    if not redis:
        return 0
    try:
        raw = await redis.get(_usage_key(user_id))
        if raw is None:
            return 0
        return int(raw)
    except REDIS_ERRORS as exc:
        logger.warning("[UserDailyToken] get_daily_usage failed user=%s: %s", user_id, exc)
        return 0


async def add_daily_usage(user_id: int, tokens: int) -> int:
    """Atomically add ``tokens`` to today's counter. Returns new total (0 if Redis down)."""
    if tokens <= 0:
        return await get_daily_usage(user_id)
    if not is_redis_available():
        return 0
    redis = get_async_redis()
    if not redis:
        return 0
    usage_key = _usage_key(user_id)
    try:
        async with redis.pipeline(transaction=False) as pipe:
            pipe.incrby(usage_key, tokens)
            pipe.expire(usage_key, _keys.TTL_USER_DAILY_TOKENS, nx=True)
            results = await pipe.execute()
        return int(results[0])
    except REDIS_ERRORS as exc:
        logger.warning("[UserDailyToken] add_daily_usage failed user=%s: %s", user_id, exc)
        return 0


async def record_tracked_daily_tokens(user_id: int | None, tokens: int) -> None:
    """Increment today's counter after a successful tracked LLM call."""
    if user_id is None or tokens <= 0:
        return
    if daily_token_cap() <= 0:
        return
    await add_daily_usage(user_id, tokens)
