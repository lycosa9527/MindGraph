"""
Daily AbuseIPDB / CrowdSec blocklist sync (Redis-coordinated single worker).

Uses the same coordination idea as backup_scheduler: one worker holds the lock.
Scheduled runs align with BACKUP_HOUR (default 3:00 local time), matching the DB backup
and COS upload window for easier log correlation.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from services.infrastructure.security import abuseipdb_service
from services.infrastructure.security import crowdsec_blocklist_service
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
from services.utils.backup_scheduler import BACKUP_HOUR, get_next_backup_time

logger = logging.getLogger(__name__)

ABUSEIPDB_LOCK_KEY = "abuseipdb:scheduler:lock"
ABUSEIPDB_LOCK_TTL = 172800


def _log_blocklist_scheduled_abuseipdb_summary(result: Dict[str, Any]) -> None:
    """One INFO line after a scheduled AbuseIPDB sync (includes CrowdSec merge outcome)."""
    parts: list[str] = []
    if result.get("crowdsec_failed"):
        parts.append("status=partial")
    else:
        parts.append("status=ok")
    parts.append(f"abuseipdb_ips={result.get('count')}")
    if result.get("crowdsec_failed"):
        parts.append(f"crowdsec_error={result['crowdsec_failed']}")
    elif result.get("crowdsec"):
        crowd = result["crowdsec"]
        if crowd.get("skipped"):
            parts.append("crowdsec_network=skipped_min_interval")
        else:
            parts.append(f"crowdsec_network_ips={crowd.get('count')}")
    if result.get("baseline_merged"):
        parts.append(f"abuseipdb_baseline_lines={result['baseline_merged']}")
    if result.get("crowdsec_baseline_merged"):
        parts.append(f"crowdsec_baseline_lines={result['crowdsec_baseline_merged']}")
    logger.info("[Blocklist] Scheduled sync completed: %s", " ".join(parts))


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


async def _sleep_until_next_blocklist_sync_time() -> None:
    """Sleep until the next BACKUP_HOUR boundary (same clock as DB backup scheduler)."""
    next_sync = get_next_backup_time()
    wait_seconds = max(0.0, (next_sync - datetime.now()).total_seconds())
    logger.info(
        "[Blocklist] Next sync at %s (local time, BACKUP_HOUR=%02d:00, in %.0fs)",
        next_sync.strftime("%Y-%m-%d %H:%M:%S"),
        BACKUP_HOUR,
        wait_seconds,
    )
    while wait_seconds > 0:
        sleep_chunk = min(300.0, wait_seconds)
        await asyncio.sleep(sleep_chunk)
        wait_seconds = max(0.0, (next_sync - datetime.now()).total_seconds())
        if not await refresh_abuseipdb_scheduler_lock():
            logger.warning("[AbuseIPDB] Lost lock during wait until next scheduled sync")
            return


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
        "[Blocklist] Scheduler started (daily at %02d:00 local time, same as BACKUP_HOUR; abuseipdb=%s crowdsec=%s)",
        BACKUP_HOUR,
        abuseipdb_sync,
        crowdsec_sync,
    )

    while True:
        try:
            if not await refresh_abuseipdb_scheduler_lock():
                logger.warning("[AbuseIPDB] Lost scheduler lock; stopping sync loop")
                return

            await _sleep_until_next_blocklist_sync_time()
            if not await refresh_abuseipdb_scheduler_lock():
                logger.warning("[AbuseIPDB] Lost scheduler lock; stopping sync loop")
                return
        except asyncio.CancelledError:
            logger.info("[AbuseIPDB] Blacklist scheduler cancelled")
            raise
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("[AbuseIPDB] Error while waiting for next blocklist sync: %s", exc)
            await asyncio.sleep(60)
            continue

        while True:
            try:
                if abuseipdb_sync:
                    result = await abuseipdb_service.sync_blacklist_to_redis(force_crowdsec_merge=True)
                    if result.get("ok"):
                        _log_blocklist_scheduled_abuseipdb_summary(result)
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
                        logger.warning(
                            "[Blocklist] Scheduled sync failed: error=%s",
                            result.get("error"),
                        )
                else:
                    cs = await crowdsec_blocklist_service.merge_crowdsec_blocklist_from_network(force=True)
                    if cs.get("ok") and not cs.get("skipped"):
                        logger.info(
                            "[Blocklist] Scheduled CrowdSec-only sync completed: status=ok crowdsec_network_ips=%s",
                            cs.get("count"),
                        )
                        await abuseipdb_service.log_shared_blacklist_redis_size_async(
                            "after CrowdSec-only scheduler merge",
                        )
                    elif cs.get("ok") and cs.get("skipped"):
                        logger.info(
                            "[Blocklist] Scheduled CrowdSec-only sync completed: status=ok "
                            "crowdsec_network=skipped_min_interval",
                        )
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
                        logger.warning(
                            "[Blocklist] Scheduled CrowdSec-only sync failed: error=%s",
                            cs.get("error"),
                        )

                break
            except asyncio.CancelledError:
                logger.info("[AbuseIPDB] Blacklist scheduler cancelled")
                raise
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("[AbuseIPDB] Blocklist sync error: %s", exc)
                await asyncio.sleep(60)
                continue
