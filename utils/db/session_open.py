"""Convenience aliases for direct DB sessions with RLS context."""

from __future__ import annotations

from typing import Any, Optional

from utils.db.rls_context import RlsContext, rls_async_session


def user_rls_session(user_id: int, organization_id: Optional[int] = None):
    """Context manager: async session for a user id (Celery, caches, collab)."""
    return rls_async_session(RlsContext.for_celery_user(user_id, organization_id))


def actor_rls_session(user: Any, *, allow_global_channels: bool = False):
    """Context manager: async session for a User model / actor."""
    return rls_async_session(
        RlsContext.from_user(user, allow_global_channels=allow_global_channels)
    )


def system_rls_session():
    """Context manager: bootstrap / recovery / cross-tenant maintenance."""
    return rls_async_session(RlsContext.system_bootstrap())


def panel_superadmin_rls_session(user: Any):
    return rls_async_session(RlsContext.panel_superadmin(user))
