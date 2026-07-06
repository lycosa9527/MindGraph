"""Tests for thinking coin ledger earn-task enrichment."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest

from models.domain.thinking_coin import ThinkingCoinLedger
from services.auth.thinking_coin.ledger_enrichment import collect_earn_task_ids, load_earn_tasks_by_ids


def _ledger_row(ref_type: str | None, ref_id: str | None) -> ThinkingCoinLedger:
    return cast(
        ThinkingCoinLedger,
        SimpleNamespace(ref_type=ref_type, ref_id=ref_id),
    )


def test_collect_earn_task_ids_deduplicates_and_skips_invalid() -> None:
    """Only valid earn_task refs are collected once."""
    rows = [
        _ledger_row("earn_task", "12"),
        _ledger_row("earn_task", "12"),
        _ledger_row("earn_task", "bad"),
        _ledger_row("request_type", "mindmate"),
        _ledger_row(None, None),
    ]
    assert collect_earn_task_ids(rows) == [12]


@pytest.mark.asyncio
async def test_load_earn_tasks_by_ids_returns_empty_for_no_ids() -> None:
    """Empty id list avoids a database query."""
    db = AsyncMock()
    result = await load_earn_tasks_by_ids(db, [])
    assert result == {}
    db.execute.assert_not_called()
