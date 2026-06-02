"""Database helpers (Postgres RLS session context)."""

from __future__ import annotations

from typing import Any

__all__ = [
    "RlsContext",
    "apply_rls_context_async",
    "apply_rls_context_sync",
    "get_rls_context",
    "reset_rls_context",
    "rls_async_session",
    "rls_sync_session",
    "set_rls_context",
    "actor_rls_session",
    "panel_superadmin_rls_session",
    "system_rls_session",
    "user_rls_session",
]

_RLS_CONTEXT_EXPORTS = frozenset(
    {
        "RlsContext",
        "apply_rls_context_async",
        "apply_rls_context_sync",
        "get_rls_context",
        "reset_rls_context",
        "rls_async_session",
        "rls_sync_session",
        "set_rls_context",
    }
)

_SESSION_OPEN_EXPORTS = frozenset(
    {
        "actor_rls_session",
        "panel_superadmin_rls_session",
        "system_rls_session",
        "user_rls_session",
    }
)


def __getattr__(name: str) -> Any:
    if name in _RLS_CONTEXT_EXPORTS:
        import importlib

        rls_context = importlib.import_module("utils.db.rls_context")
        return getattr(rls_context, name)
    if name in _SESSION_OPEN_EXPORTS:
        import importlib

        session_open = importlib.import_module("utils.db.session_open")
        return getattr(session_open, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
