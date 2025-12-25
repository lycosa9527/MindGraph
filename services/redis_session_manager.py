"""
Redis Session Manager Service
=============================

Manages user sessions in Redis for single-session control.
Ensures one account can only be logged in at one place at a time.

Features:
- Store active JWT token sessions
- Invalidate old sessions when new login occurs
- Track session invalidation notifications
- Validate session tokens on each request

Key Schema:
- session:user:{user_id} -> token_hash (TTL: JWT_EXPIRY_HOURS)
- session_invalidated:{user_id}:{old_token_hash} -> notification JSON (TTL: JWT_EXPIRY_HOURS)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
import hashlib
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from services.redis_client import is_redis_available, redis_ops, get_redis

logger = logging.getLogger(__name__)

# Key prefixes
SESSION_PREFIX = "session:user:"
SESSION_SET_PREFIX = "session:user:set:"  # For multiple concurrent sessions (bayi IP whitelist)
INVALIDATION_NOTIFICATION_PREFIX = "session_invalidated:"

# TTL matches JWT expiration (default: 24 hours)
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
SESSION_TTL_SECONDS = JWT_EXPIRY_HOURS * 3600


def _hash_token(token: str) -> str:
    """Generate SHA256 hash of token for secure storage."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _get_session_key(user_id: int) -> str:
    """Get Redis key for user session (single session mode)."""
    return f"{SESSION_PREFIX}{user_id}"

def _get_session_set_key(user_id: int) -> str:
    """Get Redis key for user session set (multiple concurrent sessions mode)."""
    return f"{SESSION_SET_PREFIX}{user_id}"


def _get_invalidation_notification_key(user_id: int, token_hash: str) -> str:
    """Get Redis key for invalidation notification."""
    return f"{INVALIDATION_NOTIFICATION_PREFIX}{user_id}:{token_hash}"


