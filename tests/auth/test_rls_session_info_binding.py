"""Session.info RLS binding survives ContextVar clear (post-commit / middleware)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from utils.db.rls_context import (
    RlsContext,
    bind_session_rls_context,
    resolve_rls_context_for_session,
    set_rls_context,
)


def test_resolve_prefers_session_info_over_cleared_contextvar() -> None:
    """after_begin must use session-pinned panel context when ContextVar is None."""
    panel = RlsContext(
        mode="panel",
        user_id=4874,
        actor_user_id=4874,
        role="expert",
        readable_org_ids=None,
    )
    session = MagicMock()
    session.info = {}
    bind_session_rls_context(session, panel)
    set_rls_context(None)

    resolved = resolve_rls_context_for_session(session)

    assert resolved.mode == "panel"
    assert resolved.user_id == 4874
    assert resolved.role == "expert"


def test_bind_session_rls_context_stores_on_info() -> None:
    """bind_session_rls_context writes RlsContext onto session.info."""
    ctx = RlsContext.from_user(SimpleNamespace(id=1, organization_id=2, role="teacher"))
    session = SimpleNamespace(info={})
    bind_session_rls_context(session, ctx)
    assert session.info["rls_context"] is ctx
