"""
Background heartbeat for the shared Dify main and backup servers.

MindMate sends the school on each request, so every school uses the same two
URLs (``DIFY_API_URL`` and ``DIFY_BACKUP_API_URL``). The poller probes those
hosts once per cycle and stores one health snapshot per URL.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Dict, List, Optional, Tuple

from services.dify.dify_failover_routing import choose_failover_route, positive_int_env
from services.dify.dify_global_servers import global_dify_servers
from services.dify.dify_health_host_probe import check_dify_host_reachable
from services.dify.dify_health_logging import (
    LOG_PREFIX,
    health_status_text,
    probe_failure_reason,
    server_label,
    traffic_route_sentence,
)
from services.dify.dify_servers import DifyServerCreds
from services.redis import keys as _keys
from services.redis.cache.redis_dify_server_health_cache import (
    DifyServerHealth,
    HEALTH_FAILURE_THRESHOLD,
    get_url_health,
    normalize_dify_health_url,
    record_url_probe_result,
)
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, REDIS_ERRORS

logger = logging.getLogger(__name__)

# 120s balances failover latency (~4 min with failure threshold 2) vs probe/log noise.
DIFY_HEALTH_POLL_INTERVAL_SECONDS = positive_int_env("DIFY_HEALTH_POLL_INTERVAL_SECONDS", 120)
DIFY_PROBE_CONCURRENCY = positive_int_env("DIFY_PROBE_CONCURRENCY", 10)

_POLLER_CYCLE_ERRORS = BACKGROUND_INFRA_ERRORS + REDIS_ERRORS

_LOCK_KEY = _keys.DIFY_HEALTH_POLLER_LOCK
_LOCK_TTL = _keys.TTL_DIFY_HEALTH_POLLER_LOCK

_MAIN_SERVER = 1
_BACKUP_SERVER = 2


class _PollerLockState:
    """Holds this worker's lock token and the last shared route it logged."""

    __slots__ = ("lock_id", "is_holder", "last_route")

    def __init__(self) -> None:
        """Create this worker's lock token."""
        self.lock_id = f"{os.getpid()}:{uuid.uuid4().hex[:8]}"
        self.is_holder = False
        self.last_route: Optional[int] = None


_lock_state = _PollerLockState()


def _server_role(server: int) -> str:
    """Return a human-readable role label for logging."""
    if server == _MAIN_SERVER:
        return "primary"
    if server == _BACKUP_SERVER:
        return "standby"
    return f"server_{server}"


def _was_considered_down(previous: Optional[DifyServerHealth]) -> bool:
    if previous is None:
        return False
    return previous.considered_down


def _log_probe_transition(
    server: int,
    previous: Optional[DifyServerHealth],
    snapshot: DifyServerHealth,
    http_status: Optional[int],
    err: Optional[str],
) -> None:
    """Emit detail logs when a shared host's probe outcome changes."""
    target = server_label(server, _server_role(server))
    prev_down = _was_considered_down(previous)
    now_down = snapshot.considered_down
    reason = probe_failure_reason(http_status, err)
    threshold = HEALTH_FAILURE_THRESHOLD

    if snapshot.online:
        if previous is None:
            logger.info(
                "%s %s responded OK on first health check.",
                LOG_PREFIX,
                target,
            )
        elif not previous.online:
            logger.info("%s %s is back online.", LOG_PREFIX, target)
        elif prev_down and not now_down:
            logger.info(
                "%s %s passed health check again and is available for traffic.",
                LOG_PREFIX,
                target,
            )
        return

    failures = snapshot.consecutive_failures
    if previous is None or previous.online:
        logger.warning(
            "%s %s health check failed (%s). %s of %s failures before failover.",
            LOG_PREFIX,
            target,
            reason,
            failures,
            threshold,
        )
    elif not prev_down and now_down:
        logger.warning(
            "%s %s marked offline after %s failed checks (%s).",
            LOG_PREFIX,
            target,
            failures,
            reason,
        )


def _log_pair_summary(health_by_server: Dict[int, DifyServerHealth]) -> None:
    """One line for the shared main and backup hosts."""
    status_parts = []
    for server in (_MAIN_SERVER, _BACKUP_SERVER):
        snapshot = health_by_server.get(server)
        if snapshot is None:
            continue
        label = server_label(server, _server_role(server))
        status_parts.append(f"{label} is {health_status_text(snapshot)}")
    if not status_parts:
        return

    main_health = health_by_server.get(_MAIN_SERVER)
    backup_health = health_by_server.get(_BACKUP_SERVER)
    if main_health is None or backup_health is None:
        logger.debug("%s %s.", LOG_PREFIX, "; ".join(status_parts))
        return

    route = choose_failover_route(_MAIN_SERVER, _BACKUP_SERVER, main_health, backup_health)
    route_note = traffic_route_sentence(
        route,
        _MAIN_SERVER,
        _BACKUP_SERVER,
        main_health,
        backup_health,
    )
    logger.debug("%s %s. %s", LOG_PREFIX, "; ".join(status_parts), route_note)
    _log_routing_change(route)


