"""Tests for the Dify server health cache + active/standby failover resolver."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Optional, cast

import pytest

import services.dify.org_mindmate_client as resolver
from models.domain.auth import Organization
from services.redis.cache.redis_dify_server_health_cache import (
    HEALTH_FAILURE_THRESHOLD,
    DifyServerHealth,
    _deserialize,
)


def _health(online: bool, failures: int) -> DifyServerHealth:
    now = time.time()
    return DifyServerHealth(
        online=online,
        consecutive_failures=failures,
        last_ok_at=now if online else None,
        last_checked_at=now,
    )


def test_considered_down_requires_threshold() -> None:
    """A server is only 'down' once failures cross the anti-flap threshold."""
    assert _health(True, 0).considered_down is False
    assert _health(False, HEALTH_FAILURE_THRESHOLD - 1).considered_down is False
    assert _health(False, HEALTH_FAILURE_THRESHOLD).considered_down is True


def test_deserialize_round_trip_and_bad_input() -> None:
    """Snapshot JSON deserializes; malformed input yields None."""
    snap = _deserialize('{"online": true, "consecutive_failures": 0, "last_ok_at": 1.0, "last_checked_at": 2.0}')
    assert snap is not None
    assert snap.online is True
    assert _deserialize("not json") is None
    assert _deserialize("[]") is None


def _org() -> Organization:
    return cast(
        Organization,
        SimpleNamespace(
            id=42,
            dify_api_base_url="https://s1/v1",
            dify_api_key="k1",
            dify_api_base_url_2="https://s2/v1",
            dify_api_key_2="k2",
            dify_active_server=1,
            dify_failover_enabled=True,
        ),
    )


@pytest.mark.asyncio
async def test_resolver_prefers_healthy_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no recorded health, the primary server is used."""

    async def fake_health(_org_id: int, _server: int) -> Optional[DifyServerHealth]:
        return None

    monkeypatch.setattr(resolver, "get_server_health", fake_health)
    assert await resolver.select_active_dify_server(_org()) == 1


@pytest.mark.asyncio
async def test_resolver_fails_over_when_primary_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """Primary down + standby up routes to the standby."""

    async def fake_health(_org_id: int, server: int) -> Optional[DifyServerHealth]:
        if server == 1:
            return _health(False, HEALTH_FAILURE_THRESHOLD)
        return _health(True, 0)

    monkeypatch.setattr(resolver, "get_server_health", fake_health)
    assert await resolver.select_active_dify_server(_org()) == 2


@pytest.mark.asyncio
async def test_resolver_switches_back_on_recovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Once the primary recovers (not considered down), it is preferred again."""

    async def fake_health(_org_id: int, server: int) -> Optional[DifyServerHealth]:
        if server == 1:
            return _health(False, HEALTH_FAILURE_THRESHOLD - 1)  # below threshold
        return _health(True, 0)

    monkeypatch.setattr(resolver, "get_server_health", fake_health)
    assert await resolver.select_active_dify_server(_org()) == 1


@pytest.mark.asyncio
async def test_resolver_no_failover_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """With failover disabled the primary is kept even when unhealthy."""

    async def fake_health(_org_id: int, _server: int) -> Optional[DifyServerHealth]:
        return _health(False, HEALTH_FAILURE_THRESHOLD)

    org = _org()
    org.dify_failover_enabled = False
    monkeypatch.setattr(resolver, "get_server_health", fake_health)
    assert await resolver.select_active_dify_server(org) == 1


@pytest.mark.asyncio
async def test_resolver_uses_standby_when_primary_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the primary has no credentials, the standby is used regardless."""

    async def fake_health(_org_id: int, _server: int) -> Optional[DifyServerHealth]:
        return None

    org = _org()
    org.dify_api_base_url = None
    org.dify_api_key = None
    monkeypatch.setattr(resolver, "get_server_health", fake_health)
    assert await resolver.select_active_dify_server(org) == 2


@pytest.mark.asyncio
async def test_resolver_fails_over_for_one_and_three_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """School on servers 1+3 fails over from 1 to 3 when primary is down."""
    from services.dify.dify_server_schema import clear_dify_server_schema_cache, organization_dify_server_slots

    clear_dify_server_schema_cache()
    monkeypatch.setattr(
        "services.dify.dify_server_schema._organization_column_names",
        lambda: frozenset(
            {
                "dify_api_base_url",
                "dify_api_key",
                "dify_api_base_url_2",
                "dify_api_key_2",
                "dify_api_base_url_3",
                "dify_api_key_3",
            }
        ),
    )
    organization_dify_server_slots.cache_clear()

    async def fake_health(_org_id: int, server: int) -> Optional[DifyServerHealth]:
        if server == 1:
            return _health(False, HEALTH_FAILURE_THRESHOLD)
        if server == 3:
            return _health(True, 0)
        return None

    org = cast(
        Organization,
        SimpleNamespace(
            id=42,
            dify_api_base_url="https://s1/v1",
            dify_api_key="k1",
            dify_api_base_url_2=None,
            dify_api_key_2=None,
            dify_api_base_url_3="https://s3/v1",
            dify_api_key_3="k3",
            dify_active_server=1,
            dify_failover_enabled=True,
        ),
    )
    monkeypatch.setattr(resolver, "get_server_health", fake_health)
    assert await resolver.select_active_dify_server(org) == 3
    clear_dify_server_schema_cache()


@pytest.mark.asyncio
async def test_resolver_keeps_primary_when_standby_also_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When both servers are down, the resolver stays on the primary."""

    async def fake_health(_org_id: int, _server: int) -> Optional[DifyServerHealth]:
        return _health(False, HEALTH_FAILURE_THRESHOLD)

    monkeypatch.setattr(resolver, "get_server_health", fake_health)
    assert await resolver.select_active_dify_server(_org()) == 1
