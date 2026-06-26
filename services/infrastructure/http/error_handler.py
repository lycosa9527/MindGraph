"""LLM Error Handler.

Provides retry logic, exponential backoff, and error handling for LLM calls.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging
import random
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Base exception for LLM service errors."""


class UserDailyTokenCapExceededError(LLMServiceError):
    """Raised when an authenticated user exceeds the daily token budget."""

    def __init__(
        self,
        cap: int,
        used: int,
        user_message: Optional[str] = None,
    ):
        """Initialize with cap, current usage, and optional localized message."""
        self.cap = cap
        self.used = used
        self.user_message = user_message or (f"Daily token usage limit reached ({cap:,} tokens per day).")
        super().__init__(self.user_message)


class ThinkingCoinInsufficientError(LLMServiceError):
    """Raised when a trial user lacks thinking coins for an AI action."""

    def __init__(
        self,
        balance: int,
        cost: int,
        user_message: Optional[str] = None,
    ):
        self.balance = balance
        self.cost = cost
        self.user_message = user_message or (f"Insufficient thinking coins (balance {balance}, need {cost}).")
        super().__init__(self.user_message)


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

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        error_code: Optional[str] = None,
        user_message: Optional[str] = None,
    ):
        """init  ."""
        super().__init__(message)
        self.provider = provider
        self.error_code = error_code
        self.user_message = user_message


def attach_llm_user_message(exception: Exception, user_message: str) -> LLMProviderError:
    """Set user-facing text on provider errors before re-raising."""
    if isinstance(exception, LLMProviderError):
        exception.user_message = user_message
        return exception
    wrapped = LLMProviderError(str(exception), user_message=user_message)
    return wrapped


class LLMInvalidParameterError(LLMProviderError):
    """Raised when API parameters are invalid - DO NOT RETRY."""

    def __init__(
        self,
        message: str,
        parameter: Optional[str] = None,
        error_code: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        """init  ."""
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
        **kwargs,
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
                logger.debug("[ErrorHandler] Attempt %d/%d", attempt + 1, max_retries)
                result = await func(*args, **kwargs)

                if attempt > 0:
                    logger.info("[ErrorHandler] Succeeded on attempt %d", attempt + 1)

                return result

            except asyncio.TimeoutError as e:
                last_exception = LLMTimeoutError(f"Timeout on attempt {attempt + 1}: {e}")
                logger.warning("[ErrorHandler] %s", last_exception)

            except LLMContentFilterError as e:
                # Content filter - DO NOT RETRY
                logger.warning("[ErrorHandler] Content filter triggered, not retrying: %s", e)
                raise  # Re-raise immediately, no retry

            except (
                LLMInvalidParameterError,
                LLMQuotaExhaustedError,
                LLMModelNotFoundError,
                LLMAccessDeniedError,
            ) as e:
                # Parameter errors, quota exhausted, model not found,
                # access denied - DO NOT RETRY
                logger.warning(
                    "[ErrorHandler] Non-retryable error: %s - %s",
                    type(e).__name__,
                    e,
                )
                raise  # Re-raise immediately, no retry

            except LLMRateLimitError as e:
                # Rate limit - retry with longer delay
                last_exception = e
                logger.warning(
                    "[ErrorHandler] Rate limited on attempt %d/%d: %s",
                    attempt + 1,
                    max_retries,
                    e,
                )
                if attempt < max_retries - 1:
                    # Longer delays for rate limits: 5s, 10s, 20s
                    # Add jitter to prevent thundering herd (random 0-2s)
                    rate_limit_base_delay = min(5.0 * (2**attempt), 30.0)
                    jitter = random.uniform(0, 2.0)
                    delay = rate_limit_base_delay + jitter
                    logger.debug(
                        "[ErrorHandler] Rate limit retry in %.1fs (base: %.1fs + jitter: %.1fs)...",
                        delay,
                        rate_limit_base_delay,
                        jitter,
                    )
                    await asyncio.sleep(delay)
                continue  # Skip normal delay calculation

            except (
                LLMServiceError,
                OSError,
                ConnectionError,
                RuntimeError,
                ValueError,
                TypeError,
                AttributeError,
                KeyError,
                LookupError,
            ) as e:
                last_exception = e
                logger.warning("[ErrorHandler] Attempt %d failed: %s", attempt + 1, e)

            # Don't sleep after last attempt
            if attempt < max_retries - 1:
                # Exponential backoff: 1s, 2s, 4s, 8s, ...
                delay = min(base_delay * (2**attempt), max_delay)
                logger.debug("[ErrorHandler] Retrying in %.1fs...", delay)
                await asyncio.sleep(delay)

        # All retries failed
        error_msg = f"All {max_retries} attempts failed. Last error: {last_exception}"
        logger.error("[ErrorHandler] %s", error_msg)
        raise LLMServiceError(error_msg) from last_exception

    @staticmethod
    async def with_timeout(func: Callable, *args, timeout: float, **kwargs) -> Any:
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
            raise LLMTimeoutError(f"Operation exceeded timeout of {timeout}s") from exc

    @staticmethod
    def validate_response(response: Any, validator: Optional[Callable[[Any], bool]] = None) -> Any:
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
