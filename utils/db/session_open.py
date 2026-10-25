"""
Convenience aliases for direct DB sessions with RLS context.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from utils.db.rls_context import RlsContext, get_rls_context, rls_async_session


def user_rls_session(user_id: int, organization_id: Optional[int] = None):
    """Context manager: async session for a user id (Celery, caches, collab)."""
    return rls_async_session(RlsContext.for_celery_user(user_id, organization_id))


def actor_rls_session(user: Any, *, allow_global_channels: bool = False):
    """Context manager: async session for a User model / actor."""
    return rls_async_session(RlsContext.from_user(user, allow_global_channels=allow_global_channels))


def system_rls_session():
    """Context manager: bootstrap / recovery / cross-tenant maintenance."""
    return rls_async_session(RlsContext.system_bootstrap())


def panel_superadmin_rls_session(user: Any):
    """Panel superadmin rls session."""
    return rls_async_session(RlsContext.panel_superadmin(user))


def request_rls_session(user: Any, request: Any = None):
    """Short-lived session for reads that finish before a long response body.

    Prefer ``request.state.rls_context``. BaseHTTPMiddleware can drop the
    ContextVar, and ``get_async_db`` reads the request for that reason. The
    session closes when the block exits, so an SSE body does not sit in an
    idle transaction.
    """
    state = getattr(request, "state", None) if request is not None else None
    ctx = getattr(state, "rls_context", None) if state is not None else None
    if ctx is None:
        ctx = get_rls_context()
    if ctx is None:
        return actor_rls_session(user)
    return rls_async_session(ctx)


async def release_open_transaction(db: AsyncSession) -> None:
    """Commit an open read transaction before awaiting slow external I/O.

    Request-scoped FastAPI sessions stay open until the handler returns. End any
    in-flight transaction before long upstream HTTP (Dify export, SSE, etc.) so
    Postgres does not hit idle_in_transaction_session_timeout.
    """
    if db.in_transaction():
        await db.commit()
