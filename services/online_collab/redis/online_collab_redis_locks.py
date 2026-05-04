"""
Redis NX lock helpers with ownership-verified (CAS) release for workshop module.

On Redis 7.0+ the CAS helpers are registered once per process as a Redis
Function (``FUNCTION LOAD``) and invoked via ``FCALL`` so Redis hands us a
native cached function (parsed + compiled into bytecode) instead of
re-interpreting a Lua script on every call. On older servers we transparently
fall back to ``EVAL``.

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
Proprietary License
"""

import asyncio
import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from redis.exceptions import RedisError

from services.online_collab.redis.online_collab_redis_keys import (
    live_changed_keys_key,
    live_spec_key,
    live_write_lock_key,
    snapshot_seq_key,
    tombstones_key,
)

logger = logging.getLogger(__name__)

_CAS_DELETE_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
else
  return 0
end
"""

_CAS_EXTEND_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
else
  return 0
end
"""

_WORKSHOP_LIB_NAME = "mg_workshop_locks"
_WORKSHOP_LIB_CODE = """#!lua name=mg_workshop_locks
redis.register_function('mg_cas_delete', function(keys, args)
  if redis.call('GET', keys[1]) == args[1] then
    return redis.call('DEL', keys[1])
  end
  return 0
end)
redis.register_function('mg_cas_extend', function(keys, args)
  if redis.call('GET', keys[1]) == args[1] then
    return redis.call('EXPIRE', keys[1], tonumber(args[2]))
  end
  return 0
end)
-- mg_node_claim_exclusive: atomic exclusive claim — only grants if no OTHER user is editing.
-- KEYS[1] = hash key (mg:ws:workshop:editors_h:{code})
-- ARGV[1] = field (node_id)
-- ARGV[2] = user_id (string, JSON object key)
-- ARGV[3] = username
-- ARGV[4] = field TTL seconds (HEXPIRE)
-- ARGV[5] = key TTL seconds
-- Returns 1 if claimed (node was free or already held by this user), 0 if denied.
redis.register_function('mg_node_claim_exclusive', function(keys, args)
  local field = args[1]
  local uid = args[2]
  local username = args[3]
  local field_ttl = tonumber(args[4])
  local key_ttl = tonumber(args[5])
  local raw = redis.call('HGET', keys[1], field)
  local map = {}
  if raw then
    local dec_ok, parsed = pcall(cjson.decode, raw)
    if dec_ok and type(parsed) == 'table' then
      map = parsed
    end
  end
  -- Deny if any key in the map belongs to a different user.
  for k, _ in pairs(map) do
    if k ~= uid then
      return 0
    end
  end
  -- Safe to claim: write uid -> username atomically.
  map[uid] = username
  redis.call('HSET', keys[1], field, cjson.encode(map))
  if field_ttl and field_ttl > 0 then
    local hex_ok = pcall(redis.call, 'HEXPIRE', keys[1], field_ttl, 'FIELDS', 1, field)
    if not hex_ok then
      redis.call('EXPIRE', keys[1], field_ttl)
    end
  end
  if key_ttl and key_ttl > 0 then
    redis.call('EXPIRE', keys[1], key_ttl)
  end
  return 1
end)
-- mg_node_editing_set: read-modify-write merge + HSET + HEXPIRE + key EXPIRE.
-- KEYS[1] = hash key (mg:ws:workshop:editors_h:{code})
-- ARGV[1] = field (node_id)
-- ARGV[2] = user_id (string, JSON object key)
-- ARGV[3] = username
-- ARGV[4] = field TTL seconds (HEXPIRE)
-- ARGV[5] = key TTL seconds
-- Returns 1 on success.
redis.register_function('mg_node_editing_set', function(keys, args)
  local field = args[1]
  local uid = args[2]
  local username = args[3]
  local field_ttl = tonumber(args[4])
  local key_ttl = tonumber(args[5])
  local raw = redis.call('HGET', keys[1], field)
  local map = {}
  if raw then
    local dec_ok, parsed = pcall(cjson.decode, raw)
    if dec_ok and type(parsed) == 'table' then
      map = parsed
    end
  end
  map[uid] = username
  redis.call('HSET', keys[1], field, cjson.encode(map))
  if field_ttl and field_ttl > 0 then
    local hex_ok = pcall(redis.call, 'HEXPIRE', keys[1], field_ttl, 'FIELDS', 1, field)
    if not hex_ok then
      redis.call('EXPIRE', keys[1], field_ttl)
    end
  end
  if key_ttl and key_ttl > 0 then
    redis.call('EXPIRE', keys[1], key_ttl)
  end
  return 1
end)
-- mg_spec_granular_apply: atomic per-node/connection upsert + delete on the live spec.
-- Each node/connection patch is merged into its matching JSONPath element so that
-- two workers editing *different* nodes never overwrite each other.
-- KEYS[1] = live_spec_key  KEYS[2] = snapshot_seq_key
-- KEYS[3] = live_changed_keys_key  KEYS[4] = tombstones_key
-- ARGV[1] = ttl_sec  ARGV[2] = nodes_json  ARGV[3] = connections_json
-- ARGV[4] = deleted_node_ids_json  ARGV[5] = deleted_connection_ids_json
-- Returns {version, seq}.
redis.register_function('mg_spec_granular_apply', function(keys, args)
  local sk, seqk, ckk, tombk = keys[1], keys[2], keys[3], keys[4]
  local ttl = tonumber(args[1]) or 0
  local function jdec(s)
    if not s or s == '' then return {} end
    local ok, v = pcall(cjson.decode, s)
    return (ok and type(v) == 'table') and v or {}
  end
  local nodes, conns = jdec(args[2]), jdec(args[3])
  local dn, dc      = jdec(args[4]), jdec(args[5])
  local chn, chc = false, false
  for _, nid in ipairs(dn) do
    local s = tostring(nid)
    local q = cjson.encode(s)
    redis.call('JSON.DEL', sk, '$.nodes[?(@.id == '        .. q .. ')]')
    redis.call('JSON.DEL', sk, '$.connections[?(@.source == ' .. q .. ')]')
    redis.call('JSON.DEL', sk, '$.connections[?(@.target == ' .. q .. ')]')
    redis.call('SADD', tombk, s)
    chn, chc = true, true
  end
  if chn then redis.call('EXPIRE', tombk, 30) end
  for _, cid in ipairs(dc) do
    redis.call('JSON.DEL', sk, '$.connections[?(@.id == ' .. cjson.encode(tostring(cid)) .. ')]')
    chc = true
  end
  for _, p in ipairs(nodes) do
    local nid = p['id']
    if nid ~= nil then
      local s = tostring(nid)
      if redis.call('SISMEMBER', tombk, s) == 0 then
        if p['text'] ~= nil and type(p['data']) == 'table' then
          p['data']['label'] = tostring(p['text'])
        end
        local q  = cjson.encode(s)
        local fp = '$.nodes[?(@.id == ' .. q .. ')]'
        local pj = cjson.encode(p)
        local h  = redis.call('JSON.GET', sk, fp)
        if h and h ~= '[]' then
          redis.call('JSON.MERGE', sk, fp, pj)
        else
          redis.call('JSON.ARRAPPEND', sk, '$.nodes', pj)
        end
        chn = true
      end
    end
  end
  for _, p in ipairs(conns) do
    local cid = p['id']
    if cid ~= nil then
      local q  = cjson.encode(tostring(cid))
      local fp = '$.connections[?(@.id == ' .. q .. ')]'
      local pj = cjson.encode(p)
      local h  = redis.call('JSON.GET', sk, fp)
      if h and h ~= '[]' then
        redis.call('JSON.MERGE', sk, fp, pj)
      else
        redis.call('JSON.ARRAPPEND', sk, '$.connections', pj)
      end
      chc = true
    end
  end
  local new_v = 1
  local ok_i, raw = pcall(redis.call, 'JSON.NUMINCRBY', sk, '$.v', 1)
  if ok_i and raw then
    local ok_d, arr = pcall(cjson.decode, tostring(raw))
    if ok_d and type(arr) == 'table' and #arr > 0 then new_v = tonumber(arr[1]) or 1 end
  end
  local new_seq = redis.call('INCR', seqk)
  if chn then redis.call('SADD', ckk, 'nodes') end
  if chc then redis.call('SADD', ckk, 'connections') end
  if ttl > 0 then
    redis.call('EXPIRE', sk,   ttl)
    redis.call('EXPIRE', ckk,  ttl)
    redis.call('EXPIRE', seqk, ttl)
  end
  return {new_v, new_seq}
end)
-- mg_node_editing_del: remove one uid from JSON map; HDEL field only if empty.
-- KEYS[1] = hash key
-- ARGV[1] = field (node_id)
-- ARGV[2] = user_id to remove (string key in JSON object)
-- ARGV[3] = field TTL seconds (HEXPIRE) when field remains
-- ARGV[4] = key TTL seconds
-- Returns 1 on success.
redis.register_function('mg_node_editing_del', function(keys, args)
  local field = args[1]
  local uid = args[2]
  local field_ttl = tonumber(args[3])
  local key_ttl = tonumber(args[4])
  local raw = redis.call('HGET', keys[1], field)
  if not raw then
    if key_ttl and key_ttl > 0 then
      redis.call('EXPIRE', keys[1], key_ttl)
    end
    return 1
  end
  local dec_ok, parsed = pcall(cjson.decode, raw)
  if not dec_ok or type(parsed) ~= 'table' then
    redis.call('HDEL', keys[1], field)
  else
    parsed[uid] = nil
    if next(parsed) == nil then
      redis.call('HDEL', keys[1], field)
    else
      redis.call('HSET', keys[1], field, cjson.encode(parsed))
      if field_ttl and field_ttl > 0 then
        local hex_ok = pcall(redis.call, 'HEXPIRE', keys[1], field_ttl, 'FIELDS', 1, field)
        if not hex_ok then
          redis.call('EXPIRE', keys[1], field_ttl)
        end
      end
    end
  end
  if key_ttl and key_ttl > 0 then
    redis.call('EXPIRE', keys[1], key_ttl)
  end
  return 1
end)
"""

