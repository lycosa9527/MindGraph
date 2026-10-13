"""
Pure failover routing decisions from cached Dify server health snapshots.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os
import time
from typing import Optional

from services.redis.cache.redis_dify_server_health_cache import DifyServerHealth


def positive_int_env(name: str, default: int) -> int:
    """Return a positive integer from the environment, or *default* when unset or invalid."""
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value <= 0:
        return default
    return value


def health_max_age_seconds() -> float:
    """Treat health snapshots older than this as stale (not trusted for routing)."""
    poll_interval = positive_int_env("DIFY_HEALTH_POLL_INTERVAL_SECONDS", 120)
    default = float(poll_interval * 4 + 60)
    raw = (os.getenv("DIFY_HEALTH_MAX_AGE_SECONDS") or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if value <= 0:
        return default
    return value


def is_health_fresh(
    snapshot: Optional[DifyServerHealth],
    *,
    max_age_s: Optional[float] = None,
) -> bool:
    """True when a snapshot exists and was updated recently enough to trust."""
    if snapshot is None:
        return False
    limit = health_max_age_seconds() if max_age_s is None else max_age_s
    return (time.time() - snapshot.last_checked_at) <= limit


def server_is_routable(snapshot: Optional[DifyServerHealth]) -> bool:
    """True when cached health says the server is fresh and not offline."""
    if snapshot is None or not is_health_fresh(snapshot):
        return False
    return bool(snapshot.online) and not snapshot.considered_down


def choose_failover_route(
    primary: int,
    partner: int,
    primary_health: Optional[DifyServerHealth],
    partner_health: Optional[DifyServerHealth],
) -> int:
    """
    Pick primary or partner for live MindMate traffic.

    Prefers a fresh, healthy primary. Fails over when that primary's snapshot
    is stale or considered down and the partner is usable. A missing primary
    snapshot stays on primary: the host has not been checked, or it is not one
    of the two shared Dify URLs.
    """
    if primary_health is None or server_is_routable(primary_health):
        return primary

    # Anti-flap: a fresh primary that failed once is not yet considered down.
    if is_health_fresh(primary_health) and not primary_health.considered_down:
        return primary

    if server_is_routable(partner_health):
        return partner

    if primary_health.considered_down and (partner_health is None or not partner_health.considered_down):
        return partner

    return primary
