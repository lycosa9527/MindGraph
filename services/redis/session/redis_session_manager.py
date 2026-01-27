"""
Redis Session Manager Service
=============================

Manages user sessions in Redis with support for multiple concurrent sessions.
Allows up to MAX_CONCURRENT_SESSIONS devices to be logged in at the same time.

Features:
- Store active JWT token sessions (supports multiple concurrent sessions)
- Automatically remove oldest sessions when max is exceeded
- Track session invalidation notifications
- Validate session tokens on each request

Key Schema:
- session:user:set:{user_id} -> SET of token_hashes (TTL: JWT_EXPIRY_HOURS)
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
import time
from typing import Optional, Dict, Any
from datetime import datetime

from services.redis.redis_client import is_redis_available, RedisOps, get_redis

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

# Maximum concurrent sessions per user (default: 2 devices)
MAX_CONCURRENT_SESSIONS = int(os.getenv("MAX_CONCURRENT_SESSIONS", "2"))


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
    Redis-based session manager with support for multiple concurrent sessions.

    Thread-safe: All operations use Redis atomic commands.
    Graceful degradation: Falls back gracefully if Redis unavailable.
    """

    def __init__(self):
        """Initialize session manager."""
        pass

    def _use_redis(self) -> bool:
        """Check if Redis should be used."""
        return is_redis_available()

    def _parse_session_entry(self, session_entry: str) -> tuple[float, str, str]:
        """
        Parse a session entry string into its components.

        Supports two formats:
        - New format: timestamp:device_hash:token_hash
        - Legacy format: timestamp:token_hash (device_hash will be empty)

        Args:
            session_entry: Session entry string from Redis

        Returns:
            Tuple of (timestamp, device_hash, token_hash)
        """
        parts = session_entry.split(':')
        if len(parts) >= 3:
            # New format: timestamp:device_hash:token_hash
            try:
                timestamp = float(parts[0])
                device_hash = parts[1]
                token_hash = ':'.join(parts[2:])  # Handle token hashes that might contain ':'
                return timestamp, device_hash, token_hash
            except ValueError:
                # Invalid timestamp, treat as legacy
                pass

        if len(parts) == 2:
            # Legacy format: timestamp:token_hash
            try:
                timestamp = float(parts[0])
                return timestamp, "", parts[1]
            except ValueError:
                # Invalid timestamp
                return 0.0, "", session_entry

        # Unknown format
        return 0.0, "", session_entry

    def _revoke_existing_device_sessions(self, user_id: int, device_hash: str, redis, session_set_key: str) -> int:
        """
        Revoke any existing access token sessions for the same device.

        This prevents session accumulation when a user logs in multiple times
        from the same device. Each device should only have one active session.

        Uses Redis pipeline for atomic operations.

        Args:
            user_id: User ID
            device_hash: Device fingerprint hash
            redis: Redis connection
            session_set_key: Redis key for session set

        Returns:
            Number of sessions revoked
        """
        if not device_hash:
            return 0

        try:
            if not redis.exists(session_set_key):
                return 0

            all_sessions = redis.smembers(session_set_key)
            sessions_to_revoke = []

            for session_entry in all_sessions:
                _, entry_device_hash, _ = self._parse_session_entry(session_entry)
                if entry_device_hash == device_hash:
                    sessions_to_revoke.append(session_entry)

            if sessions_to_revoke:
                # Use pipeline for atomic removal
                pipe = redis.pipeline()
                for session_entry in sessions_to_revoke:
                    pipe.srem(session_set_key, session_entry)
                pipe.execute()
                logger.debug(
                    "[Session] Revoked %s old session(s) for device relogin: user=%s",
                    len(sessions_to_revoke), user_id
                )

            return len(sessions_to_revoke)

        except Exception as e:
            logger.error("[Session] Error revoking device sessions for user %s: %s", user_id, e, exc_info=True)
            return 0

    def store_session(self, user_id: int, token: str, device_hash: str = "", allow_multiple: bool = True) -> bool:
        """
        Store active session for user.

        Supports multiple concurrent sessions up to MAX_CONCURRENT_SESSIONS.
        When the limit is exceeded, oldest sessions are automatically removed.

        Uses Redis pipeline for atomic operations to prevent race conditions.

        Args:
            user_id: User ID
            token: JWT token string
            device_hash: Device fingerprint hash (for same-device session replacement)
            allow_multiple: If True (default), allow up to MAX_CONCURRENT_SESSIONS concurrent sessions

        Returns:
            True if stored successfully, False otherwise
        """
        # DEBUG: Log entry point with all parameters
        device_hash_preview = device_hash[:8] if device_hash else 'none'
        logger.info(
            "[Session] store_session called: user=%s, device_hash=%s..., allow_multiple=%s",
            user_id, device_hash_preview, allow_multiple
        )

        if not self._use_redis():
            logger.info("[Session] Redis unavailable, skipping session storage for user %s", user_id)
            return False

        try:
            token_hash = _hash_token(token)
            redis = get_redis()
            if not redis:
                logger.info("[Session] Redis connection failed for user %s", user_id)
                return False

            if allow_multiple:
                # Multiple concurrent sessions mode: Use Redis SET with timestamp tracking
                session_set_key = _get_session_set_key(user_id)

                # Clean up old single-key format if it exists (migration)
                old_session_key = _get_session_key(user_id)
                if redis.exists(old_session_key):
                    redis.delete(old_session_key)
                    logger.info("[Session] Migrated user %s from single-session to multi-session mode", user_id)

                # DEBUG: Log existing sessions before any operations
                existing_sessions_before = redis.smembers(session_set_key) if redis.exists(session_set_key) else set()
                logger.info(
                    "[Session] Before store: user=%s, existing_sessions=%s, max=%s",
                    user_id, len(existing_sessions_before), MAX_CONCURRENT_SESSIONS
                )
                for idx, sess in enumerate(existing_sessions_before):
                    ts, dh, th = self._parse_session_entry(sess)
                    device_preview = dh[:8] if dh else 'none'
                    token_preview = th[:8]
                    age_seconds = time.time() - ts
                    logger.debug(
                        "[Session]   Existing[%s]: device=%s..., token=%s..., age=%.0fs",
                        idx, device_preview, token_preview, age_seconds
                    )

                # Revoke any existing sessions from the same device first
                # This prevents session accumulation from repeated logins on the same device
                if device_hash:
                    revoked = self._revoke_existing_device_sessions(user_id, device_hash, redis, session_set_key)
                    device_preview = device_hash[:8]
                    logger.info(
                        "[Session] Revoked %s existing session(s) for same device: user=%s, device=%s...",
                        revoked, user_id, device_preview
                    )

                # Store token with timestamp and device hash for ordering and identification
                # Token format: timestamp:device_hash:token_hash
                current_time = time.time()
                token_entry = f"{current_time}:{device_hash}:{token_hash}"

                # Get existing sessions for cleanup
                all_sessions = redis.smembers(session_set_key) if redis.exists(session_set_key) else set()
                stale_sessions = []

                for session_entry in all_sessions:
                    entry_time, _, _ = self._parse_session_entry(session_entry)
                    if entry_time > 0 and current_time - entry_time > SESSION_TTL_SECONDS:
                        stale_sessions.append(session_entry)

                if stale_sessions:
                    logger.info(
                        "[Session] Found %s stale session(s) to cleanup for user %s",
                        len(stale_sessions), user_id
                    )

                # Use pipeline for atomic add + cleanup + TTL
                pipe = redis.pipeline()

                # Remove stale sessions
                for stale_entry in stale_sessions:
                    pipe.srem(session_set_key, stale_entry)

                # Add new token
                pipe.sadd(session_set_key, token_entry)

                # Set TTL
                pipe.expire(session_set_key, SESSION_TTL_SECONDS)

                # Get count after operations
                pipe.scard(session_set_key)

                # Execute pipeline atomically
                results = pipe.execute()
                session_count = results[-1]  # Last result is scard

                logger.info(
                    "[Session] After add: user=%s, session_count=%s, max=%s, stale_removed=%s",
                    user_id, session_count, MAX_CONCURRENT_SESSIONS, len(stale_sessions)
                )

                # Check if we exceed max concurrent sessions
                if session_count > MAX_CONCURRENT_SESSIONS:
                    logger.info(
                        "[Session] LIMIT EXCEEDED: user=%s, count=%s, max=%s - will remove oldest",
                        user_id, session_count, MAX_CONCURRENT_SESSIONS
                    )

                    # Get all sessions and sort by timestamp (oldest first)
                    all_sessions = redis.smembers(session_set_key)
                    # Sort by timestamp (entries are timestamp:device_hash:token_hash)
                    sorted_sessions = sorted(
                        all_sessions,
                        key=lambda x: self._parse_session_entry(x)[0]
                    )

                    # Use pipeline for atomic removal of excess sessions
                    sessions_to_remove = session_count - MAX_CONCURRENT_SESSIONS
                    old_sessions_to_notify = []

                    remove_pipe = redis.pipeline()
                    for i in range(sessions_to_remove):
                        old_session = sorted_sessions[i]
                        remove_pipe.srem(session_set_key, old_session)
                        # Collect token hashes for notifications
                        old_ts, old_dh, old_token_hash = self._parse_session_entry(old_session)
                        old_sessions_to_notify.append(old_token_hash)
                        old_device_preview = old_dh[:8] if old_dh else 'none'
                        old_token_preview = old_token_hash[:8]
                        old_age = current_time - old_ts
                        logger.info(
                            "[Session] Removing session[%s]: user=%s, device=%s..., token=%s..., age=%.0fs",
                            i, user_id, old_device_preview, old_token_preview, old_age
                        )

                    # Execute removals atomically
                    remove_pipe.execute()

                    # Create invalidation notifications (outside pipeline as they use different keys)
                    for old_token_hash in old_sessions_to_notify:
                        self.create_invalidation_notification(user_id, old_token_hash)
                        token_preview = old_token_hash[:8]
                        logger.info(
                            "[Session] Created invalidation notification: "
                            "user=%s, token=%s...",
                            user_id,
                            token_preview
                        )

                    session_count = MAX_CONCURRENT_SESSIONS

                final_device_preview = device_hash[:8] if device_hash else 'none'
                logger.info(
                    "[Session] store_session complete: user=%s, final_count=%s/%s, device=%s...",
                    user_id, session_count, MAX_CONCURRENT_SESSIONS, final_device_preview
                )
                return True
            else:
                # Single session mode: Use single key-value (legacy mode)
                session_key = _get_session_key(user_id)
                success = RedisOps.set_with_ttl(session_key, token_hash, SESSION_TTL_SECONDS)

                if success:
                    logger.debug("[Session] Stored session for user %s (TTL: %ss)", user_id, SESSION_TTL_SECONDS)
                else:
                    logger.warning("[Session] Failed to store session for user %s", user_id)

                return success
        except Exception as e:
            logger.error("[Session] Error storing session for user %s: %s", user_id, e, exc_info=True)
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
            token_hash = RedisOps.get(session_key)
            return token_hash
        except Exception as e:
            logger.error("[Session] Error getting session token for user %s: %s", user_id, e, exc_info=True)
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
        # DEBUG: Log entry point
        token_hint = _hash_token(token)[:8] if token else "all"
        logger.info("[Session] delete_session called: user=%s, token=%s...", user_id, token_hint)

        if not self._use_redis():
            logger.info("[Session] Redis unavailable, skipping session deletion for user %s", user_id)
            return False

        try:
            redis = get_redis()
            if not redis:
                logger.info("[Session] Redis connection failed for delete_session: user=%s", user_id)
                return False

            # Check multiple sessions mode first (default mode)
            session_set_key = _get_session_set_key(user_id)
            if redis.exists(session_set_key):
                existing_count = redis.scard(session_set_key)
                logger.info("[Session] delete_session: user=%s, existing_sessions=%s", user_id, existing_count)

                if token:
                    # Remove specific token from set
                    token_hash = _hash_token(token)
                    # Find and remove the entry containing this token hash
                    all_sessions = redis.smembers(session_set_key)
                    removed = False
                    for session_entry in all_sessions:
                        _, entry_device_hash, entry_token_hash = self._parse_session_entry(session_entry)
                        if entry_token_hash == token_hash:
                            redis.srem(session_set_key, session_entry)
                            removed = True
                            token_preview = token_hash[:8]
                            entry_device_preview = entry_device_hash[:8] if entry_device_hash else 'none'
                            logger.info(
                                "[Session] Removed specific token: user=%s, token=%s..., device=%s...",
                                user_id, token_preview, entry_device_preview
                            )
                            break
                    if not removed:
                        token_preview = token_hash[:8]
                        logger.info(
                            "[Session] Token not found in session set: "
                            "user=%s, token=%s...",
                            user_id,
                            token_preview
                        )
                    return removed
                else:
                    # Remove entire set
                    redis.delete(session_set_key)
                    logger.info("[Session] Deleted entire session set: user=%s, count_was=%s", user_id, existing_count)
                    return True
            else:
                logger.info("[Session] No session set found for user %s (may have expired)", user_id)

            # Single session mode (legacy)
            session_key = _get_session_key(user_id)
            success = RedisOps.delete(session_key)

            if success:
                logger.debug("[Session] Deleted session for user %s", user_id)
            else:
                logger.debug("[Session] Session not found for user %s (may have expired)", user_id)

            return success
        except Exception as e:
            logger.error("[Session] Error deleting session for user %s: %s", user_id, e, exc_info=True)
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
        token_hash = _hash_token(token)
        token_preview = token_hash[:8]
        logger.debug("[Session] is_session_valid called: user=%s, token=%s...", user_id, token_preview)

        if not self._use_redis():
            # Graceful degradation: allow authentication if Redis unavailable
            logger.info("[Session] Redis unavailable, allowing authentication (fail-open): user=%s", user_id)
            return True

        try:
            redis = get_redis()
            if not redis:
                logger.info("[Session] Redis connection failed, allowing authentication (fail-open): user=%s", user_id)
                return True  # Fail-open

            # Check multiple sessions mode first (default mode)
            session_set_key = _get_session_set_key(user_id)
            if redis.exists(session_set_key):
                # Multiple sessions mode: Check if token hash is in any session entry
                # Sessions are stored as timestamp:device_hash:token_hash
                all_sessions = redis.smembers(session_set_key)
                session_count = len(all_sessions)
                logger.debug("[Session] Validating token against %s session(s): user=%s", session_count, user_id)

                for idx, session_entry in enumerate(all_sessions):
                    entry_ts, entry_device_hash, entry_token_hash = self._parse_session_entry(session_entry)
                    age_seconds = time.time() - entry_ts if entry_ts > 0 else -1
                    entry_device_preview = entry_device_hash[:8] if entry_device_hash else 'none'
                    entry_token_preview = entry_token_hash[:8]
                    logger.debug(
                        "[Session]   Session[%s]: device=%s..., token=%s..., age=%.0fs",
                        idx, entry_device_preview, entry_token_preview, age_seconds
                    )
                    if entry_token_hash == token_hash:
                        # Extend session TTL on successful validation (sliding expiration)
                        redis.expire(session_set_key, SESSION_TTL_SECONDS)
                        logger.debug(
                            "[Session] Session VALID: user=%s, "
                            "matched session[%s], age=%.0fs, TTL extended",
                            user_id,
                            idx,
                            age_seconds
                        )
                        return True

                # Token not found in any session
                token_preview = token_hash[:8]
                logger.info(
                    "[Session] Session INVALID: user=%s, token=%s... not found in %s session(s)",
                    user_id, token_preview, session_count
                )
                return False
            else:
                logger.info("[Session] No session set exists for user %s, checking legacy mode...", user_id)

            # Check single session mode (legacy)
            session_key = _get_session_key(user_id)
            stored_hash = RedisOps.get(session_key)

            if stored_hash is None:
                # Session doesn't exist (expired or invalidated)
                logger.info("[Session] Session INVALID: user=%s, no session found (expired or never created)", user_id)
                return False

            is_valid = stored_hash == token_hash
            if is_valid:
                # Extend session TTL on successful validation (sliding expiration)
                redis.expire(session_key, SESSION_TTL_SECONDS)
                logger.info("[Session] Session VALID (legacy mode): user=%s, TTL extended", user_id)
            else:
                logger.info("[Session] Session INVALID (legacy mode): user=%s, token mismatch", user_id)

            return is_valid
        except Exception as e:
            logger.error("[Session] Error validating session for user %s: %s", user_id, e, exc_info=True)
            # Fail-open: allow authentication on error (backward compatibility)
            logger.info("[Session] Error occurred, allowing authentication (fail-open): user=%s", user_id)
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
            logger.debug("[Session] Multiple sessions allowed for user %s, skipping invalidation", user_id)
            return True

        if not self._use_redis():
            logger.debug("[Session] Redis unavailable, skipping session invalidation for user %s", user_id)
            return False

        try:
            redis = get_redis()
            if not redis:
                return False

            # Check multiple sessions mode first
            session_set_key = _get_session_set_key(user_id)
            if redis.exists(session_set_key):
                # Multiple sessions mode: Get all tokens and create notifications
                all_sessions = redis.smembers(session_set_key)
                for session_entry in all_sessions:
                    # Extract token hash from timestamp:device_hash:token_hash format
                    _, _, actual_token_hash = self._parse_session_entry(session_entry)
                    self.create_invalidation_notification(
                        user_id,
                        actual_token_hash,
                        ip_address=ip_address
                    )
                # Delete the entire set
                redis.delete(session_set_key)
                logger.info(
                    "[Session] Invalidated %s sessions for user %s (multiple sessions mode)",
                    len(all_sessions), user_id
                )
                return True

            # Single session mode
            session_key = _get_session_key(user_id)
            old_hash = RedisOps.get(session_key)

            if old_hash:
                # Create invalidation notification for old session
                if old_token_hash is None:
                    old_token_hash = old_hash

                if old_token_hash:
                    self.create_invalidation_notification(
                        user_id,
                        old_token_hash,
                        ip_address=ip_address
                    )

                # Delete old session
                RedisOps.delete(session_key)
                old_hash_preview = old_hash[:16]
                logger.info(
                    "[Session] Invalidated session for user %s "
                    "(old token hash: %s...)",
                    user_id,
                    old_hash_preview
                )
            else:
                logger.debug("[Session] No existing session to invalidate for user %s", user_id)

            return True
        except Exception as e:
            logger.error("[Session] Error invalidating sessions for user %s: %s", user_id, e, exc_info=True)
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

            success = RedisOps.set_with_ttl(
                notification_key,
                json.dumps(notification_data),
                SESSION_TTL_SECONDS
            )

            if success:
                logger.debug("[Session] Created invalidation notification for user %s", user_id)

            return success
        except Exception as e:
            logger.error("[Session] Error creating invalidation notification: %s", e, exc_info=True)
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
            notification_json = RedisOps.get(notification_key)

            if notification_json:
                return json.loads(notification_json)

            return None
        except Exception as e:
            logger.error("[Session] Error checking invalidation notification: %s", e, exc_info=True)
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
            success = RedisOps.delete(notification_key)

            if success:
                logger.debug("[Session] Cleared invalidation notification for user %s", user_id)

            return success
        except Exception as e:
            logger.error("[Session] Error clearing invalidation notification: %s", e, exc_info=True)
            return False


