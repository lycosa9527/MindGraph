"""
Daily AbuseIPDB blacklist sync (Redis-coordinated single worker).

Uses the same coordination idea as backup_scheduler: one worker holds the lock.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Optional

from services.infrastructure.security import abuseipdb_service
from services.infrastructure.security import crowdsec_blocklist_service
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available

logger = logging.getLogger(__name__)

ABUSEIPDB_LOCK_KEY = "abuseipdb:scheduler:lock"
ABUSEIPDB_LOCK_TTL = 172800


class _AbuseipdbLockState:
    __slots__ = ("worker_lock_id",)

    def __init__(self) -> None:
        self.worker_lock_id: Optional[str] = None


_lock_state = _AbuseipdbLockState()


def _generate_lock_id() -> str:
    return f"{os.getpid()}:{uuid.uuid4().hex[:8]}"


async def acquire_abuseipdb_scheduler_lock() -> bool:
    if not is_redis_available():
        logger.debug("[AbuseIPDB] Redis unavailable; scheduler lock not acquired")
        return False
    redis = get_async_redis()
    if not redis:
        return False
    try:
        if _lock_state.worker_lock_id is None:
            _lock_state.worker_lock_id = _generate_lock_id()
        acquired = await redis.set(
            ABUSEIPDB_LOCK_KEY,
            _lock_state.worker_lock_id,
            nx=True,
            ex=ABUSEIPDB_LOCK_TTL,
        )
        if acquired:
            logger.info(
                "[AbuseIPDB] Scheduler lock acquired (id=%s)",
                _lock_state.worker_lock_id,
            )
            return True
        return False
    except OSError as exc:
        logger.warning("[AbuseIPDB] Lock acquisition failed: %s", exc)
        return False


async def refresh_abuseipdb_scheduler_lock() -> bool:
    if not is_redis_available() or _lock_state.worker_lock_id is None:
        return False
    redis = get_async_redis()
    if not redis:
        return False
    try:
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            redis.call("expire", KEYS[1], ARGV[2])
            return 1
        else
            return 0
        end
        """
        result = await redis.eval(
            lua_script,
            1,
            ABUSEIPDB_LOCK_KEY,
            _lock_state.worker_lock_id,
            ABUSEIPDB_LOCK_TTL,
        )
        return bool(result == 1)
    except OSError as exc:
        logger.warning("[AbuseIPDB] Lock refresh failed: %s", exc)
        return False


async def start_abuseipdb_blacklist_scheduler() -> None:
    """
    Run AbuseIPDB and/or CrowdSec blocklist sync when enabled.

    Only the Redis lock holder runs the loop; other workers sleep and retry.
    """
    abuseipdb_sync = (
        abuseipdb_service.abuseipdb_master_enabled() and abuseipdb_service.abuseipdb_blacklist_sync_enabled()
    )
    crowdsec_sync = crowdsec_blocklist_service.crowdsec_blocklist_sync_enabled()

    if not abuseipdb_sync and not crowdsec_sync:
        logger.info(
            "[Blocklist] Scheduler idle (AbuseIPDB blacklist sync=%s, CrowdSec sync=%s)",
            abuseipdb_sync,
            crowdsec_sync,
        )
        return

    interval = (
        abuseipdb_service.get_blacklist_sync_interval_seconds()
        if abuseipdb_sync
        else crowdsec_blocklist_service.get_crowdsec_sync_interval_seconds()
    )

    if not await acquire_abuseipdb_scheduler_lock():
        logger.debug("[AbuseIPDB] Another worker holds the scheduler lock; monitoring")
        follower_round = 0
        while True:
            try:
                await asyncio.sleep(300)
                follower_round += 1
                if follower_round % 12 == 0:
                    logger.info(
                        "[AbuseIPDB] Still waiting for blacklist scheduler lock (%s min)",
                        follower_round * 5,
                    )
                if await acquire_abuseipdb_scheduler_lock():
                    logger.info("[AbuseIPDB] Scheduler lock acquired on retry")
                    break
            except asyncio.CancelledError:
                logger.info("[AbuseIPDB] Scheduler monitor stopped")
                return

    logger.info(
        "[Blocklist] Scheduler started (interval=%ss abuseipdb=%s crowdsec=%s)",
        interval,
        abuseipdb_sync,
        crowdsec_sync,
    )

    while True:
        try:
            if not await refresh_abuseipdb_scheduler_lock():
                logger.warning("[AbuseIPDB] Lost scheduler lock; stopping sync loop")
                return

            if abuseipdb_sync:
                result = await abuseipdb_service.sync_blacklist_to_redis()
                if result.get("ok"):
                    logger.info("[AbuseIPDB] Sync OK: %s IPs", result.get("count"))
                elif result.get("error") == "disabled":
                    return
                elif result.get("rate_limited"):
                    retry_after = float(result.get("retry_after_seconds") or 3600)
                    logger.warning(
                        "[AbuseIPDB] Blacklist sync rate limited; waiting %.0fs before retry",
                        retry_after,
                    )
                    waited = 0.0
                    while waited < retry_after:
                        sleep_chunk = min(300.0, retry_after - waited)
                        await asyncio.sleep(sleep_chunk)
                        waited += sleep_chunk
                        if not await refresh_abuseipdb_scheduler_lock():
                            logger.warning("[AbuseIPDB] Lost lock during rate-limit wait; exiting")
                            return
                    continue
                else:
                    logger.debug("[AbuseIPDB] Sync result: %s", result)
            else:
                cs = await crowdsec_blocklist_service.merge_crowdsec_blocklist_from_network()
                if cs.get("ok") and not cs.get("skipped"):
                    logger.info("[CrowdSec] Sync OK: %s IPs", cs.get("count"))
                    await abuseipdb_service.log_shared_blacklist_redis_size_async("after CrowdSec-only scheduler merge")
                elif cs.get("rate_limited"):
                    retry_after = float(cs.get("retry_after_seconds") or 3600)
                    logger.warning(
                        "[CrowdSec] rate limited; waiting %.0fs before retry",
                        retry_after,
                    )
                    waited = 0.0
                    while waited < retry_after:
                        sleep_chunk = min(300.0, retry_after - waited)
                        await asyncio.sleep(sleep_chunk)
                        waited += sleep_chunk
                        if not await refresh_abuseipdb_scheduler_lock():
                            logger.warning("[CrowdSec] Lost lock during rate-limit wait; exiting")
                            return
                    continue
                else:
                    logger.debug("[CrowdSec] Sync result: %s", cs)

            interval = (
                abuseipdb_service.get_blacklist_sync_interval_seconds()
                if abuseipdb_sync
                else crowdsec_blocklist_service.get_crowdsec_sync_interval_seconds()
            )
            waited = 0.0
            while waited < float(interval):
                sleep_chunk = min(300.0, float(interval) - waited)
                await asyncio.sleep(sleep_chunk)
                waited += sleep_chunk
                if not await refresh_abuseipdb_scheduler_lock():
                    logger.warning("[AbuseIPDB] Lost lock during wait; exiting")
                    return

        except asyncio.CancelledError:
            logger.info("[AbuseIPDB] Blacklist scheduler cancelled")
            raise
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("[AbuseIPDB] Scheduler loop error: %s", exc)
            await asyncio.sleep(60)
