"""
LLM Error Handler
=================

Provides retry logic, exponential backoff, and error handling for LLM calls.

@author lycosa9527
@made_by MindSpring Team
"""

import asyncio
import logging
from typing import Callable, Any, Optional, TypeVar
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


class LLMServiceError(Exception):
    """Base exception for LLM service errors."""
    pass


class LLMTimeoutError(LLMServiceError):
    """Raised when LLM call times out."""
    pass


class LLMValidationError(LLMServiceError):
    """Raised when response doesn't match expected format."""
    pass


class LLMRateLimitError(LLMServiceError):
    """Raised when API rate limit is exceeded."""
    pass


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
                logger.debug(f"[ErrorHandler] Attempt {attempt + 1}/{max_retries}")
                result = await func(*args, **kwargs)
                
                if attempt > 0:
                    logger.info(f"[ErrorHandler] Succeeded on attempt {attempt + 1}")
                
                return result
                
            except asyncio.TimeoutError as e:
                last_exception = LLMTimeoutError(f"Timeout on attempt {attempt + 1}: {e}")
                logger.warning(f"[ErrorHandler] {last_exception}")
                
            except Exception as e:
                last_exception = e
                logger.warning(f"[ErrorHandler] Attempt {attempt + 1} failed: {e}")
            
            # Don't sleep after last attempt
            if attempt < max_retries - 1:
                # Exponential backoff: 1s, 2s, 4s, 8s, ...
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.debug(f"[ErrorHandler] Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)
        
        # All retries failed
        error_msg = f"All {max_retries} attempts failed. Last error: {last_exception}"
        logger.error(f"[ErrorHandler] {error_msg}")
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
        except asyncio.TimeoutError:
            raise LLMTimeoutError(f"Operation exceeded timeout of {timeout}s")
    
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


