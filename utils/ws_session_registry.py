"""
Centralized in-process WebSocket session registry.

Tracks every open WebSocket across all endpoints (collab, chat, ASR, translate,
voice) on this worker process.  Designed for high concurrency:

* Reads (count_for_user, snapshot) are lock-free — CPython GIL makes single-
  level dict access atomic.
* Writes (register, unregister) hold asyncio.Lock only for the brief dict
  mutation; no I/O inside the lock.
* Bulk closes (close_all, close_all_for_user) use asyncio.gather with
  return_exceptions=True so one hung socket never blocks the others.

Each worker maintains its own instance.  Cross-worker visibility is provided by
the redis_increment_active_total gauge already used by ws_metrics; no Redis is
needed inside the registry itself.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket
from services.infrastructure.monitoring.ws_metrics import record_ws_connection_delta

logger = logging.getLogger(__name__)


@dataclass
class WsSession:
    """Metadata record for one open WebSocket connection."""

    session_id: str
    """UUID4 string — stable key throughout the connection lifetime."""

    user_id: int
    endpoint: str
    """One of: 'collab' | 'asr' | 'translate' | 'chat' | 'voice'."""

    websocket: WebSocket
    connected_at: float
    """time.monotonic() timestamp at registration."""

    remote_addr: str
    meta: Dict[str, Any] = field(default_factory=dict)
    """Endpoint-specific extras (e.g. {'code': '123-456'} for collab)."""


class WsSessionRegistry:
    """
    In-process registry of all live WebSocket sessions on this worker.

    Thread-safety note: all public coroutines are asyncio-safe.  Synchronous
    reads (count_for_user, snapshot) rely on the CPython GIL for atomicity of
    dict access and are intentionally lock-free to avoid any await on the hot
    path.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, WsSession] = {}
        self._by_user: Dict[int, Set[str]] = {}
        self._lock = asyncio.Lock()

    # ── writes (need lock) ───────────────────────────────────────────────────

    async def register(
        self,
        user_id: int,
        endpoint: str,
        websocket: WebSocket,
        **meta: Any,
    ) -> WsSession:
        """
        Add a newly-accepted WebSocket to the registry.

        The per-user limit check + insertion is done inside the lock so there
        is no TOCTOU gap between checking the count and inserting the new entry.
        """
        remote = ""
        if websocket.client:
            remote = f"{websocket.client.host}:{websocket.client.port}"

        session = WsSession(
            session_id=uuid.uuid4().hex,
            user_id=user_id,
            endpoint=endpoint,
            websocket=websocket,
            connected_at=time.monotonic(),
            remote_addr=remote,
            meta=dict(meta),
        )

        async with self._lock:
            self._sessions[session.session_id] = session
            self._by_user.setdefault(user_id, set()).add(session.session_id)

        record_ws_connection_delta(endpoint, 1)
        logger.debug(
            "[WSRegistry] registered session=%s endpoint=%s user_id=%s",
            session.session_id,
            endpoint,
            user_id,
        )
        return session

    async def unregister(self, session_id: str) -> None:
        """Remove a session from the registry (idempotent — safe to call twice)."""
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session is None:
                return
            user_sessions = self._by_user.get(session.user_id)
            if user_sessions:
                user_sessions.discard(session_id)
                if not user_sessions:
                    del self._by_user[session.user_id]

        record_ws_connection_delta(session.endpoint, -1)
        logger.debug(
            "[WSRegistry] unregistered session=%s endpoint=%s user_id=%s",
            session_id,
            session.endpoint,
            session.user_id,
        )

    # ── reads (lock-free) ────────────────────────────────────────────────────

    def count_for_user(
        self,
        user_id: int,
        endpoint: Optional[str] = None,
    ) -> int:
        """
        Number of active sessions for *user_id*, optionally filtered by endpoint.

        Lock-free: safe to call from sync context.  GIL ensures the dict lookup
        and set len() are atomic for CPython.
        """
        session_ids = self._by_user.get(user_id)
        if not session_ids:
            return 0
        if endpoint is None:
            return len(session_ids)
        return sum(
            1
            for sid in session_ids
            if self._sessions.get(sid) and self._sessions[sid].endpoint == endpoint
        )

    def active_count(self) -> int:
        """Total number of registered sessions on this worker."""
        return len(self._sessions)

    def snapshot(self) -> Dict[str, Any]:
        """
        Point-in-time summary of all sessions — used by admin metrics endpoints.

        Lock-free; returns a shallow copy of the session list so the caller
        cannot mutate registry state.
        """
        sessions = list(self._sessions.values())
        by_endpoint: Dict[str, int] = {}
        for s in sessions:
            by_endpoint[s.endpoint] = by_endpoint.get(s.endpoint, 0) + 1
        return {
            "total": len(sessions),
            "by_endpoint": by_endpoint,
            "sessions": [
                {
                    "session_id": s.session_id,
                    "user_id": s.user_id,
                    "endpoint": s.endpoint,
                    "remote_addr": s.remote_addr,
                    "age_seconds": round(time.monotonic() - s.connected_at, 1),
                    "meta": s.meta,
                }
                for s in sessions
            ],
        }

    # ── bulk operations ──────────────────────────────────────────────────────

    async def close_all_for_user(
        self,
        user_id: int,
        code: int = 1001,
        reason: str = "Session closed",
    ) -> None:
        """
        Close every session belonging to *user_id* with the given WS close code.

        Uses asyncio.gather(return_exceptions=True) so individual close failures
        do not prevent other sessions from being closed.
        """
        async with self._lock:
            session_ids = list(self._by_user.get(user_id, set()))
            targets = [self._sessions[sid] for sid in session_ids if sid in self._sessions]

        if not targets:
            return

        async def _close(session: WsSession) -> None:
            with contextlib.suppress(Exception):
                await session.websocket.close(code=code, reason=reason)

        await asyncio.gather(*(_close(s) for s in targets), return_exceptions=True)
        logger.info(
            "[WSRegistry] closed %d session(s) for user_id=%s reason=%r",
            len(targets),
            user_id,
            reason,
        )

    async def close_all(
        self,
        code: int = 1001,
        reason: str = "Server shutting down",
    ) -> None:
        """
        Close every registered session — called during graceful shutdown.

        Each close is attempted in parallel; failures are suppressed so the
        shutdown sequence is never blocked by a single unresponsive client.
        """
        async with self._lock:
            targets = list(self._sessions.values())

        if not targets:
            return

        async def _close(session: WsSession) -> None:
            with contextlib.suppress(Exception):
                await session.websocket.close(code=code, reason=reason)

        await asyncio.gather(*(_close(s) for s in targets), return_exceptions=True)
        logger.info(
            "[WSRegistry] graceful close sent to %d session(s)", len(targets)
        )


# Module-level singleton — one per worker process.
_registry = WsSessionRegistry()
