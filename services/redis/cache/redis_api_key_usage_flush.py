"""Background flush of Redis API-key usage counters into Postgres.

``track_api_key_usage`` increments ``apikey:usage:{key_id}`` in Redis for
performance.  This module drains those deltas into ``api_keys.usage_count``
so admin dashboards and quota checks stay accurate.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import select, update

from models.domain.auth import APIKey
from services.redis import keys as _keys
from services.redis.cache.redis_api_key_cache import api_key_cache
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
from services.utils.error_types import REDIS_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

FLUSH_INTERVAL = float(os.getenv("API_KEY_USAGE_FLUSH_INTERVAL", "60"))
_USAGE_KEY_PREFIX = _keys.API_KEY_USAGE_INCR.format(key_id="")


def _usage_key_id(redis_key: str) -> Optional[int]:
    """Usage key id."""
    prefix = _USAGE_KEY_PREFIX
    if not redis_key.startswith(prefix):
        return None
    suffix = redis_key[len(prefix) :]
    try:
        return int(suffix)
    except ValueError:
        return None


async def apply_api_key_usage_delta(key_id: int, delta: int) -> bool:
    """Persist a Redis usage delta for one API key."""
    if delta <= 0:
        return False

    async with system_rls_session() as db:
        result = await db.execute(select(APIKey).where(APIKey.id == key_id))
        key_record = result.scalar_one_or_none()
        if not key_record:
            logger.debug("[APIKeyUsageFlush] key id=%s not found, skipping delta=%s", key_id, delta)
            return False

        await db.execute(
            update(APIKey)
            .where(APIKey.id == key_id)
            .values(
                usage_count=APIKey.usage_count + delta,
                last_used_at=datetime.now(UTC),
            )
        )
        try:
            await db.commit()
        except REDIS_ERRORS:
            await db.rollback()
            raise

        await api_key_cache.invalidate(key_record.key)
        return True


async def flush_api_key_usage_to_db() -> int:
    """Drain all pending Redis usage counters into Postgres."""
    if not is_redis_available():
        return 0

    redis = get_async_redis()
    if not redis:
        return 0

    flushed = 0
    match_pattern = _keys.API_KEY_USAGE_INCR.format(key_id="*")
    async for raw_key in redis.scan_iter(match=match_pattern, count=100):
        key_str = raw_key.decode("utf-8") if isinstance(raw_key, bytes) else str(raw_key)
        key_id = _usage_key_id(key_str)
        if key_id is None:
            continue

        delta = await api_key_cache.get_usage_delta(key_id)
        if delta <= 0:
            continue

        if await apply_api_key_usage_delta(key_id, delta):
            flushed += 1

    return flushed


async def _flush_worker_loop() -> None:
    """Flush worker loop."""
    logger.debug("[APIKeyUsageFlush] Worker started (interval=%ss)", FLUSH_INTERVAL)
    try:
        while True:
            await asyncio.sleep(FLUSH_INTERVAL)
            try:
                count = await flush_api_key_usage_to_db()
                if count:
                    logger.debug("[APIKeyUsageFlush] Flushed %s key(s)", count)
            except REDIS_ERRORS as exc:
                logger.warning("[APIKeyUsageFlush] Flush error: %s", exc)
    except asyncio.CancelledError:
        logger.debug("[APIKeyUsageFlush] Worker cancelled")
        raise


def start_api_key_usage_flush_scheduler() -> asyncio.Task[None]:
    """Start the periodic API-key usage flush worker."""
    return asyncio.create_task(_flush_worker_loop())
