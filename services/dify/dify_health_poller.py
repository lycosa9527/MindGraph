"""
Background heartbeat poller for per-organization Dify servers.

Platform monitoring walks every schema slot (1, 2, 3, …) and probes each unique
URL/key any school uses on that slot. Per-school failover logs and routing use
only the pair that school configured (e.g. 1+2, 2+3, or 1+3).

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

from models.domain.auth import Organization
from services.dify.dify_health_logging import (
    LOG_PREFIX,
    health_status_text,
    org_label,
    probe_failure_reason,
    server_label,
    traffic_route_sentence,
)
from services.dify.dify_health_org_loader import load_orgs_with_dify_credentials
from services.dify.dify_health_probe_plan import (
    DifyProbeAssignment,
    DifyProbePlan,
    DifyProbeTarget,
    build_deduped_probe_plan,
    probe_target_key,
)
from services.dify.dify_server_schema import organization_dify_server_slots
from services.dify.dify_servers import (
    configured_dify_servers,
    failover_partner_server,
    org_eligible_for_failover_probing,
    primary_server_no,
)
from services.dify.org_mindmate_client import select_active_dify_server
from services.mindbot.dify.service_health import check_dify_app_api_reachable
from services.redis import keys as _keys
from services.redis.cache.redis_dify_server_health_cache import (
    DifyServerHealth,
    HEALTH_FAILURE_THRESHOLD,
    get_server_health,
    record_probe_result,
)
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS, REDIS_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

DIFY_HEALTH_POLL_INTERVAL_SECONDS = int(os.getenv("DIFY_HEALTH_POLL_INTERVAL_SECONDS", "30"))
DIFY_PROBE_CONCURRENCY = max(1, int(os.getenv("DIFY_PROBE_CONCURRENCY", "10")))
_LOCK_REFRESH_EVERY_ASSIGNMENTS = 25

_POLLER_CYCLE_ERRORS = BACKGROUND_INFRA_ERRORS + DATABASE_ERRORS + REDIS_ERRORS

_LOCK_KEY = _keys.DIFY_HEALTH_POLLER_LOCK
_LOCK_TTL = _keys.TTL_DIFY_HEALTH_POLLER_LOCK

_ProbeOutcome = Tuple[bool, Optional[int], Optional[str]]


class _PollerLockState:
    """Holds this worker's lock token across loop iterations."""

    __slots__ = ("lock_id", "is_holder")

    def __init__(self) -> None:
        """init  ."""
        self.lock_id = f"{os.getpid()}:{uuid.uuid4().hex[:8]}"
        self.is_holder = False


_lock_state = _PollerLockState()


def _server_role(org: Organization, server: int) -> str:
    """Return a human-readable role label for logging."""
    primary = primary_server_no(org)
    if server == primary:
        return "primary"
    partner = failover_partner_server(org)
    if partner is not None and server == partner:
        return "standby"
    return f"server_{server}"


def _was_considered_down(previous: Optional[DifyServerHealth]) -> bool:
    if previous is None:
        return False
    return previous.considered_down


def _log_probe_transition(
    org: Organization,
    server: int,
    role: str,
    previous: Optional[DifyServerHealth],
    snapshot: DifyServerHealth,
    http_status: Optional[int],
    err: Optional[str],
) -> None:
    """Emit detail logs when a probe outcome or offline threshold changes."""
    school = org_label(org)
    target = server_label(server, role)
    prev_down = _was_considered_down(previous)
    now_down = snapshot.considered_down
    reason = probe_failure_reason(http_status, err)
    threshold = HEALTH_FAILURE_THRESHOLD

    if snapshot.online:
        if previous is None:
            logger.info(
                "%s %s: %s responded OK on first health check.",
                LOG_PREFIX,
                school,
                target,
            )
        elif not previous.online:
            logger.info(
                "%s %s: %s is back online.",
                LOG_PREFIX,
                school,
                target,
            )
        elif prev_down and not now_down:
            logger.info(
                "%s %s: %s passed health check again and is available for traffic.",
                LOG_PREFIX,
                school,
                target,
            )
        return

    failures = snapshot.consecutive_failures
    if previous is None or previous.online:
        logger.warning(
            "%s %s: %s health check failed (%s). %s of %s failures before failover.",
            LOG_PREFIX,
            school,
            target,
            reason,
            failures,
            threshold,
        )
    elif not prev_down and now_down:
        logger.warning(
            "%s %s: %s marked offline after %s failed checks (%s).",
            LOG_PREFIX,
            school,
            target,
            failures,
            reason,
        )


def _log_org_heartbeat_summary(
    org: Organization,
    health_by_server: Dict[int, Optional[DifyServerHealth]],
    active_route: Optional[int],
) -> None:
    """One readable line per org each heartbeat cycle."""
    servers = configured_dify_servers(org)
    status_parts = []
    for creds in servers:
        role = _server_role(org, creds.server)
        label = server_label(creds.server, role)
        status_parts.append(f"{label} is {health_status_text(health_by_server.get(creds.server))}")

    primary = primary_server_no(org)
    partner = failover_partner_server(org)
    partner_no = partner if partner is not None else primary
    route_note = traffic_route_sentence(
        active_route,
        primary,
        partner_no,
        health_by_server.get(primary),
        health_by_server.get(partner_no),
    )
    logger.debug(
        "%s %s: %s. %s",
        LOG_PREFIX,
        org_label(org),
        "; ".join(status_parts),
        route_note,
    )