_FUNCTIONS_DISABLED_ENV = "COLLAB_DISABLE_REDIS_FUNCTIONS"
_FUNCTIONS_LOADED_CELL: list[bool | None] = [None]


def _functions_disabled_by_env() -> bool:
    return os.getenv(_FUNCTIONS_DISABLED_ENV, "0") not in ("0", "false", "False", "")


async def ensure_online_collab_functions_loaded(redis: Any) -> bool:
    """
    Best-effort ``FUNCTION LOAD REPLACE`` of the workshop lock library.

    Returns True on success, False when FUNCTION is unsupported (Redis <7.0)
    or explicitly disabled. The result is cached per-process so we load the
    library once regardless of how many locks we acquire.
    """
    cell = _FUNCTIONS_LOADED_CELL
    if _functions_disabled_by_env():
        cell[0] = False
        return False
    cached = cell[0]
    if cached is not None:
        return cached
    if not redis:
        return False
    try:
        await redis.execute_command(
            "FUNCTION", "LOAD", "REPLACE", _WORKSHOP_LIB_CODE,
        )
        cell[0] = True
        logger.info(
            "[WorkshopLocks] Redis Function library '%s' loaded",
            _WORKSHOP_LIB_NAME,
        )
        return True
    except RedisError as exc:
        cell[0] = False
        logger.info(
            "[WorkshopLocks] Redis FUNCTION LOAD unavailable (%s) — "
            "falling back to EVAL for CAS helpers",
            exc,
        )
        return False


