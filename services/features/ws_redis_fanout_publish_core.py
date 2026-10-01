"""
Redis publish helpers for WebSocket fan-out (core transport, no PG NOTIFY).

Leaf module: no imports from pg_notify or fanout delivery to avoid cycles.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
from typing import Any, Dict, Optional

from redis.exceptions import RedisError

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
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

_FANOUT_ORIGIN_SECRET: str = os.getenv("COLLAB_FANOUT_ORIGIN_SECRET", "")


def stamp_chat_fanout_origin(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of ``envelope`` stamped with the fan-out origin secret.

    Mirrors the workshop fan-out origin stamping so a Redis/PG-write-capable
    attacker cannot forge chat channel, DM, or presence frames. When no secret
    is configured (dev), the envelope is returned unchanged and consumers do
    not enforce origin.
    """
    if not _FANOUT_ORIGIN_SECRET:
        return dict(envelope)
    out = dict(envelope)
    out["origin"] = _FANOUT_ORIGIN_SECRET
    return out


def stamp_workshop_fanout_origin(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Stamp workshop/mindmate-collab fan-out envelopes with the origin secret."""
    if not _FANOUT_ORIGIN_SECRET:
        return dict(envelope)
    out = dict(envelope)
    out["origin"] = _FANOUT_ORIGIN_SECRET
    return out


def _envelope_with_workshop_msg_id(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Guarantee every workshop fan-out JSON frame inside envelope field ``d`` has msg_id."""
    out = dict(envelope)
    payload = out.get("d")
    inner: Optional[Dict[str, Any]] = None
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except (json.JSONDecodeError, TypeError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            inner = parsed
    if isinstance(inner, dict):
        raw_mid = inner.get("msg_id")
        mid_ok = isinstance(raw_mid, str) and bool(raw_mid.strip())
        if not mid_ok:
            inner_copy = dict(inner)
            inner_copy["msg_id"] = secrets.token_hex(12)
            out["d"] = json.dumps(inner_copy, ensure_ascii=False)
    return out


def _receiver_count(raw: Any) -> int:
    """Normalize a PUBLISH/SPUBLISH reply to a subscriber count."""
    if isinstance(raw, bool) or raw is None:
        return 0
    if isinstance(raw, int):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        try:
            return int(raw)
        except ValueError:
            return 0
    return 0


async def _publish_with_channel_transport(
    client: Any,
    channel: str,
    body: str,
) -> Any:
    """Deliver ``body`` via SPUBLISH or PUBLISH. Returns the Redis receiver count."""
    if use_sharded_pubsub() and is_sharded_pubsub_active():
        try:
            return await client.execute_command("SPUBLISH", channel, body)
        except RedisError as exc:
            logger.debug(
                "[WSFanout] SPUBLISH failed channel=%s (%s) — falling back to PUBLISH",
                channel,
                exc,
            )
    return await client.publish(channel, body)


async def _audit_xadd(client: Any, body: str) -> None:
    """Best-effort XADD to the audit stream (non-delivery path)."""
    try:
        await client.execute_command(
            "XADD",
            WORKSHOP_FANOUT_STREAM_KEY,
            "MAXLEN",
            "~",
            str(WORKSHOP_FANOUT_STREAM_MAXLEN),
            "*",
            "d",
            body,
        )
    except RedisError as exc:
        logger.debug("[WSFanout] audit XADD failed: %s", exc)


async def publish_chat_fanout_async(envelope: Dict[str, Any]) -> None:
    """Publish a chat fan-out envelope using the native async Redis client."""
    if not is_ws_fanout_enabled():
        return
    out = stamp_chat_fanout_origin(envelope)
    try:
        body = json.dumps(out, ensure_ascii=False)
    except (TypeError, ValueError):
        logger.warning("[WSFanout] Chat publish skipped: invalid envelope")
        return
    client = get_async_redis()
    if not client:
        return
    try:
        record_ws_fanout_chat_published()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.debug("[WSFanout] chat publish metric failed: %s", exc)
    try:
        await _publish_with_channel_transport(client, CHAT_FANOUT_CHANNEL, body)
        try:
            record_ws_fanout_publish_success()
        except BACKGROUND_INFRA_ERRORS:
            pass
    except RedisError:
        try:
            record_ws_fanout_publish_failure()
        except BACKGROUND_INFRA_ERRORS:
            pass
        raise


async def publish_workshop_fanout_async(envelope: Dict[str, Any]) -> int:
    """
    Publish a workshop fan-out envelope via pub/sub (no PG NOTIFY fallback).

    Returns how many pub/sub clients received the message. Zero means the
    frame was not delivered and the caller should hand it to local sockets.
    """
    if not is_ws_fanout_enabled():
        return 0
    out = _envelope_with_workshop_msg_id(stamp_workshop_fanout_origin(dict(envelope)))
    try:
        body = json.dumps(out, ensure_ascii=False)
    except (TypeError, ValueError):
        logger.warning("[WSFanout] Workshop publish skipped: invalid envelope")
        return 0
    client = get_async_redis()
    if not client:
        logger.warning("[WSFanout] publish_workshop_fanout_async: no Redis client — message dropped")
        return 0
    try:
        record_ws_fanout_workshop_published()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.debug("[WSFanout] workshop publish metric failed: %s", exc)

    try:
        receivers = _receiver_count(
            await _publish_with_channel_transport(client, WORKSHOP_FANOUT_CHANNEL, body),
        )
        try:
            record_ws_fanout_publish_success()
        except BACKGROUND_INFRA_ERRORS:
            pass
        try:
            _inner = out.get("d")
            if isinstance(_inner, str):
                _parsed = json.loads(_inner)
                logger.debug(
                    "[WSFanout] publish_ok channel=%s code=%s mode=%s msg_type=%s seq=%s version=%s msg_id=%s",
                    WORKSHOP_FANOUT_CHANNEL,
                    out.get("code"),
                    out.get("mode"),
                    _parsed.get("type"),
                    _parsed.get("seq"),
                    _parsed.get("version"),
                    _parsed.get("msg_id"),
                )
        except BACKGROUND_INFRA_ERRORS:
            pass
    except RedisError:
        try:
            record_ws_fanout_publish_failure()
        except BACKGROUND_INFRA_ERRORS:
            pass
        raise

    if use_streams_audit():
        asyncio.create_task(
            _audit_xadd(client, body),
            name="ws-fanout-audit-xadd",
        )
    return receivers
