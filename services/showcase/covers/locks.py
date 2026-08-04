"""Redis single-flight lock for Showcase cover generation."""

from __future__ import annotations

import logging
import secrets
from typing import Optional

from services.redis.redis_client import get_redis, is_redis_available
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

_LOCK_PREFIX = "showcase:cover:"
_ENQUEUE_PREFIX = "showcase:cover:enq:"
_LOCK_TTL_SECONDS = 300
# Coalesce GET-post + cover-stream + EventSource reconnect enqueue spam.
_ENQUEUE_TTL_SECONDS = 90
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


def try_claim_cover_enqueue(post_id: str) -> bool:
    """Return True when this process should ``send_task`` (first claim wins).

    Fail-open when Redis is unavailable so local/dev still enqueues.
    """
    if not is_redis_available():
        return True
    redis = get_redis()
    if redis is None:
        return True
    key = f"{_ENQUEUE_PREFIX}{post_id}"
    try:
        acquired = redis.set(key, "1", nx=True, ex=_ENQUEUE_TTL_SECONDS)
    except REDIS_ERRORS as exc:
        logger.debug("[ShowcaseCover] enqueue claim failed post=%s: %s", post_id[:8], exc)
        return True
    return bool(acquired)


def acquire_cover_lock(post_id: str) -> Optional[str]:
    """Acquire single-flight lock; returns lock token or None if busy/unavailable."""
    if not is_redis_available():
        return "noredis"
    redis = get_redis()
    if redis is None:
        return "noredis"
    token = secrets.token_hex(16)
    key = f"{_LOCK_PREFIX}{post_id}"
    try:
        acquired = redis.set(key, token, nx=True, ex=_LOCK_TTL_SECONDS)
    except REDIS_ERRORS as exc:
        logger.debug("[ShowcaseCover] lock acquire failed post=%s: %s", post_id[:8], exc)
        return "noredis"
    if acquired:
        return token
    return None


def release_cover_lock(post_id: str, token: Optional[str]) -> None:
    """Release single-flight lock when token matches."""
    if not token or token == "noredis":
        return
    if not is_redis_available():
        return
    redis = get_redis()
    if redis is None:
        return
    key = f"{_LOCK_PREFIX}{post_id}"
    try:
        redis.eval(_RELEASE_LUA, 1, key, token)
    except REDIS_ERRORS as exc:
        logger.debug("[ShowcaseCover] lock release failed post=%s: %s", post_id[:8], exc)
