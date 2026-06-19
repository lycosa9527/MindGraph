"""
Background heartbeat poller for per-organization dual Dify servers.

Only orgs that have a Server 2 configured and failover enabled are probed
(single-server orgs need no failover). One worker holds a Redis lock and runs
the loop; results land in the shared health cache that the credential resolver
reads for active/standby selection.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import List, Tuple

from sqlalchemy import select

from models.domain.auth import Organization
from services.dify.dify_servers import configured_dify_servers, failover_enabled
from services.mindbot.dify.service_health import check_dify_app_api_reachable
from services.redis import keys as _keys
from services.redis.cache.redis_dify_server_health_cache import record_probe_result
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

DIFY_HEALTH_POLL_INTERVAL_SECONDS = int(os.getenv("DIFY_HEALTH_POLL_INTERVAL_SECONDS", "30"))

_LOCK_KEY = _keys.DIFY_HEALTH_POLLER_LOCK
_LOCK_TTL = _keys.TTL_DIFY_HEALTH_POLLER_LOCK


class _PollerLockState:
    """Holds this worker's lock token across loop iterations."""

    __slots__ = ("lock_id",)

    def __init__(self) -> None:
        """init  ."""
        self.lock_id = f"{os.getpid()}:{uuid.uuid4().hex[:8]}"


_lock_state = _PollerLockState()


async def _acquire_or_refresh_lock() -> bool:
    """Acquire the poller lock or refresh it if we already hold it."""
    if not is_redis_available():
        return False
    redis = get_async_redis()
    if not redis:
        return False
    try:
        current = await redis.get(_LOCK_KEY)
        if isinstance(current, bytes):
            current = current.decode("utf-8")
        if current == _lock_state.lock_id:
            await redis.expire(_LOCK_KEY, _LOCK_TTL)
            return True
        acquired = await redis.set(_LOCK_KEY, _lock_state.lock_id, nx=True, ex=_LOCK_TTL)
        return bool(acquired)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.debug("[DifyHealth] Lock acquire/refresh failed: %s", exc)
        return False


async def _load_failover_orgs() -> List[Tuple[int, List]]:
    """Return (org_id, configured_servers) for orgs with Server 2 + failover on."""
    out: List[Tuple[int, List]] = []
    async with system_rls_session() as db:
        result = await db.execute(
            select(Organization).where(
                Organization.dify_api_base_url_2.isnot(None),
                Organization.dify_api_key_2.isnot(None),
                Organization.dify_failover_enabled.is_(True),
            )
        )
        for org in result.scalars().all():
            if not failover_enabled(org):
                continue
            servers = configured_dify_servers(org)
            if len(servers) >= 2:
                out.append((org.id, servers))
    return out


async def _probe_once() -> None:
    """Probe every failover org's servers and record results in the cache."""
    orgs = await _load_failover_orgs()
    for org_id, servers in orgs:
        for creds in servers:
            online, _http_status, _err = await check_dify_app_api_reachable(creds.api_url, creds.api_key)
            await record_probe_result(org_id, creds.server, online)


async def start_dify_health_poller() -> None:
    """
    Run the dual-server heartbeat loop on the single Redis lock holder.

    Non-holders sleep and retry so failover continues if the holder dies.
    """
    logger.debug("[DifyHealth] Heartbeat poller starting (interval=%ss)", DIFY_HEALTH_POLL_INTERVAL_SECONDS)
    while True:
        try:
            if not await _acquire_or_refresh_lock():
                await asyncio.sleep(DIFY_HEALTH_POLL_INTERVAL_SECONDS)
                continue
            await _probe_once()
            await asyncio.sleep(DIFY_HEALTH_POLL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.info("[DifyHealth] Heartbeat poller cancelled")
            raise
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("[DifyHealth] Heartbeat poll error: %s", exc)
            await asyncio.sleep(DIFY_HEALTH_POLL_INTERVAL_SECONDS)
