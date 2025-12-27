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

import os
import secrets
import json
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta, timezone

from services.redis_client import is_redis_available, redis_ops, get_redis

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
    Graceful degradation: Falls back gracefully if Redis unavailable.
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
        
        Args:
            ip_address: Client IP address
            
        Returns:
            Session token string
        """
        if not self._use_redis():
            logger.warning("[DashboardSession] Redis unavailable, creating in-memory session")
            # Generate token anyway for graceful degradation
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
                logger.debug(f"[DashboardSession] Created session: {token[:20]}...")
            
            return token
            
        except Exception as e:
            logger.error(f"[DashboardSession] Error creating session: {e}")
            # Generate token anyway for graceful degradation
            token = f"dashboard_{int(datetime.now(timezone.utc).timestamp())}_{secrets.token_hex(8)}"
            return token
    
    def verify_session(self, token: str, client_ip: Optional[str] = None) -> bool:
        """
        Verify if a dashboard session token is valid.
        
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
            return False  # Fail-closed for security
        
        try:
            session_key = _get_session_key(token)
            redis = get_redis()
            if not redis:
                logger.warning("[DashboardSession] Redis connection unavailable, rejecting session")
                return False  # Fail-closed
            
            session_data_str = redis.get(session_key)
            if not session_data_str:
                logger.debug(f"[DashboardSession] Session not found: {token[:20]}...")
                return False
            
            # Parse session data
            try:
                session_data = json.loads(session_data_str)
                expires_at_str = session_data.get("expires_at")
                
                # Check expiration
                if expires_at_str:
                    expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
                    if datetime.now(timezone.utc) > expires_at:
                        logger.debug(f"[DashboardSession] Session expired: {token[:20]}...")
                        redis.delete(session_key)  # Clean up expired session
                        return False
                
                # Validate IP address if provided (lenient - only reject if both are present and don't match)
                if client_ip:
                    session_ip = session_data.get("ip")
                    # Only reject if both IPs are present and don't match
                    # This allows sessions created without IP to work, and handles proxy scenarios
                    if session_ip and client_ip and session_ip != client_ip:
                        logger.warning(f"[DashboardSession] IP mismatch: session IP {session_ip} != client IP {client_ip}")
                        return False
                
                return True
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"[DashboardSession] Invalid session data format: {e}")
                redis.delete(session_key)  # Clean up invalid session
                return False
                
        except Exception as e:
            logger.error(f"[DashboardSession] Error verifying session: {e}")
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
                logger.debug(f"[DashboardSession] Deleted session: {token[:20]}...")
                return deleted > 0
            return False
            
        except Exception as e:
            logger.error(f"[DashboardSession] Error deleting session: {e}")
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
            logger.error(f"[DashboardSession] Error getting session info: {e}")
            return None


# Global singleton instance
_session_manager: Optional[DashboardSessionManager] = None


def get_dashboard_session_manager() -> DashboardSessionManager:
    """Get global dashboard session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = DashboardSessionManager()
    return _session_manager



