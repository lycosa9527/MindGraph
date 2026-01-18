from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
import json
import logging
import secrets

from services.redis.redis_client import is_redis_available, get_redis

"""
Dashboard Session Manager Service
==================================

Manages dashboard access sessions in Redis for passkey-protected public dashboard.
Simple session management without user accounts - just token verification.

Features:
- Create dashboard session tokens
- Verify session tokens
- Delete expired sessions
- Track session metadata (IP, created_at, expires_at)

Key Schema:
- dashboard:session:{token} -> JSON with {ip, created_at, expires_at} (TTL: 24 hours)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""



logger = logging.getLogger(__name__)

# Key prefix
SESSION_PREFIX = "dashboard:session:"

# Session TTL: 24 hours
SESSION_TTL_SECONDS = 24 * 3600


def _get_session_key(token: str) -> str:
    """Get Redis key for dashboard session."""
    return f"{SESSION_PREFIX}{token}"


class DashboardSessionManager:
    """
    Redis-based dashboard session manager.

    Thread-safe: All operations use Redis atomic commands.

    IMPORTANT: Redis is REQUIRED for dashboard sessions to work.
    - Session creation without Redis will generate tokens that cannot be verified
    - Session verification will reject all sessions when Redis is unavailable (fail-closed for security)
    - This ensures security: sessions are only valid when stored in Redis

    Behavior when Redis unavailable:
    - create_session() will generate a token but it cannot be verified
    - verify_session() will reject all sessions (fail-closed)
    - This prevents security issues but may cause confusion - ensure Redis is available
    """

    def __init__(self):
        """Initialize session manager."""
        pass

    def _use_redis(self) -> bool:
        """Check if Redis should be used."""
        return is_redis_available()

    def create_session(self, ip_address: str) -> str:
        """
        Create a new dashboard session.

        NOTE: Redis is REQUIRED for sessions to work. If Redis is unavailable,
        a token will be generated but it cannot be verified (verify_session will reject it).
        This is intentional fail-closed behavior for security.

        Args:
            ip_address: Client IP address

        Returns:
            Session token string (will be unusable if Redis unavailable)
        """
        if not self._use_redis():
            logger.warning(
                "[DashboardSession] Redis unavailable, creating in-memory "
                "session (WARNING: token will not be verifiable)"
            )
            # Generate token anyway for graceful degradation, but it won't be usable
            token = f"dashboard_{int(datetime.now(timezone.utc).timestamp())}_{secrets.token_hex(8)}"
            return token

        try:
            # Generate unique token
            timestamp = int(datetime.now(timezone.utc).timestamp())
            random_part = secrets.token_hex(8)
            token = f"dashboard_{timestamp}_{random_part}"

            # Create session data
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=SESSION_TTL_SECONDS)

            session_data = {
                "ip": ip_address,
                "created_at": now.isoformat(),
                "expires_at": expires_at.isoformat()
            }

            # Store in Redis with TTL
            session_key = _get_session_key(token)
            redis = get_redis()
            if redis:
                redis.setex(
                    session_key,
                    SESSION_TTL_SECONDS,
                    json.dumps(session_data)
                )
                token_preview = token[:20] + "..."
                logger.debug("[DashboardSession] Created session: %s", token_preview)

            return token

        except Exception as e:
            logger.error("[DashboardSession] Error creating session: %s", e)
            # Generate token anyway for graceful degradation
            token = f"dashboard_{int(datetime.now(timezone.utc).timestamp())}_{secrets.token_hex(8)}"
            return token

    def verify_session(self, token: str, client_ip: Optional[str] = None) -> bool:
        """
        Verify if a dashboard session token is valid.

        NOTE: Redis is REQUIRED. If Redis is unavailable, all sessions are rejected
        (fail-closed for security). This means sessions created without Redis cannot be verified.

        Args:
            token: Session token to verify
            client_ip: Optional client IP address for validation

        Returns:
            True if session is valid, False otherwise
        """
        if not token:
            return False

        if not self._use_redis():
            logger.warning("[DashboardSession] Redis unavailable, rejecting session (fail-closed for security)")
            return False  # Fail-closed for security - Redis is required

        try:
            session_key = _get_session_key(token)
            redis = get_redis()
            if not redis:
                logger.warning("[DashboardSession] Redis connection unavailable, rejecting session")
                return False  # Fail-closed

            session_data_str = redis.get(session_key)
            if not session_data_str:
                token_preview = token[:20] + "..."
                logger.debug("[DashboardSession] Session not found: %s", token_preview)
                return False

            # Parse session data
            try:
                session_data = json.loads(session_data_str)
                expires_at_str = session_data.get("expires_at")

                # Check expiration
                if expires_at_str:
                    expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
                    if datetime.now(timezone.utc) > expires_at:
                        token_preview = token[:20] + "..."
                        logger.debug("[DashboardSession] Session expired: %s", token_preview)
                        redis.delete(session_key)  # Clean up expired session
                        return False

                # Validate IP address if provided (lenient - only reject if both are present and don't match)
                if client_ip:
                    session_ip = session_data.get("ip")
                    # Only reject if both IPs are present and don't match
                    # This allows sessions created without IP to work, and handles proxy scenarios
                    if session_ip and client_ip and session_ip != client_ip:
                        logger.warning(
                            "[DashboardSession] IP mismatch: session IP %s != "
                            "client IP %s",
                            session_ip,
                            client_ip
                        )
                        return False

                return True

            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("[DashboardSession] Invalid session data format: %s", e)
                redis.delete(session_key)  # Clean up invalid session
                return False

        except Exception as e:
            logger.error("[DashboardSession] Error verifying session: %s", e)
            return False  # Fail-closed on errors

    def delete_session(self, token: str) -> bool:
        """
        Delete a dashboard session.

        Args:
            token: Session token to delete

        Returns:
            True if session was deleted, False otherwise
        """
        if not token:
            return False

        if not self._use_redis():
            return True  # Graceful degradation

        try:
            session_key = _get_session_key(token)
            redis = get_redis()
            if redis:
                deleted = redis.delete(session_key)
                token_preview = token[:20] + "..."
                logger.debug("[DashboardSession] Deleted session: %s", token_preview)
                return deleted > 0
            return False

        except Exception as e:
            logger.error("[DashboardSession] Error deleting session: %s", e)
            return False

    def get_session_info(self, token: str) -> Optional[Dict]:
        """
        Get session information.

        Args:
            token: Session token

        Returns:
            Session data dict or None if not found
        """
        if not token or not self._use_redis():
            return None

        try:
            session_key = _get_session_key(token)
            redis = get_redis()
            if not redis:
                return None

            session_data_str = redis.get(session_key)
            if not session_data_str:
                return None

            return json.loads(session_data_str)

        except Exception as e:
            logger.error("[DashboardSession] Error getting session info: %s", e)
            return None


# Global singleton instance
_session_manager: Optional[DashboardSessionManager] = None


def get_dashboard_session_manager() -> DashboardSessionManager:
    """Get global dashboard session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = DashboardSessionManager()
    return _session_manager



