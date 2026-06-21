"""Tests for thinking coin daily earn cap."""

from __future__ import annotations

from datetime import UTC
from unittest.mock import AsyncMock

import pytest

from services.auth.thinking_coin import daily_cap as cap_mod
from services.auth.thinking_coin.dates import beijing_day_utc_bounds


def test_beijing_day_bounds_ordering() -> None:
    """Day window start precedes end."""
    start, end = beijing_day_utc_bounds()
    assert start.tzinfo is UTC
    assert end.tzinfo is UTC
    assert start < end


@pytest.mark.asyncio
async def test_daily_cap_blocks_when_over_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cap blocks credit when today's total plus amount would exceed cap."""
    db = AsyncMock()
    monkeypatch.setattr(cap_mod, "get_daily_earn_cap", AsyncMock(return_value=60))
    monkeypatch.setattr(cap_mod, "daily_earn_total_today", AsyncMock(return_value=50))

    blocked = await cap_mod.daily_earn_cap_blocks(db, 1, 15)
    assert blocked is True


@pytest.mark.asyncio
async def test_daily_cap_allows_when_under_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cap allows credit when total stays within limit."""
    db = AsyncMock()
    monkeypatch.setattr(cap_mod, "get_daily_earn_cap", AsyncMock(return_value=60))
    monkeypatch.setattr(cap_mod, "daily_earn_total_today", AsyncMock(return_value=45))

    blocked = await cap_mod.daily_earn_cap_blocks(db, 1, 15)
    assert blocked is False


@pytest.mark.asyncio
async def test_daily_cap_disabled_when_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cap of zero disables daily earn limiting."""
    db = AsyncMock()
    monkeypatch.setattr(cap_mod, "get_daily_earn_cap", AsyncMock(return_value=0))

    blocked = await cap_mod.daily_earn_cap_blocks(db, 1, 999)
    assert blocked is False


@pytest.mark.asyncio
async def test_daily_cap_allows_exactly_at_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Credit is allowed when it reaches but does not exceed the cap."""
    db = AsyncMock()
    monkeypatch.setattr(cap_mod, "get_daily_earn_cap", AsyncMock(return_value=60))
    monkeypatch.setattr(cap_mod, "daily_earn_total_today", AsyncMock(return_value=45))

    blocked = await cap_mod.daily_earn_cap_blocks(db, 1, 15)
    assert blocked is False
