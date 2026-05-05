"""
RedisJSON storage for ``workshop:live_spec:{code}`` on Redis 8+.

Live-spec reads and writes use ``JSON.GET``, ``JSON.SET``, and ``JSON.MERGE``.
The application requires Redis >= 8.0 at startup when collab is enabled
(see :func:`check_online_collab_redis_version`).

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from redis.exceptions import RedisError

from services.infrastructure.monitoring.ws_metrics import (
    record_ws_redisjson_failure_total,
)
from services.online_collab.redis.online_collab_redis_keys import live_spec_key

logger = logging.getLogger(__name__)


def _record_failure() -> None:
    """Best-effort metric increment that never raises."""
    try:
        record_ws_redisjson_failure_total()
    except (AttributeError, TypeError, ValueError, OSError, RuntimeError):
        pass


_JSON_GET_PREVIEW_MAX_CHARS = 160


def _preview_json_get_raw(raw: Any) -> str:
    """Short, bounded summary for logs (never dumps full diagram payloads)."""
    if raw is None:
        return "(nil)"
    if isinstance(raw, dict):
        sk = sorted(str(k) for k in raw.keys())
        preview_keys = ",".join(sk[:8])
        extra = ",…" if len(raw) > 8 else ""
        return f"<dict n={len(raw)} keys={preview_keys}{extra}>"
    if isinstance(raw, list):
        return f"<list len={len(raw)}>"
    if isinstance(raw, (bytes, bytearray, memoryview)):
        decoded = bytes(raw).decode("utf-8", errors="replace").strip()
        tail = len(decoded) > _JSON_GET_PREVIEW_MAX_CHARS
        body = decoded[:_JSON_GET_PREVIEW_MAX_CHARS]
        return f"{body}… [trunc]" if tail else body
    if isinstance(raw, str):
        stripped = raw.strip()
        tail = len(stripped) > _JSON_GET_PREVIEW_MAX_CHARS
        body = stripped[:_JSON_GET_PREVIEW_MAX_CHARS]
        return f"{body}… [trunc]" if tail else body
    text = repr(raw)
    tail = len(text) > _JSON_GET_PREVIEW_MAX_CHARS
    body = text[:_JSON_GET_PREVIEW_MAX_CHARS]
    return f"{body}… [trunc]" if tail else body


_JSON_GET_UNWRAP_MAX = 8


def parse_json_get_bulk(raw: Any) -> Optional[Dict[str, Any]]:
    """
    Normalize a ``JSON.GET`` bulk response (path ``$``) to a document dict.

    With RESP3 and ``decode_responses=True``, redis-py may deliver the JSON
    payload as native ``dict`` / ``list`` aggregates instead of encoded
    strings. This helper unwraps the historical ``[{...}]`` shape, parses
    string/bytes payloads, and returns ``None`` for empty or non-object
    roots.
    """
    cursor: Any = raw
    for _ in range(_JSON_GET_UNWRAP_MAX):
        if cursor is None:
            return None
        if isinstance(cursor, dict):
            return cursor
        if isinstance(cursor, list):
            if not cursor:
                return None
            cursor = cursor[0]
            continue
        if isinstance(cursor, (bytes, bytearray, memoryview)):
            try:
                cursor = bytes(cursor).decode("utf-8", errors="replace")
            except (TypeError, UnicodeDecodeError, ValueError):
                return None
            continue
        if isinstance(cursor, str):
            stripped = cursor.strip()
            if not stripped:
                return None
            try:
                cursor = json.loads(stripped)
            except (json.JSONDecodeError, TypeError, ValueError):
                return None
            continue
        return None
    return None


async def json_get_live_spec(redis: Any, code: str) -> Optional[Dict[str, Any]]:
    """``JSON.GET`` the live spec document; returns ``None`` on any failure."""
    try:
        raw = await redis.execute_command("JSON.GET", live_spec_key(code), "$")
    except RedisError as exc:
        logger.debug("[LiveSpecJSON] JSON.GET error code=%s: %s", code, exc)
        _record_failure()
        return None
    parsed = parse_json_get_bulk(raw)
    if parsed is None:
        key = live_spec_key(code)
        logger.debug(
            "[LiveSpecJSON] JSON.GET root unparsed code=%s key=%s raw_type=%s "
            "raw_preview=%s",
            code,
            key,
            type(raw).__name__,
            _preview_json_get_raw(raw),
        )
    return parsed


async def json_set_live_spec(
    redis: Any,
    code: str,
    document: Dict[str, Any],
    ttl_sec: int,
) -> bool:
    """Replace the full live-spec document and (re)apply TTL. Returns success."""
    key = live_spec_key(code)
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.execute_command("JSON.SET", key, "$", json.dumps(document))
            pipe.expire(key, max(1, int(ttl_sec)))
            await pipe.execute()
        return True
    except RedisError as exc:
        logger.debug("[LiveSpecJSON] JSON.SET error code=%s: %s", code, exc)
        _record_failure()
        return False


async def json_merge_patch(
    redis: Any,
    code: str,
    patch: Dict[str, Any],
    ttl_sec: int,
) -> bool:
    """
    Apply an RFC 7396 ``JSON.MERGE`` patch in one round-trip.

    Used for batched node/connection updates where the client has produced a
    granular dict of changes. The root document's TTL is re-asserted so
    repeated merges don't let the key expire mid-session.
    """
    key = live_spec_key(code)
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.execute_command("JSON.MERGE", key, "$", json.dumps(patch))
            pipe.expire(key, max(1, int(ttl_sec)))
            await pipe.execute()
        return True
    except RedisError as exc:
        logger.debug("[LiveSpecJSON] JSON.MERGE error code=%s: %s", code, exc)
        _record_failure()
        return False


async def json_delete_node(redis: Any, code: str, node_id: str) -> bool:
    """``JSON.DEL`` the first node with ``id == node_id``. No-op on miss."""
    if not node_id:
        return False
    key = live_spec_key(code)
    escaped = json.dumps(str(node_id))
    path = f"$.nodes[?(@.id == {escaped})]"
    try:
        await redis.execute_command("JSON.DEL", key, path)
        return True
    except RedisError as exc:
        logger.debug(
            "[LiveSpecJSON] JSON.DEL node code=%s id=%s: %s", code, node_id, exc,
        )
        _record_failure()
        return False


async def json_set_nodes(
    redis: Any,
    code: str,
    nodes: List[Dict[str, Any]],
    ttl_sec: int,
) -> bool:
    """Replace only the ``$.nodes`` array (no WATCH loop)."""
    key = live_spec_key(code)
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.execute_command("JSON.SET", key, "$.nodes", json.dumps(nodes))
            pipe.expire(key, max(1, int(ttl_sec)))
            await pipe.execute()
        return True
    except RedisError as exc:
        logger.debug("[LiveSpecJSON] JSON.SET $.nodes code=%s: %s", code, exc)
        _record_failure()
        return False
