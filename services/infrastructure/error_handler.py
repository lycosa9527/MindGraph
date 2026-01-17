"""LLM Error Handler.

Provides retry logic, exponential backoff, and error handling for LLM calls.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Any, Callable, Optional, TypeVar
import asyncio
import logging
import random


logger = logging.getLogger(__name__)

T = TypeVar('T')


class LLMServiceError(Exception):
    """Base exception for LLM service errors."""


class LLMTimeoutError(LLMServiceError):
    """Raised when LLM call times out."""


class LLMValidationError(LLMServiceError):
    """Raised when response doesn't match expected format."""


class LLMRateLimitError(LLMServiceError):
    """Raised when API rate limit is exceeded."""


class LLMContentFilterError(LLMServiceError):
    """Raised when content is flagged by safety filter - DO NOT RETRY."""


class LLMProviderError(LLMServiceError):
    """Raised for provider-specific errors with error code."""
    def __init__(self, message: str, provider: Optional[str] = None, error_code: Optional[str] = None):
        super().__init__(message)
        self.provider = provider
        self.error_code = error_code
        self.user_message: Optional[str] = None  # User-friendly error message


class LLMInvalidParameterError(LLMProviderError):
    """Raised when API parameters are invalid - DO NOT RETRY."""
    def __init__(
        self,
        message: str,
        parameter: Optional[str] = None,
        error_code: Optional[str] = None,
        provider: Optional[str] = None
    ):
        super().__init__(message, provider=provider, error_code=error_code)
        self.parameter = parameter


class LLMQuotaExhaustedError(LLMProviderError):
    """Raised when quota is exhausted - DO NOT RETRY."""


class LLMModelNotFoundError(LLMProviderError):
    """Raised when model doesn't exist - DO NOT RETRY."""


class LLMAccessDeniedError(LLMProviderError):
    """Raised when access is denied - DO NOT RETRY."""


class ErrorHandler:
    """
    Handles errors and retries for LLM API calls.
    """

    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BASE_DELAY = 1.0  # seconds
    DEFAULT_MAX_DELAY = 10.0  # seconds

    @staticmethod
    async def with_retry(
        func: Callable,
        *args,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
        **kwargs
    ) -> Any:
        """
        Execute async function with exponential backoff retry logic.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay between retries (seconds)
            max_delay: Maximum delay between retries (seconds)
            **kwargs: Keyword arguments for func

        Returns:
            Result from successful function call

        Raises:
            LLMServiceError: If all retries fail
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                logger.debug(
                    "[ErrorHandler] Attempt %d/%d",
                    attempt + 1,
                    max_retries
                )
                result = await func(*args, **kwargs)

                if attempt > 0:
                    logger.info(
                        "[ErrorHandler] Succeeded on attempt %d",
                        attempt + 1
                    )

                return result

            except asyncio.TimeoutError as e:
                last_exception = LLMTimeoutError(
                    f"Timeout on attempt {attempt + 1}: {e}"
                )
                logger.warning("[ErrorHandler] %s", last_exception)

            except LLMContentFilterError as e:
                # Content filter - DO NOT RETRY
                logger.warning(
                    "[ErrorHandler] Content filter triggered, not retrying: %s",
                    e
                )
                raise  # Re-raise immediately, no retry

            except (LLMInvalidParameterError, LLMQuotaExhaustedError,
                    LLMModelNotFoundError, LLMAccessDeniedError) as e:
                # Parameter errors, quota exhausted, model not found,
                # access denied - DO NOT RETRY
                logger.warning(
                    "[ErrorHandler] Non-retryable error: %s - %s",
                    e.__class__.__name__,
                    e
                )
                raise  # Re-raise immediately, no retry

            except LLMRateLimitError as e:
                # Rate limit - retry with longer delay
                last_exception = e
                logger.warning(
                    "[ErrorHandler] Rate limited on attempt %d/%d: %s",
                    attempt + 1,
                    max_retries,
                    e
                )
                if attempt < max_retries - 1:
                    # Longer delays for rate limits: 5s, 10s, 20s
                    # Add jitter to prevent thundering herd (random 0-2s)
                    rate_limit_base_delay = min(5.0 * (2 ** attempt), 30.0)
                    jitter = random.uniform(0, 2.0)
                    delay = rate_limit_base_delay + jitter
                    logger.debug(
                        "[ErrorHandler] Rate limit retry in %.1fs "
                        "(base: %.1fs + jitter: %.1fs)...",
                        delay,
                        rate_limit_base_delay,
                        jitter
                    )
                    await asyncio.sleep(delay)
                continue  # Skip normal delay calculation

            except Exception as e:
                last_exception = e
                logger.warning(
                    "[ErrorHandler] Attempt %d failed: %s",
                    attempt + 1,
                    e
                )

            # Don't sleep after last attempt
            if attempt < max_retries - 1:
                # Exponential backoff: 1s, 2s, 4s, 8s, ...
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.debug("[ErrorHandler] Retrying in %.1fs...", delay)
                await asyncio.sleep(delay)

        # All retries failed
        error_msg = (
            f"All {max_retries} attempts failed. "
            f"Last error: {last_exception}"
        )
        logger.error("[ErrorHandler] %s", error_msg)
        raise LLMServiceError(error_msg) from last_exception

    @staticmethod
    async def with_timeout(
        func: Callable,
        *args,
        timeout: float,
        **kwargs
    ) -> Any:
        """
        Execute async function with timeout.

        Args:
            func: Async function to execute
            *args: Positional arguments
            timeout: Timeout in seconds
            **kwargs: Keyword arguments

        Returns:
            Result from function

        Raises:
            LLMTimeoutError: If function exceeds timeout
        """
        try:
            # Await the coroutine inside wait_for
            coro = func(*args, **kwargs)
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise LLMTimeoutError(
                f"Operation exceeded timeout of {timeout}s"
            ) from exc

    @staticmethod
    def validate_response(
        response: Any,
        validator: Optional[Callable[[Any], bool]] = None
    ) -> Any:
        """
        Validate LLM response.

        Args:
            response: Response to validate
            validator: Optional custom validation function

        Returns:
            Validated response

        Raises:
            LLMValidationError: If validation fails
        """
        if response is None:
            raise LLMValidationError("Response is None")

        if isinstance(response, str) and len(response.strip()) == 0:
            raise LLMValidationError("Response is empty")

        if validator and not validator(response):
            raise LLMValidationError("Custom validation failed")

        return response


# Singleton instance
error_handler = ErrorHandler()
