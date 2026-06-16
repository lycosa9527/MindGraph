"""
Postgres RLS session context via SET LOCAL app.* GUCs.

Applied on every transaction begin (after_begin listeners) and may be
re-applied when panel scope overrides the default user context.
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

_logger = logging.getLogger(__name__)

_rls_context_var: ContextVar[Optional["RlsContext"]] = ContextVar("rls_context", default=None)


def _rls_strict_enabled() -> bool:
    return os.getenv("RLS_CONTEXT_STRICT", "0").lower() in ("1", "true", "yes")


MODE_AUTHENTICATED = "authenticated"
MODE_PANEL = "panel"
MODE_PANEL_SUPERADMIN = "panel_superadmin"
MODE_PUBLIC = "public"
MODE_DASHBOARD = "dashboard"
MODE_MINDBOT_SERVICE = "mindbot_service"
MODE_DENY = "deny"
MODE_SYSTEM = "system"

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
        return cls(mode=MODE_DENY)

    @classmethod
    def from_user(cls, user: Any, *, allow_global_channels: bool = False) -> "RlsContext":
        from utils.auth.role_constants import normalize_role

        uid = getattr(user, "id", None)
        org_id = getattr(user, "organization_id", None)
        role = normalize_role(getattr(user, "role", None))
        return cls(
            mode=MODE_AUTHENTICATED,
            user_id=int(uid) if uid is not None else None,
            organization_id=int(org_id) if org_id is not None else None,
            role=role,
            actor_user_id=int(uid) if uid is not None else None,
            allow_global_channels=allow_global_channels,
        )

    @classmethod
    def from_admin_scope(cls, scope: Any) -> "RlsContext":
        from utils.db.rls_admin_scope import admin_scope_to_session_vars

        return cls(**admin_scope_to_session_vars(scope))

    @classmethod
    def panel_superadmin(cls, user: Any) -> "RlsContext":
        from utils.auth.role_constants import normalize_role

        uid = getattr(user, "id", None)
        return cls(
            mode=MODE_PANEL_SUPERADMIN,
            user_id=int(uid) if uid is not None else None,
            role=normalize_role(getattr(user, "role", None)),
            actor_user_id=int(uid) if uid is not None else None,
            panel_global_read=True,
        )

    @classmethod
    def for_public_org_list(cls) -> "RlsContext":
        return cls(mode=MODE_PUBLIC, allow_public_org_list=True)

    @classmethod
    def for_dashboard(cls) -> "RlsContext":
        return cls(mode=MODE_DASHBOARD)

    @classmethod
    def for_celery_user(cls, user_id: int, organization_id: Optional[int] = None) -> "RlsContext":
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
        return cls(
            mode=MODE_MINDBOT_SERVICE,
            organization_id=int(organization_id),
            mindbot_callback_token=callback_token,
        )

    @classmethod
    def system_bootstrap(cls) -> "RlsContext":
        return cls(mode=MODE_SYSTEM)


def get_rls_context() -> Optional[RlsContext]:
    return _rls_context_var.get()


def set_rls_context(ctx: Optional[RlsContext]) -> Token:
    return _rls_context_var.set(ctx)


def reset_rls_context(token: Token) -> None:
    _rls_context_var.reset(token)


def resolve_rls_context_for_transaction() -> RlsContext:
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
    effective = ctx if ctx is not None else resolve_rls_context_for_transaction()
    for key, value in effective.session_vars().items():
        connection.execute(
            _SET_CONFIG_SQL,
            {"key": f"{_APP_PREFIX}{key}", "value": value},
        )


def _after_begin_apply_rls(_session: Session, _transaction, connection) -> None:
    apply_rls_context_sync(connection)


def register_rls_listeners(async_engine: Any, sync_engine: Any) -> None:
    """
    Register after_begin on sync Session (covers AsyncSession via sync_session).

    AsyncSession does not expose after_begin; SQLAlchemy routes async ORM
    transactions through the underlying Session class.
    """
    del async_engine, sync_engine
    if getattr(register_rls_listeners, "_registered", False):
        return
    event.listen(Session, "after_begin", _after_begin_apply_rls)
    register_rls_listeners._registered = True


@asynccontextmanager
async def rls_async_session(ctx: RlsContext) -> AsyncIterator[AsyncSession]:
    """Open AsyncSessionLocal with RLS context for direct-session code paths."""
    from config.database import AsyncSessionLocal

    token = set_rls_context(ctx)
    try:
        async with AsyncSessionLocal() as session:
            yield session
    finally:
        reset_rls_context(token)


@contextmanager
def rls_sync_session(ctx: RlsContext) -> Iterator[Session]:
    from config.database import SyncSessionLocal

    token = set_rls_context(ctx)
    try:
        session = SyncSessionLocal()
        try:
            yield session
        finally:
            session.close()
    finally:
        reset_rls_context(token)