# ============================================================================
# Refresh Token Storage
# ============================================================================

# Key prefixes for refresh tokens
REFRESH_TOKEN_PREFIX = "refresh:"
REFRESH_TOKEN_USER_SET_PREFIX = "refresh:user:"
REFRESH_TOKEN_LOOKUP_PREFIX = "refresh:lookup:"  # Reverse lookup: token_hash -> user_id


class RefreshTokenManager:
    """
    Redis-based refresh token manager with device binding and audit logging.

    Key Schema:
    - refresh:{user_id}:{token_hash} -> JSON{created_at, ip_address, user_agent, device_hash}
    - refresh:user:{user_id} -> SET of token_hashes (for revoke-all)
    - refresh:lookup:{token_hash} -> user_id (reverse lookup for refresh without access token)

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

    def _get_lookup_key(self, token_hash: str) -> str:
        """Get Redis key for reverse lookup (token_hash -> user_id)."""
        return f"{REFRESH_TOKEN_LOOKUP_PREFIX}{token_hash}"

    def find_user_id_from_token(self, token_hash: str) -> Optional[int]:
        """
        Find user_id from refresh token hash (reverse lookup).

        This allows the refresh endpoint to work without the access token cookie.

        Args:
            token_hash: SHA256 hash of the refresh token

        Returns:
            User ID if found, None otherwise
        """
        if not self._use_redis():
            return None

        try:
            lookup_key = self._get_lookup_key(token_hash)
            user_id_str = RedisOps.get(lookup_key)
            if user_id_str:
                return int(user_id_str)
            return None
        except Exception as e:
            logger.error("[RefreshToken] Error finding user_id from token hash: %s", e, exc_info=True)
            return None

    def _revoke_existing_device_tokens(self, user_id: int, device_hash: str) -> int:
        """
        Revoke any existing refresh tokens for the same device.

        This prevents token accumulation when a user logs in multiple times
        from the same device. Each device should only have one active refresh token.

        Args:
            user_id: User ID
            device_hash: Device fingerprint hash

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
            token_hashes = redis.smembers(user_tokens_key)

            revoked = 0
            for existing_token_hash in token_hashes:
                token_key = self._get_token_key(user_id, existing_token_hash)
                token_json = RedisOps.get(token_key)
                if token_json:
                    try:
                        token_data = json.loads(token_json)
                        if token_data.get("device_hash") == device_hash:
                            # Same device - revoke old token
                            self.revoke_refresh_token(user_id, existing_token_hash, reason="device_relogin")
                            revoked += 1
                    except json.JSONDecodeError:
                        pass

            if revoked > 0:
                logger.debug("[TokenAudit] Revoked %s old token(s) for device relogin: user=%s", revoked, user_id)

            return revoked

        except Exception as e:
            logger.error("[RefreshToken] Error revoking device tokens for user %s: %s", user_id, e, exc_info=True)
            return 0

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

            # Revoke any existing tokens from the same device first
            # This prevents token accumulation from repeated logins on the same device
            self._revoke_existing_device_tokens(user_id, device_hash)

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
            RedisOps.set_with_ttl(
                token_key,
                json.dumps(token_data),
                REFRESH_TOKEN_TTL_SECONDS
            )

            # Add to user's token set (for revoke-all)
            redis.sadd(user_tokens_key, token_hash)
            redis.expire(user_tokens_key, REFRESH_TOKEN_TTL_SECONDS)

            # Store reverse lookup: token_hash -> user_id (for refresh without access token)
            lookup_key = self._get_lookup_key(token_hash)
            RedisOps.set_with_ttl(lookup_key, str(user_id), REFRESH_TOKEN_TTL_SECONDS)

            # Enforce max concurrent sessions limit on refresh tokens
            self.enforce_max_tokens(user_id)

            logger.info(
                "[TokenAudit] Refresh token created: user=%s, ip=%s, "
                "device=%s",
                user_id,
                ip_address,
                device_hash
            )
            return True

        except Exception as e:
            logger.error("[RefreshToken] Error storing refresh token for user %s: %s", user_id, e, exc_info=True)
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
        token_preview = token_hash[:8]
        current_device_preview = current_device_hash[:8] if current_device_hash else 'none'
        logger.info(
            "[RefreshToken] validate_refresh_token called: user=%s, token=%s..., current_device=%s..., strict=%s",
            user_id, token_preview, current_device_preview, strict_device_check
        )

        if not self._use_redis():
            logger.info("[RefreshToken] Redis unavailable, cannot validate refresh token")
            return False, None, "Redis unavailable"

        try:
            token_key = self._get_token_key(user_id, token_hash)
            token_json = RedisOps.get(token_key)

            if not token_json:
                token_preview = token_hash[:8]
                logger.info(
                    "[RefreshToken] INVALID - token not found in Redis: "
                    "user=%s, token=%s...",
                    user_id,
                    token_preview
                )
                return False, None, "Invalid or expired refresh token"

            token_data = json.loads(token_json)
            stored_device_hash = token_data.get("device_hash", "")
            created_at = token_data.get("created_at", "unknown")
            ip_address = token_data.get("ip_address", "unknown")

            stored_device_preview = stored_device_hash[:8] if stored_device_hash else 'none'
            logger.info(
                "[RefreshToken] Token found: user=%s, stored_device=%s..., created=%s, ip=%s",
                user_id, stored_device_preview, created_at, ip_address
            )

            # Check device binding
            if current_device_hash and strict_device_check:
                if stored_device_hash and stored_device_hash != current_device_hash:
                    logger.info(
                        "[RefreshToken] DEVICE MISMATCH: user=%s, stored_device=%s, current_device=%s",
                        user_id, stored_device_hash, current_device_hash
                    )
                    return False, token_data, "Device mismatch"
                elif not stored_device_hash:
                    logger.info("[RefreshToken] No stored device hash, skipping device check: user=%s", user_id)

            token_preview = token_hash[:8]
            logger.info("[RefreshToken] VALID: user=%s, token=%s...", user_id, token_preview)
            return True, token_data, None

        except Exception as e:
            logger.error("[RefreshToken] Error validating refresh token for user %s: %s", user_id, e, exc_info=True)
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
            lookup_key = self._get_lookup_key(token_hash)

            # Delete the token
            deleted = RedisOps.delete(token_key)

            # Remove from user's token set
            redis.srem(user_tokens_key, token_hash)

            # Delete reverse lookup
            RedisOps.delete(lookup_key)

            if deleted:
                logger.info("[TokenAudit] Token revoked: user=%s, reason=%s", user_id, reason)

            return deleted

        except Exception as e:
            logger.error("[RefreshToken] Error revoking refresh token for user %s: %s", user_id, e, exc_info=True)
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
                logger.debug("[RefreshToken] No refresh tokens to revoke for user %s", user_id)
                return 0

            # Delete each token and its reverse lookup
            count = 0
            for token_hash in token_hashes:
                token_key = self._get_token_key(user_id, token_hash)
                lookup_key = self._get_lookup_key(token_hash)
                if RedisOps.delete(token_key):
                    count += 1
                # Also delete reverse lookup
                RedisOps.delete(lookup_key)

            # Delete the user's token set
            redis.delete(user_tokens_key)

            logger.info("[TokenAudit] All tokens revoked: user=%s, count=%s, reason=%s", user_id, count, reason)
            return count

        except Exception as e:
            logger.error("[RefreshToken] Error revoking all refresh tokens for user %s: %s", user_id, e, exc_info=True)
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
            logger.error("[RefreshToken] Error counting tokens for user %s: %s", user_id, e, exc_info=True)
            return 0

    def enforce_max_tokens(self, user_id: int) -> int:
        """
        Enforce MAX_CONCURRENT_SESSIONS limit on refresh tokens.

        If user has more refresh tokens than allowed, revoke the oldest ones.

        Args:
            user_id: User ID

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
            token_count = redis.scard(user_tokens_key)

            if token_count <= MAX_CONCURRENT_SESSIONS:
                return 0

            # Get all token hashes and their creation times
            token_hashes = redis.smembers(user_tokens_key)
            tokens_with_time = []

            for token_hash in token_hashes:
                token_key = self._get_token_key(user_id, token_hash)
                token_json = RedisOps.get(token_key)
                if token_json:
                    try:
                        token_data = json.loads(token_json)
                        created_at = token_data.get("created_at", "")
                        tokens_with_time.append((token_hash, created_at))
                    except json.JSONDecodeError:
                        # Invalid JSON, mark for removal
                        tokens_with_time.append((token_hash, ""))
                else:
                    # Token expired but still in set, mark for cleanup
                    redis.srem(user_tokens_key, token_hash)

            # Sort by creation time (oldest first)
            tokens_with_time.sort(key=lambda x: x[1])

            # Revoke oldest tokens to stay within limit
            tokens_to_revoke = len(tokens_with_time) - MAX_CONCURRENT_SESSIONS
            revoked = 0

            for i in range(tokens_to_revoke):
                if i < len(tokens_with_time):
                    token_hash = tokens_with_time[i][0]
                    if self.revoke_refresh_token(user_id, token_hash, reason="max_devices_exceeded"):
                        revoked += 1

            if revoked > 0:
                logger.info(
                    "[TokenAudit] Enforced max tokens: user=%s, revoked=%s, limit=%s",
                    user_id, revoked, MAX_CONCURRENT_SESSIONS
                )

            return revoked

        except Exception as e:
            logger.error("[RefreshToken] Error enforcing max tokens for user %s: %s", user_id, e, exc_info=True)
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

