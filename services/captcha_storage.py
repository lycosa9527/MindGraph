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

import logging
import time
from typing import Optional, Dict, Tuple

from services.redis_client import redis_ops

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
        success = redis_ops.set_with_ttl(key, code.upper(), expires_in_seconds)
        if success:
            logger.debug(f"[Captcha] Stored: {captcha_id[:8]}...")
        return success
    
    def get(self, captcha_id: str) -> Optional[Dict]:
        """Get captcha code."""
        key = f"{self.PREFIX}{captcha_id}"
        code = redis_ops.get(key)
        
        if code is None:
            return None
        
        ttl = redis_ops.get_ttl(key)
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
        stored_code = redis_ops.get_and_delete(key)
        
        if stored_code is None:
            logger.warning(f"[Captcha] Not found: {captcha_id[:8]}...")
            return False, "not_found"
        
        # Verify code (case-insensitive)
        is_valid = stored_code.upper() == user_code.upper()
        
        if is_valid:
            logger.debug(f"[Captcha] Verified: {captcha_id[:8]}...")
            return True, None
        else:
            logger.warning(
                f"[Captcha] Incorrect: {captcha_id[:8]}... "
                f"(expected: {stored_code}, got: {user_code})"
            )
            return False, "incorrect"
    
    def remove(self, captcha_id: str):
        """Remove a captcha code."""
        key = f"{self.PREFIX}{captcha_id}"
        redis_ops.delete(key)
        logger.debug(f"[Captcha] Removed: {captcha_id[:8]}...")


# Global singleton instance
_captcha_storage: Optional[CaptchaStorage] = None


def get_captcha_storage() -> CaptchaStorage:
    """Get the global captcha storage instance."""
    global _captcha_storage
    if _captcha_storage is None:
        _captcha_storage = CaptchaStorage()
        logger.info("[CaptchaStorage] Initialized (Redis)")
    return _captcha_storage
