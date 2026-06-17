"""SQLAlchemy session factories (leaf module — avoids database ↔ RLS import cycles).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

engine: Any = None
async_engine: Any = None
SyncSessionLocal: sessionmaker[Session] | None = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def _session_factory(name: str) -> Any:
    """Resolve a session factory at call time (assigned after module import)."""
    factory = globals().get(name)
    if factory is None or not callable(factory):
        raise RuntimeError(f"{name} is not initialized; import config.database first")
    return factory


def open_sync_session() -> Session:
    """Open a sync SQLAlchemy session."""
    session = _session_factory("SyncSessionLocal")()
    if not isinstance(session, Session):
        raise RuntimeError("SyncSessionLocal did not return a SQLAlchemy Session")
    return session


def open_async_session() -> AsyncSession:
    """Open an async SQLAlchemy session."""
    session = _session_factory("AsyncSessionLocal")()
    if not isinstance(session, AsyncSession):
        raise RuntimeError("AsyncSessionLocal did not return a SQLAlchemy AsyncSession")
    return session
