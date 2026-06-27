"""Redis storage for ephemeral DingTalk bind sessions."""

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
    BIND_ORG_INDEX_PREFIX,
    BIND_TOKEN_KEY_PREFIX,
    BIND_TOKEN_TTL_SECONDS,
    PAIR_PURPOSE_BIND,
    PAIR_PURPOSE_FIELD,
    PAIR_PURPOSE_UNBIND,
)
from services.auth.quick_register_room_code import (
    ROOM_CODE_PERIOD_SECONDS,
    room_code_for_step,
    room_secret_to_hmac_key,
    time_step_now,
    verify_room_code_submitted,
)
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

_BIND_CODE_GUESS_STAFF_PREFIX = "dingtalk_bind:rcg:staff:"
_BIND_CODE_GUESS_TOKEN_PREFIX = "dingtalk_bind:rcg:tok:"
_BIND_CODE_GUESS_TTL_SEC = 600
_BIND_CODE_GUESS_MAX_PER_STAFF = 30
_BIND_CODE_GUESS_MAX_PER_TOKEN = 40
_PAIR_CLAIM_LOCK_PREFIX = "dingtalk_bind:claim_lock:"
_PAIR_CLAIM_LOCK_TTL_SEC = 45
_ORG_CODE_INDEX_PREFIX = "dingtalk_bind:ocode:"
_ORG_CODE_INDEX_SKEW_WINDOWS = 1
_ORG_CODE_INDEX_TTL_SEC = ROOM_CODE_PERIOD_SECONDS * (_ORG_CODE_INDEX_SKEW_WINDOWS * 2 + 1) + 15

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


def _org_index_key(organization_id: int) -> str:
    return f"{BIND_ORG_INDEX_PREFIX}{int(organization_id)}"


def _org_code_index_key(organization_id: int, step: int, code: str) -> str:
    return f"{_ORG_CODE_INDEX_PREFIX}{int(organization_id)}:{int(step)}:{code}"


async def register_bind_code_index(
    *,
    organization_id: int,
    token: str,
    bind_secret: str,
) -> None:
    """Index rotating codes for O(1) org+code lookup (supports bulk bind events)."""
    redis = get_async_redis()
    if redis is None:
        return
    stripped = token.strip()
    secret = (bind_secret or "").strip()
    if not stripped or not secret:
        return
    hkey = room_secret_to_hmac_key(secret)
    step0 = time_step_now()
    try:
        pipe = redis.pipeline()
        for window in range(-_ORG_CODE_INDEX_SKEW_WINDOWS, _ORG_CODE_INDEX_SKEW_WINDOWS + 1):
            step = step0 + window
            code = room_code_for_step(hkey, stripped, step)
            pipe.sadd(_org_code_index_key(int(organization_id), step, code), stripped)
            pipe.expire(
                _org_code_index_key(int(organization_id), step, code),
                _ORG_CODE_INDEX_TTL_SEC,
            )
        await pipe.execute()
    except RedisError as exc:
        logger.debug("[DingtalkBind] code index register failed: %s", exc)


async def _resolve_tokens_from_code_index(
    organization_id: int,
    bind_code: str,
) -> list[str]:
    """Return token candidates registered for this org+code across time skew."""
    redis = get_async_redis()
    if redis is None:
        return []
    step0 = time_step_now()
    candidates: list[str] = []
    seen: set[str] = set()
    for window in range(-_ORG_CODE_INDEX_SKEW_WINDOWS, _ORG_CODE_INDEX_SKEW_WINDOWS + 1):
        key = _org_code_index_key(int(organization_id), step0 + window, bind_code)
        try:
            members = await redis.smembers(key)
        except RedisError as exc:
            logger.debug("[DingtalkBind] code index smembers failed: %s", exc)
            continue
        for raw_member in members:
            token = raw_member.decode("utf-8", errors="replace") if isinstance(raw_member, bytes) else str(raw_member)
            token = token.strip()
            if token and token not in seen:
                seen.add(token)
                candidates.append(token)
    return candidates


def _verify_token_for_org_code(
    *,
    token: str,
    organization_id: int,
    bind_code: str,
    data: dict[str, Any],
) -> bool:
    token_org = _organization_id_from_payload(data)
    if token_org != int(organization_id):
        return False
    bind_secret = bind_code_secret_from_payload(data)
    if not bind_secret:
        return False
    return verify_room_code_submitted(bind_secret, token, bind_code)


async def _collect_verified_token_candidates(
    *,
    organization_id: int,
    bind_code: str,
    token_ids: list[str],
) -> list[str]:
    verified: list[str] = []
    for token in token_ids:
        data = await get_bind_token_data(token)
        if data is None:
            continue
        if _verify_token_for_org_code(
            token=token,
            organization_id=organization_id,
            bind_code=bind_code,
            data=data,
        ):
            verified.append(token)
    return verified


