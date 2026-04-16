"""Tests for MindBot in-memory circuit breaker (CircuitBreaker class and check_circuit_breaker)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from services.mindbot.infra.circuit_breaker import (
    CircuitBreaker,
    check_circuit_breaker,
    get_breaker,
    record_dify_failure,
    record_dify_success,
    _breakers,
)


def _fresh_breaker() -> CircuitBreaker:
    return CircuitBreaker()


# ---------------------------------------------------------------------------
# CircuitBreaker unit tests (in-memory only)
# ---------------------------------------------------------------------------


def test_breaker_starts_closed() -> None:
    cb = _fresh_breaker()
    assert not cb.is_open()
    assert not cb.is_half_open()


def test_breaker_opens_at_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "3")
    from services.mindbot.infra import circuit_breaker as cb_mod
    cb_mod._cb_failure_threshold.cache_clear()

    cb = _fresh_breaker()
    cb.record_failure("test-key")
    assert not cb.is_open()
    cb.record_failure("test-key")
    assert not cb.is_open()
    cb.record_failure("test-key")
    assert cb.is_open()

    cb_mod._cb_failure_threshold.cache_clear()


def test_breaker_resets_after_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "1")
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_RESET_SECONDS", "5")
    from services.mindbot.infra import circuit_breaker as cb_mod
    cb_mod._cb_failure_threshold.cache_clear()
    cb_mod._cb_reset_seconds.cache_clear()

    cb = _fresh_breaker()
    cb.record_failure("key")
    assert cb.is_open()

    # Simulate time passing beyond reset window.
    cb._opened_at = time.monotonic() - 10.0
    assert not cb.is_open()

    cb_mod._cb_failure_threshold.cache_clear()
    cb_mod._cb_reset_seconds.cache_clear()


def test_breaker_half_open_after_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "1")
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_RESET_SECONDS", "5")
    from services.mindbot.infra import circuit_breaker as cb_mod
    cb_mod._cb_failure_threshold.cache_clear()
    cb_mod._cb_reset_seconds.cache_clear()

    cb = _fresh_breaker()
    cb.record_failure("key")
    cb._opened_at = time.monotonic() - 10.0
    # After window: is_half_open should be True before is_open clears the flag.
    assert cb.is_half_open()

    cb_mod._cb_failure_threshold.cache_clear()
    cb_mod._cb_reset_seconds.cache_clear()


def test_breaker_closes_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "1")
    from services.mindbot.infra import circuit_breaker as cb_mod
    cb_mod._cb_failure_threshold.cache_clear()

    cb = _fresh_breaker()
    cb.record_failure("key")
    assert cb.is_open()
    cb.record_success()
    assert not cb.is_open()

    cb_mod._cb_failure_threshold.cache_clear()


# ---------------------------------------------------------------------------
# check_circuit_breaker integration tests (Redis mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_circuit_breaker_passes_when_redis_count_low(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_ENABLED", "true")
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")
    from services.mindbot.infra import circuit_breaker as cb_mod
    cb_mod._cb_enabled.cache_clear()
    cb_mod._cb_failure_threshold.cache_clear()

    monkeypatch.setattr(cb_mod, "redis_get", AsyncMock(return_value="2"))
    _breakers.clear()

    result = await check_circuit_breaker("org-99")
    assert result is True

    cb_mod._cb_enabled.cache_clear()
    cb_mod._cb_failure_threshold.cache_clear()


@pytest.mark.asyncio
async def test_check_circuit_breaker_rejects_when_redis_count_high(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_ENABLED", "true")
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "3")
    from services.mindbot.infra import circuit_breaker as cb_mod
    cb_mod._cb_enabled.cache_clear()
    cb_mod._cb_failure_threshold.cache_clear()

    monkeypatch.setattr(cb_mod, "redis_get", AsyncMock(return_value="5"))
    monkeypatch.setattr(cb_mod, "redis_setnx_ttl", AsyncMock(return_value=False))
    _breakers.clear()

    result = await check_circuit_breaker("org-100")
    assert result is False

    cb_mod._cb_enabled.cache_clear()
    cb_mod._cb_failure_threshold.cache_clear()


@pytest.mark.asyncio
async def test_check_circuit_breaker_disabled_always_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_ENABLED", "false")
    from services.mindbot.infra import circuit_breaker as cb_mod
    cb_mod._cb_enabled.cache_clear()

    monkeypatch.setattr(cb_mod, "redis_get", AsyncMock(return_value="9999"))
    _breakers.clear()

    result = await check_circuit_breaker("org-101")
    assert result is True

    cb_mod._cb_enabled.cache_clear()


@pytest.mark.asyncio
async def test_check_circuit_breaker_falls_back_to_memory_when_redis_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_ENABLED", "true")
    from services.mindbot.infra import circuit_breaker as cb_mod
    cb_mod._cb_enabled.cache_clear()

    monkeypatch.setattr(cb_mod, "redis_get", AsyncMock(return_value=None))
    _breakers.clear()

    result = await check_circuit_breaker("org-102")
    assert result is True

    cb_mod._cb_enabled.cache_clear()


@pytest.mark.asyncio
async def test_record_dify_success_resets_breaker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_ENABLED", "true")
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "1")
    from services.mindbot.infra import circuit_breaker as cb_mod
    cb_mod._cb_enabled.cache_clear()
    cb_mod._cb_failure_threshold.cache_clear()

    monkeypatch.setattr(cb_mod, "redis_delete", AsyncMock())
    _breakers.clear()

    cb = get_breaker("org-200")
    cb.record_failure("org-200")
    assert cb.is_open()

    await record_dify_success("org-200")
    assert not cb.is_open()

    cb_mod._cb_enabled.cache_clear()
    cb_mod._cb_failure_threshold.cache_clear()


@pytest.mark.asyncio
async def test_record_dify_failure_increments_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_ENABLED", "true")
    from services.mindbot.infra import circuit_breaker as cb_mod
    cb_mod._cb_enabled.cache_clear()

    mock_incr = AsyncMock(return_value=1)
    monkeypatch.setattr(cb_mod, "redis_incr_fixed_window", mock_incr)
    _breakers.clear()

    await record_dify_failure("org-201")
    mock_incr.assert_called_once()

    cb_mod._cb_enabled.cache_clear()


# ---------------------------------------------------------------------------
# New tests for production readiness gaps
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_circuit_breaker_probe_wins_allows_single_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When Redis count >= threshold and SETNX returns True, one probe is allowed."""
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_ENABLED", "true")
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "3")
    from services.mindbot.infra import circuit_breaker as cb_mod
    cb_mod._cb_enabled.cache_clear()
    cb_mod._cb_failure_threshold.cache_clear()

    # Redis count is above threshold, probe lock acquired (True).
    monkeypatch.setattr(cb_mod, "redis_get", AsyncMock(return_value="5"))
    monkeypatch.setattr(cb_mod, "redis_setnx_ttl", AsyncMock(return_value=True))
    _breakers.clear()

    result = await check_circuit_breaker("org-probe-wins")
    assert result is True, "Probe-wins path should allow the request through"

    cb_mod._cb_enabled.cache_clear()
    cb_mod._cb_failure_threshold.cache_clear()


