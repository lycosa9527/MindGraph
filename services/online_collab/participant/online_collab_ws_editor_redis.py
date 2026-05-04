"""
Redis-backed active editor state for diagram workshop (multi-worker).

Editor maps are mutated with optimistic locking (WATCH/MULTI/EXEC) so one
worker cannot overwrite another worker's in-memory subset.

Two backends are supported:
  - ``hash`` (default): per-node HASH field with per-field HEXPIRE TTL
    (Redis 7.4+/Redis 8). O(1) writes per node_editing event. Gives
    self-healing locks when a client crashes without emitting
    ``node_editing=false``. Disable via ``COLLAB_EDITORS_USE_HASH=0``.
  - ``json`` (legacy fallback): single STRING key holding a JSON blob of
    the entire editor map. O(map) serialize per change. Use only on Redis
    versions that do not support HEXPIRE.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any, Dict, List, Optional, Tuple

from redis.exceptions import RedisError, WatchError

from services.redis.redis_async_client import get_async_redis
from services.online_collab.participant.online_collab_ws_editor_hash import (
    editors_use_hash_backend,
    hash_apply_node_editor_batch_delta,
    hash_apply_node_editor_delta,
    hash_claim_node_exclusive,
    hash_load_editors,
    hash_purge_user_from_all_nodes,
)
from services.online_collab.redis.online_collab_redis_keys import _tag

logger = logging.getLogger(__name__)

_TTL_SECONDS = 86400
_EDITORS_WATCH_MAX_ATTEMPTS = 10
_EDITORS_WATCH_BASE_BACKOFF_SEC = 0.005
_EDITORS_WATCH_MAX_BACKOFF_SEC = 0.080


def _editors_backoff_delay(attempt: int) -> float:
    """Capped exponential backoff with jitter for the editor WATCH loop."""
    base = _EDITORS_WATCH_BASE_BACKOFF_SEC * (2 ** attempt)
    capped = min(base, _EDITORS_WATCH_MAX_BACKOFF_SEC)
    return capped + random.uniform(0, capped)


def _key(code: str) -> str:
    return f"mg:ws:workshop:editors:{_tag(code)}"


def parse_editors_raw(raw: Any) -> Dict[str, Dict[int, str]]:
    """Parse Redis bytes/str JSON into nested editor dict."""
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
    out: Dict[str, Dict[int, str]] = {}
    for nid, editors in parsed.items():
        if not isinstance(editors, dict):
            continue
        inner: Dict[int, str] = {}
        for uid_s, name in editors.items():
            try:
                inner[int(uid_s)] = str(name)
            except (ValueError, TypeError):
                continue
        out[str(nid)] = inner
    return out


def _serialize_editors_payload(editors: Dict[str, Dict[int, str]]) -> str:
    serializable: Dict[str, Dict[str, str]] = {}
    for nid, ed in editors.items():
        serializable[str(nid)] = {str(uid): name for uid, name in ed.items()}
    return json.dumps(serializable, ensure_ascii=False)


def merge_node_editor_delta_into_document(
    editors: Dict[str, Dict[int, str]],
    node_id: str,
    user_id: int,
    editing: bool,
    username: str,
) -> None:
    """Apply one user's node_editing signal to an in-memory map (mutates dict)."""
    nid = str(node_id)
    if editing:
        node_map = editors.setdefault(nid, {})
        node_map[int(user_id)] = username
        return
    node_map = editors.get(nid)
    if not node_map:
        return
    node_map.pop(int(user_id), None)
    if not node_map:
        editors.pop(nid, None)


def purge_user_from_editor_document(
    editors: Dict[str, Dict[int, str]],
    user_id: int,
) -> List[str]:
    """
    Drop user_id from every node entry.

    Returns:
        node ids that had this editor before purge.
    """
    touched: List[str] = []
    nodes_to_drop: List[str] = []
    uid = int(user_id)
    for nid, node_map in list(editors.items()):
        if uid in node_map:
            touched.append(str(nid))
            node_map.pop(uid, None)
        if not node_map:
            nodes_to_drop.append(nid)
    for nid in nodes_to_drop:
        editors.pop(nid, None)
    return touched