def _log_routing_change(
    org: Organization,
    route_before: Optional[int],
    route_after: Optional[int],
) -> None:
    """Log when live routing switches between main and backup servers."""
    if route_before == route_after:
        return
    school = org_label(org)
    primary = primary_server_no(org)
    partner = failover_partner_server(org)
    main = server_label(primary, "primary")
    if partner is None:
        logger.warning(
            "%s %s: MindMate traffic routing changed to server %s.",
            LOG_PREFIX,
            school,
            route_after,
        )
        return
    backup = server_label(partner, "standby")
    if route_after == primary:
        logger.info(
            "%s %s: MindMate traffic restored to %s.",
            LOG_PREFIX,
            school,
            main,
        )
        return
    if route_after == partner:
        logger.warning(
            "%s %s: MindMate traffic switched from %s to %s because the main server is offline.",
            LOG_PREFIX,
            school,
            main,
            backup,
        )
        return
    logger.warning(
        "%s %s: MindMate traffic routing changed to server %s.",
        LOG_PREFIX,
        school,
        route_after,
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


async def _load_orgs_with_dify_credentials() -> List[Organization]:
    """Return every school that configures at least one Dify server slot."""
    async with system_rls_session() as db:
        return await load_orgs_with_dify_credentials(db)


def _failover_orgs(orgs: List[Organization]) -> List[Organization]:
    """Schools that participate in automatic failover (enabled + configured pair)."""
    return [org for org in orgs if org_eligible_for_failover_probing(org)]


async def _probe_unique_target(
    target: DifyProbeTarget,
    semaphore: asyncio.Semaphore,
) -> _ProbeOutcome:
    """Run one deduplicated HTTP health check with bounded concurrency."""
    async with semaphore:
        return await check_dify_app_api_reachable(target.api_url, target.api_key)


async def _run_deduped_probes(plan: DifyProbePlan) -> Dict[Tuple[str, str], _ProbeOutcome]:
    """Probe each unique endpoint once and index results by URL/key."""
    if not plan.unique_targets:
        return {}
    semaphore = asyncio.Semaphore(DIFY_PROBE_CONCURRENCY)
    outcomes = await asyncio.gather(*(_probe_unique_target(target, semaphore) for target in plan.unique_targets))
    return {probe_target_key(target): outcome for target, outcome in zip(plan.unique_targets, outcomes, strict=True)}


async def _apply_assignment(
    org: Organization,
    assignment: DifyProbeAssignment,
    outcome: _ProbeOutcome,
) -> None:
    """Persist one school's server-slot result and log state transitions."""
    online, http_status, err = outcome
    previous = await get_server_health(org.id, assignment.server)
    snapshot = await record_probe_result(
        org.id,
        assignment.server,
        online,
        previous=previous,
    )
    _log_probe_transition(
        org,
        assignment.server,
        _server_role(org, assignment.server),
        previous,
        snapshot,
        http_status,
        err,
    )


async def _finalize_org(org: Organization, route_before: Optional[int]) -> None:
    """Emit per-school summary and routing logs after all server slots are updated."""
    health_by_server: Dict[int, Optional[DifyServerHealth]] = {}
    for creds in configured_dify_servers(org):
        health_by_server[creds.server] = await get_server_health(org.id, creds.server)

    route_after = await select_active_dify_server(org)
    _log_org_heartbeat_summary(org, health_by_server, route_after)
    _log_routing_change(org, route_before, route_after)


async def _probe_once() -> None:
    """Probe unique endpoints once, then fan results to each school's server slots."""
    monitor_orgs = await _load_orgs_with_dify_credentials()
    if not monitor_orgs:
        logger.debug("%s No schools with Dify server credentials are configured.", LOG_PREFIX)
        return

    failover_orgs = _failover_orgs(monitor_orgs)
    plan = build_deduped_probe_plan(monitor_orgs)
    schema_slots = organization_dify_server_slots()
    logger.debug(
        "%s Health check cycle: %s unique endpoint(s) across schema slot(s) %s; "
        "%s school(s) contribute credentials (%s org/server assignment(s)).",
        LOG_PREFIX,
        plan.unique_endpoint_count,
        list(plan.monitored_schema_slots) or list(schema_slots),
        plan.contributing_school_count,
        plan.server_slot_count,
    )

    outcomes = await _run_deduped_probes(plan)
    org_by_id = {org.id: org for org in monitor_orgs}
    route_before_by_org: Dict[int, Optional[int]] = {}
    for org in failover_orgs:
        route_before_by_org[org.id] = await select_active_dify_server(org)

    assignments_applied = 0
    for target, assignments in plan.assignments_by_target:
        outcome = outcomes[probe_target_key(target)]
        for assignment in assignments:
            org = org_by_id.get(assignment.org_id)
            if org is None:
                continue
            await _apply_assignment(org, assignment, outcome)
            assignments_applied += 1
            if assignments_applied % _LOCK_REFRESH_EVERY_ASSIGNMENTS == 0:
                if not await _acquire_or_refresh_lock():
                    logger.warning(
                        "%s Lost health-check lock mid-cycle; stopping fan-out early.",
                        LOG_PREFIX,
                    )
                    return

    for org in failover_orgs:
        await _finalize_org(org, route_before_by_org.get(org.id))


async def start_dify_health_poller() -> None:
    """
    Run the Dify server heartbeat loop on the single Redis lock holder.

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
                await asyncio.sleep(DIFY_HEALTH_POLL_INTERVAL_SECONDS)
                continue

            if not _lock_state.is_holder:
                logger.info(
                    "%s This worker will run platform Dify health checks.",
                    LOG_PREFIX,
                )
                _lock_state.is_holder = True

            await _probe_once()
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
