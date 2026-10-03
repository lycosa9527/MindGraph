"""Learning Space FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from utils.auth.auth_resolution import AUTH_CONTEXT_USER_ATTR
from utils.auth.roles import is_superadmin
from utils.db.rls_context import apply_rls_context_async
from utils.db.rls_request import bind_panel_superadmin_rls


async def bind_superadmin_learning_space_rls(request: Request) -> None:
    """Superadmins read every school's classes under panel global RLS."""
    user = getattr(request.state, AUTH_CONTEXT_USER_ATTR, None)
    if user is not None and is_superadmin(user):
        bind_panel_superadmin_rls(request, user)


async def pin_superadmin_learning_space_rls(request: Request, db: AsyncSession) -> None:
    """Re-apply panel global read on the open transaction."""
    ctx = getattr(request.state, "rls_context", None)
    if ctx is not None and getattr(ctx, "panel_global_read", False):
        await apply_rls_context_async(db, ctx)


async def get_learning_space_db(
    request: Request,
    _bound: None = Depends(bind_superadmin_learning_space_rls),
    db: AsyncSession = Depends(get_async_db),
) -> AsyncIterator[AsyncSession]:
    """Request session. Superadmin panel read is pinned before and on the open transaction."""
    await pin_superadmin_learning_space_rls(request, db)
    yield db
