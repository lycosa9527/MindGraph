"""
Pre-loaded Lua scripts for the online-collab hot path.

Strategy
--------
* ``load_scripts(redis)`` is called once per worker at startup via the FastAPI
  lifespan.  It runs ``SCRIPT LOAD`` for every registered script and caches the
  40-character SHA-1 in a module-level dict.
* ``evalsha_with_reload(redis, name, numkeys, *args)`` issues ``EVALSHA``; on
  ``NOSCRIPT`` (script evicted from Redis memory) it reloads the script
  transparently and retries — callers never need to handle that edge case.
* Both hot scripts (join cap-check and combined rate-limiter) are registered
  here so that ``online_collab_manager.py`` and ``online_collab_ws_rate_limit.py``
  share one authoritative source of truth for the Lua text.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from redis.exceptions import RedisError, ResponseError

from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lua script registry
# ---------------------------------------------------------------------------

JOIN_CAP_SCRIPT_NAME = "collab_join_cap"
RATE_LIMIT_SCRIPT_NAME = "collab_rate_limit"

_SCRIPTS: Dict[str, str] = {
    # Atomically check participant cap, (re-)register the user, and set HEXPIRE.
    # KEYS[1] = participants hash key
    # ARGV[1] = str(user_id)   ARGV[2] = str(max_cap)
    # ARGV[3] = str(ttl_sec)   ARGV[4] = str(now_unix)
    # Returns: 1 = already in (re-joined), 0 = newly added, -1 = room full
    JOIN_CAP_SCRIPT_NAME: """
local key    = KEYS[1]
local member = ARGV[1]
local cap    = tonumber(ARGV[2])
local ttl    = tonumber(ARGV[3])
local now    = ARGV[4]
if redis.call('HEXISTS', key, member) == 1 then
  local ok = pcall(redis.call, 'HEXPIRE', key, ttl, 'FIELDS', 1, member)
  if not ok then redis.call('EXPIRE', key, ttl) end
  return 1
end
if redis.call('HLEN', key) >= cap then
  return -1
end
redis.call('HSET', key, member, now)
local ok = pcall(redis.call, 'HEXPIRE', key, ttl, 'FIELDS', 1, member)
if not ok then redis.call('EXPIRE', key, ttl) end
return 0
""",

    # Combined sliding-window rate-limiter: checks user bucket and IP bucket in
    # a single round-trip.  Returns a two-element array [user_ok, ip_ok] where
    # each element is 1 (allowed) or 0 (limited).  We always record the attempt
    # in both buckets regardless of the outcome so counts stay accurate.
    # KEYS[1] = user rate key   KEYS[2] = IP rate key
    # ARGV[1] = str(now_float)  ARGV[2] = str(window_start_float)
    # ARGV[3] = str(user_cap)   ARGV[4] = str(ip_cap)
    # ARGV[5] = str(window_sec)
    #
    # Member uniqueness: we use redis.call('TIME') to produce a microsecond-
    # resolution member string so two requests arriving in the same millisecond
    # do not collapse into one ZSET entry (which would under-count the window).
    RATE_LIMIT_SCRIPT_NAME: """
local function check_bucket(key, now, win_start, cap, window_sec)
  local t = redis.call('TIME')
  local uniq = t[1] .. '.' .. t[2]
  redis.call('ZREMRANGEBYSCORE', key, 0, win_start)
  redis.call('ZADD', key, now, uniq)
  local cnt = redis.call('ZCARD', key)
  redis.call('EXPIRE', key, window_sec)
  if cnt > cap then return 0, cnt end
  return 1, cnt
end
local u_ok, u_cnt = check_bucket(KEYS[1], tonumber(ARGV[1]),
  tonumber(ARGV[2]), tonumber(ARGV[3]), tonumber(ARGV[5]))
local i_ok, i_cnt = check_bucket(KEYS[2], tonumber(ARGV[1]),
  tonumber(ARGV[2]), tonumber(ARGV[4]), tonumber(ARGV[5]))
return {u_ok, u_cnt, i_ok, i_cnt}
""",
}

# SHA cache: populated by load_scripts(); empty until then.
_SHA: Dict[str, str] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def load_scripts_if_available() -> None:
    """
    Convenience wrapper: resolve the async Redis client from the module-level
    singleton and call ``load_scripts``.  Designed for use in FastAPI lifespan
    handlers where the client is always available but the caller should not have
    to import it.  Silently returns when the client is not yet initialised.
    """
    try:
        redis = get_async_redis()
        if redis:
            await load_scripts(redis)
    except (RedisError, OSError, RuntimeError, TypeError, ImportError) as exc:
        logger.warning("[CollabScripts] load_scripts_if_available failed: %s", exc)


async def load_scripts(redis: Any) -> None:
    """
    SCRIPT LOAD every registered Lua script at worker startup.

    Safe to call multiple times — existing SHAs are simply overwritten with
    the same value.  Failures are logged but do not abort startup; call sites
    fall back to plain EVAL when the SHA dict is empty.
    """
    for name, body in _SCRIPTS.items():
        try:
            sha = await redis.script_load(body)
            _SHA[name] = sha
            logger.info("[CollabScripts] Loaded %s sha=%s…", name, sha[:8])
        except (RedisError, OSError, AttributeError) as exc:
            logger.warning(
                "[CollabScripts] SCRIPT LOAD failed for %s (will fall back to EVAL): %s",
                name,
                exc,
            )


async def evalsha_with_reload(
    redis: Any,
    name: str,
    numkeys: int,
    *args: Any,
) -> Any:
    """
    Run a cached Lua script via EVALSHA with transparent NOSCRIPT recovery.

    If the SHA is not yet loaded (startup race) or has been evicted from Redis
    (``NOSCRIPT`` error), the script is reloaded on the fly and retried once.
    Raises ``RedisError`` on all other Redis errors so callers can decide how to
    handle failures.
    """
    script_body = _SCRIPTS.get(name)
    if script_body is None:
        raise KeyError(f"[CollabScripts] Unknown script name: {name!r}")

    sha = _SHA.get(name)

    async def _eval_fallback() -> Any:
        return await redis.eval(script_body, numkeys, *args)

    if not sha:
        return await _eval_fallback()

    try:
        return await redis.evalsha(sha, numkeys, *args)
    except ResponseError as exc:
        if "NOSCRIPT" not in str(exc):
            raise
        logger.warning("[CollabScripts] NOSCRIPT for %s — reloading", name)
        try:
            sha = await redis.script_load(script_body)
            _SHA[name] = sha
            return await redis.evalsha(sha, numkeys, *args)
        except (RedisError, OSError) as reload_exc:
            logger.error(
                "[CollabScripts] Reload failed for %s, using EVAL: %s", name, reload_exc
            )
            return await _eval_fallback()
