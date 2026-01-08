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

# TTL for access token sessions (1 hour with refresh tokens)
ACCESS_TOKEN_EXPIRY_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRY_MINUTES", "60"))
SESSION_TTL_SECONDS = ACCESS_TOKEN_EXPIRY_MINUTES * 60

# TTL for refresh tokens (7 days)
REFRESH_TOKEN_EXPIRY_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRY_DAYS", "7"))
REFRESH_TOKEN_TTL_SECONDS = REFRESH_TOKEN_EXPIRY_DAYS * 24 * 3600


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


# ============================================================================
# Refresh Token Storage
# ============================================================================

# Key prefixes for refresh tokens
REFRESH_TOKEN_PREFIX = "refresh:"
REFRESH_TOKEN_USER_SET_PREFIX = "refresh:user:"


class RefreshTokenManager:
    """
    Redis-based refresh token manager with device binding and audit logging.
    
    Key Schema:
    - refresh:{user_id}:{token_hash} -> JSON{created_at, ip_address, user_agent, device_hash}
    - refresh:user:{user_id} -> SET of token_hashes (for revoke-all)
    
    All tokens auto-expire via Redis TTL.
    """
    
    def __init__(self):
        """Initialize refresh token manager."""
        pass
    
    def _use_redis(self) -> bool:
        """Check if Redis should be used."""
        return is_redis_available()
    
    def _get_token_key(self, user_id: int, token_hash: str) -> str:
        """Get Redis key for a specific refresh token."""
        return f"{REFRESH_TOKEN_PREFIX}{user_id}:{token_hash}"
    
    def _get_user_tokens_key(self, user_id: int) -> str:
        """Get Redis key for user's token set."""
        return f"{REFRESH_TOKEN_USER_SET_PREFIX}{user_id}"
    
    def store_refresh_token(
        self, 
        user_id: int, 
        token_hash: str,
        ip_address: str,
        user_agent: str,
        device_hash: str
    ) -> bool:
        """
        Store a refresh token with device binding.
        
        Args:
            user_id: User ID
            token_hash: SHA256 hash of the refresh token
            ip_address: Client IP address
            user_agent: Client User-Agent header
            device_hash: Device fingerprint hash
            
        Returns:
            True if stored successfully, False otherwise
        """
        if not self._use_redis():
            logger.warning("[RefreshToken] Redis unavailable, cannot store refresh token")
            return False
        
        try:
            redis = get_redis()
            if not redis:
                return False
            
            token_key = self._get_token_key(user_id, token_hash)
            user_tokens_key = self._get_user_tokens_key(user_id)
            
            # Token data with device binding
            token_data = {
                "created_at": datetime.utcnow().isoformat(),
                "ip_address": ip_address,
                "user_agent": user_agent[:200],  # Truncate to prevent bloat
                "device_hash": device_hash
            }
            
            # Store token with TTL
            redis_ops.set_with_ttl(
                token_key, 
                json.dumps(token_data), 
                REFRESH_TOKEN_TTL_SECONDS
            )
            
            # Add to user's token set (for revoke-all)
            redis.sadd(user_tokens_key, token_hash)
            redis.expire(user_tokens_key, REFRESH_TOKEN_TTL_SECONDS)
            
            logger.info(f"[TokenAudit] Refresh token created: user={user_id}, ip={ip_address}, device={device_hash}")
            return True
            
        except Exception as e:
            logger.error(f"[RefreshToken] Error storing refresh token for user {user_id}: {e}", exc_info=True)
            return False
    
    def validate_refresh_token(
        self, 
        user_id: int, 
        token_hash: str,
        current_device_hash: Optional[str] = None,
        strict_device_check: bool = True
    ) -> tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Validate a refresh token and check device binding.
        
        Args:
            user_id: User ID
            token_hash: SHA256 hash of the refresh token
            current_device_hash: Current device fingerprint (for device binding check)
            strict_device_check: If True, reject on device mismatch. If False, log warning only.
            
        Returns:
            Tuple of (is_valid, token_data, error_message)
        """
        if not self._use_redis():
            logger.warning("[RefreshToken] Redis unavailable, cannot validate refresh token")
            return False, None, "Redis unavailable"
        
        try:
            token_key = self._get_token_key(user_id, token_hash)
            token_json = redis_ops.get(token_key)
            
            if not token_json:
                logger.warning(f"[TokenAudit] Refresh failed - invalid token: user={user_id}")
                return False, None, "Invalid or expired refresh token"
            
            token_data = json.loads(token_json)
            
            # Check device binding
            if current_device_hash and strict_device_check:
                stored_device_hash = token_data.get("device_hash")
                if stored_device_hash and stored_device_hash != current_device_hash:
                    logger.warning(
                        f"[TokenAudit] Device mismatch on refresh: user={user_id}, "
                        f"stored={stored_device_hash}, current={current_device_hash}"
                    )
                    return False, token_data, "Device mismatch"
            
            return True, token_data, None
            
        except Exception as e:
            logger.error(f"[RefreshToken] Error validating refresh token for user {user_id}: {e}", exc_info=True)
            return False, None, "Validation error"
    
    def revoke_refresh_token(self, user_id: int, token_hash: str, reason: str = "logout") -> bool:
        """
        Revoke a single refresh token.
        
        Args:
            user_id: User ID
            token_hash: SHA256 hash of the refresh token
            reason: Reason for revocation (for audit logging)
            
        Returns:
            True if revoked successfully, False otherwise
        """
        if not self._use_redis():
            return False
        
        try:
            redis = get_redis()
            if not redis:
                return False
            
            token_key = self._get_token_key(user_id, token_hash)
            user_tokens_key = self._get_user_tokens_key(user_id)
            
            # Delete the token
            deleted = redis_ops.delete(token_key)
            
            # Remove from user's token set
            redis.srem(user_tokens_key, token_hash)
            
            if deleted:
                logger.info(f"[TokenAudit] Token revoked: user={user_id}, reason={reason}")
            
            return deleted
            
        except Exception as e:
            logger.error(f"[RefreshToken] Error revoking refresh token for user {user_id}: {e}", exc_info=True)
            return False
    
    def revoke_all_refresh_tokens(self, user_id: int, reason: str = "security") -> int:
        """
        Revoke all refresh tokens for a user.
        
        Args:
            user_id: User ID
            reason: Reason for revocation (for audit logging)
            
        Returns:
            Number of tokens revoked
        """
        if not self._use_redis():
            return 0
        
        try:
            redis = get_redis()
            if not redis:
                return 0
            
            user_tokens_key = self._get_user_tokens_key(user_id)
            
            # Get all token hashes for user
            token_hashes = redis.smembers(user_tokens_key)
            
            if not token_hashes:
                logger.debug(f"[RefreshToken] No refresh tokens to revoke for user {user_id}")
                return 0
            
            # Delete each token
            count = 0
            for token_hash in token_hashes:
                token_key = self._get_token_key(user_id, token_hash)
                if redis_ops.delete(token_key):
                    count += 1
            
            # Delete the user's token set
            redis.delete(user_tokens_key)
            
            logger.info(f"[TokenAudit] All tokens revoked: user={user_id}, count={count}, reason={reason}")
            return count
            
        except Exception as e:
            logger.error(f"[RefreshToken] Error revoking all refresh tokens for user {user_id}: {e}", exc_info=True)
            return 0
    
    def get_user_token_count(self, user_id: int) -> int:
        """Get the number of active refresh tokens for a user."""
        if not self._use_redis():
            return 0
        
        try:
            redis = get_redis()
            if not redis:
                return 0
            
            user_tokens_key = self._get_user_tokens_key(user_id)
            return redis.scard(user_tokens_key)
            
        except Exception as e:
            logger.error(f"[RefreshToken] Error counting tokens for user {user_id}: {e}", exc_info=True)
            return 0
    
    def rotate_refresh_token(
        self, 
        user_id: int, 
        old_token_hash: str,
        new_token_hash: str,
        ip_address: str,
        user_agent: str,
        device_hash: str
    ) -> bool:
        """
        Rotate a refresh token (revoke old, create new).
        
        This is called after a successful token refresh to issue a new refresh token.
        Helps detect token theft (if old token is reused, it won't exist).
        
        Args:
            user_id: User ID
            old_token_hash: Hash of the old refresh token (to revoke)
            new_token_hash: Hash of the new refresh token
            ip_address: Client IP address
            user_agent: Client User-Agent header
            device_hash: Device fingerprint hash
            
        Returns:
            True if rotation successful, False otherwise
        """
        # First revoke the old token
        self.revoke_refresh_token(user_id, old_token_hash, reason="rotation")
        
        # Then store the new token
        return self.store_refresh_token(
            user_id=user_id,
            token_hash=new_token_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            device_hash=device_hash
        )


# Global instances
_session_manager = None
_refresh_token_manager = None


def get_session_manager() -> RedisSessionManager:
    """Get global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = RedisSessionManager()
    return _session_manager


def get_refresh_token_manager() -> RefreshTokenManager:
    """Get global refresh token manager instance."""
    global _refresh_token_manager
    if _refresh_token_manager is None:
        _refresh_token_manager = RefreshTokenManager()
    return _refresh_token_manager

