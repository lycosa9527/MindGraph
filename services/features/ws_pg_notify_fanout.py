"""
PostgreSQL LISTEN/NOTIFY fallback for WebSocket fan-out.

This module provides a resilience layer that activates ONLY when the Redis
pub/sub health check fails.  In normal operation (Redis healthy) this code
path is completely dormant and adds zero overhead.

Architecture
------------
* ``publish_pg_notify_fanout_async(envelope)`` — NOTIFY each registered
  listener channel.  Called from ``publish_workshop_fanout_async`` when Redis
  publish raises an error.  Uses ``psycopg.AsyncConnection`` with ``autocommit``
  so NOTIFY is flushed immediately without an explicit transaction.
* ``start_pg_notify_listener()`` / ``stop_pg_notify_listener()`` — manage a
  long-lived background task that ``LISTEN``s on the per-machine channel and
  delivers messages to the local WebSocket room via
  ``deliver_local_workshop_broadcast``.
* Channel name: ``workshop_fanout_<machine_id>`` where ``machine_id`` is the
  hostname (max 63 chars, lowercased, non-alnum replaced with ``_``).

Environment flags
-----------------
* ``COLLAB_PG_NOTIFY_FALLBACK=1`` (default 0) — opt-in: the fallback only
  activates when this flag is set AND Redis pub/sub publish raises an error.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import socket
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_RECONNECT_DELAY_SEC = 3.0
_CHANNEL_PREFIX = "workshop_fanout_"
_MAX_CHANNEL_SUFFIX = 63 - len(_CHANNEL_PREFIX)
# Shared channel: all workers LISTEN on this so a single NOTIFY reaches
# every worker regardless of which host originated the message.
_SHARED_CHANNEL = "workshop_fanout_shared"


def _pg_notify_enabled() -> bool:
    return os.getenv("COLLAB_PG_NOTIFY_FALLBACK", "0") not in ("0", "false", "False", "")


def _machine_channel() -> str:
    """Derive a stable, PG-safe channel name from the machine hostname."""
    raw = socket.gethostname() or "unknown"
    safe = re.sub(r"[^a-z0-9_]", "_", raw.lower())[:_MAX_CHANNEL_SUFFIX]
    return f"{_CHANNEL_PREFIX}{safe}"


_CHANNEL = _machine_channel()
_FANOUT_ORIGIN_SECRET: str = os.environ.get("COLLAB_FANOUT_ORIGIN_SECRET", "")


class _PgNotifyState:
    """Module-level state for the background LISTEN task."""

    listener_task: Optional[asyncio.Task] = None
    stop_event: Optional[asyncio.Event] = None


async def _listener_loop(stop: asyncio.Event) -> None:
    """
    Maintain a persistent LISTEN connection and deliver inbound NOTIFY payloads.

    Reconnects on any error after ``_RECONNECT_DELAY_SEC`` seconds.
    """
    from services.features.workshop_ws_fanout_delivery import (  # pylint: disable=import-outside-toplevel
        deliver_local_workshop_broadcast,
    )

    while not stop.is_set():
        conn = None
        try:
            import psycopg  # pylint: disable=import-outside-toplevel
            from psycopg import sql  # pylint: disable=import-outside-toplevel
            from config.database import DATABASE_URL  # pylint: disable=import-outside-toplevel

            dsn = str(DATABASE_URL).replace("+asyncpg", "").replace("+psycopg", "")
            conn = await psycopg.AsyncConnection.connect(dsn, autocommit=True)
            await conn.execute(
                sql.SQL("LISTEN {}").format(sql.Identifier(_SHARED_CHANNEL))
            )
            await conn.execute(sql.SQL("LISTEN {}").format(sql.Identifier(_CHANNEL)))
            logger.info(
                "[PgNotify] Listening on channels %s, %s",
                _SHARED_CHANNEL,
                _CHANNEL,
            )
            async for notify in conn.notifies():
                if stop.is_set():
                    break
                payload = notify.payload
                try:
                    env = json.loads(payload)
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
                if isinstance(env, dict) and env.get("fanout") == "chat":
                    inner = env.get("payload")
                    if isinstance(inner, str):
                        try:
                            from services.features.ws_redis_fanout_listener import (  # pylint: disable=import-outside-toplevel
                                dispatch_chat_fanout_raw,
                            )
                            await dispatch_chat_fanout_raw(inner)
                        except Exception as exc:  # pylint: disable=broad-except
                            logger.debug("[PgNotify] chat deliver error: %s", exc)
                    continue
                if _FANOUT_ORIGIN_SECRET and env.get("origin") != _FANOUT_ORIGIN_SECRET:
                    logger.warning("[PgNotify] rejected envelope with invalid origin")
                    continue
                code = env.get("code")
                mode = env.get("mode")
                data_str = env.get("d")
                ex = env.get("ex")
                if not isinstance(code, str) or mode not in ("all", "others"):
                    continue
                if not isinstance(data_str, str):
                    continue
                exclude = ex if isinstance(ex, int) else None
                try:
                    await deliver_local_workshop_broadcast(code, mode, exclude, data_str)
                except Exception as exc:  # pylint: disable=broad-except
                    logger.debug("[PgNotify] deliver error: %s", exc)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("[PgNotify] listener error: %s — reconnecting", exc)
        finally:
            if conn is not None:
                try:
                    await conn.close()
                except Exception:  # pylint: disable=broad-except
                    pass
        if not stop.is_set():
            await asyncio.sleep(_RECONNECT_DELAY_SEC)


def start_pg_notify_listener() -> None:
    """Spawn the background LISTEN task (no-op when the flag is off)."""
    if not _pg_notify_enabled():
        return
    if _PgNotifyState.listener_task is not None and not _PgNotifyState.listener_task.done():
        return
    stop = asyncio.Event()
    _PgNotifyState.stop_event = stop
    task = asyncio.create_task(_listener_loop(stop), name="pg_notify_fanout_listener")
    _PgNotifyState.listener_task = task
    logger.info("[PgNotify] Fallback listener started on %s", _CHANNEL)


def stop_pg_notify_listener() -> None:
    """Signal the LISTEN loop to exit gracefully."""
    if _PgNotifyState.stop_event:
        _PgNotifyState.stop_event.set()
    if _PgNotifyState.listener_task and not _PgNotifyState.listener_task.done():
        _PgNotifyState.listener_task.cancel()
    _PgNotifyState.listener_task = None
    _PgNotifyState.stop_event = None


_PG_NOTIFY_MAX_PAYLOAD_BYTES = 7900


async def publish_pg_notify_fanout_async(envelope: Dict[str, Any]) -> None:
    """
    NOTIFY the per-machine channel with the serialised envelope.

    Uses a fresh short-lived ``psycopg.AsyncConnection`` in autocommit mode so
    the NOTIFY is flushed immediately.  Errors are swallowed (best-effort) since
    this is already a degraded-mode fallback.

    Postgres pg_notify() silently truncates or rejects payloads larger than
    8000 bytes.  We pre-check and drop oversized payloads with a warning rather
    than losing updates silently.
    """
    if not _pg_notify_enabled():
        return
    try:
        body = json.dumps(envelope, ensure_ascii=False)
    except (TypeError, ValueError):
        return
    if len(body.encode("utf-8")) > _PG_NOTIFY_MAX_PAYLOAD_BYTES:
        logger.warning(
            "[PgNotify] Payload too large for pg_notify (%d bytes > %d); "
            "dropping channel=%s",
            len(body.encode("utf-8")),
            _PG_NOTIFY_MAX_PAYLOAD_BYTES,
            _CHANNEL,
        )
        return
    try:
        import psycopg  # pylint: disable=import-outside-toplevel
        from psycopg import sql  # pylint: disable=import-outside-toplevel
        from config.database import DATABASE_URL  # pylint: disable=import-outside-toplevel

        dsn = str(DATABASE_URL).replace("+asyncpg", "").replace("+psycopg", "")
        # We NOTIFY the shared channel so all workers receive the message,
        # not just the local one. The machine-specific channel is kept for
        # directed messaging (future use).
        notify_query = sql.SQL("SELECT pg_notify({}, %s)").format(
            sql.Identifier(_SHARED_CHANNEL)
        )
        async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
            await conn.execute(notify_query, (body,))
        logger.debug("[PgNotify] NOTIFY %s sent", _SHARED_CHANNEL)
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("[PgNotify] publish failed: %s", exc)
