"""
Redis SMS Verification Storage
==============================

High-performance SMS verification code storage using Redis.
Replaces SQLite for SMS verification to eliminate write contention.

Features:
- O(1) store, verify, delete operations
- Automatic TTL-based expiration (no cleanup needed)
- One-time use verification (atomic get-and-delete)
- Shared across all workers (accurate verification)

Key Schema:
- sms:verify:{phone} -> {code}:{expires_at}:{purpose}

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from services.redis_client import is_redis_available, get_redis, redis_ops

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
    - Verify: O(1) - GET + DEL atomic via pipeline
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
        success = redis_ops.set_with_ttl(key, code, ttl_seconds)
        
        if success:
            logger.info(f"[SMS] Code stored for {phone[:3]}***{phone[-4:]} (purpose: {purpose}, TTL: {ttl_seconds}s)")
        else:
            logger.error(f"[SMS] Failed to store code for {phone}")
        
        return success
    
    def verify_and_remove(
        self,
        phone: str,
        code: str,
        purpose: str = "verification"
    ) -> bool:
        """
        Verify SMS code and remove it (one-time use).
        
        Uses atomic GET+DELETE to prevent race conditions.
        
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
        
        key = self._get_key(phone, purpose)
        
        # Atomic get and delete
        stored_code = redis_ops.get_and_delete(key)
        
        if stored_code is None:
            logger.debug(f"[SMS] No code found for {phone[:3]}***{phone[-4:]} (purpose: {purpose})")
            return False
        
        if stored_code == code:
            logger.info(f"[SMS] Code verified for {phone[:3]}***{phone[-4:]} (purpose: {purpose})")
            return True
        else:
            logger.warning(f"[SMS] Invalid code for {phone[:3]}***{phone[-4:]} (purpose: {purpose})")
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
        return redis_ops.exists(key)
    
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
        return redis_ops.get(key)
    
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
        return redis_ops.get_ttl(key)
    
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
        return redis_ops.delete(key)


# Global singleton
_sms_storage: Optional[RedisSMSStorage] = None


def get_sms_storage() -> RedisSMSStorage:
    """Get or create global SMS storage instance."""
    global _sms_storage
    if _sms_storage is None:
        _sms_storage = RedisSMSStorage()
    return _sms_storage

