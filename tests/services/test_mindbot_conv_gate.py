"""Tests for MindBot Redis conversation gate helpers."""

from __future__ import annotations

import pytest

from services.mindbot.core.conv_gate import (
    gate_key_for,
    poll_dify_conv_key_async,
)


def test_gate_key_format() -> None:
    assert gate_key_for(10, "cid-1") == "mindbot:conv_gate:10:cid-1"


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
