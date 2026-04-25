"""
Redis storage for ephemeral quick-registration channel tokens.

Tokens are server-minted opaque strings bound to an organization.
Single-use: removed after successful registration or explicit close.

Copyright 2024-2026 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import secrets
from datetime import UTC, datetime
from typing import Any, Optional, Tuple

from redis.exceptions import RedisError

from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

QUICK_REG_KEY_PREFIX = "quick_reg:"
MINTER_INDEX_PREFIX = "quick_reg:minter:"
WORKSHOP_USAGE_PREFIX = "quick_reg:ws_usage:"
# JSON field: per-mint HMAC key material for 6-digit room code (not from env).
ROOM_CODE_SECRET_FIELD = "room_code_secret"
DEFAULT_TTL_SECONDS = 3600
WORKSHOP_DEFAULT_MAX_USES = 500
WORKSHOP_MAX_USES_CAP = 2000
_DELETE_RETRIES = 3
_DELETE_BACKOFF_BASE = 0.05

_LUA_RESERVE_WORKSHOP = """
local token_key = KEYS[1]
local usage_key = KEYS[2]
local max_uses = tonumber(ARGV[1])
if redis.call('EXISTS', token_key) == 0 then
  return {-1, 0}
end
local n = redis.call('INCR', usage_key)
if n > max_uses then
  redis.call('DECR', usage_key)
  return {0, 0}
end
local tttl = redis.call('TTL', token_key)
if tttl and tttl > 0 then
  redis.call('EXPIRE', usage_key, tttl)
end
return {1, n}
"""

_LUA_INCR_WITH_TTL = """
local n = redis.call('INCR', KEYS[1])
local t = redis.call('TTL', KEYS[1])
if t == -1 then
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
return n
"""

_LUA_CAS_DEL = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  redis.call('DEL', KEYS[1])
  return 1
end
return 0
"""

_LUA_DECR_CLEANUP = """
local n = redis.call('DECR', KEYS[1])
if tonumber(n) < 0 then
  redis.call('DEL', KEYS[1])
  return 0
end
return n
"""


def _key(token: str) -> str:
    return f"{QUICK_REG_KEY_PREFIX}{token}"


def _minter_key(user_id: int) -> str:
    return f"{MINTER_INDEX_PREFIX}{int(user_id)}"


def parse_organization_id_from_stored_value(data: object) -> Optional[int]:
    """
    Return organization_id from Redis JSON, or None if shape is invalid.
    Rejects non-dict payloads and non-positive org ids.
    """
    if not isinstance(data, dict):
        return None
    raw = data.get("organization_id")
    if raw is None:
        return None
    try:
        org_id = int(raw)
    except (TypeError, ValueError):
        return None
    if org_id <= 0:
        return None
    return org_id


def parse_channel_type(data: object) -> str:
    """Return 'workshop' or 'single_use' (default for legacy tokens)."""
    if not isinstance(data, dict):
        return "single_use"
    if data.get("channel_type") == "workshop":
        return "workshop"
    return "single_use"


def effective_workshop_max_uses(data: object) -> int:
    """
    Return max signups for a workshop token. Legacy/missing: WORKSHOP_DEFAULT_MAX_USES.
    Capped at WORKSHOP_MAX_USES_CAP.
    """
    if not isinstance(data, dict):
        return WORKSHOP_DEFAULT_MAX_USES
    raw = data.get("max_uses")
    if raw is None:
        n = WORKSHOP_DEFAULT_MAX_USES
    else:
        try:
            n = int(raw)
        except (TypeError, ValueError):
            n = WORKSHOP_DEFAULT_MAX_USES
    n = max(n, 1)
    return min(n, WORKSHOP_MAX_USES_CAP)


def workshop_usage_key(token: str) -> str:
    """Stable short Redis key for per-token workshop usage counter."""
    h = hashlib.sha256(token.encode("utf-8")).hexdigest()[:40]
    return f"{WORKSHOP_USAGE_PREFIX}{h}"


async def workshop_reserve_or_fail(
    token: str,
    max_uses: int,
) -> Tuple[str, int]:
    """
    Atomically reserve one workshop slot. Returns (status, n_after).
    status: 'ok' | 'full' | 'no_token' | 'redis_error'
    """
    redis = get_async_redis()
    tkey = _key(token)
    ukey = workshop_usage_key(token)
    try:
        result = await redis.eval(_LUA_RESERVE_WORKSHOP, 2, tkey, ukey, str(int(max_uses)))
        if not result or len(result) < 2:
            return "redis_error", 0
        a = int(result[0])
        b = int(result[1])
        if a < 0:
            return "no_token", 0
        if a == 0:
            return "full", 0
        return "ok", b
    except RedisError as exc:
        logger.warning("[QuickReg] workshop reserve failed: %s", exc)
        return "redis_error", 0


async def workshop_release_reservation(
    token: str,
) -> None:
    """Decrement usage after a failed commit (reservation must be released).

    Uses an atomic Lua script so the DECR and conditional DELETE are never split
    by a crash or a concurrent writer.
    """
    redis = get_async_redis()
    ukey = workshop_usage_key(token)
    try:
        await redis.eval(_LUA_DECR_CLEANUP, 1, ukey)
    except RedisError as exc:
        logger.debug("[QuickReg] workshop release decr: %s", exc)


