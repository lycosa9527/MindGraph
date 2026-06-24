"""Tests for Dify failover routing decisions."""

from __future__ import annotations

import time

from services.dify.dify_failover_routing import (
    choose_failover_route,
    is_health_fresh,
    server_is_routable,
)
from services.redis.cache.redis_dify_server_health_cache import (
    HEALTH_FAILURE_THRESHOLD,
    DifyServerHealth,
)


def _snap(online: bool, failures: int = 0) -> DifyServerHealth:
    now = time.time()
    return DifyServerHealth(
        online=online,
        consecutive_failures=failures,
        last_ok_at=now if online else None,
        last_checked_at=now,
    )


def test_server_is_routable_requires_fresh_online() -> None:
    """Only fresh, online, non-down snapshots are routable."""
    assert server_is_routable(_snap(True, 0)) is True
    assert server_is_routable(_snap(False, HEALTH_FAILURE_THRESHOLD)) is False
    stale = DifyServerHealth(False, 0, None, 1.0)
    assert is_health_fresh(stale) is False
    assert server_is_routable(stale) is False


def test_choose_failover_route_prefers_healthy_primary() -> None:
    """Healthy primary wins even when partner is also healthy."""
    assert choose_failover_route(1, 2, _snap(True), _snap(True)) == 1


def test_choose_failover_route_fails_over_when_primary_down() -> None:
    """Primary considered down routes to healthy partner."""
    primary = _snap(False, HEALTH_FAILURE_THRESHOLD)
    partner = _snap(True, 0)
    assert choose_failover_route(1, 3, primary, partner) == 3


def test_choose_failover_route_keeps_primary_during_anti_flap() -> None:
    """One failed check (below threshold) stays on primary."""
    primary = _snap(False, HEALTH_FAILURE_THRESHOLD - 1)
    partner = _snap(True, 0)
    assert choose_failover_route(1, 2, primary, partner) == 1


def test_choose_failover_route_cold_start_stays_on_primary() -> None:
    """No cache data yet keeps traffic on the configured primary."""
    assert choose_failover_route(1, 2, None, None) == 1
