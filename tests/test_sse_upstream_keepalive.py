"""Tests for SSE upstream keepalive bridge."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from services.infrastructure.http.sse_upstream_keepalive import iter_upstream_with_keepalive


async def _slow_upstream() -> AsyncIterator[str]:
    yield "first"
    await asyncio.sleep(0.05)
    yield "second"


@pytest.mark.asyncio
async def test_iter_upstream_with_keepalive_yields_all_items() -> None:
    """All upstream items are forwarded when they arrive faster than the interval."""
    items: list[str | None] = []
    async for item in iter_upstream_with_keepalive(_slow_upstream(), interval_seconds=60.0):
        items.append(item)
    assert items == ["first", "second"]


@pytest.mark.asyncio
async def test_iter_upstream_with_keepalive_emits_none_on_silence() -> None:
    """None is yielded when upstream is silent longer than the keepalive interval."""

    async def _delayed() -> AsyncIterator[str]:
        await asyncio.sleep(0.05)
        yield "only"

    items: list[str | None] = []
    async for item in iter_upstream_with_keepalive(_delayed(), interval_seconds=0.01):
        items.append(item)
    assert None in items
    assert items[-1] == "only"
