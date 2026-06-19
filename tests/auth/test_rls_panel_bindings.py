"""Tests for panel RLS binding on elevated routes."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from routers.auth.dependencies import (
    get_async_db_with_request_rls,
    require_admin_or_manager_with_rls,
    require_workshop_chat_access,
)
from tests.typing_helpers import as_user
from utils.db.rls_request import bind_panel_superadmin_rls
from utils.db.rls_types import MODE_AUTHENTICATED, MODE_PANEL_SUPERADMIN


@pytest.mark.asyncio
async def test_require_workshop_chat_access_binds_panel_for_superadmin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Platform superadmin workshop routes need panel_global_read under RLS."""
    monkeypatch.setattr(
        "routers.auth.dependencies.can_access_workshop_chat",
        AsyncMock(return_value=True),
    )

    request = MagicMock()
    user = as_user(SimpleNamespace(id=1, role="admin", organization_id=None))

    result = await require_workshop_chat_access(request, user, "en")

    assert result is user
    assert request.state.rls_context.mode == MODE_PANEL_SUPERADMIN


@pytest.mark.asyncio
async def test_require_workshop_chat_access_keeps_authenticated_for_teacher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-superadmin workshop users stay on authenticated RLS."""
    monkeypatch.setattr(
        "routers.auth.dependencies.can_access_workshop_chat",
        AsyncMock(return_value=True),
    )

    request = MagicMock()
    user = as_user(SimpleNamespace(id=2, role="user", organization_id=42))

    result = await require_workshop_chat_access(request, user, "en")

    assert result is user
    assert request.state.rls_context.mode == MODE_AUTHENTICATED


@pytest.mark.asyncio
async def test_require_admin_or_manager_with_rls_binds_panel_for_superadmin() -> None:
    """Quick-register mint path must see arbitrary organizations under RLS."""
    request = MagicMock()
    user = as_user(SimpleNamespace(id=1, role="admin", organization_id=None))

    result = await require_admin_or_manager_with_rls(request, user)

    assert result is user
    assert request.state.rls_context.mode == MODE_PANEL_SUPERADMIN


@pytest.mark.asyncio
async def test_get_async_db_with_request_rls_applies_request_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When auth binds panel scope on request.state, refresh SET LOCAL on the session."""
    applied: list[str] = []

    async def _capture_apply(_db: object, ctx: object) -> None:
        applied.append(getattr(ctx, "mode", ""))

    monkeypatch.setattr(
        "routers.auth.dependencies.apply_rls_context_async",
        _capture_apply,
    )

    request = MagicMock()
    user = SimpleNamespace(id=1, role="admin", organization_id=None)
    bind_panel_superadmin_rls(request, user)

    db = AsyncMock()
    result = await get_async_db_with_request_rls(request, db)

    assert result is db
    assert applied == [MODE_PANEL_SUPERADMIN]
