"""Redis TTL for workshop keys derived from diagram session expiry."""

import asyncio
import logging
import time
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from config.database import AsyncSessionLocal
from models.domain.diagrams import Diagram
from services.online_collab.lifecycle.session_meta_cache import get_session_meta_cached
from services.online_collab.lifecycle.online_collab_expiry import redis_ttl_seconds_for_expires_at

logger = logging.getLogger(__name__)

_FALLBACK_TTL = 86400
_DB_TIMEOUT_SEC = 2.0


async def _redis_ttl_from_session_meta(code: str) -> Optional[int]:
    """
    Derive Redis TTL from the cached ``session_meta.expires_at`` field.

    Goes through the process-local :func:`get_session_meta_cached` so repeated
    TTL lookups on the hot join path don't hit Redis each time. Returns
    ``None`` when the session isn't live or the stored value is malformed so
    callers fall back to DB.
    """
    if not code:
        return None
    meta = await get_session_meta_cached(code)
    if not meta:
        return None
    raw = meta.get("expires_at")
    if not raw:
        return None
    try:
        expires_unix = int(raw)
    except (ValueError, TypeError):
        return None
    if expires_unix <= 0:
        return None
    now = int(time.time())
    rem = expires_unix - now
    if rem <= 0:
        return None
    return max(1, min(rem, 86400 * 14))


async def get_online_collab_redis_ttl_seconds(
    diagram_id: str,
    code: Optional[str] = None,
) -> int:
    """
    TTL to use for ``live_spec`` and related keys (capped, min 1s).

    When ``code`` is supplied the session_meta HASH is consulted first (one
    Redis HGET) to avoid the DB round-trip on the join-handshake hot path. On
    Redis miss/unavailable, falls back to a bounded DB read wrapped in an
    ``asyncio.timeout`` so a hung DB never blocks the WebSocket handler.
    """
    if code:
        cached = await _redis_ttl_from_session_meta(code)
        if cached is not None:
            return cached
    try:
        async with asyncio.timeout(_DB_TIMEOUT_SEC):
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Diagram.workshop_expires_at).where(
                        Diagram.id == diagram_id,
                        ~Diagram.is_deleted,
                    )
                )
                row = result.first()
                if row is None:
                    return _FALLBACK_TTL
                expires_at = row[0]
                if expires_at:
                    return redis_ttl_seconds_for_expires_at(expires_at)
                return _FALLBACK_TTL
    except asyncio.TimeoutError:
        logger.warning(
            "[WorkshopTTL] get_online_collab_redis_ttl_seconds timed out "
            "(%.1fs) diagram_id=%s — returning fallback TTL",
            _DB_TIMEOUT_SEC,
            diagram_id,
        )
        return _FALLBACK_TTL
    except SQLAlchemyError as exc:
        logger.warning(
            "[WorkshopTTL] get_online_collab_redis_ttl_seconds DB error "
            "diagram_id=%s: %s — returning fallback TTL",
            diagram_id,
            exc,
        )
        return _FALLBACK_TTL
