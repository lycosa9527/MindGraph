"""
Background scheduler to purge old error_events rows (retention TTL).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from config.db_sessions import open_async_session
from models.domain.error_event import ErrorEvent, ErrorGroup
from services.monitoring.error_alert_config import error_collection_enabled, error_retention_days
from services.monitoring.error_reporting import record_exception
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

try:
    from services.redis.redis_async_client import get_async_redis
    from services.redis.redis_client import is_redis_available

    _REDIS_AVAILABLE = True
except ImportError:
    get_async_redis = None
    is_redis_available = None
    _REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

RETENTION_LOCK_KEY = "error_collection:retention:lock"
RETENTION_LOCK_TTL_SECONDS = 600
DEFAULT_INTERVAL_HOURS = 24


async def _acquire_retention_lock() -> str | None:
    if not _REDIS_AVAILABLE or is_redis_available is None or not is_redis_available():
        return None
    if get_async_redis is None:
        return None
    try:
        redis_client = get_async_redis()
        if redis_client is None:
            return None
        token = f"{os.getpid()}:{uuid.uuid4().hex[:8]}"
        acquired = await redis_client.set(
            RETENTION_LOCK_KEY,
            token,
            nx=True,
            ex=RETENTION_LOCK_TTL_SECONDS,
        )
        return token if acquired else None
    except BACKGROUND_INFRA_ERRORS as lock_error:
        logger.debug("[ErrorRetention] Lock acquire failed: %s", lock_error)
        return None


async def _release_retention_lock(token: str) -> None:
    if not _REDIS_AVAILABLE or is_redis_available is None or not is_redis_available():
        return
    if get_async_redis is None:
        return
    try:
        redis_client = get_async_redis()
        if redis_client is None:
            return
        current = await redis_client.get(RETENTION_LOCK_KEY)
        if current == token:
            await redis_client.delete(RETENTION_LOCK_KEY)
    except BACKGROUND_INFRA_ERRORS as release_error:
        logger.debug("[ErrorRetention] Lock release failed: %s", release_error)


async def purge_expired_error_events() -> int:
    """Delete events older than retention window; remove empty groups."""
    if not error_collection_enabled():
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=error_retention_days())
    deleted = 0
    async with open_async_session() as session:
        result = await session.execute(
            delete(ErrorEvent).where(ErrorEvent.created_at < cutoff).returning(ErrorEvent.id)
        )
        deleted = len(result.fetchall())
        await session.execute(
            delete(ErrorGroup).where(~ErrorGroup.id.in_(select(ErrorEvent.group_id)))
        )
        await session.commit()
    if deleted:
        logger.info("[ErrorRetention] Purged %s error events older than %s days", deleted, error_retention_days())
    return deleted


async def start_error_retention_scheduler(interval_hours: int = DEFAULT_INTERVAL_HOURS) -> None:
    """Run retention purge on a fixed interval (one worker via Redis lock)."""
    interval_seconds = max(3600, interval_hours * 3600)
    logger.debug("[ErrorRetention] Scheduler started (interval=%sh)", interval_hours)
    while True:
        await asyncio.sleep(interval_seconds)
        if not error_collection_enabled():
            continue
        token = await _acquire_retention_lock()
        if token is None:
            continue
        try:
            await purge_expired_error_events()
        except BACKGROUND_INFRA_ERRORS as purge_error:
            logger.warning("[ErrorRetention] Purge failed: %s", purge_error)
            if error_collection_enabled():
                record_exception(
                    source="background",
                    component="ErrorRetentionScheduler",
                    exc=purge_error,
                )
        finally:
            await _release_retention_lock(token)


async def count_error_events() -> int:
    """Return total persisted error event count."""
    async with open_async_session() as session:
        result = await session.execute(select(func.count()).select_from(ErrorEvent))
        return int(result.scalar_one())
