"""
HASH-backed active editor state for workshop with per-field TTL (Redis 7.4+ HEXPIRE).

Opt-in alternative to the JSON-blob backend in workshop_ws_editor_redis.py.
Activate by setting ``COLLAB_EDITORS_USE_HASH=1`` in the environment.

Layout:
  KEY:   mg:ws:workshop:editors_h:{code}     (HASH)
  FIELD: node_id                              (string; node identifier)
  VALUE: JSON-encoded {user_id: username}     (small JSON blob; O(1) users per
         node because only one editor may hold a lock at a time and observers
         rarely exceed 2-3)

Each HSET applies ``HEXPIRE`` to the field with ``_FIELD_TTL_SEC`` so a
crashed client that failed to emit ``node_editing=false`` self-heals within
the TTL window, without waiting for the whole session's 24 h key expiry.

HEXPIRE is supported on Redis 7.4+. On older servers the HEXPIRE call is
skipped (the key itself still has the session-wide TTL via whole-key EXPIRE).

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from typing import Any, Awaitable, Dict, List, Optional, Tuple, cast

from redis.exceptions import RedisError, WatchError

from services.redis.redis_async_client import get_async_redis
from services.online_collab.redis.online_collab_redis_keys import _tag
from services.online_collab.redis.online_collab_redis_locks import (
    fcall_node_claim_exclusive,
    fcall_node_editing_del,
    fcall_node_editing_set,
)

logger = logging.getLogger(__name__)

_KEY_TTL_SEC = 86400
_FIELD_TTL_SEC = 30
_HASH_WATCH_MAX_ATTEMPTS = 10
_HASH_WATCH_BASE_BACKOFF_SEC = 0.005
_HASH_WATCH_MAX_BACKOFF_SEC = 0.080
_HEXPIRE_SUPPORTED_CELL: list[bool | None] = [None]


def editors_use_hash_backend() -> bool:
    """
    True when the HASH editor backend is active (Redis 7.4+ HEXPIRE required).

    Defaults to ``1`` (enabled) for production workloads; set
    ``COLLAB_EDITORS_USE_HASH=0`` to fall back to the legacy JSON STRING path
    on clusters that do not yet support HEXPIRE.
    """
    return os.getenv("COLLAB_EDITORS_USE_HASH", "1") not in ("0", "false", "False", "")


def _key(code: str) -> str:
    return f"mg:ws:workshop:editors_h:{_tag(code)}"


def _field(node_id: str) -> str:
    return str(node_id)


def _node_map_to_json(node_map: Dict[int, str]) -> str:
    return json.dumps(
        {str(uid): name for uid, name in node_map.items()}, ensure_ascii=False,
    )


def _json_to_node_map(raw: Any) -> Dict[int, str]:
    if raw is None:
        return {}
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    out: Dict[int, str] = {}
    for uid_s, name in parsed.items():
        try:
            out[int(uid_s)] = str(name)
        except (ValueError, TypeError):
            continue
    return out


def _hash_backoff_delay(attempt: int) -> float:
    base = _HASH_WATCH_BASE_BACKOFF_SEC * (2 ** attempt)
    capped = min(base, _HASH_WATCH_MAX_BACKOFF_SEC)
    return capped + random.uniform(0, capped)


async def _call_hexpire(redis: Any, key: str, seconds: int, field: str) -> None:
    """
    Best-effort HEXPIRE KEY SECONDS FIELDS 1 FIELD.

    Gracefully no-ops on Redis < 7.4 (command returns an error or command not
    found) and caches the unsupported flag so subsequent calls skip the wire
    round-trip entirely.
    """
    cell = _HEXPIRE_SUPPORTED_CELL
    if cell[0] is False:
        return
    try:
        await redis.execute_command("HEXPIRE", key, seconds, "FIELDS", 1, field)
        cell[0] = True
    except RedisError as exc:
        msg = str(exc).lower()
        if (
            "unknown command" in msg
            or "err" in msg and "hexpire" in msg
        ):
            cell[0] = False
            logger.info(
                "[WorkshopEditorsHash] HEXPIRE unsupported — falling back to "
                "key-level TTL only (Redis < 7.4)"
            )
            return
        logger.debug("[WorkshopEditorsHash] HEXPIRE failed (non-fatal): %s", exc)


async def hash_load_editors(code: str) -> Dict[str, Dict[int, str]]:
    """Load the full editor map from the HASH backend."""
    redis = get_async_redis()
    if not redis:
        return {}
    try:
        raw_map = await cast(Awaitable[Any], redis.hgetall(_key(code)))
    except (RedisError, OSError) as exc:
        logger.warning("[WorkshopEditorsHash] hgetall failed: %s", exc)
        return {}
    if not raw_map:
        return {}
    out: Dict[str, Dict[int, str]] = {}
    for nid_raw, val in raw_map.items():
        nid = nid_raw.decode("utf-8") if isinstance(nid_raw, bytes) else str(nid_raw)
        parsed = _json_to_node_map(val)
        if parsed:
            out[nid] = parsed
    return out


async def hash_claim_node_exclusive(
    code: str,
    node_id: str,
    user_id: int,
    username: str,
) -> Optional[bool]:
    """
    Atomically claim exclusive edit ownership of a node using the hash backend.

    Returns True  — claim granted (node was free or already held by this user).
    Returns False — claim denied (another user is already editing this node).
    Returns None  — FCALL unavailable; caller should fall back to read-check-write.

    Only meaningful when the hash backend is active (``editors_use_hash_backend()``).
    """
    redis = get_async_redis()
    if not redis:
        return None
    return await fcall_node_claim_exclusive(
        redis,
        hash_key=_key(code),
        field=_field(node_id),
        user_id_str=str(user_id),
        username=username,
        field_ttl_sec=_FIELD_TTL_SEC,
        key_ttl_sec=_KEY_TTL_SEC,
    )


async def hash_apply_node_editor_delta(
    code: str,
    node_id: str,
    user_id: int,
    editing: bool,
    username: str,
) -> bool:
    """
    HASH-backend equivalent of apply_node_editor_delta_redis.

    Fast path (editing=True, single editor): tries a 1-RTT
    ``mg_node_editing_set`` FCALL. Falls back to WATCH/MULTI on older Redis.
    Fast path (editing=False): tries a 1-RTT ``mg_node_editing_del`` FCALL.
    """
    redis = get_async_redis()
    if not redis:
        return False
    key = _key(code)
    field = _field(node_id)
    uid = int(user_id)

    if editing:
        ok = await fcall_node_editing_set(
            redis, key, field, str(uid), username, _FIELD_TTL_SEC, _KEY_TTL_SEC,
        )
        if ok:
            return True
    else:
        ok = await fcall_node_editing_del(
            redis, key, field, str(uid), _FIELD_TTL_SEC, _KEY_TTL_SEC,
        )
        if ok:
            return True

    for attempt in range(_HASH_WATCH_MAX_ATTEMPTS):
        try:
            async with redis.pipeline(transaction=True) as pipe:
                await pipe.watch(key)
                raw = await cast(Awaitable[Any], pipe.hget(key, field))
                node_map = _json_to_node_map(raw)
                if editing:
                    node_map[uid] = username
                else:
                    node_map.pop(uid, None)
                pipe.multi()
                if node_map:
                    pipe.hset(key, field, _node_map_to_json(node_map))
                else:
                    pipe.hdel(key, field)
                pipe.expire(key, _KEY_TTL_SEC, gt=True)
                await pipe.execute()
            if editing:
                await _call_hexpire(redis, key, _FIELD_TTL_SEC, field)
            return True
        except WatchError:
            if attempt < _HASH_WATCH_MAX_ATTEMPTS - 1:
                await asyncio.sleep(_hash_backoff_delay(attempt))
            continue
        except (RedisError, OSError) as exc:
            logger.warning(
                "[WorkshopEditorsHash] delta failed code=%s field=%s: %s",
                code, field, exc,
            )
            return False
    logger.warning(
        "[WorkshopEditorsHash] delta retries exhausted code=%s field=%s", code, field,
    )
    return False


async def hash_apply_node_editor_batch_delta(
    code: str,
    node_ids: List[str],
    user_id: int,
    editing: bool,
    username: str,
) -> Tuple[List[str], bool]:
    """HASH-backend equivalent of apply_node_editor_batch_delta_redis."""
    redis = get_async_redis()
    if not redis:
        return [], False
    if not node_ids:
        return [], True
    key = _key(code)
    uid = int(user_id)
    fields = [_field(nid) for nid in node_ids if isinstance(nid, str) and nid]
    if not fields:
        return [], True
    for attempt in range(_HASH_WATCH_MAX_ATTEMPTS):
        try:
            async with redis.pipeline(transaction=True) as pipe:
                await pipe.watch(key)
                effective: List[str] = []
                raw_values = await cast(
                    Awaitable[Any], pipe.hmget(key, fields),
                )
                node_maps: Dict[str, Dict[int, str]] = {}
                for field, raw in zip(fields, raw_values):
                    node_maps[field] = _json_to_node_map(raw)
                for field in fields:
                    node_map = node_maps[field]
                    if editing:
                        locked_by_other = any(int(u) != uid for u in node_map)
                        if locked_by_other:
                            continue
                        node_map[uid] = username
                        effective.append(field)
                    else:
                        if uid not in node_map:
                            continue
                        node_map.pop(uid, None)
                        effective.append(field)
                pipe.multi()
                for field in fields:
                    node_map = node_maps[field]
                    if node_map:
                        pipe.hset(key, field, _node_map_to_json(node_map))
                    else:
                        pipe.hdel(key, field)
                pipe.expire(key, _KEY_TTL_SEC, gt=True)
                await pipe.execute()
            if editing and effective:
                try:
                    await redis.execute_command(
                        "HEXPIRE", key, _FIELD_TTL_SEC,
                        "FIELDS", len(effective), *effective,
                    )
                except RedisError as exc:
                    logger.debug(
                        "[WorkshopEditorsHash] batch HEXPIRE skipped: %s", exc,
                    )
            return effective, True
        except WatchError:
            if attempt < _HASH_WATCH_MAX_ATTEMPTS - 1:
                await asyncio.sleep(_hash_backoff_delay(attempt))
            continue
        except (RedisError, OSError) as exc:
            logger.warning(
                "[WorkshopEditorsHash] batch delta failed code=%s: %s", code, exc,
            )
            return [], False
    logger.warning(
        "[WorkshopEditorsHash] batch delta retries exhausted code=%s", code,
    )
    return [], False


async def hash_purge_user_from_all_nodes(
    code: str, user_id: int,
) -> Tuple[List[str], bool]:
    """HASH-backend equivalent of purge_user_from_all_nodes_redis_watched."""
    redis = get_async_redis()
    if not redis:
        return [], False
    key = _key(code)
    uid = int(user_id)
    for attempt in range(_HASH_WATCH_MAX_ATTEMPTS):
        try:
            async with redis.pipeline(transaction=True) as pipe:
                await pipe.watch(key)
                raw_map = await cast(Awaitable[Any], pipe.hgetall(key))
                touched: List[str] = []
                updates: Dict[str, str] = {}
                deletes: List[str] = []
                for nid_raw, val in (raw_map or {}).items():
                    nid = (
                        nid_raw.decode("utf-8")
                        if isinstance(nid_raw, bytes)
                        else str(nid_raw)
                    )
                    node_map = _json_to_node_map(val)
                    if uid not in node_map:
                        continue
                    touched.append(nid)
                    node_map.pop(uid, None)
                    if node_map:
                        updates[nid] = _node_map_to_json(node_map)
                    else:
                        deletes.append(nid)
                pipe.multi()
                for nid, payload in updates.items():
                    pipe.hset(key, nid, payload)
                if deletes:
                    pipe.hdel(key, *deletes)
                pipe.expire(key, _KEY_TTL_SEC, gt=True)
                await pipe.execute()
            return touched, True
        except WatchError:
            if attempt < _HASH_WATCH_MAX_ATTEMPTS - 1:
                await asyncio.sleep(_hash_backoff_delay(attempt))
            continue
        except (RedisError, OSError) as exc:
            logger.warning(
                "[WorkshopEditorsHash] purge failed code=%s: %s", code, exc,
            )
            return [], False
    logger.warning(
        "[WorkshopEditorsHash] purge retries exhausted code=%s", code,
    )
    return [], False
