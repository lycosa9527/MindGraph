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


def parse_json_get_bulk(raw: Any) -> Optional[Dict[str, Any]]:
    """
    Normalize a ``JSON.GET`` bulk response (path ``$``) to a document dict.

    Returns ``None`` for empty, unparseable, or non-object roots.
    """
    if not raw:
        return None
    try:
        parsed = json.loads(raw if isinstance(raw, str) else raw.decode("utf-8"))
    except (ValueError, AttributeError, UnicodeDecodeError):
        return None
    if isinstance(parsed, list):
        if not parsed:
            return None
        doc = parsed[0]
        return doc if isinstance(doc, dict) else None
    return parsed if isinstance(parsed, dict) else None


async def json_get_live_spec(redis: Any, code: str) -> Optional[Dict[str, Any]]:
    """``JSON.GET`` the live spec document; returns ``None`` on any failure."""
    try:
        raw = await redis.execute_command("JSON.GET", live_spec_key(code), "$")
    except RedisError as exc:
        logger.debug("[LiveSpecJSON] JSON.GET error code=%s: %s", code, exc)
        _record_failure()
        return None
    return parse_json_get_bulk(raw)


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
