"""Tests for thinking coin client event earns."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.auth.thinking_coin import client_event_earn as earn_mod
from utils.auth.thinking_coin_config import HANDLER_CLIENT_EVENT


def _client_task(slug: str, event_key: str, reward: int = 10) -> MagicMock:
    task = MagicMock()
    task.id = 42
    task.slug = slug
    task.reward_amount = reward
    task.monthly_cap = None
    task.handler_key = HANDLER_CLIENT_EVENT
    task.action_config = {"event_key": event_key}
    task.is_active = True
    return task


@pytest.mark.asyncio
async def test_client_event_credits_matching_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Matching event_key credits once."""
    task = _client_task("daily_mindmate_share", "mindmate_share")
    db = AsyncMock()

    monkeypatch.setattr(earn_mod, "load_active_tasks", AsyncMock(return_value=[task]))
    monkeypatch.setattr(earn_mod, "_event_done_today", AsyncMock(return_value=False))
    monkeypatch.setattr(earn_mod, "task_monthly_cap_reached", AsyncMock(return_value=False))
    monkeypatch.setattr(earn_mod, "daily_earn_cap_blocks", AsyncMock(return_value=False))
    monkeypatch.setattr(earn_mod, "credit_wallet", AsyncMock(return_value=110))

    credited, slug = await earn_mod.try_client_event_earn(db, 1, "mindmate_share")
    assert credited == 10
    assert slug == "daily_mindmate_share"


@pytest.mark.asyncio
async def test_client_event_skips_unknown_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown event_key returns zero."""
    db = AsyncMock()
    monkeypatch.setattr(earn_mod, "load_active_tasks", AsyncMock(return_value=[]))

    credited, slug = await earn_mod.try_client_event_earn(db, 1, "unknown")
    assert credited == 0
    assert slug is None
