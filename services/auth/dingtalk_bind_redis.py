"""Redis storage for ephemeral DingTalk bind QR tokens."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from typing import Any, Awaitable, Optional, cast

from redis.exceptions import RedisError

from services.auth.dingtalk_bind_constants import (
    BIND_CODE_SECRET_FIELD,
    BIND_CONSUMED_PREFIX,
    BIND_MINTER_PREFIX,
    BIND_TOKEN_KEY_PREFIX,
    BIND_TOKEN_TTL_SECONDS,
)
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_BIND_CODE_GUESS_STAFF_PREFIX = "dingtalk_bind:rcg:staff:"
_BIND_CODE_GUESS_TOKEN_PREFIX = "dingtalk_bind:rcg:tok:"
_BIND_CODE_GUESS_TTL_SEC = 600
_BIND_CODE_GUESS_MAX_PER_STAFF = 30
_BIND_CODE_GUESS_MAX_PER_TOKEN = 40

_LUA_INCR_WITH_TTL = """
local n = redis.call('INCR', KEYS[1])
local t = redis.call('TTL', KEYS[1])
if t == -1 then
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
return n
"""

_LUA_CONSUME_BIND_TOKEN = """
local token_key = KEYS[1]
local consumed_key = KEYS[2]
local ttl = tonumber(ARGV[1])
local val = redis.call('GET', token_key)
if not val then
  return false
end
local ok = redis.call('SET', consumed_key, '1', 'NX', 'EX', ttl)
if not ok then
  return false
