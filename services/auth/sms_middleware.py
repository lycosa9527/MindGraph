"""
SMS Middleware Module

Middleware for SMS service requests with rate limiting, error handling,
and performance tracking.

Features:
- Rate limiting (concurrent request limits)
- QPM (Queries Per Minute) limiting
- Error handling
- Performance tracking

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, Tuple
import asyncio
import logging
import time

from config.settings import config
from models.domain.messages import Language
from services.infrastructure.rate_limiting.rate_limiter import DashscopeRateLimiter
from services.monitoring.performance_tracker import performance_tracker
from services.auth.sms_service import (
    SMSService,
    SMSServiceError,
    SMS_CODE_EXPIRY_MINUTES,
    SMS_RESEND_INTERVAL_SECONDS,
    SMS_MAX_ATTEMPTS_PER_PHONE,
    SMS_MAX_ATTEMPTS_WINDOW_HOURS
)


logger = logging.getLogger(__name__)


class SMSMiddleware:
    """
    Middleware for SMS service requests.

    Provides rate limiting, error handling, and performance tracking
    for SMS API calls to Tencent Cloud.
    """

    def __init__(
        self,
        max_concurrent_requests: Optional[int] = None,
        qpm_limit: Optional[int] = None,
        enable_rate_limiting: bool = True,
        enable_error_handling: bool = True,
        enable_performance_tracking: bool = True
    ):
        """
        Initialize SMS middleware.

        Args:
            max_concurrent_requests: Max concurrent SMS API requests (None = use config)
            qpm_limit: Queries per minute limit (None = use config)
            enable_rate_limiting: Enable rate limiting
            enable_error_handling: Enable error handling
            enable_performance_tracking: Enable performance metrics tracking
        """
        self.max_concurrent_requests = max_concurrent_requests or config.SMS_MAX_CONCURRENT_REQUESTS
        self.qpm_limit = qpm_limit or config.SMS_QPM_LIMIT
        # Enable rate limiting only if both parameter and config are True
        if enable_rate_limiting is None:
            self.enable_rate_limiting = config.SMS_RATE_LIMITING_ENABLED
        else:
            self.enable_rate_limiting = enable_rate_limiting and config.SMS_RATE_LIMITING_ENABLED
        self.enable_error_handling = enable_error_handling
        self.enable_performance_tracking = enable_performance_tracking

        # Initialize internal SMS service
        self._sms_service = SMSService()

        # Track active requests
        self._active_requests = 0
        self._request_lock = asyncio.Lock()

        # Create SMS-specific rate limiter
        self.rate_limiter = None
        if self.enable_rate_limiting:
            self.rate_limiter = DashscopeRateLimiter(
                qpm_limit=self.qpm_limit,
                concurrent_limit=self.max_concurrent_requests,
                enabled=True
            )
            logger.info(
                "[SMSMiddleware] Initialized with rate limiting: "
                "QPM=%s, Concurrent=%s",
                self.qpm_limit,
                self.max_concurrent_requests
            )
        else:
            logger.info(
                "[SMSMiddleware] Initialized without rate limiting: "
                "Concurrent=%s",
                self.max_concurrent_requests
            )

    @property
    def is_available(self) -> bool:
        """Check if SMS service is available"""
        return self._sms_service.is_available

    def generate_code(self) -> str:
        """Generate random verification code"""
        return self._sms_service.generate_code()

    @asynccontextmanager
    async def request_context(
        self,
        phone: str,
        purpose: str,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None
    ):
        """
        Context manager for SMS request lifecycle.

        Provides rate limiting, request tracking, and error handling.

        Args:
            phone: Phone number (masked in logs)
            purpose: SMS purpose ('register', 'login', 'reset_password')
            user_id: User ID for tracking
            organization_id: Organization ID for tracking

        Yields:
            Dict with request metadata and tracking info

        Example:
            async with sms_middleware.request_context(phone, purpose) as ctx:
                success, msg, code = await sms_middleware.send_verification_code(...)
        """
        request_start_time = time.time()
        request_id = f"sms_{purpose}_{int(time.time() * 1000)}"
        masked_phone = f"{phone[:3]}****{phone[-4:]}" if len(phone) >= 7 else "****"

        # Track active requests (for monitoring, even without rate limiter)
        async with self._request_lock:
            self._active_requests += 1
            logger.debug(
                "[SMSMiddleware] Request %s started "
                "(%s/%s active) "
                "for %s (%s)",
                request_id,
                self._active_requests,
                self.max_concurrent_requests,
                masked_phone,
                purpose
            )

        # Apply rate limiting if enabled
        if self.enable_rate_limiting and self.rate_limiter:
            try:
                async with self.rate_limiter:
                    try:
                        # Prepare context for request
                        ctx = {
                            'request_id': request_id,
                            'phone': phone,
                            'masked_phone': masked_phone,
                            'purpose': purpose,
                            'user_id': user_id,
                            'organization_id': organization_id,
                            'start_time': request_start_time
                        }

                        yield ctx

                        # Track successful request
                        duration = time.time() - request_start_time
                        if self.enable_performance_tracking:
                            self._track_performance(
                                duration=duration,
                                success=True,
                                error=None,
                                purpose=purpose
                            )

                        logger.debug(
                            "[SMSMiddleware] Request %s completed successfully "
                            "in %.2fs for %s",
                            request_id,
                            duration,
                            masked_phone
                        )

                    except Exception as e:
                        # Track failed request
                        duration = time.time() - request_start_time
                        if self.enable_performance_tracking:
                            self._track_performance(
                                duration=duration,
                                success=False,
                                error=str(e),
                                purpose=purpose
                            )

                        logger.error(
                            "[SMSMiddleware] Request %s failed "
                            "after %.2fs for %s: %s",
                            request_id,
                            duration,
                            masked_phone,
                            e,
                            exc_info=True
                        )

                        # Apply error handling if enabled
                        if self.enable_error_handling:
                            # Re-raise with SMS-specific error context
                            raise SMSServiceError(f"SMS request failed: {e}") from e
                        raise
                    finally:
                        # Decrement active requests
                        async with self._request_lock:
                            self._active_requests -= 1
                            logger.debug(
                                "[SMSMiddleware] Request %s completed "
                                "(%s/%s active)",
                                request_id,
                                self._active_requests,
                                self.max_concurrent_requests
                            )
            except Exception as e:
                logger.warning("[SMSMiddleware] Rate limiter acquisition failed: %s", e)
                # Decrement active requests on rate limiter failure
                async with self._request_lock:
                    self._active_requests -= 1
                if self.enable_error_handling:
                    raise SMSServiceError(
                        "SMS service temporarily unavailable due to rate limiting. "
                        "Please try again in a moment."
                    ) from e
                raise
        else:
            # No rate limiting - proceed directly
            try:
                # Prepare context for request
                ctx = {
                    'request_id': request_id,
                    'phone': phone,
                    'masked_phone': masked_phone,
                    'purpose': purpose,
                    'user_id': user_id,
                    'organization_id': organization_id,
                    'start_time': request_start_time
                }

                yield ctx

                # Track successful request
                duration = time.time() - request_start_time
                if self.enable_performance_tracking:
                    self._track_performance(
                        duration=duration,
                        success=True,
                        error=None,
                        purpose=purpose
                    )

                logger.debug(
                    "[SMSMiddleware] Request %s completed successfully "
                    "in %.2fs for %s",
                    request_id,
                    duration,
                    masked_phone
                )

            except Exception as e:
                # Track failed request
                duration = time.time() - request_start_time
                if self.enable_performance_tracking:
                    self._track_performance(
                        duration=duration,
                        success=False,
                        error=str(e),
                        purpose=purpose
                    )

                logger.error(
                    "[SMSMiddleware] Request %s failed "
                    "after %.2fs for %s: %s",
                    request_id,
                    duration,
                    masked_phone,
                    e,
                    exc_info=True
                )

                # Apply error handling if enabled
                if self.enable_error_handling:
                    # Re-raise with SMS-specific error context
                    raise SMSServiceError(f"SMS request failed: {e}") from e
                raise
            finally:
                # Decrement active requests
                async with self._request_lock:
                    self._active_requests -= 1
                    logger.debug(
                        "[SMSMiddleware] Request %s completed "
                        "(%s/%s active)",
                        request_id,
                        self._active_requests,
                        self.max_concurrent_requests
                    )

    async def send_verification_code(
        self,
        phone: str,
        purpose: str,
        code: Optional[str] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        lang: Language = "en"
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Send SMS verification code with middleware (recommended method).

        This method wraps the SMS service call with rate limiting and tracking.

        Args:
            phone: 11-digit Chinese mobile number
            purpose: 'register', 'login', or 'reset_password'
            code: Optional pre-generated code (will generate if not provided)
            user_id: User ID for tracking
            organization_id: Organization ID for tracking
            lang: Language code ('zh', 'en', or 'az') for error messages

        Returns:
            Tuple of (success, message, code_if_success)
        """
        async with self.request_context(phone, purpose, user_id, organization_id):
            return await self._sms_service.send_verification_code(phone, purpose, code, lang)

    async def send_alert(
        self,
        phones: list[str],
        lang: Language = "zh"
    ) -> Tuple[bool, str]:
        """
        Send SMS alert notification to multiple admin phones.

        Used for critical system alerts. Bypasses rate limiting for alerts.

        Args:
            phones: List of phone numbers (11-digit Chinese mobile numbers)
            lang: Language code ('zh', 'en', or 'az') for error messages

        Returns:
            Tuple of (success, message)
        """
        if not self.is_available:
            return False, "SMS service not available"

        return await self._sms_service.send_alert(phones, lang)

    async def send_notification(
        self,
        phones: list[str],
        template_id: str,
        template_params: Optional[list[str]] = None,
        lang: Language = "zh"
    ) -> Tuple[bool, str]:
        """
        Send SMS notification with custom template ID.

        Used for custom notifications (e.g., startup notifications, custom alerts).
        Bypasses rate limiting for notifications.

        Args:
            phones: List of phone numbers (11-digit Chinese mobile numbers)
            template_id: Tencent SMS template ID
            template_params: Optional list of template parameters (empty list if template has no params)
            lang: Language code ('zh', 'en', or 'az') for error messages

        Returns:
            Tuple of (success, message)
        """
        if not self.is_available:
            return False, "SMS service not available"

        return await self._sms_service.send_notification(phones, template_id, template_params, lang)

    def _track_performance(
        self,
        duration: float,
        success: bool,
        error: Optional[str] = None,
        purpose: Optional[str] = None
    ):
        """Track performance metrics for SMS requests."""
        try:
            # Use 'sms' as model name, append purpose for better tracking
            model_name = f"sms-{purpose}" if purpose else "sms"
            performance_tracker.record_request(
                model=model_name,
                duration=duration,
                success=success,
                error=error
            )
        except Exception as e:
            logger.debug("[SMSMiddleware] Performance tracking failed (non-critical): %s", e)

    def get_active_requests(self) -> int:
        """Get number of active SMS requests."""
        return self._active_requests

    def get_max_requests(self) -> int:
        """Get maximum concurrent SMS requests."""
        return self.max_concurrent_requests

    def get_rate_limiter_stats(self) -> Optional[Dict[str, Any]]:
        """Get rate limiter statistics if available."""
        if self.rate_limiter:
            return self.rate_limiter.get_stats()
        return None

    async def close(self):
        """Close SMS service (call on shutdown)"""
        await self._sms_service.close()


