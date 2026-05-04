"""
Redis publish helpers for WebSocket fan-out (no subscription / listener).

Phase 1: pub/sub is the ONLY broadcast delivery path.
  Streams XADD is an optional audit log (COLLAB_REDIS_STREAMS_AUDIT=1);
  it runs in a background task after PUBLISH so it never blocks the hot path.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from typing import Any, Dict, Optional

from redis.exceptions import RedisError

from services.features.ws_pg_notify_fanout import publish_pg_notify_fanout_async
from services.features.ws_redis_fanout_config import (
    CHAT_FANOUT_CHANNEL,
    WORKSHOP_FANOUT_CHANNEL,
    WORKSHOP_FANOUT_STREAM_KEY,
    WORKSHOP_FANOUT_STREAM_MAXLEN,
    is_sharded_pubsub_active,
    is_ws_fanout_enabled,
    use_sharded_pubsub,
    use_streams_audit,
)
from services.infrastructure.monitoring.ws_metrics import (
    record_ws_fanout_chat_published,
    record_ws_fanout_publish_failure,
    record_ws_fanout_publish_success,
    record_ws_fanout_workshop_published,
)
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)


def _envelope_with_workshop_msg_id(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """
    Guarantee every workshop fan-out JSON frame inside envelope field ``d`` has msg_id.

    Duplicate SPUBLISH + PG NOTIFY delivery must dedupe in
    ``deliver_local_workshop_broadcast`` using that field.
    """
    out = dict(envelope)
    payload = out.get('d')
    inner: Optional[Dict[str, Any]] = None
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except (json.JSONDecodeError, TypeError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            inner = parsed
    if isinstance(inner, dict):
        raw_mid = inner.get('msg_id')
        mid_ok = isinstance(raw_mid, str) and bool(raw_mid.strip())
        if not mid_ok:
            inner_copy = dict(inner)
            inner_copy['msg_id'] = secrets.token_hex(12)
            out['d'] = json.dumps(inner_copy, ensure_ascii=False)
    return out


async def _publish_with_channel_transport(
    client: Any, channel: str, body: str,
) -> None:
    """
    Deliver ``body`` via the best available push transport.

    Resolution order (fail-open):
      1. ``SPUBLISH`` only when BOTH ``COLLAB_REDIS_SPUBLISH=1`` AND the
         listener confirmed SSUBSCRIBE is active (``is_sharded_pubsub_active``).
         This prevents the silent-loss bug on Redis 7.0+ where SPUBLISH and
         PUBLISH use separate pub/sub mechanisms that do NOT cross-deliver.
      2. Plain ``PUBLISH`` in all other cases (subscriber used SUBSCRIBE).
      3. PG LISTEN/NOTIFY fallback when both Redis paths raise (only when
         ``COLLAB_PG_NOTIFY_FALLBACK=1``).
    """
    if use_sharded_pubsub() and is_sharded_pubsub_active():
        try:
            await client.execute_command("SPUBLISH", channel, body)
            return
        except RedisError as exc:
            logger.debug(
                "[WSFanout] SPUBLISH failed channel=%s (%s) — falling back "
                "to PUBLISH", channel, exc,
            )
    try:
        await client.publish(channel, body)
    except RedisError as exc:
        logger.warning("[WSFanout] PUBLISH failed channel=%s (%s) — PG NOTIFY fallback", channel, exc)
        raise


async def _audit_xadd(client: Any, body: str) -> None:
    """Best-effort XADD to the audit stream (non-delivery path)."""
    try:
        await client.execute_command(
            "XADD",
            WORKSHOP_FANOUT_STREAM_KEY,
            "MAXLEN", "~", str(WORKSHOP_FANOUT_STREAM_MAXLEN),
            "*",
            "d", body,
        )
    except RedisError as exc:
        logger.debug("[WSFanout] audit XADD failed: %s", exc)


async def publish_chat_fanout_async(envelope: Dict[str, Any]) -> None:
    """Publish a chat fan-out envelope using the native async Redis client."""
    if not is_ws_fanout_enabled():
        return
    try:
        body = json.dumps(envelope, ensure_ascii=False)
    except (TypeError, ValueError):
        logger.warning("[WSFanout] Chat publish skipped: invalid envelope")
        return
    client = get_async_redis()
    if not client:
        return
    try:
        record_ws_fanout_chat_published()
    except Exception as exc:
        logger.debug("[WSFanout] chat publish metric failed: %s", exc)
    try:
        await _publish_with_channel_transport(client, CHAT_FANOUT_CHANNEL, body)
        try:
            record_ws_fanout_publish_success()
        except Exception:
            pass
    except RedisError:
        try:
            record_ws_fanout_publish_failure()
        except Exception:
            pass
        asyncio.create_task(
            publish_pg_notify_fanout_async(
                {"fanout": "chat", "payload": body},
            ),
            name="ws-chat-fanout-pg-notify",
        )


async def publish_workshop_fanout_async(envelope: Dict[str, Any]) -> None:
    """
    Publish a workshop fan-out envelope via pub/sub.

    Transport: SPUBLISH (default) → PUBLISH fallback → PG NOTIFY fallback.
    Audit: if COLLAB_REDIS_STREAMS_AUDIT=1, XADD runs in a background task
    after the pub/sub publish so it never adds latency to the hot path.
    """
    if not is_ws_fanout_enabled():
        return
    out = _envelope_with_workshop_msg_id(dict(envelope))
    try:
        body = json.dumps(out, ensure_ascii=False)
    except (TypeError, ValueError):
        logger.warning("[WSFanout] Workshop publish skipped: invalid envelope")
        return
    client = get_async_redis()
    if not client:
        logger.warning("[WSFanout] publish_workshop_fanout_async: no Redis client — message dropped")
        return
    try:
        record_ws_fanout_workshop_published()
    except Exception as exc:
        logger.debug("[WSFanout] workshop publish metric failed: %s", exc)

    try:
        await _publish_with_channel_transport(client, WORKSHOP_FANOUT_CHANNEL, body)
        try:
            record_ws_fanout_publish_success()
        except Exception:
            pass
        try:
            _inner = out.get("d")
            if isinstance(_inner, str):
                _parsed = json.loads(_inner)
                logger.debug(
                    "[WSFanout] publish_ok channel=%s code=%s mode=%s"
                    " msg_type=%s seq=%s version=%s msg_id=%s",
                    WORKSHOP_FANOUT_CHANNEL,
                    out.get("code"), out.get("mode"),
                    _parsed.get("type"), _parsed.get("seq"),
                    _parsed.get("version"), _parsed.get("msg_id"),
                )
        except Exception:
            pass
    except RedisError:
        try:
            record_ws_fanout_publish_failure()
        except Exception:
            pass
        asyncio.create_task(
            publish_pg_notify_fanout_async(out),
            name="ws-fanout-pg-notify",
        )
        return

    if use_streams_audit():
        asyncio.create_task(
            _audit_xadd(client, body),
            name="ws-fanout-audit-xadd",
        )
