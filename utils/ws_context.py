"""
Async context manager for WebSocket session lifecycle management.

Usage in a router (after websocket.accept()):

    async with ws_managed_session(
        websocket,
        user_id=user.id,
        endpoint="asr",
        max_per_user_endpoint=1,
        close_error_fn=bridge_error_json,
    ) as _session:
        await run_asr_relay(websocket, ...)

The context manager guarantees:
  1. Per-user connection limits are enforced before the session is registered.
  2. The session is registered in the global registry and metrics are incremented.
  3. On exit (clean, disconnect, exception, or CancelledError from SIGTERM) the
     session is always unregistered and metrics are decremented.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional

from fastapi import WebSocket

from services.infrastructure.monitoring.ws_metrics import redis_increment_active_total
from utils.ws_session_registry import WsSession, _registry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def ws_managed_session(
    websocket: WebSocket,
    *,
    user_id: int,
    endpoint: str,
    max_per_user_endpoint: Optional[int] = None,
    max_per_user_global: Optional[int] = None,
    close_error_fn: Optional[Callable[[str, str], str]] = None,
    **meta: Any,
) -> AsyncIterator[WsSession]:
    """
    Async context manager that owns the full lifecycle of a WebSocket session.

    Called after ``websocket.accept()``.  If the caller has not yet accepted,
    the close frame and error JSON cannot be sent — in that case omit
    ``close_error_fn`` and handle the response before calling this.

    Args:
        websocket: The accepted FastAPI/Starlette WebSocket.
        user_id: Authenticated user's ID.
        endpoint: Registry label ('collab' | 'asr' | 'translate' | 'chat' | 'voice').
        max_per_user_endpoint: If set, reject if the user already has this many
            open sessions on the same endpoint.
        max_per_user_global: If set, reject if the user has this many open
            sessions across all endpoints.
        close_error_fn: Optional callable(code_str, message) -> str that returns
            an error JSON payload sent before closing on limit violation.
        **meta: Endpoint-specific metadata stored on the session object.
    """
    # ── 1. Enforce per-user limits ───────────────────────────────────────────
    # count_for_user is lock-free; checked before register() so that the
    # register() call (under lock) is the authoritative atomic insert.
    if max_per_user_endpoint is not None:
        current = _registry.count_for_user(user_id, endpoint)
        if current >= max_per_user_endpoint:
            logger.warning(
                "[WSContext] Connection limit reached user_id=%s endpoint=%s "
                "current=%d limit=%d",
                user_id,
                endpoint,
                current,
                max_per_user_endpoint,
            )
            if close_error_fn is not None:
                from utils.ws_limits import safe_websocket_send_text  # local import avoids circularity
                await safe_websocket_send_text(
                    websocket,
                    close_error_fn("connection_limit", "Connection limit reached"),
                )
            await websocket.close(code=4029, reason="Connection limit reached")
            return

    if max_per_user_global is not None:
        current_global = _registry.count_for_user(user_id)
        if current_global >= max_per_user_global:
            logger.warning(
                "[WSContext] Global connection limit reached user_id=%s "
                "current=%d limit=%d",
                user_id,
                current_global,
                max_per_user_global,
            )
            if close_error_fn is not None:
                from utils.ws_limits import safe_websocket_send_text
                await safe_websocket_send_text(
                    websocket,
                    close_error_fn("connection_limit", "Too many connections"),
                )
            await websocket.close(code=4029, reason="Too many connections")
            return

    # ── 2. Register ──────────────────────────────────────────────────────────
    # registry.register() also bumps the per-endpoint in-process counter.
    session = await _registry.register(user_id, endpoint, websocket, **meta)
    await redis_increment_active_total(1)
    _started = time.monotonic()

    logger.info(
        "[WSSession] OPEN  session=%s endpoint=%s user_id=%s remote=%s",
        session.session_id,
        endpoint,
        user_id,
        session.remote_addr,
    )

    try:
        yield session
    finally:
        # ── 3. Always unregister ─────────────────────────────────────────────
        # Runs on clean exit, WebSocketDisconnect, unhandled exception, and
        # asyncio.CancelledError (SIGTERM / graceful shutdown).
        # registry.unregister() also decrements the per-endpoint counter.
        await _registry.unregister(session.session_id)
        await redis_increment_active_total(-1)
        duration = time.monotonic() - _started
        logger.info(
            "[WSSession] CLOSE session=%s endpoint=%s user_id=%s duration=%.1fs",
            session.session_id,
            endpoint,
            user_id,
            duration,
        )
