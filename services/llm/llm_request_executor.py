"""
LLM Request Executor
====================

Executes LLM API calls with rate limiting, retry logic, and error handling.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, List, Optional, Any, AsyncGenerator
import asyncio
import logging
import time

from services.infrastructure.http.error_handler import error_handler

logger = logging.getLogger(__name__)


class LLMRequestExecutor:
    """Executes LLM API requests with rate limiting and error handling."""

    @staticmethod
    async def execute_chat_request(
        client: Any,
        messages: List[Dict[str, Any]],
        rate_limiter: Optional[Any],
        timeout: float,
        model: str,
        actual_model: str,
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a chat completion request with rate limiting and retry logic.

        Args:
            client: LLM client instance
            messages: List of message dicts
            rate_limiter: Optional rate limiter instance
            timeout: Request timeout in seconds
            model: Logical model name (for logging)
            actual_model: Physical model name (for logging)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model-specific parameters

        Returns:
            Response dict with 'content' and 'usage' keys

        Raises:
            LLMServiceError: If request fails after retries
        """
        if rate_limiter:
            # Time rate limiter operations to diagnose delays
            rate_limit_start = time.time()
            async with rate_limiter:
                rate_limit_duration = time.time() - rate_limit_start
                # Always log rate limiter timing for Kimi to diagnose delays
                if model == 'kimi' or rate_limit_duration > 0.1:
                    logger.info(
                        "[LLMRequestExecutor] Rate limiter acquire: %.3fs for %s (%s)",
                        rate_limit_duration, model, actual_model
                    )

                # Execute with retry and timeout
                api_start = time.time()
                response = await LLMRequestExecutor._execute_api_call(
                    client=client,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    **kwargs
                )
                api_duration = time.time() - api_start
                # Always log API timing for Kimi to diagnose delays
                if model == 'kimi' or api_duration > 2.0:
                    logger.info(
                        "[LLMRequestExecutor] API call duration: %.2fs for %s (%s)",
                        api_duration, model, actual_model
                    )
        else:
            # No rate limiting
            response = await LLMRequestExecutor._execute_api_call(
                client=client,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                **kwargs
            )

        # Validate response
        return error_handler.validate_response(response)

    @staticmethod
    async def _execute_api_call(
        client: Any,
        messages: List[Dict[str, Any]],
        temperature: Optional[float],
        max_tokens: int,
        timeout: float,
        **kwargs
    ) -> Any:
        """
        Execute the actual API call with retry logic.

        Args:
            client: LLM client instance
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            timeout: Request timeout
            **kwargs: Additional parameters

        Returns:
            Raw API response
        """
        async def _call():
            # DeepSeek and Kimi use async_chat_completion
            if hasattr(client, 'async_chat_completion'):
                return await client.async_chat_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
            # Qwen and Hunyuan use chat_completion
            return await client.chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

        # Properly await with_retry inside timeout
        return await asyncio.wait_for(
            error_handler.with_retry(_call),
            timeout=timeout
        )

    @staticmethod
    async def execute_stream_request(
        client: Any,
        messages: List[Dict[str, Any]],
        rate_limiter: Optional[Any],
        model: str,
        actual_model: str,
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        enable_thinking: bool = False,
        yield_structured: bool = False,
        **kwargs
    ) -> AsyncGenerator[Any, None]:
        """
        Execute a streaming chat completion request.

        Args:
            client: LLM client instance
            messages: List of message dicts
            rate_limiter: Optional rate limiter instance
            model: Logical model name (for logging)
            actual_model: Physical model name (for logging)
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            enable_thinking: Enable thinking mode for reasoning models
            yield_structured: If True, yield dicts with 'type' key
            **kwargs: Additional model-specific parameters

        Yields:
            Chunks from streaming response (strings or dicts)
        """
        # Check if client supports streaming
        if hasattr(client, 'async_stream_chat_completion'):
            stream_method = client.async_stream_chat_completion
        elif hasattr(client, 'stream_chat_completion'):
            stream_method = client.stream_chat_completion
        else:
            # Fallback: client doesn't support streaming
            raise ValueError(
                f"Client for {model} does not support streaming"
            )

        # Apply rate limiting if available
        if rate_limiter:
            # Time rate limiter operations to diagnose delays
            rate_limit_start = time.time()
            async with rate_limiter:
                rate_limit_duration = time.time() - rate_limit_start
                # Log rate limiter timing for debugging
                if model == 'kimi' or rate_limit_duration > 0.1:
                    logger.info(
                        "[LLMRequestExecutor] Rate limiter acquire: %.3fs "
                        "for %s (%s) [stream]",
                        rate_limit_duration, model, actual_model
                    )

                # Stream with rate limiting applied
                async for chunk in stream_method(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    enable_thinking=enable_thinking,
                    **kwargs
                ):
                    # Handle usage chunks separately (always yield for tracking)
                    if isinstance(chunk, dict) and chunk.get('type') == 'usage':
                        yield chunk
                        continue
                    # Process other chunks
                    processed = LLMRequestExecutor._process_stream_chunk(
                        chunk, yield_structured
                    )
                    if processed is not None:
                        yield processed
        else:
            # Stream without rate limiting
            async for chunk in stream_method(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                enable_thinking=enable_thinking,
                **kwargs
            ):
                # Handle usage chunks separately (always yield for tracking)
                if isinstance(chunk, dict) and chunk.get('type') == 'usage':
                    yield chunk
                    continue
                # Process other chunks
                processed = LLMRequestExecutor._process_stream_chunk(
                    chunk, yield_structured
                )
                if processed is not None:
                    yield processed

    @staticmethod
    def _process_stream_chunk(
        chunk: Any,
        yield_structured: bool
    ) -> Any:
        """
        Process a stream chunk and format according to yield_structured flag.

        Args:
            chunk: Raw chunk from stream
            yield_structured: If True, yield structured dicts

        Returns:
            Formatted chunk (string or dict)
        """
        # Handle new format: chunk can be dict with 'type' and content/usage
        if isinstance(chunk, dict):
            chunk_type = chunk.get('type', 'token')
            if chunk_type == 'usage':
                # Usage data from final chunk
                if yield_structured:
                    return chunk
                # In non-structured mode, skip usage chunks
                return None
            elif chunk_type == 'thinking':
                # Yield thinking/reasoning content
                if yield_structured:
                    return chunk
                # In non-structured mode, thinking is discarded
                # (for backward compatibility with existing callers)
                return None
            elif chunk_type == 'token':
                # Yield content token
                content = chunk.get('content', '')
                if content:
                    if yield_structured:
                        return chunk
                    return content
                return None

        # Backward compatibility: plain string chunk
        return chunk