async def get_workshop_usage_count(token: str) -> int:
    """Current workshop INCR value for the token (0 if key missing)."""
    redis = get_async_redis()
    ukey = workshop_usage_key(token)
    try:
        raw = await redis.get(ukey)
    except RedisError as exc:
        logger.debug("[QuickReg] usage count get: %s", exc)
        return 0
    if raw is None:
        return 0
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    try:
        return int(str(raw).strip() or 0)
    except (TypeError, ValueError):
        return 0


async def refresh_workshop_channel_ttl(
    token: str,
    minter_user_id: int,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    """Extend token, minter index, and usage key TTL (active workshop).

    All three EXPIRE commands are batched in a single pipeline round-trip.
    EXPIRE on a missing key is a no-op in Redis so no pre-check is needed.
    """
    redis = get_async_redis()
    tkey = _key(token)
    ukey = workshop_usage_key(token)
    try:
        async with redis.pipeline(transaction=False) as pipe:
            pipe.expire(tkey, ttl_seconds)
            if int(minter_user_id) > 0:
                pipe.expire(_minter_key(int(minter_user_id)), ttl_seconds)
            pipe.expire(ukey, ttl_seconds)
            await pipe.execute()
    except RedisError as exc:
        logger.debug("[QuickReg] refresh workshop TTL: %s", exc)


async def get_minter_token(user_id: int) -> Optional[str]:
    """Return the token string last minted for this user, or None."""
    redis = get_async_redis()
    try:
        raw = await redis.get(_minter_key(user_id))
        if not raw:
            return None
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        return str(raw)
    except RedisError as exc:
        logger.warning("[QuickReg] Redis get minter index failed: %s", exc)
        return None


async def set_minter_token(user_id: int, token: str, ttl_seconds: int) -> bool:
    """Point minter index at the current open-channel token (same TTL as the token)."""
    redis = get_async_redis()
    try:
        await redis.set(_minter_key(user_id), token, ex=ttl_seconds)
        return True
    except RedisError as exc:
        logger.warning("[QuickReg] Redis set minter index failed: %s", exc)
        return False


async def clear_minter_index_if_token_matches(user_id: int, token: str) -> None:
    """Remove minter index when it still points at this token (e.g. after close).

    Uses an atomic Lua compare-and-delete so no other writer can slip in between
    the GET check and the DEL that a plain Python GET+DEL sequence would allow.
    """
    redis = get_async_redis()
    key = _minter_key(user_id)
    try:
        await redis.eval(_LUA_CAS_DEL, 1, key, token)
    except RedisError as exc:
        logger.debug("[QuickReg] clear minter index non-fatal: %s", exc)


async def revoke_previous_minted_token_for_user(user_id: int) -> None:
    """Delete the previous quick_reg token for this minter, if any (one active channel)."""
    old = await get_minter_token(user_id)
    if not old:
        return
    await delete_token(old)


async def store_token(
    token: str,
    organization_id: int,
    created_by_user_id: int,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    channel_type: str = "single_use",
    max_uses: Optional[int] = None,
) -> bool:
    """Persist token metadata in Redis with TTL. Returns False on connection/command failure."""
    redis = get_async_redis()
    payload: dict[str, Any] = {
        "organization_id": organization_id,
        "created_by_user_id": created_by_user_id,
        "created_at": datetime.now(tz=UTC).isoformat(),
        "channel_type": channel_type,
        ROOM_CODE_SECRET_FIELD: secrets.token_urlsafe(32),
    }
    if channel_type == "workshop" and max_uses is not None:
        payload["max_uses"] = int(max_uses)
    try:
        await redis.set(_key(token), json.dumps(payload), ex=ttl_seconds)
        return True
    except RedisError as exc:
        logger.warning("[QuickReg] Redis set failed: %s", exc)
        return False


async def get_token_data(token: str) -> Optional[dict[str, Any]]:
    """
    Return parsed token payload or None if missing/invalid.

    Legacy keys without room_code_secret are upgraded on read (SET with
    remaining TTL) so existing channels keep working after deploy.
    """
    redis = get_async_redis()
    key = _key(token)
    try:
        raw = await redis.get(key)
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None
        sec_raw = parsed.get(ROOM_CODE_SECRET_FIELD)
        if not (isinstance(sec_raw, str) and sec_raw.strip()):
            parsed[ROOM_CODE_SECRET_FIELD] = secrets.token_urlsafe(32)
            try:
                ttl = await redis.ttl(key)
            except RedisError as exc:
                logger.warning("[QuickReg] Redis ttl for migration: %s", exc)
                return None
            if ttl is None or ttl < 0 or int(ttl) == -1:
                ex = DEFAULT_TTL_SECONDS
            else:
                ex = int(ttl)
            if ex < 1:
                ex = DEFAULT_TTL_SECONDS
            try:
                await redis.set(key, json.dumps(parsed), ex=ex)
            except RedisError as exc:
                logger.warning("[QuickReg] room_code_secret migration set failed: %s", exc)
                return None
        return parsed
    except (RedisError, json.JSONDecodeError, TypeError, ValueError, OSError) as exc:
        logger.warning("[QuickReg] Redis get/migrate failed: %s", exc)
        return None


async def delete_token(token: str) -> bool:
    """Delete token key and workshop usage auxiliary key. Idempotent."""
    redis = get_async_redis()
    try:
        await redis.delete(_key(token), workshop_usage_key(token))
        return True
    except RedisError as exc:
        logger.warning("[QuickReg] Redis delete failed: %s", exc)
        return False


async def delete_token_with_retries(token: str) -> bool:
    """Delete quick_reg key with small exponential backoff on failure."""
    for attempt in range(_DELETE_RETRIES):
        if await delete_token(token):
            return True
        if attempt < _DELETE_RETRIES - 1:
            delay = _DELETE_BACKOFF_BASE * (2**attempt)
            await asyncio.sleep(delay)
    return False


ROOM_CODE_GUESS_IP_PREFIX = "quick_reg:rcg:ip:"
ROOM_CODE_GUESS_BIND_PREFIX = "quick_reg:rcg:bind:"
ROOM_CODE_GUESS_TTL_SEC = 600
ROOM_CODE_GUESS_MAX_PER_IP = 30
ROOM_CODE_GUESS_MAX_PER_BIND = 40


def _ip_bucket_32(client_ip: str) -> str:
    return hashlib.sha256(
        client_ip.encode("utf-8", errors="replace")
    ).hexdigest()[:32]


def _token_print_16(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8", errors="replace")
    ).hexdigest()[:16]


def _room_guess_ip_key(client_ip: str) -> str:
    return f"{ROOM_CODE_GUESS_IP_PREFIX}{_ip_bucket_32(client_ip)}"


def _room_guess_bind_key(client_ip: str, token: str) -> str:
    return (
        f"{ROOM_CODE_GUESS_BIND_PREFIX}{_ip_bucket_32(client_ip)}:"
        f"{_token_print_16(token)}"
    )


def _redis_count_from_raw(raw: object) -> int:
    if raw is None:
        return 0
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    try:
        return int(str(raw).strip() or 0)
    except (TypeError, ValueError):
        return 0


async def _incr_with_ttl(key: str, ttl_sec: int) -> int:
    """Atomically increment a counter and guarantee a TTL via a Lua script.

    A plain INCR followed by EXPIRE is not atomic: if the process crashes between
    the two commands the key persists forever.  The Lua script runs atomically on
    the Redis server so INCR and the conditional EXPIRE can never be split.
    """
    redis = get_async_redis()
    return int(await redis.eval(_LUA_INCR_WITH_TTL, 1, key, str(ttl_sec)))


async def is_room_code_guess_blocked(client_ip: str, token: str) -> bool:
    """
    True if the client has exceeded HMAC-miss rate limits (per IP, per IP+token).
    Fails open if Redis is unavailable (availability over strict abuse cap).
    """
    redis = get_async_redis()
    ikey = _room_guess_ip_key(client_ip)
    bkey = _room_guess_bind_key(client_ip, token)
    try:
        raw_ip, raw_bind = await redis.mget(ikey, bkey)
    except RedisError as exc:
        logger.warning("[QuickReg] room guess mget: %s", exc)
        return False
    n_ip = _redis_count_from_raw(raw_ip)
    n_b = _redis_count_from_raw(raw_bind)
    return n_ip >= ROOM_CODE_GUESS_MAX_PER_IP or n_b >= ROOM_CODE_GUESS_MAX_PER_BIND


async def record_room_code_guess_failure(client_ip: str, token: str) -> None:
    """Count a failed 6-digit HMAC (wrong or expired) attempt.

    Both counter increments are dispatched in a single pipeline round-trip.
    Each uses the atomic Lua INCR-with-TTL script so neither counter can lose
    its expiry under concurrent load or partial failures.
    """
    ikey = _room_guess_ip_key(client_ip)
    bkey = _room_guess_bind_key(client_ip, token)
    try:
        redis = get_async_redis()
        ttl_str = str(ROOM_CODE_GUESS_TTL_SEC)
        async with redis.pipeline(transaction=False) as pipe:
            pipe.eval(_LUA_INCR_WITH_TTL, 1, ikey, ttl_str)
            pipe.eval(_LUA_INCR_WITH_TTL, 1, bkey, ttl_str)
            await pipe.execute()
    except RedisError as exc:
        logger.warning("[QuickReg] room guess incr: %s", exc)


async def clear_room_code_guess_failures(client_ip: str, token: str) -> None:
    """Reset guess counters after a successful registration (valid room code + success)."""
    redis = get_async_redis()
    ikey = _room_guess_ip_key(client_ip)
    bkey = _room_guess_bind_key(client_ip, token)
    try:
        await redis.delete(ikey, bkey)
    except RedisError as exc:
        logger.debug("[QuickReg] room guess clear non-fatal: %s", exc)