def _organization_id_from_payload(data: object) -> Optional[int]:
    if not isinstance(data, dict):
        return None
    raw_org = data.get("organization_id")
    if isinstance(raw_org, int):
        return raw_org
    if isinstance(raw_org, str) and raw_org.isdigit():
        return int(raw_org)
    return None


async def _remove_token_from_org_index(organization_id: int, token: str) -> None:
    redis = get_async_redis()
    if redis is None:
        return
    stripped = token.strip()
    if not stripped:
        return
    try:
        await redis.srem(_org_index_key(organization_id), stripped)
    except RedisError as exc:
        logger.debug("[DingtalkBind] org index remove failed: %s", exc)


async def _add_token_to_org_index(organization_id: int, token: str) -> None:
    redis = get_async_redis()
    if redis is None:
        return
    stripped = token.strip()
    if not stripped:
        return
    key = _org_index_key(organization_id)
    try:
        pipe = redis.pipeline()
        pipe.sadd(key, stripped)
        pipe.expire(key, BIND_TOKEN_TTL_SECONDS)
        await pipe.execute()
    except RedisError as exc:
        logger.warning("[DingtalkBind] org index add failed: %s", exc)


async def resolve_bind_token_for_org_code(
    organization_id: int,
    bind_code: str,
) -> Optional[str]:
    """
    Resolve a pending bind token from org scope + rotating 6-digit code.

    Returns the matching token, or None when no active session matches.
    """
    redis = get_async_redis()
    if redis is None:
        return None
    stripped_code = (bind_code or "").strip()
    if len(stripped_code) != 6 or not stripped_code.isdigit():
        return None

    indexed_tokens = await _resolve_tokens_from_code_index(int(organization_id), stripped_code)
    if indexed_tokens:
        index_candidates = await _collect_verified_token_candidates(
            organization_id=int(organization_id),
            bind_code=stripped_code,
            token_ids=indexed_tokens,
        )
        if len(index_candidates) == 1:
            return index_candidates[0]
        if len(index_candidates) > 1:
            logger.warning(
                "[DingtalkBind] ambiguous bind code index match org_id=%s count=%s",
                organization_id,
                len(index_candidates),
            )
            return None

    org_key = _org_index_key(int(organization_id))
    try:
        members = await redis.smembers(org_key)
    except RedisError as exc:
        logger.warning("[DingtalkBind] org index smembers failed: %s", exc)
        return None
    if not members:
        return None

    token_candidates: list[str] = []
    stale_tokens: list[str] = []
    for raw_member in members:
        token = raw_member.decode("utf-8", errors="replace") if isinstance(raw_member, bytes) else str(raw_member)
        token = token.strip()
        if not token:
            continue
        data = await get_bind_token_data(token)
        if data is None:
            stale_tokens.append(token)
            continue
        if _verify_token_for_org_code(
            token=token,
            organization_id=int(organization_id),
            bind_code=stripped_code,
            data=data,
        ):
            token_candidates.append(token)
        else:
            token_org = _organization_id_from_payload(data)
            if token_org != int(organization_id):
                stale_tokens.append(token)

    if stale_tokens:
        try:
            await redis.srem(org_key, *stale_tokens)
        except RedisError as exc:
            logger.debug("[DingtalkBind] org index stale cleanup failed: %s", exc)

    if len(token_candidates) == 1:
        return token_candidates[0]
    if len(token_candidates) > 1:
        logger.warning(
            "[DingtalkBind] ambiguous bind code match org_id=%s count=%s",
            organization_id,
            len(token_candidates),
        )
    return None


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


def _pair_claim_lock_key(token: str) -> str:
    return f"{_PAIR_CLAIM_LOCK_PREFIX}{_token_print(token.strip())}"


async def try_acquire_pair_claim_lock(token: str) -> bool:
    """Acquire a short-lived lock so only one claim proceeds per pair token."""
    redis = get_async_redis()
    if redis is None:
        return False
    stripped = token.strip()
    if not stripped:
        return False
    try:
        acquired = await redis.set(
            _pair_claim_lock_key(stripped),
            "1",
            nx=True,
            ex=_PAIR_CLAIM_LOCK_TTL_SEC,
        )
        return acquired is True
    except RedisError as exc:
        logger.warning("[DingtalkBind] pair claim lock acquire failed: %s", exc)
        return False


async def release_pair_claim_lock(token: str) -> None:
    """Release a pair claim lock (best effort)."""
    redis = get_async_redis()
    if redis is None:
        return
    stripped = token.strip()
    if not stripped:
        return
    try:
        await redis.delete(_pair_claim_lock_key(stripped))
    except RedisError as exc:
        logger.debug("[DingtalkBind] pair claim lock release failed: %s", exc)


async def get_pending_pair_purpose(user_id: int) -> Optional[str]:
    """Return bind/unbind purpose for the user's pending pair session, if any."""
    token = await get_minter_bind_token(user_id)
    if not token:
        return None
    data = await get_bind_token_data(token)
    if data is None:
        return None
    return pair_purpose_from_payload(data)


