"""End-to-end Dify failover: main outage moves traffic to backup, recovery moves it back."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock

import pytest

import services.dify.dify_health_poller as poller
import services.dify.org_mindmate_client as resolver
import services.redis.cache.redis_dify_server_health_cache as health_cache
from models.domain.auth import Organization
from tests.typing_helpers import as_organization

_MAIN_URL = "https://main.example/v1"
_BACKUP_URL = "https://backup.example/v1"
_MAIN_KEY = "main-key"
_BACKUP_KEY = "backup-key"


class _HealthRedis:
    """In-memory stand-in for the health-cache GET / EVAL used by the poller."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, key: str) -> Optional[str]:
        """Return the stored snapshot, if any."""
        return self.values.get(key)

    async def eval(
        self,
        _script: str,
        _numkeys: int,
        key: str,
        now: str,
        online_flag: str,
        max_failures: str,
        _ttl: str,
    ) -> str:
        """Apply one probe the same way the Redis Lua script does."""
        previous: Optional[dict[str, object]] = None
        raw = self.values.get(key)
        if raw:
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                previous = loaded
        raw_failures = previous.get("consecutive_failures") if previous else 0
        prev_failures = int(raw_failures) if isinstance(raw_failures, (int, str)) else 0
        prev_last_ok = previous.get("last_ok_at") if previous else None
        online = online_flag == "1"
        if online:
            failures = 0
            last_ok: object = float(now)
        else:
            failures = min(prev_failures + 1, int(max_failures))
            last_ok = prev_last_ok
        payload = json.dumps(
            {
                "online": online,
                "consecutive_failures": failures,
                "last_ok_at": last_ok,
                "last_checked_at": float(now),
            }
        )
        self.values[key] = payload
        return payload


def _school() -> Organization:
    """A school with no per-slot override, so it uses the env main/backup pair."""
    return as_organization(
        SimpleNamespace(
            id=42,
            name="Example School",
            display_name="Example School",
            dify_api_base_url=None,
            dify_api_key=None,
            dify_api_base_url_2=None,
            dify_api_key_2=None,
            dify_active_server=1,
            dify_failover_enabled=True,
            dify_timeout_seconds=120,
        )
    )


def _install_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the process at the test main and backup Dify servers."""
    monkeypatch.setenv("DIFY_API_KEY", _MAIN_KEY)
    monkeypatch.setenv("DIFY_API_URL", _MAIN_URL)
    monkeypatch.setenv("DIFY_BACKUP_API_KEY", _BACKUP_KEY)
    monkeypatch.setenv("DIFY_BACKUP_API_URL", _BACKUP_URL)
    monkeypatch.setenv("DIFY_TIMEOUT", "300")


def _install_health_redis(monkeypatch: pytest.MonkeyPatch) -> _HealthRedis:
    """Route health reads and writes to an isolated Redis stand-in."""
    redis = _HealthRedis()
    monkeypatch.setattr(health_cache, "is_redis_available", lambda: True)
    monkeypatch.setattr(health_cache, "get_async_redis", lambda: redis)
    return redis


@pytest.mark.asyncio
async def test_main_outage_switches_to_backup_and_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Heartbeats drive live MindMate routing for a school on the env pair.

    One failed check stays on 主服务器. The next failed check moves traffic to
    备用服务器. The first successful check after recovery moves it back.
    """
    _install_env(monkeypatch)
    _install_health_redis(monkeypatch)
    school = _school()
    main_up = True

    async def probe(
        base_url: str,
        _api_keys: object,
    ) -> tuple[bool, Optional[int], Optional[str]]:
        """Report 主服务器 down only while the outage flag is set."""
        if base_url.rstrip("/") == _MAIN_URL and not main_up:
            return False, None, "connection_refused"
        return True, 200, None

    class _Result:
        def scalar_one_or_none(self) -> Organization:
            """The school row for this MindMate request."""
            return school

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result())
    monkeypatch.setattr(poller, "check_dify_host_reachable", probe)

    async def routed_url() -> str:
        client = await resolver.resolve_mindmate_dify_client(db, school.id)
        return client.api_url

    assert await routed_url() == _MAIN_URL

    await poller.run_dify_health_check_once([school])
    assert await routed_url() == _MAIN_URL

    main_up = False
    await poller.run_dify_health_check_once([school])
    assert await routed_url() == _MAIN_URL

    await poller.run_dify_health_check_once([school])
    client = await resolver.resolve_mindmate_dify_client(db, school.id)
    assert client.api_url == _BACKUP_URL
    assert client.api_key == _BACKUP_KEY

    main_up = True
    await poller.run_dify_health_check_once([school])
    client = await resolver.resolve_mindmate_dify_client(db, school.id)
    assert client.api_url == _MAIN_URL
    assert client.api_key == _MAIN_KEY