class _SMSMiddlewareSingleton:
    """Singleton holder for SMS middleware instance."""
    _instance: Optional[SMSMiddleware] = None

    @classmethod
    def get_instance(cls) -> SMSMiddleware:
        """Get singleton SMS middleware instance."""
        if cls._instance is None:
            cls._instance = SMSMiddleware()
        return cls._instance

    @classmethod
    def get_instance_if_exists(cls) -> Optional[SMSMiddleware]:
        """Get singleton instance if it exists, otherwise None."""
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing/shutdown)."""
        cls._instance = None


def get_sms_middleware() -> SMSMiddleware:
    """
    Get singleton SMS middleware instance.

    Returns:
        SMSMiddleware instance
    """
    return _SMSMiddlewareSingleton.get_instance()


def get_sms_service() -> SMSMiddleware:
    """
    Get SMS service (backward compatibility - returns middleware).

    The middleware now contains the SMS service functionality.
    Use get_sms_middleware() for new code.

    Returns:
        SMSMiddleware instance (which includes SMS service)
    """
    return get_sms_middleware()


async def shutdown_sms_service() -> None:
    """
    Shutdown SMS service (call on app shutdown)

    Closes the httpx async client properly.
    """
    instance = _SMSMiddlewareSingleton.get_instance_if_exists()
    if instance is not None:
        await instance.close()
        _SMSMiddlewareSingleton.reset_instance()
        logger.info("SMS service shut down")
