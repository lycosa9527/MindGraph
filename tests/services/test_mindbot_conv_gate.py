"""Tests for MindBot Redis conversation gate helpers."""

from __future__ import annotations

import pytest

from services.mindbot.core.conv_gate import (
    CONV_GATE_SENTINEL,
    gate_key_for,
    normalize_dify_conversation_id_from_redis,
    poll_dify_conv_key_async,
)


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
    monkeypatch.setenv("MINDBOT_CONV_GATE_POLL_MS", "500")
    monkeypatch.setenv("MINDBOT_CONV_GATE_POLL_STEP_MS", "50")
    calls = {"n": 0}

    async def fake_get(_key: str) -> str | None:
        calls["n"] += 1
        if calls["n"] < 2:
            return None
        return "conv-bound"

    result = await poll_dify_conv_key_async(fake_get, "mindbot:dify_conv:1:x")
    assert result == "conv-bound"


@pytest.mark.asyncio
async def test_poll_returns_none_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_CONV_GATE_POLL_MS", "80")
    monkeypatch.setenv("MINDBOT_CONV_GATE_POLL_STEP_MS", "30")

    async def never_get(_key: str) -> None:
        return None

    result = await poll_dify_conv_key_async(never_get, "k")
    assert result is None
