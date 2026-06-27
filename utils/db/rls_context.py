"""
Postgres RLS session context via SET LOCAL app.* GUCs.

Applied on every transaction begin (after_begin listeners) and may be
re-applied when panel scope overrides the default user context.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Iterator, Mapping, Optional

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from config.db_sessions import open_async_session, open_sync_session
from config.settings import config
from utils.db.rls_context_from_actor import (
    build_from_admin_scope_kwargs,
    build_from_user_kwargs,
    build_panel_superadmin_kwargs,
)
from utils.db.rls_types import (
    MODE_AUTHENTICATED,
    MODE_DASHBOARD,
    MODE_DENY,
    MODE_MINDBOT_SERVICE,
    MODE_PUBLIC,
    MODE_SYSTEM,
    RlsListenerRegistration,
)

_logger = logging.getLogger(__name__)

_rls_context_var: ContextVar[Optional["RlsContext"]] = ContextVar("rls_context", default=None)


def _rls_strict_enabled() -> bool:
    """Rls strict enabled."""
    raw = os.getenv("RLS_CONTEXT_STRICT")
    if raw is not None:
        return raw.strip().lower() in ("1", "true", "yes")
    return not config.debug


_APP_PREFIX = "app."


@dataclass(frozen=True)
class RlsContext:
    """Maps to PostgreSQL current_setting('app.*', true) keys."""

    mode: str = MODE_DENY
    user_id: Optional[int] = None
    organization_id: Optional[int] = None
    role: Optional[str] = None
    readable_org_ids: Optional[str] = None
    mindbot_callback_token: Optional[str] = None
    allow_public_org_list: bool = False
    allow_global_channels: bool = False
    panel_global_read: bool = False
    actor_user_id: Optional[int] = None
    extra: Mapping[str, str] = field(default_factory=dict)

    def session_vars(self) -> dict[str, str]:
        """Keys without app. prefix — values are strings for set_config."""
        out: dict[str, str] = {"rls_mode": self.mode}
        if self.user_id is not None:
            out["user_id"] = str(int(self.user_id))
        if self.organization_id is not None:
            out["organization_id"] = str(int(self.organization_id))
        if self.role:
            out["role"] = self.role
        if self.readable_org_ids is not None:
            out["readable_org_ids"] = self.readable_org_ids
        if self.mindbot_callback_token:
            out["mindbot_callback_token"] = self.mindbot_callback_token
        if self.allow_public_org_list:
            out["allow_public_org_list"] = "1"
        if self.allow_global_channels:
            out["allow_global_channels"] = "1"
        if self.panel_global_read:
            out["panel_global_read"] = "1"
        if self.actor_user_id is not None:
            out["actor_user_id"] = str(int(self.actor_user_id))
        out.update(self.extra)
        return out

    @classmethod
    def deny_default(cls) -> "RlsContext":
        """Deny default."""
        return cls(mode=MODE_DENY)

    @classmethod
    def from_user(cls, user: Any, *, allow_global_channels: bool = False) -> "RlsContext":
        """From user."""
        return cls(**build_from_user_kwargs(user, allow_global_channels=allow_global_channels))

    @classmethod
    def from_admin_scope(cls, scope: Any) -> "RlsContext":
        """From admin scope."""
        return cls(**build_from_admin_scope_kwargs(scope))

    @classmethod
    def panel_superadmin(cls, user: Any) -> "RlsContext":
        """Panel superadmin."""
        return cls(**build_panel_superadmin_kwargs(user))

    @classmethod
    def for_public_org_list(cls) -> "RlsContext":
        """For public org list."""
        return cls(mode=MODE_PUBLIC, allow_public_org_list=True)

    @classmethod
    def for_dashboard(cls) -> "RlsContext":
        """For dashboard."""
        return cls(mode=MODE_DASHBOARD)

    @classmethod
    def for_celery_user(cls, user_id: int, organization_id: Optional[int] = None) -> "RlsContext":
        """For celery user."""
        return cls(
            mode=MODE_AUTHENTICATED,
            user_id=int(user_id),
            organization_id=int(organization_id) if organization_id is not None else None,
            actor_user_id=int(user_id),
        )

    @classmethod
    def for_mindbot_service(
        cls,
        *,
        organization_id: int,
        callback_token: Optional[str] = None,
    ) -> "RlsContext":
        """For mindbot service."""
        return cls(
            mode=MODE_MINDBOT_SERVICE,
            organization_id=int(organization_id),
            mindbot_callback_token=callback_token,
        )

    @classmethod
    def system_bootstrap(cls) -> "RlsContext":
        """System bootstrap."""
        return cls(mode=MODE_SYSTEM)


def get_rls_context() -> Optional[RlsContext]:
    """Get rls context."""
    return _rls_context_var.get()


def set_rls_context(ctx: Optional[RlsContext]) -> Token:
    """Set rls context."""
    return _rls_context_var.set(ctx)


def reset_rls_context(token: Token) -> None:
    """Reset rls context."""
    _rls_context_var.reset(token)


def resolve_rls_context_for_transaction() -> RlsContext:
    """Resolve rls context for transaction."""
    ctx = get_rls_context()
    if ctx is not None:
        return ctx
    if _rls_strict_enabled():
        _logger.error(
            "[RLS] Transaction started without RlsContext (RLS_CONTEXT_STRICT=1); "
            "using deny_default — set user_rls_session / middleware / request.state.rls_context"
        )
    return RlsContext.deny_default()


_SET_CONFIG_SQL = text("SELECT set_config(:key, :value, true)")


async def apply_rls_context_async(session: AsyncSession, ctx: Optional[RlsContext] = None) -> None:
    """Apply SET LOCAL app.* on the session's connection (same transaction)."""
    effective = ctx if ctx is not None else resolve_rls_context_for_transaction()
    for key, value in effective.session_vars().items():
        await session.execute(
            _SET_CONFIG_SQL,
            {"key": f"{_APP_PREFIX}{key}", "value": value},
        )


