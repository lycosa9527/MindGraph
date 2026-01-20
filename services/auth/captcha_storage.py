"""
Redis Captcha Storage
=====================

High-performance captcha storage using Redis.

Benefits:
- 0.1ms operations (100x faster than SQLite)
- No database write locks under high concurrency
- Automatic TTL expiration (no cleanup scheduler needed)
- Shared across all workers

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, Dict, Tuple
import logging
import time

from services.redis.redis_client import RedisOps



logger = logging.getLogger(__name__)


class CaptchaStorage:
    """
    Redis-based captcha storage.

    Features:
    - 100x faster than SQLite (0.1ms vs 10ms)
    - No database locks
    - Automatic TTL expiration (no cleanup task needed)
    - Shared across all workers
    - Atomic verify-and-remove (prevents race conditions)
    """

    PREFIX = "captcha:"
    DEFAULT_TTL = 300  # 5 minutes

    def store(self, captcha_id: str, code: str, expires_in_seconds: int = 300) -> bool:
        """Store captcha with automatic expiration."""
        key = f"{self.PREFIX}{captcha_id}"
        code_upper = code.upper()
        success = RedisOps.set_with_ttl(key, code_upper, expires_in_seconds)
        captcha_preview = captcha_id[:8] + "..."
        if success:
            logger.debug("[Captcha] Stored: %s (code: %s, TTL: %ss)", captcha_preview, code_upper, expires_in_seconds)
        else:
            logger.error("[Captcha] Failed to store: %s (Redis may be unavailable)", captcha_preview)
        return success

    def get(self, captcha_id: str) -> Optional[Dict]:
        """Get captcha code."""
        key = f"{self.PREFIX}{captcha_id}"
        code = RedisOps.get(key)

        if code is None:
            return None

        ttl = RedisOps.get_ttl(key)
        expires_at = time.time() + ttl if ttl > 0 else time.time()

        return {
            "code": code,
            "expires": expires_at
        }

    def verify_and_remove(
        self,
        captcha_id: str,
        user_code: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify captcha code and remove it (one-time use).

        Uses atomic GET+DELETE to prevent race conditions.

        Returns:
            Tuple of (is_valid: bool, error_reason: Optional[str])
            error_reason: "not_found", "incorrect", or None if valid
        """
        key = f"{self.PREFIX}{captcha_id}"

        # Atomic get and delete using pipeline
        stored_code = RedisOps.get_and_delete(key)

        captcha_preview = captcha_id[:8] + "..."
        if stored_code is None:
            logger.warning("[Captcha] Not found: %s (key: %s)", captcha_preview, key)
            return False, "not_found"

        # Ensure stored_code is a string (should be with decode_responses=True)
        if not isinstance(stored_code, str):
            logger.error("[Captcha] Invalid stored code type: %s for %s", type(stored_code), captcha_preview)
            return False, "error"

        # Verify code (case-insensitive)
        stored_upper = stored_code.upper()
        user_upper = user_code.upper()
        is_valid = stored_upper == user_upper

        captcha_preview = captcha_id[:8] + "..."
        if is_valid:
            logger.debug("[Captcha] Verified: %s (code: %s)", captcha_preview, stored_upper)
            return True, None
        else:
            logger.warning(
                "[Captcha] Incorrect: %s (expected: %s, got: %s)",
                captcha_preview, stored_upper, user_upper
            )
            return False, "incorrect"

    def remove(self, captcha_id: str):
        """Remove a captcha code."""
        key = f"{self.PREFIX}{captcha_id}"
        RedisOps.delete(key)
        captcha_preview = captcha_id[:8] + "..."
        logger.debug("[Captcha] Removed: %s", captcha_preview)


class _CaptchaStorageSingleton:
    """Singleton wrapper for CaptchaStorage instance."""

    _instance: Optional[CaptchaStorage] = None

    @classmethod
    def get_instance(cls) -> CaptchaStorage:
        """Get the singleton captcha storage instance."""
        if cls._instance is None:
            cls._instance = CaptchaStorage()
            logger.info("[CaptchaStorage] Initialized (Redis)")
        return cls._instance


def get_captcha_storage() -> CaptchaStorage:
    """Get the global captcha storage instance."""
    return _CaptchaStorageSingleton.get_instance()
