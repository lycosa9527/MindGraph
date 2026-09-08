"""One-shot Redis grants binding an upload key to user + course + role."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

_GRANT_TTL = 900


def _grant_key(user_id: int, course_id: str, role: str) -> str:
    return f"training:upload:{int(user_id)}:{course_id}:{role}"


async def save_upload_grant(
    *,
    user_id: int,
    course_id: str,
    role: str,
    logical_key: str,
    content_type: str,
    max_bytes: int,
    ttl_seconds: int = _GRANT_TTL,
) -> None:
    """Persist anti-swap upload grant."""
    redis = get_async_redis()
    if redis is None:
        raise RuntimeError("Redis is not available")
    payload = json.dumps(
        {
            "key": logical_key,
            "content_type": content_type,
            "max_bytes": int(max_bytes),
            "course_id": course_id,
            "role": role,
        },
        separators=(",", ":"),
    )
    await redis.set(_grant_key(user_id, course_id, role), payload, ex=ttl_seconds)


async def pop_upload_grant(
    *,
    user_id: int,
    course_id: str,
    role: str,
) -> Optional[dict[str, Any]]:
    """Consume upload grant (one-shot)."""
    redis = get_async_redis()
    if redis is None:
        return None
    key = _grant_key(user_id, course_id, role)
    try:
        raw = await redis.get(key)
        if raw is None:
            return None
        await redis.delete(key)
    except REDIS_ERRORS as exc:
        logger.debug("[Training] pop_upload_grant failed: %s", exc)
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed
