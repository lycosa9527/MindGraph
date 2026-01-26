"""
Redis Bayi Token Tracking Service
==================================

High-performance token tracking for bayi mode authentication.

Features:
- Replay attack prevention (token can only be used once)
- Validation result caching (skip decryption for cached tokens)
- Rate limiting integration (prevent brute force attacks)
- Automatic TTL-based expiration (matches token expiration: 5 minutes)

Key Schema:
- bayi:token:used:{sha256_hash} -> timestamp (TTL: 5 min)
- bayi:token:valid:{sha256_hash} -> "1" (TTL: 5 min)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, Tuple
import hashlib
import logging
import time

from services.redis.redis_client import is_redis_available, RedisOps
from services.redis.rate_limiting.redis_rate_limiter import RedisRateLimiter



logger = logging.getLogger(__name__)

# Key prefixes
TOKEN_USED_PREFIX = "bayi:token:used:"
TOKEN_VALID_PREFIX = "bayi:token:valid:"

# TTL matches token expiration (5 minutes)
TOKEN_TTL = 300  # 5 minutes = 300 seconds

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
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def is_token_used(self, token: str) -> bool:
        """
        Check if token was already used (replay attack prevention).

        Args:
            token: Encrypted token string

        Returns:
            True if token was already used, False otherwise
        """
        if not self._use_redis():
            # If Redis unavailable, skip replay prevention (backward compatibility)
            return False

        token_hash = self._hash_token(token)
        key = f"{TOKEN_USED_PREFIX}{token_hash}"

        try:
            # Check if token hash exists in Redis
            exists = RedisOps.exists(key)
            if exists:
                logger.debug("[BayiToken] Token already used (replay attack prevented)")
                return True
            return False
        except Exception as e:
            logger.warning("[BayiToken] Redis error checking token usage, allowing request: %s", e)
            # Fail-open: if Redis fails, allow request (backward compatibility)
            return False

    def mark_token_used(self, token: str) -> bool:
        """
        Mark token as used (prevent replay attacks).

        Args:
            token: Encrypted token string

        Returns:
            True if marked successfully, False otherwise
        """
        if not self._use_redis():
            return False

        token_hash = self._hash_token(token)
        key = f"{TOKEN_USED_PREFIX}{token_hash}"

        try:
            # Store token hash with TTL (matches token expiration)
            # Use current timestamp as value (for potential audit trail)
            timestamp = str(int(time.time()))
            success = RedisOps.set_with_ttl(key, timestamp, TOKEN_TTL)
            if success:
                logger.debug("[BayiToken] Marked token as used (TTL: %ss)", TOKEN_TTL)
            return success
        except Exception as e:
            logger.warning("[BayiToken] Failed to mark token as used: %s", e)
            return False

    def is_token_validated(self, token: str) -> Optional[bool]:
        """
        Check if token validation result is cached.

        Args:
            token: Encrypted token string

        Returns:
            True if cached and valid, False if cached and invalid, None if not cached
        """
        if not self._use_redis():
            return None

        token_hash = self._hash_token(token)
        key = f"{TOKEN_VALID_PREFIX}{token_hash}"

        try:
            cached = RedisOps.get(key)
            if cached == "1":
                logger.debug("[BayiToken] Token validation cached (valid)")
                return True
            elif cached == "0":
                logger.debug("[BayiToken] Token validation cached (invalid)")
                return False
            return None  # Not cached
        except Exception as e:
            logger.warning("[BayiToken] Redis error checking validation cache: %s", e)
            return None

    def cache_token_validation(self, token: str, valid: bool) -> bool:
        """
        Cache token validation result (performance optimization).

        Args:
            token: Encrypted token string
            valid: Whether token is valid

        Returns:
            True if cached successfully, False otherwise
        """
        if not self._use_redis():
            return False

        token_hash = self._hash_token(token)
        key = f"{TOKEN_VALID_PREFIX}{token_hash}"

        try:
            # Cache validation result with TTL (matches token expiration)
            value = "1" if valid else "0"
            success = RedisOps.set_with_ttl(key, value, TOKEN_TTL)
            if success:
                logger.debug("[BayiToken] Cached token validation result: %s (TTL: %ss)", valid, TOKEN_TTL)
            return success
        except Exception as e:
            logger.warning("[BayiToken] Failed to cache token validation: %s", e)
            return False

    def check_rate_limit(self, ip: str) -> Tuple[bool, int, str]:
        """
        Check rate limit for token verification attempts.

        Args:
            ip: Client IP address

        Returns:
            Tuple of (is_allowed, attempt_count, error_message)
        """
        return self._rate_limiter.check_and_record(
            category="bayi_token",
            identifier=ip,
            max_attempts=RATE_LIMIT_MAX_ATTEMPTS,
            window_seconds=RATE_LIMIT_WINDOW
        )

    def clear_rate_limit(self, ip: str) -> bool:
        """
        Clear rate limit for IP (e.g., on successful login).

        Args:
            ip: Client IP address

        Returns:
            True if cleared successfully, False otherwise
        """
        return self._rate_limiter.clear("bayi_token", ip)


def get_bayi_token_tracker() -> BayiTokenTracker:
    """Get singleton instance of BayiTokenTracker."""
    if not hasattr(get_bayi_token_tracker, '_instance'):
        setattr(get_bayi_token_tracker, '_instance', BayiTokenTracker())
    return getattr(get_bayi_token_tracker, '_instance')


# Convenience alias
bayi_token_tracker = get_bayi_token_tracker()
