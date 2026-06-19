"""Tests for release_open_transaction helper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.db.session_open import release_open_transaction


@pytest.mark.asyncio
async def test_release_open_transaction_commits_when_active() -> None:
    """An open transaction is committed before slow external I/O."""
    db = MagicMock()
    db.in_transaction.return_value = True
    db.commit = AsyncMock()

    await release_open_transaction(db)

    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_release_open_transaction_skips_when_idle() -> None:
    """No commit when the session has no open transaction."""
    db = MagicMock()
    db.in_transaction.return_value = False
    db.commit = AsyncMock()

    await release_open_transaction(db)

    db.commit.assert_not_called()