@pytest.mark.asyncio
async def test_check_circuit_breaker_probe_setnx_none_falls_back_to_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When SETNX returns None (Redis error), fall back to in-memory breaker, not fail-close."""
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_ENABLED", "true")
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "3")
    from services.mindbot.infra import circuit_breaker as cb_mod
    cb_mod._cb_enabled.cache_clear()
    cb_mod._cb_failure_threshold.cache_clear()

    # Redis count is above threshold, SETNX returns None (Redis error).
    monkeypatch.setattr(cb_mod, "redis_get", AsyncMock(return_value="5"))
    monkeypatch.setattr(cb_mod, "redis_setnx_ttl", AsyncMock(return_value=None))
    _breakers.clear()

    # In-memory breaker has no failures recorded, so it should pass.
    result = await check_circuit_breaker("org-probe-setnx-none")
    assert result is True, "Redis SETNX None should fall back to in-memory (not fail-close)"

    cb_mod._cb_enabled.cache_clear()
    cb_mod._cb_failure_threshold.cache_clear()


@pytest.mark.asyncio
async def test_check_circuit_breaker_probe_setnx_none_uses_memory_open_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When SETNX returns None and in-memory breaker is open, the request is rejected."""
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_ENABLED", "true")
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "1")
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_RESET_SECONDS", "60")
    from services.mindbot.infra import circuit_breaker as cb_mod
    cb_mod._cb_enabled.cache_clear()
    cb_mod._cb_failure_threshold.cache_clear()
    cb_mod._cb_reset_seconds.cache_clear()

    monkeypatch.setattr(cb_mod, "redis_get", AsyncMock(return_value="5"))
    monkeypatch.setattr(cb_mod, "redis_setnx_ttl", AsyncMock(return_value=None))
    _breakers.clear()

    key = "org-probe-setnx-none-open"
    breaker = get_breaker(key)
    breaker.record_failure(key)
    assert breaker.is_open()

    result = await check_circuit_breaker(key)
    assert result is False, "In-memory open state should reject when Redis SETNX fails"

    cb_mod._cb_enabled.cache_clear()
    cb_mod._cb_failure_threshold.cache_clear()
    cb_mod._cb_reset_seconds.cache_clear()
    _breakers.clear()


def test_get_breaker_evicts_oldest_when_at_max(monkeypatch: pytest.MonkeyPatch) -> None:
    """When _breakers reaches max, the oldest key is evicted.

    MINDBOT_CIRCUIT_BREAKER_MAX_KEYS is clamped to min=100, so we pre-fill
    _breakers to exactly 100 entries (max) and verify the 101st evicts the first.
    """
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_MAX_KEYS", "100")
    from services.mindbot.infra import circuit_breaker as cb_mod
    cb_mod._cb_max_keys.cache_clear()
    _breakers.clear()

    for i in range(100):
        get_breaker(f"evict-key-{i}")
    assert "evict-key-0" in _breakers
    assert len(_breakers) == 100

    # Adding key 101 should evict evict-key-0 (oldest).
    get_breaker("evict-key-extra")
    assert "evict-key-0" not in _breakers, "Oldest key should have been evicted"
    assert "evict-key-extra" in _breakers
    assert len(_breakers) == 100, "Size must stay bounded at max_keys"

    cb_mod._cb_max_keys.cache_clear()
    _breakers.clear()


@pytest.mark.asyncio
async def test_record_dify_failure_uses_fixed_window_not_sliding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """record_dify_failure must call redis_incr_fixed_window (fixed window) not redis_incr_with_ttl."""
    monkeypatch.setenv("MINDBOT_CIRCUIT_BREAKER_ENABLED", "true")
    from services.mindbot.infra import circuit_breaker as cb_mod
    cb_mod._cb_enabled.cache_clear()

    fixed_window_mock = AsyncMock(return_value=1)
    monkeypatch.setattr(cb_mod, "redis_incr_fixed_window", fixed_window_mock)
    _breakers.clear()

    await record_dify_failure("org-fixed-window")
    fixed_window_mock.assert_called_once()

    cb_mod._cb_enabled.cache_clear()
