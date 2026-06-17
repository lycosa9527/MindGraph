"""
Email (SES) middleware — rate limiting and tracking for Tencent SES calls.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, Tuple

from config.settings import config
from models.domain.messages import Language
from services.auth.ses_service import SESService, SESServiceError
from services.infrastructure.rate_limiting.rate_limiter import DashscopeRateLimiter
from services.monitoring.performance_tracker import performance_tracker
from services.redis.redis_email_storage import mask_email_for_log
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)


class EmailMiddleware:
    """Middleware for Tencent SES verification email requests."""

    def __init__(
        self,
        max_concurrent_requests: Optional[int] = None,
        qpm_limit: Optional[int] = None,
        enable_rate_limiting: bool = True,
        enable_error_handling: bool = True,
        enable_performance_tracking: bool = True,
    ):
        """init  ."""
        self.max_concurrent_requests = max_concurrent_requests or config.EMAIL_MAX_CONCURRENT_REQUESTS
        self.qpm_limit = qpm_limit or config.EMAIL_QPM_LIMIT
        self.enable_rate_limiting = enable_rate_limiting and config.EMAIL_RATE_LIMITING_ENABLED
        self.enable_error_handling = enable_error_handling
        self.enable_performance_tracking = enable_performance_tracking

        self._ses_service = SESService()

        self._active_requests = 0
        self._request_lock = asyncio.Lock()

        self.rate_limiter = None
        if self.enable_rate_limiting:
            self.rate_limiter = DashscopeRateLimiter(
                qpm_limit=self.qpm_limit,
                concurrent_limit=self.max_concurrent_requests,
                enabled=True,
            )
            logger.info(
                "[EmailMiddleware] Initialized with rate limiting: QPM=%s, Concurrent=%s",
                self.qpm_limit,
                self.max_concurrent_requests,
            )
        else:
            logger.info(
                "[EmailMiddleware] Initialized without rate limiting: Concurrent=%s",
                self.max_concurrent_requests,
            )

    @property
    def is_available(self) -> bool:
        """Is available."""
        return self._ses_service.is_available

    def generate_code(self) -> str:
        """Generate code."""
        return self._ses_service.generate_code()

    @asynccontextmanager
    async def request_context(
        self,
        email: str,
        purpose: str,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
    ):
        """Request context."""
        request_start_time = time.time()
        request_id = f"email_{purpose}_{int(time.time() * 1000)}"
        masked = mask_email_for_log(email)

        async with self._request_lock:
            self._active_requests += 1
            logger.debug(
                "[EmailMiddleware] Request %s started (%s/%s active) for %s (%s)",
                request_id,
                self._active_requests,
                self.max_concurrent_requests,
                masked,
                purpose,
            )

        if self.enable_rate_limiting and self.rate_limiter:
            try:
                async with self.rate_limiter:
                    try:
                        ctx: Dict[str, Any] = {
                            "request_id": request_id,
                            "email": email,
                            "masked_email": masked,
                            "purpose": purpose,
                            "user_id": user_id,
                            "organization_id": organization_id,
                            "start_time": request_start_time,
                        }

                        yield ctx

                        duration = time.time() - request_start_time
                        if self.enable_performance_tracking:
                            self._track_performance(duration=duration, success=True, error=None, purpose=purpose)

                        logger.debug(
                            "[EmailMiddleware] Request %s completed successfully in %.2fs for %s",
                            request_id,
                            duration,
                            masked,
                        )

                    except BACKGROUND_INFRA_ERRORS as exc:
                        duration = time.time() - request_start_time
                        if self.enable_performance_tracking:
                            self._track_performance(
                                duration=duration,
                                success=False,
                                error=str(exc),
                                purpose=purpose,
                            )

                        logger.error(
                            "[EmailMiddleware] Request %s failed after %.2fs for %s: %s",
                            request_id,
                            duration,
                            masked,
                            exc,
                            exc_info=True,
                        )

                        if self.enable_error_handling:
                            raise SESServiceError(f"Email request failed: {exc}") from exc
                        raise
                    finally:
                        async with self._request_lock:
                            self._active_requests -= 1
                            logger.debug(
                                "[EmailMiddleware] Request %s completed (%s/%s active)",
                                request_id,
                                self._active_requests,
                                self.max_concurrent_requests,
                            )
            except BACKGROUND_INFRA_ERRORS as exc:
                logger.warning("[EmailMiddleware] Rate limiter acquisition failed: %s", exc)
                async with self._request_lock:
                    self._active_requests -= 1
                if self.enable_error_handling:
                    raise SESServiceError(
                        "Email service temporarily unavailable due to rate limiting. Please try again in a moment."
                    ) from exc
                raise
        else:
            try:
                ctx = {
                    "request_id": request_id,
                    "email": email,
                    "masked_email": masked,
                    "purpose": purpose,
                    "user_id": user_id,
                    "organization_id": organization_id,
                    "start_time": request_start_time,
                }

                yield ctx

                duration = time.time() - request_start_time
                if self.enable_performance_tracking:
                    self._track_performance(duration=duration, success=True, error=None, purpose=purpose)

                logger.debug(
                    "[EmailMiddleware] Request %s completed successfully in %.2fs for %s",
                    request_id,
                    duration,
                    masked,
                )

            except BACKGROUND_INFRA_ERRORS as exc:
                duration = time.time() - request_start_time
                if self.enable_performance_tracking:
                    self._track_performance(duration=duration, success=False, error=str(exc), purpose=purpose)

                logger.error(
                    "[EmailMiddleware] Request %s failed after %.2fs for %s: %s",
                    request_id,
                    duration,
                    masked,
                    exc,
                    exc_info=True,
                )

                if self.enable_error_handling:
                    raise SESServiceError(f"Email request failed: {exc}") from exc
                raise
            finally:
                async with self._request_lock:
                    self._active_requests -= 1
                    logger.debug(
                        "[EmailMiddleware] Request %s completed (%s/%s active)",
                        request_id,
                        self._active_requests,
                        self.max_concurrent_requests,
                    )

    async def send_verification_code(
        self,
        email: str,
        purpose: str,
        code: Optional[str] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        lang: Language = "en",
    ) -> Tuple[bool, str, Optional[str]]:
        """Send verification code."""
        async with self.request_context(email, purpose, user_id, organization_id):
            return await self._ses_service.send_verification_code(email, purpose, code, lang)

    def _track_performance(
        self,
        duration: float,
        success: bool,
        error: Optional[str] = None,
        purpose: Optional[str] = None,
    ) -> None:
        """Track performance."""
        try:
            model_name = f"email-{purpose}" if purpose else "email"
            performance_tracker.record_request(model=model_name, duration=duration, success=success, error=error)
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.debug("[EmailMiddleware] Performance tracking failed (non-critical): %s", exc)

    async def close(self) -> None:
        """Close."""
        await self._ses_service.close()


class _EmailMiddlewareSingleton:
    """_EmailMiddlewareSingleton helper."""

    instance: Optional[EmailMiddleware] = None

    @classmethod
    def get_instance(cls) -> EmailMiddleware:
        """Get instance."""
        if cls.instance is None:
            cls.instance = EmailMiddleware()
        return cls.instance


def get_email_middleware() -> EmailMiddleware:
    """Get email middleware."""
    return _EmailMiddlewareSingleton.get_instance()
