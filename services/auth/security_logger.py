"""
Security Event Logger
=====================

Centralized security event logging for audit trails.

Logs security-relevant events with consistent format for monitoring and analysis.
All events are prefixed with [Security] for easy filtering in log aggregators.

Events logged:
- Authentication (login success/failure, logout)
- Authorization (access denied, role violations)
- Rate limiting (exceeded limits)
- Input validation (oversized requests, malicious input)
- Session management (token refresh, session invalidation)

Usage:
    from services.security_logger import security_log

    security_log.auth_success(user_id=123, method='password', ip='1.2.3.4')
    security_log.auth_failure(phone='138****1234', reason='invalid_password', ip='1.2.3.4')
    security_log.rate_limit_exceeded(identifier='user:123', endpoint='/api/generate', ip='1.2.3.4')

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional
import logging


logger = logging.getLogger(__name__)


class SecurityLogger:
    """
    Centralized security event logger.

    Provides structured logging for security events with consistent format.
    All events include timestamp, event type, and relevant context.
    """

    # Event type constants
    AUTH_SUCCESS = "AUTH_SUCCESS"
    AUTH_FAILURE = "AUTH_FAILURE"
    LOGOUT = "LOGOUT"
    TOKEN_REFRESH = "TOKEN_REFRESH"
    SESSION_INVALIDATED = "SESSION_INVALIDATED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    ACCESS_DENIED = "ACCESS_DENIED"
    INPUT_VALIDATION_FAILED = "INPUT_VALIDATION_FAILED"
    SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY"

    def _log(self, level: int, event_type: str, message: str, **context):
        """Internal logging method with consistent format."""
        # Build context string
        context_str = ", ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        full_message = f"[Security] [{event_type}] {message}"
        if context_str:
            full_message += f" | {context_str}"
        logger.log(level, full_message)

    def auth_success(
        self,
        user_id: int,
        method: str = "password",
        ip: Optional[str] = None,
        phone: Optional[str] = None,
        org: Optional[str] = None
    ):
        """Log successful authentication."""
        # Mask phone for privacy
        masked_phone = f"{phone[:3]}****{phone[-4:]}" if phone and len(phone) >= 7 else phone
        self._log(
            logging.INFO,
            self.AUTH_SUCCESS,
            "User authenticated successfully",
            user_id=user_id,
            method=method,
            phone=masked_phone,
            org=org,
            ip=ip
        )

    def auth_failure(
        self,
        reason: str,
        ip: Optional[str] = None,
        phone: Optional[str] = None,
        attempts_remaining: Optional[int] = None
    ):
        """Log failed authentication attempt."""
        masked_phone = f"{phone[:3]}****{phone[-4:]}" if phone and len(phone) >= 7 else phone
        self._log(
            logging.WARNING,
            self.AUTH_FAILURE,
            f"Authentication failed: {reason}",
            phone=masked_phone,
            attempts_remaining=attempts_remaining,
            ip=ip
        )

    def logout(
        self,
        user_id: int,
        ip: Optional[str] = None
    ):
        """Log user logout."""
        self._log(
            logging.INFO,
            self.LOGOUT,
            "User logged out",
            user_id=user_id,
            ip=ip
        )

    def token_refresh(
        self,
        user_id: int,
        ip: Optional[str] = None
    ):
        """Log token refresh."""
        self._log(
            logging.DEBUG,  # Debug level since this happens frequently
            self.TOKEN_REFRESH,
            "Token refreshed",
            user_id=user_id,
            ip=ip
        )

    def session_invalidated(
        self,
        user_id: int,
        reason: str = "logout",
        ip: Optional[str] = None
    ):
        """Log session invalidation."""
        self._log(
            logging.INFO,
            self.SESSION_INVALIDATED,
            f"Session invalidated: {reason}",
            user_id=user_id,
            ip=ip
        )

    def rate_limit_exceeded(
        self,
        identifier: str,
        endpoint: str,
        ip: Optional[str] = None,
        limit: Optional[int] = None
    ):
        """Log rate limit exceeded."""
        self._log(
            logging.WARNING,
            self.RATE_LIMIT_EXCEEDED,
            f"Rate limit exceeded for {endpoint}",
            identifier=identifier,
            limit=limit,
            ip=ip
        )

    def access_denied(
        self,
        user_id: Optional[int],
        resource: str,
        reason: str = "insufficient_permissions",
        ip: Optional[str] = None
    ):
        """Log access denied event."""
        self._log(
            logging.WARNING,
            self.ACCESS_DENIED,
            f"Access denied to {resource}: {reason}",
            user_id=user_id,
            ip=ip
        )

    def input_validation_failed(
        self,
        field: str,
        reason: str,
        ip: Optional[str] = None,
        value_size: Optional[int] = None
    ):
        """Log input validation failure (potential attack)."""
        self._log(
            logging.WARNING,
            self.INPUT_VALIDATION_FAILED,
            f"Input validation failed for {field}: {reason}",
            value_size=value_size,
            ip=ip
        )

    def suspicious_activity(
        self,
        description: str,
        ip: Optional[str] = None,
        user_id: Optional[int] = None,
        **extra_context
    ):
        """Log suspicious activity for investigation."""
        self._log(
            logging.WARNING,
            self.SUSPICIOUS_ACTIVITY,
            description,
            user_id=user_id,
            ip=ip,
            **extra_context
        )


# Global singleton instance
security_log = SecurityLogger()