def _log_routing_change(route_after: int) -> None:
    """Log when the shared main/backup route changes."""
    route_before = _lock_state.last_route
    _lock_state.last_route = route_after
    if route_before is None or route_before == route_after:
        return
    main = server_label(_MAIN_SERVER, "primary")
    backup = server_label(_BACKUP_SERVER, "standby")
    if route_after == _MAIN_SERVER:
        logger.info("%s MindMate traffic restored to %s.", LOG_PREFIX, main)
        return
    logger.warning(
        "%s MindMate traffic switched from %s to %s because the main server is offline.",
        LOG_PREFIX,
        main,
        backup,
    )


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
    except (*BACKGROUND_INFRA_ERRORS, *REDIS_ERRORS) as exc:
        logger.debug("%s Could not acquire health-check lock: %s", LOG_PREFIX, exc)
        return False


def _group_servers_by_url(
    servers: List[DifyServerCreds],
) -> Tuple[List[str], Dict[str, List[DifyServerCreds]]]:
    """Collapse slots that share a base URL so one cycle probes each host once."""
    order: List[str] = []
    grouped: Dict[str, List[DifyServerCreds]] = {}
    for creds in servers:
        url = normalize_dify_health_url(creds.api_url)
        if not url:
            continue
        if url not in grouped:
            order.append(url)
            grouped[url] = []
        grouped[url].append(creds)
    return order, grouped


async def _probe_url(
    url: str,
    group: List[DifyServerCreds],
    semaphore: asyncio.Semaphore,
) -> Tuple[str, DifyServerHealth]:
    """Probe one shared host and store a single health snapshot."""
    try:
        async with semaphore:
            outcome = await check_dify_host_reachable(url, (entry.api_key for entry in group))
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("%s Health check could not finish for %s: %s", LOG_PREFIX, url, exc)
        outcome = (False, None, "probe_failed")
    online, http_status, err = outcome
    previous = await get_url_health(url)
    snapshot = await record_url_probe_result(url, online, previous=previous)
    _log_probe_transition(group[0].server, previous, snapshot, http_status, err)
    return url, snapshot


async def _probe_once() -> None:
    """Probe Dify main and Dify backup once and publish the shared snapshots."""
    order, grouped = _group_servers_by_url(global_dify_servers())
    if not order:
        logger.debug("%s Dify main and backup URLs are not configured.", LOG_PREFIX)
        return

    logger.debug(
        "%s Health check cycle: %s Dify host(s).",
        LOG_PREFIX,
        len(order),
    )
    semaphore = asyncio.Semaphore(DIFY_PROBE_CONCURRENCY)
    probed = await asyncio.gather(*(_probe_url(url, grouped[url], semaphore) for url in order))
    health_by_server: Dict[int, DifyServerHealth] = {}
    for url, snapshot in probed:
        for creds in grouped[url]:
            health_by_server[creds.server] = snapshot
    _log_pair_summary(health_by_server)


async def run_dify_health_check_once() -> None:
    """Run one heartbeat cycle against the shared Dify main and backup URLs."""
    await _probe_once()


async def start_dify_health_poller() -> None:
    """
    Run the shared Dify heartbeat loop on the single Redis lock holder.

    Non-holders sleep and retry so failover continues if the holder dies.
    """
    logger.info(
        "%s Background health checks started (every %s seconds).",
        LOG_PREFIX,
        DIFY_HEALTH_POLL_INTERVAL_SECONDS,
    )
    while True:
        try:
            if not await _acquire_or_refresh_lock():
                if _lock_state.is_holder:
                    logger.info(
                        "%s This worker stopped running health checks; another worker took over.",
                        LOG_PREFIX,
                    )
                    _lock_state.is_holder = False
                    _lock_state.last_route = None
                await asyncio.sleep(DIFY_HEALTH_POLL_INTERVAL_SECONDS)
                continue

            if not _lock_state.is_holder:
                logger.info("%s This worker will run Dify main and backup health checks.", LOG_PREFIX)
                _lock_state.is_holder = True

            await _probe_once()
            if not await _acquire_or_refresh_lock():
                _lock_state.is_holder = False
                _lock_state.last_route = None
            await asyncio.sleep(DIFY_HEALTH_POLL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.info("%s Background health checks stopped.", LOG_PREFIX)
            raise
        except _POLLER_CYCLE_ERRORS as exc:
            logger.warning(
                "%s Health check cycle error; will retry: %s",
                LOG_PREFIX,
                exc,
            )
            await asyncio.sleep(DIFY_HEALTH_POLL_INTERVAL_SECONDS)