end
redis.call('DEL', token_key)
return val
"""


def _token_key(token: str) -> str:
    return f"{BIND_TOKEN_KEY_PREFIX}{token}"


def _consumed_key(token: str) -> str:
    return f"{BIND_CONSUMED_PREFIX}{token.strip()}"


def _minter_key(user_id: int) -> str:
    return f"{BIND_MINTER_PREFIX}{int(user_id)}"


def _staff_bucket(staff_id: str) -> str:
    return hashlib.sha256(staff_id.encode("utf-8", errors="replace")).hexdigest()[:32]


def _token_print(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8", errors="replace")).hexdigest()[:16]


def _guess_staff_key(staff_id: str) -> str:
    return f"{_BIND_CODE_GUESS_STAFF_PREFIX}{_staff_bucket(staff_id)}"


def _guess_token_key(staff_id: str, token: str) -> str:
    return f"{_BIND_CODE_GUESS_TOKEN_PREFIX}{_staff_bucket(staff_id)}:{_token_print(token)}"


def bind_code_secret_from_payload(data: object) -> str:
    """Return per-token HMAC secret for rotating bind QR codes."""
    if not isinstance(data, dict):
        return ""
    raw = data.get(BIND_CODE_SECRET_FIELD)
    if not isinstance(raw, str):
        return ""
    return raw.strip()


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
    redis = get_async_redis()
    if redis is None:
        return 0
    return int(
        await cast(
            Awaitable[Any],
            redis.eval(_LUA_INCR_WITH_TTL, 1, key, str(ttl_sec)),
        ),
    )


async def has_pending_bind_token(user_id: int) -> bool:
    """Return True when user has an unconsumed pending bind token."""
    redis = get_async_redis()
    if redis is None:
        return False
    try:
        raw = await redis.get(_minter_key(user_id))
    except RedisError:
        return False
    return isinstance(raw, str) and bool(raw.strip())


async def get_minter_bind_token(user_id: int) -> Optional[str]:
    """Return the pending bind token for this user, if any."""
    redis = get_async_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(_minter_key(user_id))
    except RedisError as exc:
        logger.debug("[DingtalkBind] get_minter_bind_token failed: %s", exc)
        return None
    if not isinstance(raw, str):
        return None
    stripped = raw.strip()
    return stripped or None


async def get_bind_token_consumed(token: str) -> bool:
    """Return True when token was recently consumed."""
    redis = get_async_redis()
    if redis is None:
        return False
    try:
        raw = await redis.get(_consumed_key(token))
    except RedisError:
        return False
    return raw is not None


def mint_bind_token() -> str:
    """Return a new opaque bind token string."""
    return secrets.token_urlsafe(32)


async def store_bind_token(
    *,
    token: str,
    user_id: int,
    organization_id: int,
) -> bool:
    """Store bind token and index by minter user id. Returns False if Redis unavailable."""
    redis = get_async_redis()
    if redis is None:
        return False
    payload = json.dumps(
        {
            "user_id": int(user_id),
            "organization_id": int(organization_id),
            BIND_CODE_SECRET_FIELD: secrets.token_urlsafe(32),
        },
        separators=(",", ":"),
    )
    try:
        old = await redis.get(_minter_key(user_id))
        if isinstance(old, str) and old.strip():
            await redis.delete(_token_key(old.strip()))
        pipe = redis.pipeline()
        pipe.set(_token_key(token), payload, ex=BIND_TOKEN_TTL_SECONDS)
        pipe.set(_minter_key(user_id), token, ex=BIND_TOKEN_TTL_SECONDS)
        await pipe.execute()
        return True
    except RedisError as exc:
        logger.warning("[DingtalkBind] store_bind_token failed: %s", exc)
        return False


async def get_bind_token_data(token: str) -> Optional[dict[str, Any]]:
    """Return token payload dict or None if missing/invalid."""
    redis = get_async_redis()
    if redis is None:
        return None
    key = _token_key(token.strip())
    try:
        raw = await redis.get(key)
    except RedisError as exc:
        logger.warning("[DingtalkBind] get_bind_token_data failed: %s", exc)
        return None
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    sec_raw = data.get(BIND_CODE_SECRET_FIELD)
    if not (isinstance(sec_raw, str) and sec_raw.strip()):
        data[BIND_CODE_SECRET_FIELD] = secrets.token_urlsafe(32)
        try:
            ttl = await redis.ttl(key)
        except RedisError as exc:
            logger.warning("[DingtalkBind] bind_code_secret migration ttl failed: %s", exc)
            return None
        if ttl is None or ttl < 0 or int(ttl) == -1:
            ex = BIND_TOKEN_TTL_SECONDS
        else:
            ex = int(ttl)
        if ex < 1:
            ex = BIND_TOKEN_TTL_SECONDS
        try:
            await redis.set(key, json.dumps(data, separators=(",", ":")), ex=ex)
        except RedisError as exc:
            logger.warning("[DingtalkBind] bind_code_secret migration set failed: %s", exc)
            return None
    return data


async def consume_bind_token(token: str) -> Optional[dict[str, Any]]:
    """Atomically consume token. Returns payload or None."""
    redis = get_async_redis()
    if redis is None:
        return None
    stripped = token.strip()
    tkey = _token_key(stripped)
    ckey = _consumed_key(stripped)
    try:
        raw = await cast(
            Awaitable[Any],
            redis.eval(
                _LUA_CONSUME_BIND_TOKEN,
                2,
                tkey,
                ckey,
                str(BIND_TOKEN_TTL_SECONDS),
            ),
        )
    except RedisError as exc:
        logger.warning("[DingtalkBind] consume_bind_token failed: %s", exc)
        return None
    if raw is False or raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    user_id = data.get("user_id")
    if isinstance(user_id, int) or (isinstance(user_id, str) and str(user_id).isdigit()):
        try:
            await redis.delete(_minter_key(int(user_id)))
        except RedisError as exc:
            logger.debug("[DingtalkBind] consume minter cleanup: %s", exc)
    return data


async def revoke_pending_bind_token(user_id: int) -> None:
    """Remove pending bind token for user (modal close / new mint)."""
    redis = get_async_redis()
    if redis is None:
        return
    try:
        raw = await redis.get(_minter_key(user_id))
        if isinstance(raw, str) and raw.strip():
            await redis.delete(_token_key(raw.strip()))
        await redis.delete(_minter_key(user_id))
    except RedisError as exc:
        logger.warning("[DingtalkBind] revoke_pending_bind_token failed: %s", exc)


async def is_bind_code_guess_blocked(staff_id: str, token: str) -> bool:
    """True when rotating-code guess limits are exceeded for staff/token pair."""
    redis = get_async_redis()
    if redis is None:
        return False
    staff = (staff_id or "").strip()
    if not staff:
        return False
    skey = _guess_staff_key(staff)
    tkey = _guess_token_key(staff, token)
    try:
        raw_staff, raw_token = await redis.mget(skey, tkey)
    except RedisError as exc:
        logger.warning("[DingtalkBind] bind code guess mget failed: %s", exc)
        return False
    n_staff = _redis_count_from_raw(raw_staff)
    n_token = _redis_count_from_raw(raw_token)
    return (
        n_staff >= _BIND_CODE_GUESS_MAX_PER_STAFF
        or n_token >= _BIND_CODE_GUESS_MAX_PER_TOKEN
    )


async def record_bind_code_guess_failure(staff_id: str, token: str) -> None:
    """Count a failed rotating bind-code verification."""
    staff = (staff_id or "").strip()
    if not staff:
        return
    skey = _guess_staff_key(staff)
    tkey = _guess_token_key(staff, token)
    try:
        redis = get_async_redis()
        if redis is None:
            return
        ttl_str = str(_BIND_CODE_GUESS_TTL_SEC)
        async with redis.pipeline(transaction=False) as pipe:
            pipe.eval(_LUA_INCR_WITH_TTL, 1, skey, ttl_str)
            pipe.eval(_LUA_INCR_WITH_TTL, 1, tkey, ttl_str)
            await pipe.execute()
    except RedisError as exc:
        logger.warning("[DingtalkBind] bind code guess incr failed: %s", exc)


async def clear_bind_code_guess_failures(staff_id: str, token: str) -> None:
    """Reset guess counters after a successful bind."""
    redis = get_async_redis()
    if redis is None:
        return
    staff = (staff_id or "").strip()
    if not staff:
        return
    try:
        await redis.delete(_guess_staff_key(staff), _guess_token_key(staff, token))
    except RedisError as exc:
        logger.debug("[DingtalkBind] bind code guess clear non-fatal: %s", exc)
