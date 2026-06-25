"""Tests for short-lived AdminScope auth (no request-scoped DB session)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from routers.auth.dependencies import get_admin_scope_short_lived
from utils.auth.admin_panel_permissions import CAP_PANEL_ACCESS, CAP_SCOPE_GLOBAL
from utils.auth.admin_scope import AdminScope


def _fake_scope() -> AdminScope:
    actor = MagicMock()
    actor.id = 3
    return AdminScope(
        actor=actor,
        role="superadmin",
        capabilities=frozenset({CAP_PANEL_ACCESS, CAP_SCOPE_GLOBAL}),
        org_ids=None,
        effective_org_id=None,
        read_only=False,
    )


@pytest.mark.asyncio
async def test_get_admin_scope_short_lived_does_not_open_async_session_local() -> None:
    """Long-running auth-only routes must not hold get_async_db for the handler."""
    request = Request({"type": "http", "headers": [], "method": "GET", "path": "/"})
    fake_scope = _fake_scope()

    with patch(
        "routers.auth.dependencies.build_admin_scope_async",
        new_callable=AsyncMock,
        return_value=fake_scope,
    ):
        with patch("config.database.AsyncSessionLocal") as session_factory:
            scope = await get_admin_scope_short_lived(
                request=request,
                organization_id=None,
                current_user=MagicMock(),
                lang="en",
            )

    session_factory.assert_not_called()
    assert scope is fake_scope
    assert request.state.rls_context is not None