def new_lock_token() -> str:
    """Return a fresh ownership token for a Redis NX lock."""
    return uuid.uuid4().hex


async def acquire_nx_lock(
    redis: Any,
    key: str,
    ttl_sec: int,
    token: Optional[str] = None,
) -> Optional[str]:
    """
    Attempt to acquire an NX lock with a per-caller token.

    Returns the token on success or None on failure. Callers keep the token
    and pass it to release_nx_lock for CAS-delete semantics.
    """
    if not redis:
        return None
    tok = token or new_lock_token()
    try:
        ok = bool(await redis.set(key, tok, nx=True, ex=int(ttl_sec)))
    except (RedisError, OSError, RuntimeError, TypeError) as exc:
        logger.warning("[WorkshopLocks] NX SET failed key=%s: %s", key, exc)
        return None
    return tok if ok else None


async def release_nx_lock(redis: Any, key: str, token: str) -> bool:
    """
    Release an NX lock only if the stored token still matches (CAS-delete).

    Uses the cached Redis Function ``mg_cas_delete`` when available; falls
    back to EVAL'd Lua otherwise. Never raises: all Redis errors are
    swallowed and logged at debug level.
    """
    if not redis or not token:
        return False
    use_fcall = await ensure_online_collab_functions_loaded(redis)
    try:
        if use_fcall:
            result = await redis.execute_command(
                "FCALL", "mg_cas_delete", 1, key, token,
            )
        else:
            result = await redis.eval(_CAS_DELETE_LUA, 1, key, token)
    except RedisError as exc:
        msg = str(exc).lower()
        if use_fcall and (
            "function not found" in msg or "unknown command" in msg
        ):
            _FUNCTIONS_LOADED_CELL[0] = False
            try:
                result = await redis.eval(_CAS_DELETE_LUA, 1, key, token)
            except (RedisError, OSError, RuntimeError, TypeError) as eval_exc:
                logger.debug(
                    "[WorkshopLocks] CAS-delete fallback failed key=%s: %s",
                    key, eval_exc,
                )
                return False
        else:
            logger.debug(
                "[WorkshopLocks] CAS-delete failed key=%s: %s", key, exc,
            )
            return False
    except (OSError, RuntimeError, TypeError) as exc:
        logger.debug("[WorkshopLocks] CAS-delete failed key=%s: %s", key, exc)
        return False
    try:
        return int(result) == 1
    except (TypeError, ValueError):
        return False