async def load_editors(code: str) -> Dict[str, Dict[int, str]]:
    """Load node_id -> {user_id: username} from Redis (backend-aware)."""
    if editors_use_hash_backend():
        return await hash_load_editors(code)
    try:
        redis = get_async_redis()
        if not redis:
            return {}
        raw = await redis.get(_key(code))
        return parse_editors_raw(raw)
    except (RedisError, OSError) as exc:
        logger.warning("[OnlineCollabEditorsRedis] load failed: %s", exc)
        return {}


async def save_editors(code: str, editors: Dict[str, Dict[int, str]]) -> None:
    """Persist full editor map (delete key when empty). Prefer atomic helpers."""
    try:
        redis = get_async_redis()
        if not redis:
            return
        key = _key(code)
        if not editors:
            await redis.delete(key)
            return
        await redis.setex(key, _TTL_SECONDS, _serialize_editors_payload(editors))
    except (RedisError, OSError) as exc:
        logger.warning("[OnlineCollabEditorsRedis] save failed: %s", exc)


async def claim_node_exclusive_redis(
    code: str,
    node_id: str,
    user_id: int,
    username: str,
) -> Optional[bool]:
    """
    Atomically claim exclusive edit ownership of a node.

    Returns True  — claim granted.
    Returns False — claim denied (node held by another user).
    Returns None  — atomic path unavailable; caller should fall back.

    Currently implemented only for the hash backend; callers that receive None
    must fall back to the existing read-check-write path.
    """
    if editors_use_hash_backend():
        return await hash_claim_node_exclusive(code, node_id, user_id, username)
    return None


async def apply_node_editor_delta_redis(
    code: str,
    node_id: str,
    user_id: int,
    editing: bool,
    username: str,
) -> bool:
    """
    Atomically merge one node_editing event into Redis (multi-worker safe).

    Returns:
        True if committed, False if retries exhausted or Redis unavailable.
    """
    if editors_use_hash_backend():
        return await hash_apply_node_editor_delta(
            code, node_id, user_id, editing, username,
        )
    redis = get_async_redis()
    if not redis:
        return False
    key = _key(code)
    for attempt in range(_EDITORS_WATCH_MAX_ATTEMPTS):
        try:
            async with redis.pipeline(transaction=True) as pipe:
                await pipe.watch(key)
                raw_get = await pipe.get(key)
                editors = parse_editors_raw(raw_get)
                merge_node_editor_delta_into_document(
                    editors,
                    node_id,
                    user_id,
                    editing,
                    username,
                )
                pipe.multi()
                if not editors:
                    pipe.delete(key)
                else:
                    pipe.setex(
                        key,
                        _TTL_SECONDS,
                        _serialize_editors_payload(editors),
                    )
                await pipe.execute()
            return True
        except WatchError:
            if attempt < _EDITORS_WATCH_MAX_ATTEMPTS - 1:
                await asyncio.sleep(_editors_backoff_delay(attempt))
            continue
        except (RedisError, OSError) as exc:
            logger.warning(
                "[OnlineCollabEditorsRedis] atomic node delta failed: %s",
                exc,
            )
            return False
    logger.warning(
        "[OnlineCollabEditorsRedis] atomic node delta retries exhausted workshop=%s",
        code,
    )
    return False