def bind_code_secret_from_payload(data: object) -> str:
    """Return per-token HMAC secret for rotating pair codes."""
    if not isinstance(data, dict):
        return ""
    raw = data.get(BIND_CODE_SECRET_FIELD)
    if not isinstance(raw, str):
        return ""
    return raw.strip()


def pair_purpose_from_payload(data: object) -> str:
    """Return pair session purpose (bind/unbind); legacy tokens default to bind."""
    if not isinstance(data, dict):
        return PAIR_PURPOSE_BIND
    raw = data.get(PAIR_PURPOSE_FIELD)
    if raw == PAIR_PURPOSE_UNBIND:
        return PAIR_PURPOSE_UNBIND
    return PAIR_PURPOSE_BIND


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
    purpose: str = PAIR_PURPOSE_BIND,
) -> bool:
    """Store pair session and index by minter user id. Returns False if Redis unavailable."""
    redis = get_async_redis()
    if redis is None:
        return False
    session_purpose = PAIR_PURPOSE_UNBIND if purpose == PAIR_PURPOSE_UNBIND else PAIR_PURPOSE_BIND
    session_payload = {
        "user_id": int(user_id),
        "organization_id": int(organization_id),
        BIND_CODE_SECRET_FIELD: secrets.token_urlsafe(32),
        PAIR_PURPOSE_FIELD: session_purpose,
    }
    payload = json.dumps(session_payload, separators=(",", ":"))
    try:
        old = await redis.get(_minter_key(user_id))
        if isinstance(old, str) and old.strip():
            old_token = old.strip()
            old_data = await get_bind_token_data(old_token)
            old_org = _organization_id_from_payload(old_data) if old_data else int(organization_id)
            if old_org is not None:
                await _remove_token_from_org_index(old_org, old_token)
            await redis.delete(_token_key(old_token))
        pipe = redis.pipeline()
        pipe.set(_token_key(token), payload, ex=BIND_TOKEN_TTL_SECONDS)
        pipe.set(_minter_key(user_id), token, ex=BIND_TOKEN_TTL_SECONDS)
        await pipe.execute()
        await _add_token_to_org_index(int(organization_id), token)
        secret = bind_code_secret_from_payload(session_payload)
        if secret:
            await register_bind_code_index(
                organization_id=int(organization_id),
                token=token,
                bind_secret=secret,
            )
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


async def force_burn_bind_token(token: str) -> bool:
    """Mark a token consumed and delete it when normal consume fails after DB commit."""
    redis = get_async_redis()
    if redis is None:
        return False
    stripped = token.strip()
    if not stripped:
        return False
    if await get_bind_token_consumed(stripped):
        return True
    payload = await consume_bind_token(stripped)
    if payload is not None:
        return True
    data = await get_bind_token_data(stripped)
    try:
        pipe = redis.pipeline()
        pipe.set(_consumed_key(stripped), "1", ex=BIND_TOKEN_TTL_SECONDS)
        pipe.delete(_token_key(stripped))
        await pipe.execute()
    except RedisError as exc:
        logger.error("[DingtalkBind] force_burn_bind_token failed: %s", exc)
        return False
    if data is not None:
        token_org = _organization_id_from_payload(data)
        if token_org is not None:
            await _remove_token_from_org_index(token_org, stripped)
        user_id = data.get("user_id")
        if isinstance(user_id, int) or (isinstance(user_id, str) and str(user_id).isdigit()):
            try:
                await redis.delete(_minter_key(int(user_id)))
            except RedisError as exc:
                logger.debug("[DingtalkBind] force_burn minter cleanup: %s", exc)
    return True


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
    token_org = _organization_id_from_payload(data)
    if token_org is not None:
        await _remove_token_from_org_index(token_org, stripped)
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
            pending_token = raw.strip()
            pending_data = await get_bind_token_data(pending_token)
            pending_org = _organization_id_from_payload(pending_data) if pending_data else None
            if pending_org is not None:
                await _remove_token_from_org_index(pending_org, pending_token)
            await redis.delete(_token_key(pending_token))
        await redis.delete(_minter_key(user_id))
    except RedisError as exc:
        logger.warning("[DingtalkBind] revoke_pending_bind_token failed: %s", exc)


async def is_bind_code_guess_blocked(staff_id: str, token: str) -> bool:
    """True when rotating-code guess limits are exceeded for staff/token pair."""
    redis = get_async_redis()
    if redis is None:
        return True
    staff = (staff_id or "").strip()
    if not staff:
        return False
    skey = _guess_staff_key(staff)
    tkey = _guess_token_key(staff, token)
    try:
        raw_staff, raw_token = await redis.mget(skey, tkey)
    except REDIS_ERRORS as exc:
        logger.warning("[DingtalkBind] bind code guess mget failed: %s", exc)
        return True
    n_staff = _redis_count_from_raw(raw_staff)
    n_token = _redis_count_from_raw(raw_token)
    return n_staff >= _BIND_CODE_GUESS_MAX_PER_STAFF or n_token >= _BIND_CODE_GUESS_MAX_PER_TOKEN


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
