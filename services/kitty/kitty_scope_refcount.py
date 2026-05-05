"""Global Kitty WebSocket refcount in Redis (multi-worker safe, same hash slot as session keys)."""

from __future__ import annotations

import asyncio
import logging
import os
from enum import IntEnum
from typing import Any, Dict, Optional

from redis.exceptions import NoScriptError, RedisError

from services.kitty.kitty_redis_keys import (
    kitty_live_spec_key,
    kitty_refcount_ttl_seconds,
    kitty_scope_owner_key,
    kitty_sessionmeta_key,
    kitty_ws_refcount_key,
)
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_LUA_ATTACH = """
local n = redis.call('INCR', KEYS[1])
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
return n
"""

_LUA_DETACH = """
local ttl = tonumber(ARGV[1])
local uid = ARGV[2]
local n = redis.call('DECR', KEYS[1])
if n < 0 then
  redis.call('SET', KEYS[1], 0)
  n = 0
end
if n > 0 then
  redis.call('EXPIRE', KEYS[1], ttl)
  return n
end
local own = redis.call('GET', KEYS[4])
if (not own) or (tostring(own) ~= uid) then
  redis.call('INCR', KEYS[1])
  redis.call('EXPIRE', KEYS[1], ttl)
  return -2
end
redis.call('DEL', KEYS[2], KEYS[3], KEYS[4], KEYS[1])
return 0
"""

_LUA_FORCE_TEARDOWN = """
local uid = ARGV[1]
local own = redis.call('GET', KEYS[4])
if (not own) or (tostring(own) ~= uid) then
  return 0
end
redis.call('DEL', KEYS[1], KEYS[2], KEYS[3], KEYS[4])
return 1
"""

_SCRIPT_NAMES = ("attach", "detach", "force")
_lua_shas: Dict[str, Optional[str]] = {name: None for name in _SCRIPT_NAMES}
_lua_load_lock = asyncio.Lock()


def _refcount_evalsha_enabled() -> bool:
    raw = os.getenv("KITTY_REFCOUNT_USE_EVALSHA", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _normalize_sha(loaded: Any) -> str:
    if isinstance(loaded, bytes):
        return loaded.decode("utf-8")
    return str(loaded)


async def _eval_with_optional_sha(
    redis: Any,
    which: str,
    lua: str,
    numkeys: int,
    *keys_and_args: Any,
) -> Any:
    """EVAL or EVALSHA (cached per process) with automatic reload after ``NOSCRIPT``."""
    if not _refcount_evalsha_enabled():
        return await redis.eval(lua, numkeys, *keys_and_args)
    async with _lua_load_lock:
        sha = _lua_shas.get(which)
        if not sha:
            loaded = await redis.script_load(lua)
            sha = _normalize_sha(loaded)
            _lua_shas[which] = sha
    try:
        return await redis.evalsha(sha, numkeys, *keys_and_args)
    except NoScriptError:
        async with _lua_load_lock:
            loaded = await redis.script_load(lua)
            sha = _normalize_sha(loaded)
            _lua_shas[which] = sha
        return await redis.evalsha(sha, numkeys, *keys_and_args)


class KittyDetachResult(IntEnum):
    """Result of refcount detach Lua."""

    KEYS_REMOVED = 0
    OWNER_MISMATCH_ROLLBACK = -2


async def kitty_scope_refcount_attach(scope: str) -> Optional[int]:
    """INCR global refcount for ``scope``; refresh TTL. Returns new count or ``None`` if no Redis."""
    redis = get_async_redis()
    if redis is None:
        return None
    rk = kitty_ws_refcount_key(scope)
    ttl = kitty_refcount_ttl_seconds()
    try:
        raw = await _eval_with_optional_sha(redis, "attach", _LUA_ATTACH, 1, rk, str(ttl))
        if raw is None:
            return None
        return int(raw)
    except (RedisError, TypeError, ValueError) as exc:
        logger.warning("[KittyRefcount] attach failed scope=%s: %s", scope, exc)
        return None


async def kitty_scope_refcount_detach(scope: str, user_id: int) -> Optional[int]:
    """
    DECR refcount; atomically remove sessionmeta, live_spec, owner when count hits 0.

    Returns:
        New refcount if > 0,
        ``KittyDetachResult.KEYS_REMOVED`` (0) when meta/live removed,
        ``KittyDetachResult.OWNER_MISMATCH_ROLLBACK`` (-2) on owner mismatch,
        ``None`` on Redis error / missing client.
    """
    redis = get_async_redis()
    if redis is None:
        return None
    rk = kitty_ws_refcount_key(scope)
    mk = kitty_sessionmeta_key(scope)
    lk = kitty_live_spec_key(scope)
    ok = kitty_scope_owner_key(scope)
    ttl = kitty_refcount_ttl_seconds()
    uid_arg = str(int(user_id))
    try:
        raw = await _eval_with_optional_sha(
            redis,
            "detach",
            _LUA_DETACH,
            4,
            rk,
            mk,
            lk,
            ok,
            str(ttl),
            uid_arg,
        )
        if raw is None:
            return None
        return int(raw)
    except (RedisError, TypeError, ValueError) as exc:
        logger.warning("[KittyRefcount] detach failed scope=%s: %s", scope, exc)
        return None


async def kitty_scope_force_teardown_redis(scope: str, user_id: int) -> bool:
    """Delete refcount + meta + live + owner when ``scope_owner`` matches ``user_id`` (HTTP stale cleanup)."""
    redis = get_async_redis()
    if redis is None:
        return False
    rk = kitty_ws_refcount_key(scope)
    mk = kitty_sessionmeta_key(scope)
    lk = kitty_live_spec_key(scope)
    ok = kitty_scope_owner_key(scope)
    uid_arg = str(int(user_id))
    try:
        raw = await _eval_with_optional_sha(
            redis,
            "force",
            _LUA_FORCE_TEARDOWN,
            4,
            rk,
            mk,
            lk,
            ok,
            uid_arg,
        )
        return bool(raw and int(raw) == 1)
    except (RedisError, TypeError, ValueError) as exc:
        logger.debug("[KittyRefcount] force teardown failed scope=%s: %s", scope, exc)
        return False


async def kitty_scope_refcount_read(scope: str) -> Optional[int]:
    """Read refcount or ``None`` if missing / error."""
    redis = get_async_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(kitty_ws_refcount_key(scope))
        if raw is None:
            return None
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        return int(text, 10)
    except (RedisError, TypeError, ValueError) as exc:
        logger.debug("[KittyRefcount] read failed scope=%s: %s", scope, exc)
        return None
