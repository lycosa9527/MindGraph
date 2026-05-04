"""Short-lived join resume secrets for canvas-collab WebSocket reconnect."""

from __future__ import annotations

import json
import logging
import os
import secrets
from typing import Any, Dict, Optional

from redis.exceptions import RedisError

from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_REDIS_NS = 'collab:ws:jresume:'
_TOKEN_HEX_BYTES = 16
_MAX_RESUME_QUERY_LEN = 96
_DEFAULT_RECONNECT_TTL_SEC = 900


async def peek_join_resume_claims_async(
    raw_query_token: str,
) -> Optional[Dict[str, Any]]:
    """
    Return parsed resume payload from Redis WITHOUT deleting.

    Tokens are hashed server-side keys; guesses do not degrade security.
    """
    trimmed = raw_query_token.strip()
    if not trimmed or len(trimmed) > _MAX_RESUME_QUERY_LEN:
        return None
    redis = get_async_redis()
    if not redis:
        return None
    key = _REDIS_NS + trimmed
    try:
        body = await redis.get(key)
    except (RedisError, OSError, TypeError):
        return None
    if body is None:
        return None
    if isinstance(body, (bytes, bytearray)):
        try:
            text = body.decode('utf-8')
        except UnicodeDecodeError:
            return None
    else:
        text = str(body)
    try:
        decoded = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(decoded, dict):
        return None
    return decoded


def join_resume_claims_match_user_room(
    user_id: int,
    workshop_code_upper: str,
    claims: Dict[str, Any],
) -> bool:
    """Cheap match on user + normalized room token before trusting bypass."""
    code_val = claims.get('c')
    raw_uid = claims.get('u')
    try:
        record_uid = int(raw_uid)
    except (TypeError, ValueError):
        return False
    return (
        record_uid == int(user_id)
        and code_val == workshop_code_upper.strip().upper()
    )


def _resume_ttl_seconds() -> int:
    raw = os.getenv('WORKSHOP_JOIN_RESUME_TTL_SEC', str(_DEFAULT_RECONNECT_TTL_SEC))
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return _DEFAULT_RECONNECT_TTL_SEC
    return max(120, min(parsed, 86_400))


async def mint_join_resume_token_async(
    *,
    user_id: int,
    workshop_code_upper: str,
    diagram_id: str,
) -> str:
    """Store proof-of-reconnect credentials in Redis with a short TTL."""
    redis = get_async_redis()
    if not redis:
        return ''
    digest = secrets.token_hex(_TOKEN_HEX_BYTES)
    key = _REDIS_NS + digest
    payload: Dict[str, Any] = {
        'u': int(user_id),
        'c': workshop_code_upper.strip().upper(),
        'd': diagram_id.strip(),
    }
    try:
        body = json.dumps(payload, separators=(',', ':'))
    except (TypeError, ValueError):
        return ''
    try:
        ttl = _resume_ttl_seconds()
        await redis.setex(key, ttl, body)
    except (RedisError, OSError, TypeError) as exc:
        logger.debug('[collab:jresume] mint failed user=%s: %s', user_id, exc)
        return ''
    return digest


async def try_consume_join_resume_token_async(
    *,
    raw_query_token: str,
    user_id: int,
    workshop_code_upper: str,
    diagram_id: str,
) -> bool:
    """
    Consume a previously minted reconnect token owned by workshop + diagram.

    Returns True while removing the Redis key unless payload mismatch.
    """
    trimmed = raw_query_token.strip()
    if not trimmed or len(trimmed) > _MAX_RESUME_QUERY_LEN:
        return False
    redis = get_async_redis()
    if not redis:
        return False
    key = _REDIS_NS + trimmed
    try:
        body = await redis.get(key)
    except (RedisError, OSError, TypeError) as exc:
        logger.debug('[collab:jresume] get failed user=%s: %s', user_id, exc)
        return False
    if body is None:
        return False
    if isinstance(body, (bytes, bytearray)):
        try:
            text = body.decode('utf-8')
        except UnicodeDecodeError:
            return False
    else:
        text = str(body)
    try:
        decoded = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return False
    if not isinstance(decoded, dict):
        return False
    try:
        record_uid = int(decoded.get('u'))
    except (TypeError, ValueError):
        return False
    code_val = decoded.get('c')
    diagram_val = decoded.get('d')
    if (
        record_uid != int(user_id)
        or code_val != workshop_code_upper.strip().upper()
        or diagram_val != diagram_id.strip()
    ):
        return False
    try:
        await redis.delete(key)
    except (RedisError, OSError, TypeError):
        logger.debug('[collab:jresume] delete failed — allowing rate limit reuse')
        return False
    return True
