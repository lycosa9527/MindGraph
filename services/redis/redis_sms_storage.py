from typing import Optional, Tuple
import logging

from services.redis.redis_client import is_redis_available, get_redis, RedisOps

"""
Redis SMS Verification Storage
==============================

High-performance SMS verification code storage using Redis.
Replaces SQLite for SMS verification to eliminate write contention.

Features:
- O(1) store, verify, delete operations
- Automatic TTL-based expiration (no cleanup needed)
- One-time use verification (atomic compare-and-delete via Lua script)
- Shared across all workers (accurate verification)

Key Schema:
- sms:verify:{phone} -> {code}:{expires_at}:{purpose}

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""



logger = logging.getLogger(__name__)

# Key prefix for SMS verification codes
SMS_PREFIX = "sms:verify:"

# Default TTL for SMS codes (5 minutes)
DEFAULT_SMS_TTL = 300


class RedisSMSStorage:
    """
    Redis-based SMS verification code storage.

    Performance:
    - Store: O(1) - SETEX command
    - Verify: O(1) - Atomic compare-and-delete via Lua script
    - No background cleanup needed (Redis TTL handles expiration)

    Thread-safe: All operations are atomic Redis commands.
    """

    def __init__(self):
        self._fallback_enabled = False

    def _get_key(self, phone: str, purpose: str = "verification") -> str:
        """Generate Redis key for phone/purpose combination."""
        return f"{SMS_PREFIX}{purpose}:{phone}"

    def store(
        self,
        phone: str,
        code: str,
        purpose: str = "verification",
        ttl_seconds: int = DEFAULT_SMS_TTL
    ) -> bool:
        """
        Store SMS verification code with TTL.

        Args:
            phone: Phone number
            code: Verification code (6 digits)
            purpose: Purpose of code (verification, password_reset, etc.)
            ttl_seconds: Time-to-live in seconds (default: 300 = 5 min)

        Returns:
            True if stored successfully, False otherwise
        """
        if not is_redis_available():
            logger.warning("[SMS] Redis unavailable, SMS code NOT stored")
            return False

        key = self._get_key(phone, purpose)

        # Store with TTL
        success = RedisOps.set_with_ttl(key, code, ttl_seconds)

        if success:
            phone_masked = phone[:3] + "***" + phone[-4:]
            logger.info("[SMS] Code stored for %s (purpose: %s, TTL: %ss)", phone_masked, purpose, ttl_seconds)
        else:
            logger.error("[SMS] Failed to store code for %s", phone)

        return success

    def verify_and_remove(
        self,
        phone: str,
        code: str,
        purpose: str = "verification"
    ) -> bool:
        """
        Verify SMS code and remove it (one-time use).

        Uses atomic Lua script for compare-and-delete to prevent race conditions.
        Only removes the code if it matches. Wrong attempts do not consume the code,
        allowing users to retry with the correct code.

        Args:
            phone: Phone number
            code: Code to verify
            purpose: Purpose of code

        Returns:
            True if code matches and was removed, False otherwise
        """
        if not is_redis_available():
            logger.warning("[SMS] Redis unavailable, cannot verify code")
            return False

        redis = get_redis()
        if not redis:
            logger.warning("[SMS] Redis client unavailable, cannot verify code")
            return False

        key = self._get_key(phone, purpose)

        try:
            # Atomic compare-and-delete using Lua script
            # Only deletes if stored code matches provided code
            # Prevents race condition where two concurrent requests could both consume the same code
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            result = redis.eval(lua_script, 1, key, code)

            if result == 1:
                phone_masked = phone[:3] + "***" + phone[-4:]
                logger.info("[SMS] Code verified and consumed for %s (purpose: %s)", phone_masked, purpose)
                return True
            elif result == 0:
                # Code doesn't match or doesn't exist - check which case
                stored_code = RedisOps.get(key)
                phone_masked = phone[:3] + "***" + phone[-4:]
                if stored_code is None:
                    logger.debug("[SMS] No code found for %s (purpose: %s)", phone_masked, purpose)
                else:
                    logger.warning(
                        "[SMS] Invalid code for %s (purpose: %s) - "
                        "code preserved for retry",
                        phone_masked,
                        purpose
                    )
                return False
            else:
                logger.warning("[SMS] Unexpected Lua script result: %s", result)
                return False

        except Exception as e:
            logger.error("[SMS] Lua script execution failed: %s", e)
            return False

    def check_exists(self, phone: str, purpose: str = "verification") -> bool:
        """
        Check if a code exists for this phone (without consuming it).

        Useful for rate limiting SMS sends.

        Args:
            phone: Phone number
            purpose: Purpose of code

        Returns:
            True if code exists, False otherwise
        """
        if not is_redis_available():
            return False

        key = self._get_key(phone, purpose)
        return RedisOps.exists(key)

    def peek(self, phone: str, purpose: str = "verification") -> Optional[str]:
        """
        Get stored code without consuming it (for verification preview).

        Unlike verify_and_remove, this does NOT delete the code.
        Useful for the /sms/verify endpoint that validates without consuming.

        Args:
            phone: Phone number
            purpose: Purpose of code

        Returns:
            Stored code if exists, None otherwise
        """
        if not is_redis_available():
            return None

        key = self._get_key(phone, purpose)
        return RedisOps.get(key)

    def check_exists_and_get_ttl(self, phone: str, purpose: str = "verification") -> Tuple[bool, int]:
        """
        Atomically check if code exists and get its remaining TTL.

        Uses Redis pipeline to get both EXISTS and TTL in a single operation,
        eliminating race conditions where code could expire between checks.

        Args:
            phone: Phone number
            purpose: Purpose of code

        Returns:
            Tuple of (exists: bool, ttl: int)
            - exists: True if code exists, False otherwise
            - ttl: Remaining TTL in seconds, -1 if no TTL, -2 if key doesn't exist
        """
        if not is_redis_available():
            return False, -2

        redis = get_redis()
        if not redis:
            return False, -2

        key = self._get_key(phone, purpose)

        try:
            # Atomic pipeline: check existence and get TTL in one operation
            pipe = redis.pipeline()
            pipe.exists(key)
            pipe.ttl(key)
            results = pipe.execute()

            exists = bool(results[0])
            ttl = results[1] if results[1] is not None else -2

            return exists, ttl
        except Exception as e:
            logger.error("[SMS] Pipeline execution failed: %s", e)
            return False, -2

    def get_remaining_ttl(self, phone: str, purpose: str = "verification") -> int:
        """
        Get remaining TTL for an SMS code.

        Args:
            phone: Phone number
            purpose: Purpose of code

        Returns:
            Remaining TTL in seconds, -1 if no TTL, -2 if key doesn't exist
        """
        if not is_redis_available():
            return -2

        key = self._get_key(phone, purpose)
        return RedisOps.get_ttl(key)

    def remove(self, phone: str, purpose: str = "verification") -> bool:
        """
        Remove SMS code without verification.

        Args:
            phone: Phone number
            purpose: Purpose of code

        Returns:
            True if removed, False otherwise
        """
        if not is_redis_available():
            return False

        key = self._get_key(phone, purpose)
        return RedisOps.delete(key)


# Global singleton
_sms_storage: Optional[RedisSMSStorage] = None


def get_sms_storage() -> RedisSMSStorage:
    """Get or create global SMS storage instance."""
    global _sms_storage
    if _sms_storage is None:
        _sms_storage = RedisSMSStorage()
    return _sms_storage

