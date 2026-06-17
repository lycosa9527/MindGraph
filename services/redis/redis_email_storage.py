"""
Redis email verification code storage (parallel to SMS).

Key schema: email:verify:{purpose}:{normalized_email} -> code (TTL).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Optional, Tuple

from services.redis import keys as _keys
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_async_ops import AsyncRedisOps
from services.redis.redis_client import is_redis_available
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

EMAIL_PREFIX = "email:verify:"
DEFAULT_EMAIL_TTL = _keys.TTL_EMAIL


def normalize_verification_email(email: str) -> str:
    """Normalize email for Redis keys (strip + lowercase)."""
    return email.strip().lower()


def mask_email_for_log(email: str) -> str:
    """Mask email for safe logging."""
    email = email.strip()
    if "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        return f"**@{domain}"
    return f"{local[0]}***{local[-1]}@{domain}"


class RedisEmailStorage:
    """Redis-based email verification code storage."""

    def __init__(self) -> None:
        """Initialize Redis email verification storage."""

    def _get_key(self, email: str, purpose: str = "verification") -> str:
        """Get key."""
        norm = normalize_verification_email(email)
        return f"{EMAIL_PREFIX}{purpose}:{norm}"

    async def store(
        self,
        email: str,
        code: str,
        purpose: str = "verification",
        ttl_seconds: int = DEFAULT_EMAIL_TTL,
    ) -> bool:
        """Store."""
        if not is_redis_available():
            logger.warning("[Email] Redis unavailable, email code NOT stored")
            return False

        key = self._get_key(email, purpose)
        success = await AsyncRedisOps.set_with_ttl(key, code, ttl_seconds)

        if success:
            logger.info(
                "[Email] Code stored for %s (purpose: %s, TTL: %ss)",
                mask_email_for_log(email),
                purpose,
                ttl_seconds,
            )
        else:
            logger.error("[Email] Failed to store code for %s", mask_email_for_log(email))

        return success

    async def verify_and_remove(self, email: str, code: str, purpose: str = "verification") -> bool:
        """Verify and remove."""
        if not is_redis_available():
            logger.warning("[Email] Redis unavailable, cannot verify code")
            return False

        key = self._get_key(email, purpose)
        masked = mask_email_for_log(email)

        deleted = await AsyncRedisOps.compare_and_delete(key, code)

        if deleted:
            logger.info(
                "[Email] Code verified and consumed for %s (purpose: %s)",
                masked,
                purpose,
            )
            return True

        try:
            if await AsyncRedisOps.exists(key):
                logger.warning(
                    "[Email] Invalid code for %s (purpose: %s) - code preserved for retry",
                    masked,
                    purpose,
                )
            else:
                logger.debug("[Email] No code found for %s (purpose: %s)", masked, purpose)
        except REDIS_ERRORS as exc:
            logger.debug("[Email] exists check failed: %s", exc)
        return False

    async def peek(self, email: str, purpose: str = "verification") -> Optional[str]:
        """Peek."""
        if not is_redis_available():
            return None

        key = self._get_key(email, purpose)
        return await AsyncRedisOps.get(key)

    async def check_exists_and_get_ttl(self, email: str, purpose: str = "verification") -> Tuple[bool, int]:
        """Check exists and get ttl."""
        if not is_redis_available():
            return False, -2

        redis = get_async_redis()
        if not redis:
            return False, -2

        key = self._get_key(email, purpose)

        try:
            async with redis.pipeline(transaction=False) as pipe:
                pipe.exists(key)
                pipe.ttl(key)
                results = await pipe.execute()

            exists = bool(results[0])
            ttl = results[1] if results[1] is not None else -2

            return exists, ttl
        except REDIS_ERRORS as exc:
            logger.error("[Email] Pipeline execution failed: %s", exc)
            return False, -2

    async def remove(self, email: str, purpose: str = "verification") -> bool:
        """Remove."""
        if not is_redis_available():
            return False

        key = self._get_key(email, purpose)
        return await AsyncRedisOps.delete(key)


class _EmailStorageHolder:
    """_EmailStorageHolder helper."""

    instance: Optional["RedisEmailStorage"] = None


def get_email_storage() -> RedisEmailStorage:
    """Get email storage."""
    if _EmailStorageHolder.instance is None:
        _EmailStorageHolder.instance = RedisEmailStorage()
    return _EmailStorageHolder.instance