async def extend_nx_lock(
    redis: Any,
    key: str,
    token: str,
    ttl_sec: int,
) -> bool:
    """Extend the TTL of an NX lock if the stored token still matches."""
    if not redis or not token:
        return False
    use_fcall = await ensure_online_collab_functions_loaded(redis)
    try:
        if use_fcall:
            result = await redis.execute_command(
                "FCALL", "mg_cas_extend", 1, key, token, int(ttl_sec),
            )
        else:
            result = await redis.eval(
                _CAS_EXTEND_LUA, 1, key, token, int(ttl_sec),
            )
    except RedisError as exc:
        msg = str(exc).lower()
        if use_fcall and (
            "function not found" in msg or "unknown command" in msg
        ):
            _FUNCTIONS_LOADED_CELL[0] = False
            try:
                result = await redis.eval(
                    _CAS_EXTEND_LUA, 1, key, token, int(ttl_sec),
                )
            except (RedisError, OSError, RuntimeError, TypeError) as eval_exc:
                logger.debug(
                    "[WorkshopLocks] CAS-extend fallback failed key=%s: %s",
                    key, eval_exc,
                )
                return False
        else:
            logger.debug(
                "[WorkshopLocks] CAS-extend failed key=%s: %s", key, exc,
            )
            return False
    except (OSError, RuntimeError, TypeError) as exc:
        logger.debug("[WorkshopLocks] CAS-extend failed key=%s: %s", key, exc)
        return False
    try:
        return int(result) == 1
    except (TypeError, ValueError):
        return False


async def fcall_node_claim_exclusive(
    redis: Any,
    hash_key: str,
    field: str,
    user_id_str: str,
    username: str,
    field_ttl_sec: int,
    key_ttl_sec: int,
) -> Optional[bool]:
    """
    Atomically claim exclusive edit ownership of a node via ``mg_node_claim_exclusive``.

    Returns True  — claim granted (node was free or already held by this user).
    Returns False — claim denied (another user is editing this node).
    Returns None  — FCALL not available; caller must fall back to read-check-write.
    """
    use_fcall = await ensure_online_collab_functions_loaded(redis)
    if not use_fcall:
        return None
    try:
        result = await redis.execute_command(
            "FCALL", "mg_node_claim_exclusive", 1,
            hash_key, field, user_id_str, username,
            int(field_ttl_sec), int(key_ttl_sec),
        )
        return int(result) == 1
    except RedisError as exc:
        msg = str(exc).lower()
        if "function not found" in msg or "unknown command" in msg:
            _FUNCTIONS_LOADED_CELL[0] = False
        logger.debug("[WorkshopLocks] mg_node_claim_exclusive failed: %s", exc)
        return None


async def fcall_node_editing_set(
    redis: Any,
    hash_key: str,
    field: str,
    user_id_str: str,
    username: str,
    field_ttl_sec: int,
    key_ttl_sec: int,
) -> bool:
    """
    Atomically merge editor into HASH field + HEXPIRE (field TTL) + key EXPIRE
    via ``mg_node_editing_set`` Redis Function.

    Returns True on success; False on any error or when Functions are not
    available (callers should fall back to the multi-RTT HSET path).
    """
    use_fcall = await ensure_online_collab_functions_loaded(redis)
    if not use_fcall:
        return False
    try:
        await redis.execute_command(
            "FCALL", "mg_node_editing_set", 1,
            hash_key, field, user_id_str, username,
            int(field_ttl_sec), int(key_ttl_sec),
        )
        return True
    except RedisError as exc:
        msg = str(exc).lower()
        if "function not found" in msg or "unknown command" in msg:
            _FUNCTIONS_LOADED_CELL[0] = False
        logger.debug("[WorkshopLocks] mg_node_editing_set failed: %s", exc)
        return False


