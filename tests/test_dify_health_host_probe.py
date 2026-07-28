"""Tests for host-level Dify failover probe classification and key retry."""

from __future__ import annotations

from typing import List, Optional, Tuple
from unittest.mock import AsyncMock

import pytest

from services.dify.dify_health_host_probe import (
    check_dify_host_reachable,
    classify_host_probe_outcome,
    is_dify_auth_failure,
)

_ProbeOutcome = Tuple[bool, Optional[int], Optional[str]]


def test_is_dify_auth_failure_detects_http_codes() -> None:
    """401/403 are auth failures; timeouts and 5xx are not."""
    assert is_dify_auth_failure(401, "http_401")
    assert is_dify_auth_failure(403, None)
    assert not is_dify_auth_failure(500, "http_500")
    assert not is_dify_auth_failure(None, "timeout")


def test_classify_host_probe_outcome_prefers_success() -> None:
    """A later successful key wins over an earlier auth failure."""
    assert classify_host_probe_outcome(
        [
            (False, 401, "http_401"),
            (True, 200, None),
        ]
    ) == (True, 200, None)


def test_classify_host_probe_outcome_auth_only_means_host_online() -> None:
    """Auth-only responses still mean the Dify host answered."""
    assert classify_host_probe_outcome(
        [
            (False, 401, "http_401"),
            (False, 403, "http_403"),
        ]
    ) == (True, 403, "http_403")


def test_classify_host_probe_outcome_unreachable_stays_offline() -> None:
    """Timeouts and non-auth HTTP errors mark the host offline."""
    assert classify_host_probe_outcome(
        [
            (False, 401, "http_401"),
            (False, None, "timeout"),
        ]
    ) == (False, None, "timeout")
    assert classify_host_probe_outcome([(False, 502, "http_502")]) == (False, 502, "http_502")


@pytest.mark.asyncio
async def test_check_dify_host_reachable_retries_after_auth_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Host probe tries the next candidate key after 401."""
    calls: List[str] = []

    async def _fake(base_url: str, api_key: str, *, timeout_s: float = 10.0) -> _ProbeOutcome:
        del base_url, timeout_s
        calls.append(api_key)
        if api_key == "bad":
            return False, 401, "http_401"
        return True, 200, None

    monkeypatch.setattr(
        "services.dify.dify_health_host_probe.check_dify_app_api_reachable",
        _fake,
    )
    online, status, err = await check_dify_host_reachable(
        "https://main/v1",
        ["bad", "good"],
    )
    assert online is True
    assert status == 200
    assert err is None
    assert calls == ["bad", "good"]


@pytest.mark.asyncio
async def test_check_dify_host_reachable_stops_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unreachable hosts fail fast without trying remaining keys."""
    fake = AsyncMock(return_value=(False, None, "timeout"))
    monkeypatch.setattr(
        "services.dify.dify_health_host_probe.check_dify_app_api_reachable",
        fake,
    )
    online, status, err = await check_dify_host_reachable(
        "https://main/v1",
        ["k1", "k2"],
    )
    assert online is False
    assert status is None
    assert err == "timeout"
    assert fake.await_count == 1


@pytest.mark.asyncio
async def test_check_dify_host_reachable_all_auth_failures_still_online(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every candidate key rejected still counts as host reachable for failover."""

    async def _fake(base_url: str, api_key: str, *, timeout_s: float = 10.0) -> _ProbeOutcome:
        del base_url, api_key, timeout_s
        return False, 401, "http_401"

    monkeypatch.setattr(
        "services.dify.dify_health_host_probe.check_dify_app_api_reachable",
        _fake,
    )
    online, status, err = await check_dify_host_reachable(
        "https://main/v1",
        ["a", "b"],
    )
    assert online is True
    assert status == 401
    assert err == "http_401"
