"""Tests for MindBot Redis conversation gate helpers."""

from __future__ import annotations

import pytest

from services.mindbot.core.conv_gate import (
    CONV_GATE_SENTINEL,
    _conv_gate_poll_step_initial_ms,
    _conv_gate_poll_total_ms,
    _conv_gate_ttl_seconds,
    gate_key_for,
    normalize_dify_conversation_id_from_redis,
    poll_dify_conv_key_async,
)


def _clear_conv_gate_caches() -> None:
    """Clear all @functools.cache on conv_gate env-reader functions.

    Must be called at the start of any test that uses monkeypatch.setenv for
    MINDBOT_CONV_GATE_* variables, otherwise cached values from earlier tests
    in the same process can make tests order-dependent.
    """
    _conv_gate_poll_total_ms.cache_clear()
    _conv_gate_poll_step_initial_ms.cache_clear()
    _conv_gate_ttl_seconds.cache_clear()


def test_gate_key_format() -> None:
    assert gate_key_for(10, "cid-1") == "mindbot:conv_gate:10:cid-1"


def test_normalize_redis_conv_skips_gate_sentinel() -> None:
    assert normalize_dify_conversation_id_from_redis(CONV_GATE_SENTINEL) is None
    assert normalize_dify_conversation_id_from_redis(f"  {CONV_GATE_SENTINEL}  ") is None


def test_normalize_redis_conv_keeps_uuid() -> None:
    cid = "550e8400-e29b-41d4-a716-446655440000"
    assert normalize_dify_conversation_id_from_redis(cid) == cid
    assert normalize_dify_conversation_id_from_redis(f"  {cid}  ") == cid


def test_normalize_redis_conv_empty() -> None:
    assert normalize_dify_conversation_id_from_redis(None) is None
    assert normalize_dify_conversation_id_from_redis("") is None
    assert normalize_dify_conversation_id_from_redis("   ") is None


@pytest.mark.asyncio
async def test_poll_returns_when_key_appears(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_conv_gate_caches()
    monkeypatch.setenv("MINDBOT_CONV_GATE_POLL_MS", "500")
    monkeypatch.setenv("MINDBOT_CONV_GATE_POLL_STEP_MS", "50")
    _clear_conv_gate_caches()
    calls = {"n": 0}

    async def fake_get(_key: str) -> str | None:
        calls["n"] += 1
        if calls["n"] < 2:
            return None
        return "conv-bound"

    result = await poll_dify_conv_key_async(fake_get, "mindbot:dify_conv:1:x")
    assert result == "conv-bound"
    _clear_conv_gate_caches()


@pytest.mark.asyncio
async def test_poll_returns_none_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_conv_gate_caches()
    # MINDBOT_CONV_GATE_POLL_MS=80 is below the minimum; the implementation
    # clamps it to max(100, ...) so the effective window is 100 ms.
    monkeypatch.setenv("MINDBOT_CONV_GATE_POLL_MS", "80")
    monkeypatch.setenv("MINDBOT_CONV_GATE_POLL_STEP_MS", "30")
    _clear_conv_gate_caches()

    async def never_get(_key: str) -> None:
        return None

    result = await poll_dify_conv_key_async(never_get, "k")
    assert result is None
    _clear_conv_gate_caches()