async def fcall_node_editing_del(
    redis: Any,
    hash_key: str,
    field: str,
    user_id_str: str,
    field_ttl_sec: int,
    key_ttl_sec: int,
) -> bool:
    """
    Atomically remove one editor from HASH field JSON + key EXPIRE
    via ``mg_node_editing_del`` Redis Function.

    Returns True on success; False on any error or when Functions are not
    available.
    """
    use_fcall = await ensure_online_collab_functions_loaded(redis)
    if not use_fcall:
        return False
    try:
        await redis.execute_command(
            "FCALL", "mg_node_editing_del", 1,
            hash_key, field, user_id_str,
            int(field_ttl_sec), int(key_ttl_sec),
        )
        return True
    except RedisError as exc:
        msg = str(exc).lower()
        if "function not found" in msg or "unknown command" in msg:
            _FUNCTIONS_LOADED_CELL[0] = False
        logger.debug("[WorkshopLocks] mg_node_editing_del failed: %s", exc)
        return False


_WRITE_LOCK_TTL_SEC = 5
_WRITE_LOCK_RETRY_SLEEP_SEC = 0.05


async def acquire_room_write_lock(
    redis: Any,
    code: str,
    user_id: int,
    ttl_sec: int = _WRITE_LOCK_TTL_SEC,
) -> Optional[str]:
    """
    Try to acquire the room-level write lock for ``user_id``.

    The token stored in Redis encodes ``user_id`` for introspection without a
    separate lookup.  Returns the token on success, or ``None`` when another
    user is still holding the lock after one retry.  The retry window is
    intentionally short (50 ms) so hot-path latency is unaffected when the
    room is uncontested; it only helps serialise two workers that race for the
    same room within the same network round-trip window.
    """
    if not redis:
        return None
    key = live_write_lock_key(code)
    token = f"{user_id}:{uuid.uuid4().hex}"
    for attempt in range(2):
        try:
            ok = bool(await redis.set(key, token, nx=True, ex=int(ttl_sec)))
            if ok:
                return token
            if attempt == 0:
                await asyncio.sleep(_WRITE_LOCK_RETRY_SLEEP_SEC)
        except (RedisError, OSError, RuntimeError, TypeError) as exc:
            logger.debug(
                "[WorkshopLocks] write-lock acquire failed code=%s: %s", code, exc,
            )
            return None
    return None


async def release_room_write_lock(
    redis: Any,
    code: str,
    token: str,
) -> bool:
    """CAS-delete the room write lock; only succeeds when the stored token matches."""
    return await release_nx_lock(redis, live_write_lock_key(code), token)


async def fcall_spec_granular_apply(
    redis: Any,
    code: str,
    ttl_sec: int,
    nodes: Optional[List[Dict[str, Any]]],
    connections: Optional[List[Dict[str, Any]]],
    deleted_node_ids: Optional[List[str]],
    deleted_connection_ids: Optional[List[str]],
) -> Optional[Tuple[int, int]]:
    """
    FCALL mg_spec_granular_apply: atomic per-node/connection upsert + delete
    on the live spec key, returning ``(version, seq)``.

    Each node/connection patch is applied via ``JSON.MERGE`` at the matching
    JSONPath so two workers editing different nodes never overwrite each other.
    Returns ``None`` when FCALL is unavailable or the call fails; callers must
    fall back to the Python read-modify-write path in that case.
    """
    use_fcall = await ensure_online_collab_functions_loaded(redis)
    if not use_fcall:
        return None
    nodes_json = json.dumps(nodes or [], ensure_ascii=False)
    conns_json = json.dumps(connections or [], ensure_ascii=False)
    del_nodes_json = json.dumps(deleted_node_ids or [], ensure_ascii=False)
    del_conns_json = json.dumps(deleted_connection_ids or [], ensure_ascii=False)
    try:
        result = await redis.execute_command(
            "FCALL", "mg_spec_granular_apply", 4,
            live_spec_key(code),
            snapshot_seq_key(code),
            live_changed_keys_key(code),
            tombstones_key(code),
            int(ttl_sec),
            nodes_json,
            conns_json,
            del_nodes_json,
            del_conns_json,
        )
    except RedisError as exc:
        msg = str(exc).lower()
        if "function not found" in msg or "unknown command" in msg:
            _FUNCTIONS_LOADED_CELL[0] = False
        logger.debug(
            "[WorkshopLocks] mg_spec_granular_apply failed code=%s: %s", code, exc,
        )
        return None
    except (OSError, RuntimeError, TypeError) as exc:
        logger.debug(
            "[WorkshopLocks] mg_spec_granular_apply error code=%s: %s", code, exc,
        )
        return None
    if not isinstance(result, (list, tuple)) or len(result) < 2:
        return None
    try:
        return (int(result[0]), int(result[1]))
    except (TypeError, ValueError):
        return None