async def purge_user_from_all_nodes_redis_watched(code: str, user_id: int) -> Tuple[List[str], bool]:
    """
    Remove user from all node editor entries atomically.

    Returns:
        (sorted unique node ids that had this user before removal, ok)
    """
    if editors_use_hash_backend():
        return await hash_purge_user_from_all_nodes(code, user_id)
    redis = get_async_redis()
    if not redis:
        return [], False
    key = _key(code)
    for attempt in range(_EDITORS_WATCH_MAX_ATTEMPTS):
        try:
            async with redis.pipeline(transaction=True) as pipe:
                await pipe.watch(key)
                raw_get = await pipe.get(key)
                editors = parse_editors_raw(raw_get)
                touched = purge_user_from_editor_document(editors, user_id)
                pipe.multi()
                if not editors:
                    pipe.delete(key)
                else:
                    pipe.setex(
                        key,
                        _TTL_SECONDS,
                        _serialize_editors_payload(editors),
                    )
                await pipe.execute()
            return touched, True
        except WatchError:
            if attempt < _EDITORS_WATCH_MAX_ATTEMPTS - 1:
                await asyncio.sleep(_editors_backoff_delay(attempt))
            continue
        except (RedisError, OSError) as exc:
            logger.warning(
                "[OnlineCollabEditorsRedis] atomic purge failed: %s",
                exc,
            )
            return [], False
    logger.warning(
        "[OnlineCollabEditorsRedis] purge retries exhausted workshop=%s",
        code,
    )
    return [], False


async def apply_node_editor_batch_delta_redis(
    code: str,
    node_ids: List[str],
    user_id: int,
    editing: bool,
    username: str,
) -> Tuple[List[str], bool]:
    """
    Atomically merge a batch of node_editing deltas into Redis (one WATCH/MULTI).

    Used by the subtree/structural-op lock path so all descendants are locked
    or released in a single transaction and either every id appears in a
    ``node_editing_batch`` broadcast or none do.

    Returns:
        (effective_node_ids, ok) where effective_node_ids is the subset of
        requested ids that actually changed state (e.g. skip already-locked
        by-others when acquiring). ok=False on retry exhaustion or Redis
        unavailable.
    """
    if editors_use_hash_backend():
        return await hash_apply_node_editor_batch_delta(
            code, node_ids, user_id, editing, username,
        )
    redis = get_async_redis()
    if not redis:
        return [], False
    if not node_ids:
        return [], True
    key = _key(code)
    uid = int(user_id)
    ids = [str(nid) for nid in node_ids if isinstance(nid, str) and nid]
    for attempt in range(_EDITORS_WATCH_MAX_ATTEMPTS):
        try:
            async with redis.pipeline(transaction=True) as pipe:
                await pipe.watch(key)
                raw_get = await pipe.get(key)
                editors = parse_editors_raw(raw_get)
                effective: List[str] = []
                for nid in ids:
                    if editing:
                        node_map = editors.get(nid) or {}
                        locked_by_other = any(int(u) != uid for u in node_map)
                        if locked_by_other:
                            continue
                        editors.setdefault(nid, {})[uid] = username
                        effective.append(nid)
                    else:
                        node_map = editors.get(nid)
                        if not node_map or uid not in node_map:
                            continue
                        node_map.pop(uid, None)
                        if not node_map:
                            editors.pop(nid, None)
                        effective.append(nid)
                pipe.multi()
                if not editors:
                    pipe.delete(key)
                else:
                    pipe.setex(
                        key,
                        _TTL_SECONDS,
                        _serialize_editors_payload(editors),
                    )
                await pipe.execute()
            return effective, True
        except WatchError:
            if attempt < _EDITORS_WATCH_MAX_ATTEMPTS - 1:
                await asyncio.sleep(_editors_backoff_delay(attempt))
            continue
        except (RedisError, OSError) as exc:
            logger.warning(
                "[OnlineCollabEditorsRedis] batch node delta failed: %s", exc,
            )
            return [], False
    logger.warning(
        "[OnlineCollabEditorsRedis] batch node delta retries exhausted workshop=%s",
        code,
    )
    return [], False


async def remove_user_from_all_nodes(
    code: str,
    user_id: int,
    editors: Dict[str, Dict[int, str]],
) -> Tuple[Dict[str, Dict[int, str]], bool]:
    """Legacy: mutate provided dict then save (prefer purge_user_from_all_nodes_redis_watched)."""
    touched = purge_user_from_editor_document(editors, user_id)
    if touched:
        await save_editors(code, editors)
    return editors, bool(touched)
