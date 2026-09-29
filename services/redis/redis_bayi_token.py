"""
Redis Bayi Token Tracking Service
==================================

High-performance token tracking for bayi mode authentication.

Features:
- Replay attack prevention (token can only be used once)
- Rate limiting integration (prevent brute force attacks)
- Automatic TTL-based expiration (matches token expiration: 5 minutes)

Key Schema:
- bayi:token:used:{sha256_hash} -> timestamp (TTL: 5 min)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import hashlib
import logging
import time
from typing import Tuple

from services.redis import keys as _keys
from services.redis.rate_limiting.redis_rate_limiter import RedisRateLimiter
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_async_ops import AsyncRedisOps
from services.redis.redis_client import is_redis_available
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

# TTL sourced from central registry.
TOKEN_TTL = _keys.TTL_BAYI_TOKEN

# Rate limiting configuration
RATE_LIMIT_MAX_ATTEMPTS = 10  # 10 attempts per 5 minutes
RATE_LIMIT_WINDOW = 300  # 5 minutes (matches token expiration)


class BayiTokenTracker:
    """
    Redis-based bayi token tracking service.

    Prevents replay attacks and caches validation results for performance.
    Integrates with RedisRateLimiter for brute force protection.

    Thread-safe: All operations are atomic Redis commands.
    """

    def __init__(self):
        """Initialize BayiTokenTracker instance."""
        self._rate_limiter = RedisRateLimiter()

    def _use_redis(self) -> bool:
        """Check if Redis should be used."""
        return is_redis_available()

    def _hash_token(self, token: str) -> str:
        """
        Generate SHA256 hash of token for storage.

        Args:
            token: Encrypted token string

        Returns:
            SHA256 hash (hex string)
        """
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def is_token_used(self, token: str) -> bool:
        """
        Check if token was already used (replay attack prevention).

        Args:
            token: Encrypted token string

        Returns:
            True if token was already used, False otherwise
        """
        if not self._use_redis():
            raise RuntimeError("Bayi token replay store unavailable")

        token_hash = self._hash_token(token)
        key = _keys.BAYI_TOKEN_USED.format(sha256=token_hash)

        try:
            exists = await AsyncRedisOps.exists(key)
            if exists:
                logger.debug("[BayiToken] Token already used (replay attack prevented)")
                return True
            return False
        except REDIS_ERRORS as e:
            logger.warning("[BayiToken] Redis error checking token usage: %s", e)
            raise RuntimeError("Bayi token replay store unavailable") from e

    async def claim_token_once(self, token: str) -> bool:
        """
        Atomically mark a token used.

        Returns True only for the first caller. A second caller, or a Redis
        outage, must not be treated as a fresh login.
        """
        if not self._use_redis():
            raise RuntimeError("Bayi token replay store unavailable")

        token_hash = self._hash_token(token)
        key = _keys.BAYI_TOKEN_USED.format(sha256=token_hash)
        try:
            redis = get_async_redis()
            created = await redis.set(key, str(int(time.time())), ex=TOKEN_TTL, nx=True)
        except REDIS_ERRORS as e:
            logger.warning("[BayiToken] Failed to claim token: %s", e)
            raise RuntimeError("Bayi token replay store unavailable") from e
        if created:
            logger.debug("[BayiToken] Claimed token (TTL: %ss)", TOKEN_TTL)
            return True
        logger.debug("[BayiToken] Token already claimed")
        return False

    async def check_rate_limit(self, ip: str) -> Tuple[bool, int, str]:
        """
        Check rate limit for token verification attempts.

        Args:
            ip: Client IP address

        Returns:
            Tuple of (is_allowed, attempt_count, error_message)
        """
        return await self._rate_limiter.check_and_record(
            category="bayi_token",
            identifier=ip,
            max_attempts=RATE_LIMIT_MAX_ATTEMPTS,
            window_seconds=RATE_LIMIT_WINDOW,
        )

    async def clear_rate_limit(self, ip: str) -> bool:
        """
        Clear rate limit for IP (e.g., on successful login).

        Args:
            ip: Client IP address

        Returns:
            True if cleared successfully, False otherwise
        """
        return await self._rate_limiter.clear("bayi_token", ip)


class _BayiTokenTrackerState:
    """Holds the global BayiTokenTracker singleton."""

    instance: BayiTokenTracker | None = None


_bayi_token_tracker_state = _BayiTokenTrackerState()


def get_bayi_token_tracker() -> BayiTokenTracker:
    """Get singleton instance of BayiTokenTracker."""
    if _bayi_token_tracker_state.instance is None:
        _bayi_token_tracker_state.instance = BayiTokenTracker()
    return _bayi_token_tracker_state.instance


# Convenience alias
bayi_token_tracker = get_bayi_token_tracker()
