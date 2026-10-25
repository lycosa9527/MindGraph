"""Tests for release_open_transaction helper."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.db.session_open import release_open_transaction, request_rls_session


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


def test_request_rls_session_uses_the_request_context() -> None:
    """A stream read must use the RLS context middleware already set."""
    ctx = object()
    sentinel = object()
    with (
        patch("utils.db.session_open.get_rls_context", return_value=ctx),
        patch("utils.db.session_open.rls_async_session", return_value=sentinel) as opened,
    ):
        assert request_rls_session(object()) is sentinel
    opened.assert_called_once_with(ctx)


def test_request_rls_session_prefers_request_state() -> None:
    """request.state survives BaseHTTPMiddleware dropping the ContextVar."""
    pinned = object()
    stale = object()
    sentinel = object()
    request = SimpleNamespace(state=SimpleNamespace(rls_context=pinned))
    with (
        patch("utils.db.session_open.get_rls_context", return_value=stale),
        patch("utils.db.session_open.rls_async_session", return_value=sentinel) as opened,
    ):
        assert request_rls_session(object(), request) is sentinel
    opened.assert_called_once_with(pinned)


def test_request_rls_session_falls_back_to_the_actor() -> None:
    """Direct calls with no request context still open a user session."""
    user = object()
    sentinel = object()
    with (
        patch("utils.db.session_open.get_rls_context", return_value=None),
        patch("utils.db.session_open.actor_rls_session", return_value=sentinel) as opened,
    ):
        assert request_rls_session(user) is sentinel
    opened.assert_called_once_with(user)