class RedisSessionManager:
    """
    Redis-based session manager for single-session control.
    
    Thread-safe: All operations use Redis atomic commands.
    Graceful degradation: Falls back gracefully if Redis unavailable.
    """
    
    def __init__(self):
        """Initialize session manager."""
        pass
    
    def _use_redis(self) -> bool:
        """Check if Redis should be used."""
        return is_redis_available()
    
    def store_session(self, user_id: int, token: str, allow_multiple: bool = False) -> bool:
        """
        Store active session for user.
        
        Args:
            user_id: User ID
            token: JWT token string
            allow_multiple: If True, allow multiple concurrent sessions (for shared accounts like bayi-ip@system.com)
            
        Returns:
            True if stored successfully, False otherwise
        """
        if not self._use_redis():
            logger.debug(f"[Session] Redis unavailable, skipping session storage for user {user_id}")
            return False
        
        try:
            token_hash = _hash_token(token)
            
            if allow_multiple:
                # Multiple concurrent sessions mode: Use Redis SET
                session_set_key = _get_session_set_key(user_id)
                redis = get_redis()
                if redis:
                    # Add token hash to set
                    redis.sadd(session_set_key, token_hash)
                    # Set TTL on the set
                    redis.expire(session_set_key, SESSION_TTL_SECONDS)
                    logger.debug(f"[Session] Added session to set for user {user_id} (multiple sessions allowed)")
                    return True
                return False
            else:
                # Single session mode: Use single key-value
                session_key = _get_session_key(user_id)
                success = redis_ops.set_with_ttl(session_key, token_hash, SESSION_TTL_SECONDS)
                
                if success:
                    logger.debug(f"[Session] Stored session for user {user_id} (TTL: {SESSION_TTL_SECONDS}s)")
                else:
                    logger.warning(f"[Session] Failed to store session for user {user_id}")
                
                return success
        except Exception as e:
            logger.error(f"[Session] Error storing session for user {user_id}: {e}", exc_info=True)
            return False
    
    def get_session_token(self, user_id: int) -> Optional[str]:
        """
        Get current active token hash for user.
        
        Args:
            user_id: User ID
            
        Returns:
            Token hash if session exists, None otherwise
        """
        if not self._use_redis():
            return None
        
        try:
            session_key = _get_session_key(user_id)
            token_hash = redis_ops.get(session_key)
            return token_hash
        except Exception as e:
            logger.error(f"[Session] Error getting session token for user {user_id}: {e}", exc_info=True)
            return None
    
    def delete_session(self, user_id: int, token: Optional[str] = None) -> bool:
        """
        Remove session for user (on logout).
        
        Args:
            user_id: User ID
            token: Optional token to remove (for multiple sessions mode). If None, removes all sessions.
            
        Returns:
            True if deleted successfully, False otherwise
        """
        if not self._use_redis():
            logger.debug(f"[Session] Redis unavailable, skipping session deletion for user {user_id}")
            return False
        
        try:
            redis = get_redis()
            if not redis:
                return False
            
            # Check multiple sessions mode first
            session_set_key = _get_session_set_key(user_id)
            if redis.exists(session_set_key):
                if token:
                    # Remove specific token from set
                    token_hash = _hash_token(token)
                    removed = redis.srem(session_set_key, token_hash)
                    logger.debug(f"[Session] Removed token from session set for user {user_id}")
                    return removed > 0
                else:
                    # Remove entire set
                    redis.delete(session_set_key)
                    logger.debug(f"[Session] Deleted session set for user {user_id}")
                    return True
            
            # Single session mode
            session_key = _get_session_key(user_id)
            success = redis_ops.delete(session_key)
            
            if success:
                logger.debug(f"[Session] Deleted session for user {user_id}")
            else:
                logger.debug(f"[Session] Session not found for user {user_id} (may have expired)")
            
            return success
        except Exception as e:
            logger.error(f"[Session] Error deleting session for user {user_id}: {e}", exc_info=True)
            return False
    
    def is_session_valid(self, user_id: int, token: str) -> bool:
        """
        Check if token matches active session.
        
        Supports both single session mode and multiple concurrent sessions mode.
        
        Args:
            user_id: User ID
            token: JWT token string
            
        Returns:
            True if session is valid, False otherwise
        """
        if not self._use_redis():
            # Graceful degradation: allow authentication if Redis unavailable
            logger.debug(f"[Session] Redis unavailable, allowing authentication for user {user_id}")
            return True
        
        try:
            token_hash = _hash_token(token)
            redis = get_redis()
            if not redis:
                return True  # Fail-open
            
            # Check multiple sessions mode first (for shared accounts)
            session_set_key = _get_session_set_key(user_id)
            if redis.exists(session_set_key):
                # Multiple sessions mode: Check if token hash is in set
                is_member = redis.sismember(session_set_key, token_hash)
                if is_member:
                    return True
                logger.debug(f"[Session] Token not found in session set for user {user_id}")
                return False
            
            # Check single session mode
            session_key = _get_session_key(user_id)
            stored_hash = redis_ops.get(session_key)
            
            if stored_hash is None:
                # Session doesn't exist (expired or invalidated)
                logger.debug(f"[Session] No active session found for user {user_id}")
                return False
            
            is_valid = stored_hash == token_hash
            if not is_valid:
                logger.debug(f"[Session] Token mismatch for user {user_id} (session invalidated)")
            
            return is_valid
        except Exception as e:
            logger.error(f"[Session] Error validating session for user {user_id}: {e}", exc_info=True)
            # Fail-open: allow authentication on error (backward compatibility)
            return True
    
    def invalidate_user_sessions(self, user_id: int, old_token_hash: Optional[str] = None, 
                                 ip_address: Optional[str] = None, allow_multiple: bool = False) -> bool:
        """
        Invalidate all sessions for user (called on new login).
        
        Args:
            user_id: User ID
            old_token_hash: Hash of old token (if exists) for notification
            ip_address: IP address of new login (for notification)
            allow_multiple: If True, don't invalidate (for shared accounts like bayi-ip@system.com)
            
        Returns:
            True if invalidated successfully, False otherwise
        """
        if allow_multiple:
            # For shared accounts, don't invalidate old sessions
            logger.debug(f"[Session] Multiple sessions allowed for user {user_id}, skipping invalidation")
            return True
        
        if not self._use_redis():
            logger.debug(f"[Session] Redis unavailable, skipping session invalidation for user {user_id}")
            return False
        
        try:
            redis = get_redis()
            if not redis:
                return False
            
            # Check multiple sessions mode first
            session_set_key = _get_session_set_key(user_id)
            if redis.exists(session_set_key):
                # Multiple sessions mode: Get all tokens and create notifications
                token_hashes = redis.smembers(session_set_key)
                for hash_val in token_hashes:
                    if old_token_hash is None:
                        old_token_hash = hash_val
                    self.create_invalidation_notification(
                        user_id,
                        hash_val,
                        ip_address=ip_address
                    )
                # Delete the entire set
                redis.delete(session_set_key)
                logger.info(f"[Session] Invalidated {len(token_hashes)} sessions for user {user_id} (multiple sessions mode)")
                return True
            
            # Single session mode
            session_key = _get_session_key(user_id)
            old_hash = redis_ops.get(session_key)
            
            if old_hash:
                # Create invalidation notification for old session
                if old_token_hash is None:
                    old_token_hash = old_hash
                
                self.create_invalidation_notification(
                    user_id, 
                    old_token_hash,
                    ip_address=ip_address
                )
                
                # Delete old session
                redis_ops.delete(session_key)
                logger.info(f"[Session] Invalidated session for user {user_id} (old token hash: {old_hash[:16]}...)")
            else:
                logger.debug(f"[Session] No existing session to invalidate for user {user_id}")
            
            return True
        except Exception as e:
            logger.error(f"[Session] Error invalidating sessions for user {user_id}: {e}", exc_info=True)
            return False
    
    def create_invalidation_notification(self, user_id: int, old_token_hash: str,
                                         ip_address: Optional[str] = None) -> bool:
        """
        Store notification that session was invalidated.
        
        Args:
            user_id: User ID
            old_token_hash: Hash of invalidated token
            ip_address: IP address of new login
            
        Returns:
            True if notification stored successfully, False otherwise
        """
        if not self._use_redis():
            return False
        
        try:
            notification_key = _get_invalidation_notification_key(user_id, old_token_hash)
            notification_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "ip_address": ip_address or "unknown"
            }
            
            success = redis_ops.set_with_ttl(
                notification_key,
                json.dumps(notification_data),
                SESSION_TTL_SECONDS
            )
            
            if success:
                logger.debug(f"[Session] Created invalidation notification for user {user_id}")
            
            return success
        except Exception as e:
            logger.error(f"[Session] Error creating invalidation notification: {e}", exc_info=True)
            return False
    
    def check_invalidation_notification(self, user_id: int, token_hash: str) -> Optional[Dict[str, Any]]:
        """
        Check if notification exists for token.
        
        Args:
            user_id: User ID
            token_hash: Hash of token to check
            
        Returns:
            Notification data if exists, None otherwise
        """
        if not self._use_redis():
            return None
        
        try:
            notification_key = _get_invalidation_notification_key(user_id, token_hash)
            notification_json = redis_ops.get(notification_key)
            
            if notification_json:
                return json.loads(notification_json)
            
            return None
        except Exception as e:
            logger.error(f"[Session] Error checking invalidation notification: {e}", exc_info=True)
            return None
    
    def clear_invalidation_notification(self, user_id: int, token_hash: str) -> bool:
        """
        Remove notification after user acknowledges.
        
        Args:
            user_id: User ID
            token_hash: Hash of token
            
        Returns:
            True if cleared successfully, False otherwise
        """
        if not self._use_redis():
            return False
        
        try:
            notification_key = _get_invalidation_notification_key(user_id, token_hash)
            success = redis_ops.delete(notification_key)
            
            if success:
                logger.debug(f"[Session] Cleared invalidation notification for user {user_id}")
            
            return success
        except Exception as e:
            logger.error(f"[Session] Error clearing invalidation notification: {e}", exc_info=True)
            return False


# Global instance
_session_manager = None


def get_session_manager() -> RedisSessionManager:
    """Get global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = RedisSessionManager()
    return _session_manager

