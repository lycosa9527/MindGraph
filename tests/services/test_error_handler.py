"""
Unit Tests for Error Handler
=============================

@author lycosa9527
@made_by MindSpring Team
"""

import pytest
import asyncio
from services.error_handler import (
    error_handler,
    LLMServiceError,
    LLMTimeoutError,
    LLMValidationError
)


class TestErrorHandler:
    """Test suite for ErrorHandler."""
    
    @pytest.mark.asyncio
    async def test_with_retry_success(self):
        """Test successful retry."""
        call_count = 0
        
        async def success_after_2_tries():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return "Success"
        
        result = await error_handler.with_retry(
            success_after_2_tries,
            max_retries=3,
            base_delay=0.1
        )
        
        assert result == "Success"
        assert call_count == 2
        print(f"Succeeded after {call_count} attempts")
    
    @pytest.mark.asyncio
    async def test_with_retry_all_fail(self):
        """Test that all retries fail."""
        async def always_fail():
            raise Exception("Always fails")
        
        with pytest.raises(LLMServiceError):
            await error_handler.with_retry(
                always_fail,
                max_retries=2,
                base_delay=0.1
            )
    
    @pytest.mark.asyncio
    async def test_with_timeout_success(self):
        """Test successful execution within timeout."""
        async def quick_function():
            await asyncio.sleep(0.1)
            return "Done"
        
        result = await error_handler.with_timeout(
            quick_function,
            timeout=1.0
        )
        
        assert result == "Done"
    
    @pytest.mark.asyncio
    async def test_with_timeout_failure(self):
        """Test timeout when function takes too long."""
        async def slow_function():
            await asyncio.sleep(2.0)
            return "Done"
        
        with pytest.raises(LLMTimeoutError):
            await error_handler.with_timeout(
                slow_function,
                timeout=0.5
            )
    
    def test_validate_response_success(self):
        """Test response validation with valid response."""
        response = "Valid response"
        validated = error_handler.validate_response(response)
        assert validated == response
    
    def test_validate_response_none(self):
        """Test response validation with None."""
        with pytest.raises(LLMValidationError):
            error_handler.validate_response(None)
    
    def test_validate_response_empty(self):
        """Test response validation with empty string."""
        with pytest.raises(LLMValidationError):
            error_handler.validate_response("")
    
    def test_validate_response_custom_validator(self):
        """Test response validation with custom validator."""
        def custom_validator(resp):
            return "success" in resp.lower()
        
        # Valid response
        validated = error_handler.validate_response(
            "Success!",
            validator=custom_validator
        )
        assert validated == "Success!"
        
        # Invalid response
        with pytest.raises(LLMValidationError):
            error_handler.validate_response(
                "Failure!",
                validator=custom_validator
            )


