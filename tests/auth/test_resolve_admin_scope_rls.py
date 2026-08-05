"""Panel RLS must be pinned on request.state before get_async_db opens."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from routers.auth.dependencies import get_admin_scope, resolve_admin_scope_rls
from utils.auth.admin_panel_permissions import CAP_PANEL_ACCESS, CAP_SCOPE_INVITED_ORGS
from utils.auth.admin_scope import AdminScope
from utils.db.rls_types import MODE_PANEL


def _expert_scope() -> AdminScope:
    actor = MagicMock()
    actor.id = 5011
    actor.organization_id = None
    actor.role = "expert"
    return AdminScope(
        actor=actor,
        role="expert",
        capabilities=frozenset({CAP_PANEL_ACCESS, CAP_SCOPE_INVITED_ORGS}),
        org_ids=None,
        effective_org_id=None,
        read_only=False,
        invited_org_ids=frozenset(),
    )


def test_get_admin_scope_declares_resolve_before_db_dependency() -> None:
    """FastAPI resolves sibling Depends in declaration order — panel pin before DB."""
    params = list(inspect.signature(get_admin_scope).parameters)
    assert params.index("scope") < params.index("db")


@pytest.mark.asyncio
async def test_resolve_admin_scope_rls_pins_panel_on_request_state() -> None:
    """Expert panel context must be on request.state before the DB dependency runs."""
    request = Request({"type": "http", "headers": [], "method": "POST", "path": "/"})
    fake_scope = _expert_scope()

    with patch(
        "routers.auth.dependencies.build_admin_scope_async",
        new_callable=AsyncMock,
        return_value=fake_scope,
    ):
        scope = await resolve_admin_scope_rls(
            request=request,
            organization_id=None,
            current_user=MagicMock(),
            lang="en",
        )

    assert scope is fake_scope
    ctx = request.state.rls_context
    assert ctx is not None
    assert ctx.mode == MODE_PANEL
    assert ctx.user_id == 5011
    assert ctx.role == "expert"


@pytest.mark.asyncio
async def test_get_admin_scope_applies_pinned_panel_context() -> None:
    """get_admin_scope refreshes SET LOCAL from request.state panel context."""
    request = Request({"type": "http", "headers": [], "method": "POST", "path": "/"})
    fake_scope = _expert_scope()
    applied: list[object] = []

    async def _capture_apply(_db: object, ctx: object) -> None:
        applied.append(ctx)

    with patch(
        "routers.auth.dependencies.build_admin_scope_async",
        new_callable=AsyncMock,
        return_value=fake_scope,
    ):
        pinned = await resolve_admin_scope_rls(
            request=request,
            organization_id=None,
            current_user=MagicMock(),
            lang="en",
        )

    with patch(
        "routers.auth.dependencies.apply_rls_context_async",
        new=_capture_apply,
    ):
        result = await get_admin_scope(
            request=request,
            scope=pinned,
            db=AsyncMock(),
        )

    assert result is pinned
    assert len(applied) == 1
    assert applied[0] is request.state.rls_context
    assert getattr(applied[0], "mode", None) == MODE_PANEL