def apply_rls_context_sync(connection: Any, ctx: Optional[RlsContext] = None) -> None:
    """Apply rls context sync."""
    effective = ctx if ctx is not None else resolve_rls_context_for_transaction()
    for key, value in effective.session_vars().items():
        connection.execute(
            _SET_CONFIG_SQL,
            {"key": f"{_APP_PREFIX}{key}", "value": value},
        )


def _after_begin_apply_rls(_session: Session, _transaction, connection) -> None:
    """After begin apply rls."""
    apply_rls_context_sync(connection)


def register_rls_listeners(async_engine: Any, sync_engine: Any) -> None:
    """
    Register after_begin on sync Session (covers AsyncSession via sync_session).

    AsyncSession does not expose after_begin; SQLAlchemy routes async ORM
    transactions through the underlying Session class.
    """
    del async_engine, sync_engine
    if RlsListenerRegistration.registered:
        return
    event.listen(Session, "after_begin", _after_begin_apply_rls)
    RlsListenerRegistration.registered = True


@asynccontextmanager
async def rls_async_session(ctx: RlsContext) -> AsyncIterator[AsyncSession]:
    """Open async DB session with RLS context for direct-session code paths."""
    token = set_rls_context(ctx)
    try:
        async with open_async_session() as session:
            yield session
    finally:
        reset_rls_context(token)


@contextmanager
def rls_sync_session(ctx: RlsContext) -> Iterator[Session]:
    """Rls sync session."""
    token = set_rls_context(ctx)
    try:
        session = open_sync_session()
        try:
            yield session
        finally:
            session.close()
    finally:
        reset_rls_context(token)


def to_rls_session_vars(scope: Any) -> dict[str, str]:
    """Flat app.* key → value map for SET LOCAL (panel routes)."""
    ctx = RlsContext.from_admin_scope(scope)
    return ctx.session_vars()


def rls_context_from_admin_scope(scope: Any) -> RlsContext:
    """Rls context from admin scope."""
    return RlsContext.from_admin_scope(scope)


def rls_context_panel_superadmin(user: Any) -> RlsContext:
    """Rls context panel superadmin."""
    return RlsContext.panel_superadmin(user)
