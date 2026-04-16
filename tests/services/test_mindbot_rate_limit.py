"""Tests for MindBot per-org rate limiter (Redis + in-memory fallback)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from services.mindbot.infra.rate_limit import (
    _mem_counters,
    check_org_rate_limit,
)


# ---------------------------------------------------------------------------
# check_org_rate_limit via Redis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_passes_when_under_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("MINDBOT_ORG_RATE_LIMIT", "10")
    from services.mindbot.infra import rate_limit as rl_mod
    rl_mod._rate_limit_enabled.cache_clear()
    rl_mod._rate_limit_max.cache_clear()

    monkeypatch.setattr(rl_mod, "redis_incr_fixed_window", AsyncMock(return_value=5))
    _mem_counters.clear()

    result = await check_org_rate_limit(org_id=1)
    assert result is True

    rl_mod._rate_limit_enabled.cache_clear()
    rl_mod._rate_limit_max.cache_clear()


@pytest.mark.asyncio
async def test_rate_limit_rejects_when_over_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("MINDBOT_ORG_RATE_LIMIT", "10")
    from services.mindbot.infra import rate_limit as rl_mod
    rl_mod._rate_limit_enabled.cache_clear()
    rl_mod._rate_limit_max.cache_clear()

    monkeypatch.setattr(rl_mod, "redis_incr_fixed_window", AsyncMock(return_value=11))
    _mem_counters.clear()

    result = await check_org_rate_limit(org_id=2)
    assert result is False

    rl_mod._rate_limit_enabled.cache_clear()
    rl_mod._rate_limit_max.cache_clear()


@pytest.mark.asyncio
async def test_rate_limit_passes_exactly_at_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("MINDBOT_ORG_RATE_LIMIT", "10")
    from services.mindbot.infra import rate_limit as rl_mod
    rl_mod._rate_limit_enabled.cache_clear()
    rl_mod._rate_limit_max.cache_clear()

    monkeypatch.setattr(rl_mod, "redis_incr_fixed_window", AsyncMock(return_value=10))
    _mem_counters.clear()

    result = await check_org_rate_limit(org_id=3)
    assert result is True

    rl_mod._rate_limit_enabled.cache_clear()
    rl_mod._rate_limit_max.cache_clear()


@pytest.mark.asyncio
async def test_rate_limit_disabled_always_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_RATE_LIMIT_ENABLED", "false")
    from services.mindbot.infra import rate_limit as rl_mod
    rl_mod._rate_limit_enabled.cache_clear()

    monkeypatch.setattr(rl_mod, "redis_incr_fixed_window", AsyncMock(return_value=9999))
    _mem_counters.clear()

    result = await check_org_rate_limit(org_id=4)
    assert result is True

    rl_mod._rate_limit_enabled.cache_clear()


# ---------------------------------------------------------------------------
# Fallback to in-memory when Redis is unavailable (returns None)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_fallback_memory_passes_under_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINDBOT_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("MINDBOT_ORG_RATE_LIMIT", "5")
    from services.mindbot.infra import rate_limit as rl_mod
    rl_mod._rate_limit_enabled.cache_clear()
    rl_mod._rate_limit_max.cache_clear()

    monkeypatch.setattr(rl_mod, "redis_incr_fixed_window", AsyncMock(return_value=None))
    _mem_counters.clear()

    result = await check_org_rate_limit(org_id=10)
    assert result is True

    rl_mod._rate_limit_enabled.cache_clear()
    rl_mod._rate_limit_max.cache_clear()


@pytest.mark.asyncio
async def test_rate_limit_fallback_memory_rejects_when_over_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINDBOT_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("MINDBOT_ORG_RATE_LIMIT", "2")
    monkeypatch.setenv("MINDBOT_ORG_RATE_WINDOW_SECONDS", "60")
    from services.mindbot.infra import rate_limit as rl_mod
    rl_mod._rate_limit_enabled.cache_clear()
    rl_mod._rate_limit_max.cache_clear()
    rl_mod._rate_limit_window_seconds.cache_clear()

    monkeypatch.setattr(rl_mod, "redis_incr_fixed_window", AsyncMock(return_value=None))
    _mem_counters.clear()

    # First two calls should pass (counter goes 1, 2).
    assert await check_org_rate_limit(org_id=11) is True
    assert await check_org_rate_limit(org_id=11) is True
    # Third call exceeds limit of 2.
    assert await check_org_rate_limit(org_id=11) is False

    rl_mod._rate_limit_enabled.cache_clear()
    rl_mod._rate_limit_max.cache_clear()
    rl_mod._rate_limit_window_seconds.cache_clear()


# ---------------------------------------------------------------------------
# Memory counter eviction (max keys exceeded)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_mem_eviction_removes_oldest_on_overflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When _mem_counters exceeds max_keys, expired or oldest entries are evicted.

    MINDBOT_RATE_LIMIT_MEM_MAX_KEYS is clamped to min=100, so we pre-fill
    _mem_counters to exactly 100 entries and verify the 101st triggers eviction.
    """
    monkeypatch.setenv("MINDBOT_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("MINDBOT_ORG_RATE_LIMIT", "200")
    monkeypatch.setenv("MINDBOT_ORG_RATE_WINDOW_SECONDS", "60")
    monkeypatch.setenv("MINDBOT_RATE_LIMIT_MEM_MAX_KEYS", "100")
    from services.mindbot.infra import rate_limit as rl_mod
    rl_mod._rate_limit_enabled.cache_clear()
    rl_mod._rate_limit_max.cache_clear()
    rl_mod._rate_limit_window_seconds.cache_clear()
    rl_mod._mem_max_keys.cache_clear()

    monkeypatch.setattr(rl_mod, "redis_incr_fixed_window", AsyncMock(return_value=None))
    _mem_counters.clear()

    # Pre-fill to exactly 100 orgs.
    import time as _time
    for i in range(100):
        _mem_counters[90000 + i] = (1, _time.monotonic())
    assert len(_mem_counters) == 100

    # Adding a 101st org via check_org_rate_limit must not grow beyond 100.
    await check_org_rate_limit(org_id=99999)
    assert len(_mem_counters) <= 100, "Memory counter must be bounded by MINDBOT_RATE_LIMIT_MEM_MAX_KEYS"

    rl_mod._rate_limit_enabled.cache_clear()
    rl_mod._rate_limit_max.cache_clear()
    rl_mod._rate_limit_window_seconds.cache_clear()
    rl_mod._mem_max_keys.cache_clear()
    _mem_counters.clear()
