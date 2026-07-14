"""
Daily COS mirror scheduler (CrowdSec + Qdrant + Celery on consumer; publish on publisher).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import Optional

from services.infrastructure.sync.cos_sync_env import (
    cos_sync_enabled,
    is_cos_consumer,
    is_cos_publisher,
)
from services.infrastructure.sync.crowdsec_cos_sync import merge_crowdsec_blocklist_from_cos
from services.infrastructure.sync.abuseipdb_cos_sync import merge_abuseipdb_blocklist_from_cos
from services.infrastructure.sync.celery_cos_sync import (
    install_celery_from_cos,
    publish_celery_release_to_cos,
)
from services.infrastructure.sync.geolite_cos_sync import (
    install_geolite_from_cos,
    publish_geolite_to_cos,
)
from services.infrastructure.sync.qdrant_cos_sync import (
    install_qdrant_from_cos,
    maybe_auto_install_qdrant_from_cos,
    publish_qdrant_release_to_cos,
)
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
from services.utils.backup_scheduler import BACKUP_HOUR, get_next_backup_time
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

COS_MIRROR_LOCK_KEY = "cos:mirror:scheduler:lock"
COS_MIRROR_LOCK_TTL = 172800


class _CosMirrorLockState:
    """Holds worker lock id for Redis coordination."""

    __slots__ = ("worker_lock_id",)

    def __init__(self) -> None:
        """init."""
        self.worker_lock_id: Optional[str] = None


_lock_state = _CosMirrorLockState()


def _generate_lock_id() -> str:
    return f"{os.getpid()}:{uuid.uuid4().hex[:8]}"


async def acquire_cos_mirror_lock() -> bool:
    """Acquire scheduler lock."""
    if not is_redis_available():
        return False
    redis = get_async_redis()
    if not redis:
        return False
    lock_id = _generate_lock_id()
    acquired = await redis.set(COS_MIRROR_LOCK_KEY, lock_id, nx=True, ex=COS_MIRROR_LOCK_TTL)
    if acquired:
        _lock_state.worker_lock_id = lock_id
        return True
    return False


async def refresh_cos_mirror_lock() -> bool:
    """Refresh lock TTL if still owned."""
    if not _lock_state.worker_lock_id or not is_redis_available():
        return False
    redis = get_async_redis()
    if not redis:
        return False
    current = await redis.get(COS_MIRROR_LOCK_KEY)
    if current != _lock_state.worker_lock_id:
        return False
    await redis.expire(COS_MIRROR_LOCK_KEY, COS_MIRROR_LOCK_TTL)
    return True


async def release_cos_mirror_lock() -> None:
    """Release lock on shutdown."""
    if not _lock_state.worker_lock_id or not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    current = await redis.get(COS_MIRROR_LOCK_KEY)
    if current == _lock_state.worker_lock_id:
        await redis.delete(COS_MIRROR_LOCK_KEY)
    _lock_state.worker_lock_id = None


async def _sleep_until_next_sync() -> None:
    next_run = get_next_backup_time()
    wait_seconds = max(0.0, (next_run - datetime.now()).total_seconds())
    logger.debug("[COSMirror] Next sync at %s", next_run.isoformat())
    while wait_seconds > 0:
        chunk = min(wait_seconds, 300.0)
        await asyncio.sleep(chunk)
        wait_seconds -= chunk
        if wait_seconds > 0 and not await refresh_cos_mirror_lock():
            return


async def _run_mirror_tick() -> None:
    """One scheduled mirror cycle."""
    if is_cos_consumer():
        cs = await merge_crowdsec_blocklist_from_cos(force=True)
        if cs.get("ok") and not cs.get("skipped"):
            logger.info("[COSMirror] CrowdSec consumer sync: %s IPs", cs.get("count"))
        ab = await merge_abuseipdb_blocklist_from_cos(force=True)
        if ab.get("ok") and not ab.get("skipped"):
            logger.info("[COSMirror] AbuseIPDB consumer sync: %s IPs", ab.get("count"))
        gl = await install_geolite_from_cos()
        if gl.get("ok") and not gl.get("skipped"):
            logger.info("[COSMirror] GeoLite installed from COS")
        qd = await install_qdrant_from_cos()
        if qd.get("ok") and not qd.get("skipped"):
            logger.info("[COSMirror] Qdrant installed v%s from COS", qd.get("version"))
        elif qd.get("needs_root"):
            logger.debug("[COSMirror] Qdrant install needs root")
        cl = await install_celery_from_cos()
        if cl.get("ok") and not cl.get("skipped"):
            logger.info("[COSMirror] Celery installed v%s from COS", cl.get("version"))
    elif is_cos_publisher():
        pub = await publish_qdrant_release_to_cos()
        if pub.get("ok") and not pub.get("skipped"):
            logger.info("[COSMirror] Qdrant published v%s to COS", pub.get("version"))
        cl_pub = await publish_celery_release_to_cos()
        if cl_pub.get("ok") and not cl_pub.get("skipped"):
            logger.info("[COSMirror] Celery published v%s to COS", cl_pub.get("version"))
        gl_pub = await publish_geolite_to_cos()
        if gl_pub.get("ok") and not gl_pub.get("skipped"):
            logger.info("[COSMirror] GeoLite published to COS")
        elif gl_pub.get("error") == "local_mmdb_missing":
            logger.debug("[COSMirror] GeoLite local MMDB missing; skip publish")


async def start_cos_mirror_scheduler() -> None:
    """Background loop aligned with BACKUP_HOUR."""
    if not cos_sync_enabled():
        logger.debug("[COSMirror] COS sync disabled")
        return

    role = "consumer" if is_cos_consumer() else "publisher" if is_cos_publisher() else "off"
    if role == "off":
        logger.debug("[COSMirror] COS_SYNC_ROLE=off")
        return

    if not await acquire_cos_mirror_lock():
        while True:
            try:
                await asyncio.sleep(60)
                if await acquire_cos_mirror_lock():
                    break
            except asyncio.CancelledError:
                return

    logger.info("[COSMirror] Scheduler started (role=%s, hour=%02d:00)", role, BACKUP_HOUR)

    while True:
        try:
            if not await refresh_cos_mirror_lock():
                logger.warning("[COSMirror] Lost scheduler lock")
                return
            await _sleep_until_next_sync()
            if not await refresh_cos_mirror_lock():
                return
            await _run_mirror_tick()
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            await release_cos_mirror_lock()
            logger.info("[COSMirror] Scheduler stopped")
            raise
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("[COSMirror] Scheduler error: %s", exc)
            await asyncio.sleep(60)


async def run_cos_mirror_startup() -> None:
    """Startup hooks: consumer auto-install Qdrant when configured."""
    if not cos_sync_enabled():
        return
    if is_cos_consumer():
        await maybe_auto_install_qdrant_from_cos()
