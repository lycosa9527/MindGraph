"""Tests for thinking coin monthly earn caps."""

from __future__ import annotations

from datetime import UTC
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.auth.thinking_coin import monthly_cap as cap_mod
from services.auth.thinking_coin.dates import beijing_month_utc_bounds


def test_beijing_month_bounds_ordering() -> None:
    """Month window start precedes end."""
    start, end = beijing_month_utc_bounds()
    assert start.tzinfo is UTC
    assert end.tzinfo is UTC
    assert start < end


@pytest.mark.asyncio
async def test_monthly_cap_reached_when_at_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cap blocks further earns when count meets monthly_cap."""
    task = MagicMock()
    task.id = 7
    task.monthly_cap = 2

    db = AsyncMock()
    monkeypatch.setattr(cap_mod, "monthly_earn_count_for_task", AsyncMock(return_value=2))

    reached = await cap_mod.task_monthly_cap_reached(db, 1, task)
    assert reached is True


@pytest.mark.asyncio
async def test_monthly_cap_open_when_unlimited() -> None:
    """Null monthly_cap never blocks."""
    task = MagicMock()
    task.monthly_cap = None

    db = AsyncMock()
    reached = await cap_mod.task_monthly_cap_reached(db, 1, task)
    assert reached is False
