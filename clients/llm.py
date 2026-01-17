from typing import Dict, List, Optional, Any, AsyncGenerator, Union
import asyncio
import json
import logging
import os
import re

from openai import AsyncOpenAI, RateLimitError, APIStatusError
import httpx

"""
LLM Clients for Hybrid Agent Processing

This module provides async interfaces for Qwen LLM clients
used by diagram agents for layout optimization and style enhancement.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from config.settings import config
from services.infrastructure.error_handler import (
    LLMRateLimitError,
    LLMContentFilterError,
    LLMProviderError,
    LLMInvalidParameterError,
    LLMQuotaExhaustedError,
    LLMModelNotFoundError,
    LLMAccessDeniedError,
    LLMTimeoutError
)
from services.llm.dashscope_error_parser import parse_and_raise_dashscope_error
from services.llm.doubao_error_parser import parse_and_raise_doubao_error
from services.llm.hunyuan_error_parser import parse_and_raise_hunyuan_error

# Note: Environment variables are loaded by config.settings module
logger = logging.getLogger(__name__)


# ============================================================================
# SHARED HTTPX CLIENT MANAGER
# ============================================================================

class HTTPXClientManager:
    """
    Manages shared httpx AsyncClient instances for LLM providers.

    Benefits:
    - HTTP/2 multiplexing for concurrent requests
    - Connection pooling across requests
    - Lazy initialization (clients created on first use)
    - Proper cleanup on shutdown
    """

    _instance: Optional['HTTPXClientManager'] = None

    def __init__(self):
        self._clients: Dict[str, httpx.AsyncClient] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> 'HTTPXClientManager':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def get_client(
        self,
        provider: str,
        base_url: str,
        timeout: float = 60.0,
        stream_timeout: float = 120.0
    ) -> httpx.AsyncClient:
        """
        Get or create an httpx AsyncClient for a provider.

        Args:
            provider: Provider identifier (e.g., 'dashscope', 'volcengine')
            base_url: Base URL for the provider API
            timeout: Default timeout for non-streaming requests
            stream_timeout: Timeout for streaming requests (longer for thinking models)

        Returns:
            Shared httpx.AsyncClient instance
        """
        async with self._lock:
            if provider not in self._clients or self._clients[provider].is_closed:
                self._clients[provider] = httpx.AsyncClient(
                    base_url=base_url,
                    timeout=httpx.Timeout(
                        timeout,
                        connect=10.0,
                        read=stream_timeout  # Longer read timeout for streaming
                    ),
                    http2=True,  # Enable HTTP/2 for better multiplexing
                    limits=httpx.Limits(
                        max_connections=100,
                        max_keepalive_connections=20,
                        keepalive_expiry=30.0
                    )
                )
                logger.debug(f"[HTTPXClientManager] Created client for {provider}")
            return self._clients[provider]

    async def close_all(self):
        """Close all client connections. Call on app shutdown."""
        async with self._lock:
            for provider, client in self._clients.items():
                if not client.is_closed:
                    await client.aclose()
                    logger.debug(f"[HTTPXClientManager] Closed client for {provider}")
            self._clients.clear()


# Global httpx client manager instance
_httpx_manager: Optional[HTTPXClientManager] = None


def get_httpx_manager() -> HTTPXClientManager:
    """Get the global httpx client manager."""
    global _httpx_manager
    if _httpx_manager is None:
        _httpx_manager = HTTPXClientManager.get_instance()
    return _httpx_manager


async def close_httpx_clients():
    """Close all httpx clients. Call on app shutdown."""
    global _httpx_manager
    if _httpx_manager is not None:
        await _httpx_manager.close_all()


class QwenClient:
    """Async client for Qwen LLM API using httpx with HTTP/2 support."""

    def __init__(self, model_type='classification'):
        """
        Initialize QwenClient with specific model type

        Args:
            model_type (str): 'classification' for qwen-plus-latest, 'generation' for qwen-plus
        """
        self.api_url = config.QWEN_API_URL
        self.api_key = config.QWEN_API_KEY
        self.timeout = 30  # seconds
        self.stream_timeout = 120  # Longer timeout for streaming (thinking models)
        self.model_type = model_type
        # DIVERSITY FIX: Use higher temperature for generation to increase variety
        self.default_temperature = 0.9 if model_type == 'generation' else 0.7

    async def chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 1000,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        presence_penalty: Optional[float] = None,
        stop: Optional[Union[str, List[str]]] = None,
        seed: Optional[int] = None,
        n: Optional[int] = None,
        logprobs: Optional[bool] = None,
        top_logprobs: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:  # type: ignore[return-value]
        """
        Send chat completion request to Qwen (async version).

        Args:
            messages: List of message dictionaries with 'role' and 'content'.
                     Supports multimodal content:
                     - Text: {"role": "user", "content": "text"}
                     - Image: {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "..."}}]}
                     - Video: {"role": "user", "content": [{"type": "video", "video": ["url1", "url2"]}]}
                     - Mixed: {"role": "user", "content": [{"type": "text", "text": "..."}, {"type": "image_url", ...}]}
            temperature: Sampling temperature (0.0 to 2.0), None uses default
            max_tokens: Maximum tokens in response
            top_p: Nucleus sampling threshold (0.0 to 1.0)
            top_k: Top-k sampling (via extra_body, DashScope-specific)
            presence_penalty: Repetition control (-2.0 to 2.0)
            stop: Stop sequences (string or list of strings)
            seed: Random seed for reproducibility (0 to 2^31-1)
            n: Number of completions to generate (1-4, only for qwen-plus, Qwen3 non-thinking)
            logprobs: Whether to return token log probabilities
            top_logprobs: Number of top logprobs to return (0-5, requires logprobs=True)
            **kwargs: Additional parameters:
                - tools: Function calling tools array
                - tool_choice: Tool selection strategy
                - parallel_tool_calls: Enable parallel tool calls
                - response_format: JSON mode ({"type": "json_object"} or {"type": "json_schema"})
                - enable_search: Web search (DashScope-specific, via extra_body)
                - search_options: Search configuration (DashScope-specific, via extra_body)
                - vl_high_resolution_images: High-res image processing (DashScope-specific, via extra_body)
                - modalities: Output modalities for Qwen-Omni ["text", "audio"] (DashScope-specific, via extra_body)
                - audio: Audio output config for Qwen-Omni (DashScope-specific, via extra_body)
                - enable_code_interpreter: Code interpreter (DashScope-specific, via extra_body)
                - thinking_budget: Limit thinking length (DashScope-specific, via extra_body)

        Returns:
            Dict with 'content' and 'usage' keys (or list of dicts if n > 1).
            If tool_calls are present, includes 'tool_calls' key.
        """
        try:
            # Use instance default if not specified
            if temperature is None:
                temperature = self.default_temperature

            # Select appropriate model based on task type
            if self.model_type == 'classification':
                model_name = config.QWEN_MODEL_CLASSIFICATION
            else:  # generation
                model_name = config.QWEN_MODEL_GENERATION

            # Build extra_body for DashScope-specific parameters
            extra_body: Dict[str, Any] = {"enable_thinking": False}

            # Add DashScope-specific parameters to extra_body
            if top_k is not None:
                extra_body["top_k"] = top_k
            if "enable_search" in kwargs:
                extra_body["enable_search"] = kwargs.pop("enable_search")
            if "search_options" in kwargs:
                extra_body["search_options"] = kwargs.pop("search_options")
            if "vl_high_resolution_images" in kwargs:
                extra_body["vl_high_resolution_images"] = kwargs.pop("vl_high_resolution_images")
            if "modalities" in kwargs:
                extra_body["modalities"] = kwargs.pop("modalities")
            if "audio" in kwargs:
                extra_body["audio"] = kwargs.pop("audio")
            if "enable_code_interpreter" in kwargs:
                extra_body["enable_code_interpreter"] = kwargs.pop("enable_code_interpreter")
            if "thinking_budget" in kwargs:
                extra_body["thinking_budget"] = kwargs.pop("thinking_budget")

            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
                "extra_body": extra_body
            }

            # Add optional standard parameters
            if top_p is not None:
                payload["top_p"] = top_p
            if presence_penalty is not None:
                payload["presence_penalty"] = presence_penalty
            if stop is not None:
                payload["stop"] = stop
            if seed is not None:
                payload["seed"] = seed
            if n is not None:
                payload["n"] = n
            if logprobs is not None:
                payload["logprobs"] = logprobs
            if top_logprobs is not None:
                payload["top_logprobs"] = top_logprobs

            # Add function calling parameters if provided
            if "tools" in kwargs:
                payload["tools"] = kwargs.pop("tools")
            if "tool_choice" in kwargs:
                payload["tool_choice"] = kwargs.pop("tool_choice")
            if "parallel_tool_calls" in kwargs:
                payload["parallel_tool_calls"] = kwargs.pop("parallel_tool_calls")

            # Add response format if provided
            if "response_format" in kwargs:
                payload["response_format"] = kwargs.pop("response_format")

            # Pass through any remaining kwargs (for future extensibility)
            if kwargs:
                logger.debug(f"[QwenClient] Additional kwargs passed through: {list(kwargs.keys())}")
                payload.update(kwargs)

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # Use httpx with HTTP/2 support
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                http2=True
            ) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    choices = data.get('choices', [])
                    usage = data.get('usage', {})

                    # Handle multiple completions (n > 1)
                    if n and n > 1 and len(choices) > 1:
                        # Return list of completions
                        completions = []
                        for choice in choices:
                            message = choice.get('message', {})
                            content = message.get('content', '')
                            tool_calls = message.get('tool_calls')
                            completion_item = {
                                'content': content,
                                'index': choice.get('index', 0),
                                'finish_reason': choice.get('finish_reason'),
                                'logprobs': choice.get('logprobs')
                            }
                            # Include tool_calls if present
                            if tool_calls:
                                completion_item['tool_calls'] = tool_calls
                            completions.append(completion_item)
                        return {
                            'content': completions,  # List of completions
                            'usage': usage
                        }
                    else:
                        # Single completion (default behavior)
                        message = choices[0].get('message', {}) if choices else {}
                        content = message.get('content', '')
                        tool_calls = message.get('tool_calls')
                        result = {
                            'content': content,
                            'usage': usage
                        }
                        # Include tool_calls if present (function calling response)
                        if tool_calls:
                            result['tool_calls'] = tool_calls
                        # Include logprobs if requested
                        if choices and logprobs and 'logprobs' in choices[0]:
                            result['logprobs'] = choices[0].get('logprobs')
                        return result
                else:
                    error_text = response.text
                    logger.error(f"Qwen API error {response.status_code}: {error_text}")

                    # Parse error using comprehensive DashScope error parser
                    try:
                        error_data = json.loads(error_text)
                        # This function always raises an exception, never returns
                        parse_and_raise_dashscope_error(response.status_code, error_text, error_data)
                    except json.JSONDecodeError:
                        # Fallback for non-JSON errors
                        if response.status_code == 429:
                            raise LLMRateLimitError(f"Qwen rate limit: {error_text}")
                        elif response.status_code == 401:
                            raise LLMAccessDeniedError(f"Unauthorized: {error_text}", provider='qwen', error_code='Unauthorized')
                        else:
                            raise LLMProviderError(f"Qwen API error ({response.status_code}): {error_text}", provider='qwen', error_code=f'HTTP{response.status_code}')

        except httpx.TimeoutException as e:
            logger.error("Qwen API timeout")
            raise LLMTimeoutError("Qwen API timeout") from e
        except httpx.HTTPError as e:
            logger.error(f"Qwen HTTP error: {e}")
            raise LLMProviderError(f"Qwen HTTP error: {e}", provider='qwen', error_code='HTTPError')
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Qwen API error: {e}")
            raise

    async def async_stream_chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 1000,
        enable_thinking: bool = False,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        presence_penalty: Optional[float] = None,
        stop: Optional[Union[str, List[str]]] = None,
        seed: Optional[int] = None,
        logprobs: Optional[bool] = None,
        top_logprobs: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat completion from Qwen API (async generator).

        Args:
            messages: List of message dictionaries with 'role' and 'content'.
                     Supports multimodal content:
                     - Text: {"role": "user", "content": "text"}
                     - Image: {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "..."}}]}
                     - Video: {"role": "user", "content": [{"type": "video", "video": ["url1", "url2"]}]}
                     - Mixed: {"role": "user", "content": [{"type": "text", "text": "..."}, {"type": "image_url", ...}]}
            temperature: Sampling temperature (0.0 to 2.0), None uses default
            max_tokens: Maximum tokens in response
            enable_thinking: Whether to enable thinking mode (for Qwen3 models)
            top_p: Nucleus sampling threshold (0.0 to 1.0)
            top_k: Top-k sampling (via extra_body, DashScope-specific)
            presence_penalty: Repetition control (-2.0 to 2.0)
            stop: Stop sequences (string or list of strings)
            seed: Random seed for reproducibility (0 to 2^31-1)
            logprobs: Whether to return token log probabilities
            top_logprobs: Number of top logprobs to return (0-5, requires logprobs=True)
            **kwargs: Additional parameters:
                - tools: Function calling tools array
                - tool_choice: Tool selection strategy
                - parallel_tool_calls: Enable parallel tool calls
                - response_format: JSON mode ({"type": "json_object"} or {"type": "json_schema"})
                - enable_search: Web search (DashScope-specific, via extra_body)
                - search_options: Search configuration (DashScope-specific, via extra_body)
                - vl_high_resolution_images: High-res image processing (DashScope-specific, via extra_body)
                - modalities: Output modalities for Qwen-Omni ["text", "audio"] (DashScope-specific, via extra_body)
                - audio: Audio output config for Qwen-Omni (DashScope-specific, via extra_body)
                - enable_code_interpreter: Code interpreter (DashScope-specific, via extra_body)
                - thinking_budget: Limit thinking length (DashScope-specific, via extra_body)

        Yields:
            Dict with 'type' and 'content' keys:
            - {'type': 'thinking', 'content': '...'} - Reasoning content
            - {'type': 'token', 'content': '...'} - Response content
            - {'type': 'tool_calls', 'tool_calls': [...]} - Tool calls (function calling)
            - {'type': 'usage', 'usage': {...}} - Token usage stats
        """
        try:
            # Use instance default if not specified
            if temperature is None:
                temperature = self.default_temperature

            # Select appropriate model
            if self.model_type == 'classification':
                model_name = config.QWEN_MODEL_CLASSIFICATION
            else:
                model_name = config.QWEN_MODEL_GENERATION

            # Build extra_body for DashScope-specific parameters
            extra_body: Dict[str, Any] = {"enable_thinking": enable_thinking}

            # Add DashScope-specific parameters to extra_body
            if top_k is not None:
                extra_body["top_k"] = top_k
            if "enable_search" in kwargs:
                extra_body["enable_search"] = kwargs.pop("enable_search")
            if "search_options" in kwargs:
                extra_body["search_options"] = kwargs.pop("search_options")
            if "vl_high_resolution_images" in kwargs:
                extra_body["vl_high_resolution_images"] = kwargs.pop("vl_high_resolution_images")
            if "modalities" in kwargs:
                extra_body["modalities"] = kwargs.pop("modalities")
            if "audio" in kwargs:
                extra_body["audio"] = kwargs.pop("audio")
            if "enable_code_interpreter" in kwargs:
                extra_body["enable_code_interpreter"] = kwargs.pop("enable_code_interpreter")
            if "thinking_budget" in kwargs:
                extra_body["thinking_budget"] = kwargs.pop("thinking_budget")

            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
                "stream_options": {"include_usage": True},
                "extra_body": extra_body
            }

            # Add optional standard parameters
            if top_p is not None:
                payload["top_p"] = top_p
            if presence_penalty is not None:
                payload["presence_penalty"] = presence_penalty
            if stop is not None:
                payload["stop"] = stop
            if seed is not None:
                payload["seed"] = seed
            if logprobs is not None:
                payload["logprobs"] = logprobs
            if top_logprobs is not None:
                payload["top_logprobs"] = top_logprobs

            # Add function calling parameters if provided
            if "tools" in kwargs:
                payload["tools"] = kwargs.pop("tools")
            if "tool_choice" in kwargs:
                payload["tool_choice"] = kwargs.pop("tool_choice")
            if "parallel_tool_calls" in kwargs:
                payload["parallel_tool_calls"] = kwargs.pop("parallel_tool_calls")

            # Add response format if provided
            if "response_format" in kwargs:
                payload["response_format"] = kwargs.pop("response_format")

            # Pass through any remaining kwargs
            if kwargs:
                logger.debug(f"[QwenClient] Additional kwargs in stream: {list(kwargs.keys())}")
                payload.update(kwargs)

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # Use httpx with streaming and HTTP/2 support
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(None, connect=10.0, read=self.stream_timeout),
                http2=True
            ) as client:
                async with client.stream('POST', self.api_url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        error_text = error_text.decode('utf-8')
                        logger.error(f"Qwen stream error {response.status_code}: {error_text}")

                        # Parse error using comprehensive DashScope error parser
                        try:
                            error_data = json.loads(error_text)
                            parse_and_raise_dashscope_error(response.status_code, error_text, error_data)
                        except json.JSONDecodeError:
                            if response.status_code == 429:
                                raise LLMRateLimitError(f"Qwen rate limit: {error_text}")
                            elif response.status_code == 401:
                                raise LLMAccessDeniedError(f"Unauthorized: {error_text}", provider='qwen', error_code='Unauthorized')
                            else:
                                raise LLMProviderError(f"Qwen stream error ({response.status_code}): {error_text}", provider='qwen', error_code=f'HTTP{response.status_code}')

                    # Read SSE stream line by line using httpx's aiter_lines()
                    last_usage = None
                    async for line in response.aiter_lines():
                        if not line or not line.startswith('data: '):
                            continue

                        data_content = line[6:]  # Remove 'data: ' prefix

                        # Handle [DONE] signal
                        if data_content.strip() == '[DONE]':
                            if last_usage:
                                yield {'type': 'usage', 'usage': last_usage}
                            break

                        try:
                            data = json.loads(data_content)

                            # Check for usage data (in final chunk)
                            if 'usage' in data and data['usage']:
                                last_usage = data.get('usage', {})

                            # Extract delta from streaming response
                            choices = data.get('choices', [])
                            if choices:
                                delta = choices[0].get('delta', {})

                                # Check for thinking/reasoning content (Qwen3 thinking mode)
                                reasoning_content = delta.get('reasoning_content', '')
                                if reasoning_content:
                                    yield {'type': 'thinking', 'content': reasoning_content}

                                # Check for tool calls (function calling)
                                tool_calls = delta.get('tool_calls')
                                if tool_calls:
                                    yield {'type': 'tool_calls', 'tool_calls': tool_calls}

                                # Check for regular content
                                content = delta.get('content', '')
                                if content:
                                    yield {'type': 'token', 'content': content}

                        except json.JSONDecodeError:
                            continue

                    # If stream ended without [DONE], yield usage if we have it
                    if last_usage:
                        yield {'type': 'usage', 'usage': last_usage}

        except httpx.TimeoutException as e:
            logger.error("Qwen streaming timeout")
            raise LLMTimeoutError("Qwen streaming timeout") from e
        except httpx.HTTPError as e:
            logger.error(f"Qwen streaming HTTP error: {e}")
            raise LLMProviderError(f"Qwen streaming HTTP error: {e}", provider='qwen', error_code='HTTPError')
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Qwen streaming error: {e}")
            raise


# ============================================================================
# MULTI-LLM CLIENT (DeepSeek, Kimi, ChatGLM)
# ============================================================================

class DeepSeekClient:
    """Client for DeepSeek R1 via Dashscope API using httpx with HTTP/2 support."""

    def __init__(self):
        """Initialize DeepSeek client"""
        self.api_url = config.QWEN_API_URL  # Dashscope uses same endpoint
        self.api_key = config.QWEN_API_KEY
        self.timeout = 60  # seconds (DeepSeek R1 can be slower for reasoning)
        self.stream_timeout = 180  # Longer timeout for streaming (DeepSeek thinking can be slow)
        self.model_id = 'deepseek'
        self.model_name = config.DEEPSEEK_MODEL
        # DIVERSITY FIX: Lower temperature for DeepSeek (reasoning model, more deterministic)
        self.default_temperature = 0.6
        logger.debug(f"DeepSeekClient initialized with model: {self.model_name}")

    async def async_chat_completion(self, messages: List[Dict], temperature: Optional[float] = None,
                                   max_tokens: int = 2000) -> Dict[str, Any]:  # type: ignore[return-value]
        """
        Send async chat completion request to DeepSeek R1

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0), None uses default
            max_tokens: Maximum tokens in response

        Returns:
            Dict with 'content' and 'usage' keys
        """
        try:
            # Use instance default if not specified
            if temperature is None:
                temperature = self.default_temperature

            payload = config.get_llm_data(
                messages[-1]['content'] if messages else '',
                self.model_id
            )
            payload['messages'] = messages
            payload['temperature'] = temperature
            payload['max_tokens'] = max_tokens

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            logger.debug(f"DeepSeek async API request: {self.model_name}")

            # Use httpx with HTTP/2 support
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                http2=True
            ) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    logger.debug(f"DeepSeek response length: {len(content)} chars")
                    # Extract usage data
                    usage = data.get('usage', {})
                    return {
                        'content': content,
                        'usage': usage
                    }
                else:
                    error_text = response.text
                    logger.error(f"DeepSeek API error {response.status_code}: {error_text}")

                    # Parse error using comprehensive DashScope error parser
                    try:
                        error_data = json.loads(error_text)
                        parse_and_raise_dashscope_error(response.status_code, error_text, error_data)
                    except json.JSONDecodeError:
                        if response.status_code == 429:
                            raise LLMRateLimitError(f"DeepSeek rate limit: {error_text}")
                        elif response.status_code == 401:
                            raise LLMAccessDeniedError(f"Unauthorized: {error_text}", provider='deepseek', error_code='Unauthorized')
                        else:
                            raise LLMProviderError(f"DeepSeek API error ({response.status_code}): {error_text}", provider='deepseek', error_code=f'HTTP{response.status_code}')

        except httpx.TimeoutException as e:
            logger.error("DeepSeek API timeout")
            raise LLMTimeoutError("DeepSeek API timeout") from e
        except httpx.HTTPError as e:
            logger.error(f"DeepSeek HTTP error: {e}")
            raise LLMProviderError(f"DeepSeek HTTP error: {e}", provider='deepseek', error_code='HTTPError')
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"DeepSeek API error: {e}")
            raise

    # Alias for compatibility with agents that call chat_completion
    async def chat_completion(self, messages: List[Dict], temperature: Optional[float] = None,
                             max_tokens: int = 2000) -> Dict[str, Any]:
        """Alias for async_chat_completion for API consistency"""
        return await self.async_chat_completion(messages, temperature, max_tokens)

    async def async_stream_chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        enable_thinking: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat completion from DeepSeek R1 (async generator).

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0), None uses default
            max_tokens: Maximum tokens in response
            enable_thinking: Whether to enable thinking mode (for DeepSeek R1)

        Yields:
            Dict with 'type' and 'content' keys:
            - {'type': 'thinking', 'content': '...'} - Reasoning content
            - {'type': 'token', 'content': '...'} - Response content
            - {'type': 'usage', 'usage': {...}} - Token usage stats
        """
        try:
            if temperature is None:
                temperature = self.default_temperature

            payload = config.get_llm_data(
                messages[-1]['content'] if messages else '',
                self.model_id
            )
            payload['messages'] = messages
            payload['temperature'] = temperature
            payload['max_tokens'] = max_tokens
            payload['stream'] = True
            payload['stream_options'] = {"include_usage": True}

            # Enable thinking mode if requested
            if 'extra_body' not in payload:
                payload['extra_body'] = {}
            payload['extra_body']['enable_thinking'] = enable_thinking

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # Use httpx with streaming and HTTP/2 support
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(None, connect=10.0, read=self.stream_timeout),
                http2=True
            ) as client:
                async with client.stream('POST', self.api_url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        error_text = error_text.decode('utf-8')
                        logger.error(f"DeepSeek stream error {response.status_code}: {error_text}")

                        try:
                            error_data = json.loads(error_text)
                            parse_and_raise_dashscope_error(response.status_code, error_text, error_data)
                        except json.JSONDecodeError:
                            if response.status_code == 429:
                                raise LLMRateLimitError(f"DeepSeek rate limit: {error_text}")
                            elif response.status_code == 401:
                                raise LLMAccessDeniedError(f"Unauthorized: {error_text}", provider='deepseek', error_code='Unauthorized')
                            else:
                                raise LLMProviderError(f"DeepSeek stream error ({response.status_code}): {error_text}", provider='deepseek', error_code=f'HTTP{response.status_code}')

                    # Read SSE stream using httpx's aiter_lines()
                    last_usage = None
                    async for line in response.aiter_lines():
                        if not line or not line.startswith('data: '):
                            continue

                        data_content = line[6:]

                        if data_content.strip() == '[DONE]':
                            if last_usage:
                                yield {'type': 'usage', 'usage': last_usage}
                            break

                        try:
                            data = json.loads(data_content)

                            # Check for usage data (in final chunk)
                            if 'usage' in data and data['usage']:
                                last_usage = data.get('usage', {})

                            choices = data.get('choices', [])
                            if choices:
                                delta = choices[0].get('delta', {})

                                # Check for thinking/reasoning content (DeepSeek R1)
                                reasoning_content = delta.get('reasoning_content', '')
                                if reasoning_content:
                                    yield {'type': 'thinking', 'content': reasoning_content}

                                # Check for regular content
                                content = delta.get('content', '')
                                if content:
                                    yield {'type': 'token', 'content': content}

                        except json.JSONDecodeError:
                            continue

                    # If stream ended without [DONE], yield usage if we have it
                    if last_usage:
                        yield {'type': 'usage', 'usage': last_usage}

        except httpx.TimeoutException as e:
            logger.error("DeepSeek streaming timeout")
            raise LLMTimeoutError("DeepSeek streaming timeout") from e
        except httpx.HTTPError as e:
            logger.error(f"DeepSeek streaming HTTP error: {e}")
            raise LLMProviderError(f"DeepSeek streaming HTTP error: {e}", provider='deepseek', error_code='HTTPError')
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"DeepSeek streaming error: {e}")
            raise


class KimiClient:
    """Client for Kimi (Moonshot AI) via Dashscope API using httpx with HTTP/2 support."""

    def __init__(self):
        """Initialize Kimi client"""
        self.api_url = config.QWEN_API_URL  # Dashscope uses same endpoint
        self.api_key = config.QWEN_API_KEY
        self.timeout = 60  # seconds
        self.stream_timeout = 180  # Longer timeout for streaming (Kimi K2 thinking)
        self.model_id = 'kimi'
        self.model_name = config.KIMI_MODEL
        # DIVERSITY FIX: Higher temperature for Kimi to increase creative variation
        self.default_temperature = 1.0
        logger.debug(f"KimiClient initialized with model: {self.model_name}")

    async def async_chat_completion(self, messages: List[Dict], temperature: Optional[float] = None,
                                   max_tokens: int = 2000) -> Dict[str, Any]:  # type: ignore[return-value]
        """Async chat completion for Kimi"""
        try:
            # Use instance default if not specified
            if temperature is None:
                temperature = self.default_temperature

            payload = config.get_llm_data(
                messages[-1]['content'] if messages else '',
                self.model_id
            )
            payload['messages'] = messages
            payload['temperature'] = temperature
            payload['max_tokens'] = max_tokens

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            logger.debug(f"Kimi async API request: {self.model_name}")

            # Use httpx with HTTP/2 support
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                http2=True
            ) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    logger.debug(f"Kimi response length: {len(content)} chars")
                    # Extract usage data
                    usage = data.get('usage', {})
                    return {
                        'content': content,
                        'usage': usage
                    }
                else:
                    error_text = response.text
                    logger.error(f"Kimi API error {response.status_code}: {error_text}")

                    try:
                        error_data = json.loads(error_text)
                        parse_and_raise_dashscope_error(response.status_code, error_text, error_data)
                    except json.JSONDecodeError:
                        if response.status_code == 429:
                            raise LLMRateLimitError(f"Kimi rate limit: {error_text}")
                        elif response.status_code == 401:
                            raise LLMAccessDeniedError(f"Unauthorized: {error_text}", provider='kimi', error_code='Unauthorized')
                        else:
                            raise LLMProviderError(f"Kimi API error ({response.status_code}): {error_text}", provider='kimi', error_code=f'HTTP{response.status_code}')

        except httpx.TimeoutException as e:
            logger.error("Kimi API timeout")
            raise LLMTimeoutError("Kimi API timeout") from e
        except httpx.HTTPError as e:
            logger.error(f"Kimi HTTP error: {e}")
            raise LLMProviderError(f"Kimi HTTP error: {e}", provider='kimi', error_code='HTTPError')
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Kimi API error: {e}")
            raise

    # Alias for compatibility with agents that call chat_completion
    async def chat_completion(self, messages: List[Dict], temperature: Optional[float] = None,
                             max_tokens: int = 2000) -> Dict[str, Any]:
        """Alias for async_chat_completion for API consistency"""
        return await self.async_chat_completion(messages, temperature, max_tokens)

    async def async_stream_chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        enable_thinking: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat completion from Kimi (async generator).

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0), None uses default
            max_tokens: Maximum tokens in response
            enable_thinking: Whether to enable thinking mode (for Kimi K2)

        Yields:
            Dict with 'type' and 'content' keys:
            - {'type': 'thinking', 'content': '...'} - Reasoning content
            - {'type': 'token', 'content': '...'} - Response content
            - {'type': 'usage', 'usage': {...}} - Token usage stats
        """
        try:
            if temperature is None:
                temperature = self.default_temperature

            payload = config.get_llm_data(
                messages[-1]['content'] if messages else '',
                self.model_id
            )
            payload['messages'] = messages
            payload['temperature'] = temperature
            payload['max_tokens'] = max_tokens
            payload['stream'] = True
            payload['stream_options'] = {"include_usage": True}

            # Enable thinking mode if requested
            if 'extra_body' not in payload:
                payload['extra_body'] = {}
            payload['extra_body']['enable_thinking'] = enable_thinking

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # Use httpx with streaming and HTTP/2 support
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(None, connect=10.0, read=self.stream_timeout),
                http2=True
            ) as client:
                async with client.stream('POST', self.api_url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        error_text = error_text.decode('utf-8')
                        logger.error(f"Kimi stream error {response.status_code}: {error_text}")

                        try:
                            error_data = json.loads(error_text)
                            parse_and_raise_dashscope_error(response.status_code, error_text, error_data)
                        except json.JSONDecodeError:
                            if response.status_code == 429:
                                raise LLMRateLimitError(f"Kimi rate limit: {error_text}")
                            elif response.status_code == 401:
                                raise LLMAccessDeniedError(f"Unauthorized: {error_text}", provider='kimi', error_code='Unauthorized')
                            else:
                                raise LLMProviderError(f"Kimi stream error ({response.status_code}): {error_text}", provider='kimi', error_code=f'HTTP{response.status_code}')

                    # Read SSE stream using httpx's aiter_lines()
                    last_usage = None
                    async for line in response.aiter_lines():
                        if not line or not line.startswith('data: '):
                            continue

                        data_content = line[6:]

                        if data_content.strip() == '[DONE]':
                            if last_usage:
                                yield {'type': 'usage', 'usage': last_usage}
                            break

                        try:
                            data = json.loads(data_content)

                            # Check for usage data (in final chunk)
                            if 'usage' in data and data['usage']:
                                last_usage = data.get('usage', {})

                            choices = data.get('choices', [])
                            if choices:
                                delta = choices[0].get('delta', {})

                                # Check for thinking/reasoning content (Kimi K2)
                                reasoning_content = delta.get('reasoning_content', '')
                                if reasoning_content:
                                    yield {'type': 'thinking', 'content': reasoning_content}

                                # Check for regular content
                                content = delta.get('content', '')
                                if content:
                                    yield {'type': 'token', 'content': content}

                        except json.JSONDecodeError:
                            continue

                    # If stream ended without [DONE], yield usage if we have it
                    if last_usage:
                        yield {'type': 'usage', 'usage': last_usage}

        except httpx.TimeoutException as e:
            logger.error("Kimi streaming timeout")
            raise LLMTimeoutError("Kimi streaming timeout") from e
        except httpx.HTTPError as e:
            logger.error(f"Kimi streaming HTTP error: {e}")
            raise LLMProviderError(f"Kimi streaming HTTP error: {e}", provider='kimi', error_code='HTTPError')
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Kimi streaming error: {e}")
            raise


class HunyuanClient:
    """Client for Tencent Hunyuan (混元) using OpenAI-compatible API"""

    def __init__(self):
        """Initialize Hunyuan client with OpenAI SDK"""
        self.api_key = config.HUNYUAN_API_KEY
        self.base_url = "https://api.hunyuan.cloud.tencent.com/v1"
        self.model_name = "hunyuan-turbo"  # Using standard model name
        self.timeout = 60  # seconds

        # DIVERSITY FIX: Highest temperature for HunYuan for maximum variation
        self.default_temperature = 1.2

        # Initialize AsyncOpenAI client with custom base URL
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )

        logger.debug(f"HunyuanClient initialized with OpenAI-compatible API: {self.model_name}")

    async def async_chat_completion(self, messages: List[Dict], temperature: Optional[float] = None,
                                   max_tokens: int = 2000) -> Dict[str, Any]:  # type: ignore[return-value]
        """
        Send async chat completion request to Tencent Hunyuan (OpenAI-compatible)

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0), None uses default
            max_tokens: Maximum tokens in response

        Returns:
            Response content as string
        """
        try:
            # Use instance default if not specified
            if temperature is None:
                temperature = self.default_temperature

            logger.debug(f"Hunyuan async API request: {self.model_name} (temp: {temperature})")

            # Call OpenAI-compatible API
            completion = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            # Extract content from response
            content = completion.choices[0].message.content

            if content:
                logger.debug(f"Hunyuan response length: {len(content)} chars")
                # Extract usage data (OpenAI SDK uses 'usage' attribute)
                usage = {}
                if hasattr(completion, 'usage') and completion.usage:
                    usage = {
                        'prompt_tokens': completion.usage.prompt_tokens if hasattr(completion.usage, 'prompt_tokens') else 0,
                        'completion_tokens': completion.usage.completion_tokens if hasattr(completion.usage, 'completion_tokens') else 0,
                        'total_tokens': completion.usage.total_tokens if hasattr(completion.usage, 'total_tokens') else 0
                    }
                return {
                    'content': content,
                    'usage': usage
                }
            else:
                logger.error("Hunyuan API returned empty content")
                raise Exception("Hunyuan API returned empty content")

        except RateLimitError as e:
            logger.error(f"Hunyuan rate limit error: {e}")
            raise LLMRateLimitError(f"Hunyuan rate limit: {e}")

        except APIStatusError as e:
            error_msg = str(e)
            logger.error(f"Hunyuan API status error: {error_msg}")

            # Try to extract error code from OpenAI SDK error
            error_code = None
            if hasattr(e, 'code'):
                error_code = e.code
            elif hasattr(e, 'response') and hasattr(e.response, 'json'):
                try:
                    error_data = e.response.json()
                    if 'error' in error_data:
                        error_code = error_data['error'].get('code', 'Unknown')
                        error_msg = error_data['error'].get('message', error_msg)
                except Exception as parse_error:
                    logger.debug(f"Failed to parse error response JSON: {parse_error}")

            # Try to extract from error message if code not found
            if not error_code:
                # Look for error code patterns in message:
                # 1. Numeric codes (e.g., "2003", "400") - common in Tencent Cloud API
                numeric_match = re.search(r'\b(\d{3,4})\b', error_msg)
                if numeric_match:
                    error_code = numeric_match.group(1)
                else:
                    # 2. String codes starting with uppercase letter (e.g., "AuthFailure", "InvalidParameter")
                    string_match = re.search(r'([A-Z][a-zA-Z0-9]+(?:\.[A-Z][a-zA-Z0-9]+)*)', error_msg)
                    if string_match:
                        error_code = string_match.group(1)
                    else:
                        error_code = 'Unknown'

            # Parse error using comprehensive Hunyuan error parser
            try:
                parse_and_raise_hunyuan_error(error_code, error_msg, status_code=getattr(e, 'status_code', None))
            except (LLMInvalidParameterError, LLMQuotaExhaustedError, LLMModelNotFoundError,
                    LLMAccessDeniedError, LLMContentFilterError, LLMRateLimitError, LLMTimeoutError):
                # Re-raise parsed exceptions
                raise
            except Exception:
                # Fallback to generic error if parsing fails
                raise LLMProviderError(f"Hunyuan API error ({error_code}): {error_msg}", provider='hunyuan', error_code=error_code)

        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Hunyuan API error: {e}")
            raise

    # Alias for compatibility with agents that call chat_completion
    async def chat_completion(self, messages: List[Dict], temperature: Optional[float] = None,
                             max_tokens: int = 2000) -> Dict[str, Any]:
        """Alias for async_chat_completion for API consistency"""
        return await self.async_chat_completion(messages, temperature, max_tokens)

    async def async_stream_chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        enable_thinking: bool = False  # Not supported by Hunyuan, for API consistency
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat completion from Hunyuan using OpenAI-compatible API.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0), None uses default
            max_tokens: Maximum tokens in response
            enable_thinking: Not supported by Hunyuan, included for API consistency

        Yields:
            Dict with 'type' and 'content' keys:
            - {'type': 'token', 'content': '...'} - Response content
            - {'type': 'usage', 'usage': {...}} - Token usage stats
        """
        try:
            if temperature is None:
                temperature = self.default_temperature

            logger.debug(f"Hunyuan stream API request: {self.model_name} (temp: {temperature})")

            # Use OpenAI SDK's streaming with usage tracking
            # Note: enable_thinking is ignored as Hunyuan doesn't support it
            stream = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,  # Enable streaming
                stream_options={"include_usage": True}  # Request usage in stream
            )

            last_usage = None
            async for chunk in stream:
                # Check for usage data (usually in last chunk)
                if hasattr(chunk, 'usage') and chunk.usage:
                    last_usage = {
                        'prompt_tokens': chunk.usage.prompt_tokens if hasattr(chunk.usage, 'prompt_tokens') else 0,
                        'completion_tokens': chunk.usage.completion_tokens if hasattr(chunk.usage, 'completion_tokens') else 0,
                        'total_tokens': chunk.usage.total_tokens if hasattr(chunk.usage, 'total_tokens') else 0
                    }

                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield {'type': 'token', 'content': delta.content}

            # Yield usage data as final chunk
            if last_usage:
                yield {'type': 'usage', 'usage': last_usage}

        except RateLimitError as e:
            logger.error(f"Hunyuan streaming rate limit: {e}")
            raise LLMRateLimitError(f"Hunyuan rate limit: {e}")

        except APIStatusError as e:
            error_msg = str(e)
            logger.error(f"Hunyuan streaming API error: {error_msg}")

            # Try to extract error code from OpenAI SDK error
            error_code = None
            if hasattr(e, 'code'):
                error_code = e.code
            elif hasattr(e, 'response') and hasattr(e.response, 'json'):
                try:
                    error_data = e.response.json()
                    if 'error' in error_data:
                        error_code = error_data['error'].get('code', 'Unknown')
                        error_msg = error_data['error'].get('message', error_msg)
                except:
                    pass

            # Try to extract from error message if code not found
            if not error_code:
                code_match = re.search(r'([A-Z][a-zA-Z0-9]+(?:\.[A-Z][a-zA-Z0-9]+)*)', error_msg)
                if code_match:
                    error_code = code_match.group(1)
                else:
                    error_code = 'Unknown'

            # Parse error using comprehensive Hunyuan error parser
            try:
                parse_and_raise_hunyuan_error(error_code, error_msg, status_code=getattr(e, 'status_code', None))
            except (LLMInvalidParameterError, LLMQuotaExhaustedError, LLMModelNotFoundError,
                    LLMAccessDeniedError, LLMContentFilterError, LLMRateLimitError, LLMTimeoutError):
                # Re-raise parsed exceptions
                raise
            except Exception:
                # Fallback to generic error if parsing fails
                raise LLMProviderError(f"Hunyuan stream error ({error_code}): {error_msg}", provider='hunyuan', error_code=error_code)

        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Hunyuan streaming error: {e}")
            raise


class DoubaoClient:
    """
    Client for Volcengine Doubao (豆包) using OpenAI-compatible API.

    DEPRECATED: This class uses direct model names. For higher RPM limits,
    use VolcengineClient('ark-doubao') instead, which uses endpoint IDs.

    This class is kept for backward compatibility only.
    """

    def __init__(self):
        """Initialize Doubao client with OpenAI SDK"""
        logger.warning(
            "[DoubaoClient] DEPRECATED: DoubaoClient uses direct model names. "
            "Use VolcengineClient('ark-doubao') for higher RPM limits via endpoints."
        )
        self.api_key = config.ARK_API_KEY
        self.base_url = config.ARK_BASE_URL
        self.model_name = config.DOUBAO_MODEL
        self.timeout = 60  # seconds

        # DIVERSITY FIX: Moderate temperature for Doubao
        self.default_temperature = 0.8

        # Initialize AsyncOpenAI client with custom base URL
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )

        logger.debug(f"DoubaoClient initialized with OpenAI-compatible API: {self.model_name}")

    async def async_chat_completion(self, messages: List[Dict], temperature: Optional[float] = None,
                                   max_tokens: int = 2000) -> Dict[str, Any]:  # type: ignore[return-value]
        """
        Send async chat completion request to Volcengine Doubao (OpenAI-compatible)

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0), None uses default
            max_tokens: Maximum tokens in response

        Returns:
            Response content as string
        """
        try:
            # Use instance default if not specified
            if temperature is None:
                temperature = self.default_temperature

            logger.debug(f"Doubao async API request: {self.model_name} (temp: {temperature})")

            # Call OpenAI-compatible API
            completion = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            # Extract content from response
            content = completion.choices[0].message.content

            if content:
                logger.debug(f"Doubao response length: {len(content)} chars")
                # Extract usage data (OpenAI SDK uses 'usage' attribute)
                usage = {}
                if hasattr(completion, 'usage') and completion.usage:
                    usage = {
                        'prompt_tokens': completion.usage.prompt_tokens if hasattr(completion.usage, 'prompt_tokens') else 0,
                        'completion_tokens': completion.usage.completion_tokens if hasattr(completion.usage, 'completion_tokens') else 0,
                        'total_tokens': completion.usage.total_tokens if hasattr(completion.usage, 'total_tokens') else 0
                    }
                return {
                    'content': content,
                    'usage': usage
                }
            else:
                logger.error("Doubao API returned empty content")
                raise Exception("Doubao API returned empty content")

        except RateLimitError as e:
            logger.error(f"Doubao rate limit error: {e}")
            raise LLMRateLimitError(f"Doubao rate limit: {e}")

        except APIStatusError as e:
            error_msg = str(e)
            logger.error(f"Doubao API status error: {error_msg}")

            # Try to extract error code from OpenAI SDK error
            error_code = None
            status_code = getattr(e, 'status_code', None)

            if hasattr(e, 'code'):
                error_code = e.code
            elif hasattr(e, 'response') and hasattr(e.response, 'json'):
                try:
                    error_data = e.response.json()
                    if 'error' in error_data:
                        error_code = error_data['error'].get('code', 'Unknown')
                        error_msg = error_data['error'].get('message', error_msg)
                    # Also check for status_code in response
                    if status_code is None:
                        status_code = error_data.get('status_code')
                except:
                    pass

            # Try to extract from error message if code not found
            if not error_code:
                # Look for common error code patterns in message
                code_match = re.search(r'([A-Z][a-zA-Z0-9]+(?:\.[A-Z][a-zA-Z0-9]+)*)', error_msg)
                if code_match:
                    error_code = code_match.group(1)
                else:
                    error_code = 'Unknown'

            # Parse error using comprehensive Doubao error parser
            try:
                parse_and_raise_doubao_error(error_code, error_msg, status_code=status_code)
            except (LLMInvalidParameterError, LLMQuotaExhaustedError, LLMModelNotFoundError,
                    LLMAccessDeniedError, LLMContentFilterError, LLMRateLimitError, LLMTimeoutError):
                # Re-raise parsed exceptions
                raise
            except Exception:
                # Fallback to generic error if parsing fails
                raise LLMProviderError(f"Doubao API error ({error_code}): {error_msg}", provider='doubao', error_code=error_code)

        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Doubao API error: {e}")
            raise

    # Alias for compatibility with agents that call chat_completion
    async def chat_completion(self, messages: List[Dict], temperature: Optional[float] = None,
                             max_tokens: int = 2000) -> Dict[str, Any]:
        """Alias for async_chat_completion for API consistency"""
        return await self.async_chat_completion(messages, temperature, max_tokens)

    async def async_stream_chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 2000
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat completion from Doubao using OpenAI-compatible API.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0), None uses default
            max_tokens: Maximum tokens in response

        Yields:
            Dict with 'type' and 'content' keys:
            - {'type': 'token', 'content': '...'} - Response content
            - {'type': 'usage', 'usage': {...}} - Token usage stats
        """
        try:
            if temperature is None:
                temperature = self.default_temperature

            logger.debug(f"Doubao stream API request: {self.model_name} (temp: {temperature})")

            # Use OpenAI SDK's streaming with usage tracking
            stream = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,  # Enable streaming
                stream_options={"include_usage": True}  # Request usage in stream
            )

            last_usage = None
            async for chunk in stream:
                # Check for usage data (usually in last chunk)
                if hasattr(chunk, 'usage') and chunk.usage:
                    last_usage = {
                        'prompt_tokens': chunk.usage.prompt_tokens if hasattr(chunk.usage, 'prompt_tokens') else 0,
                        'completion_tokens': chunk.usage.completion_tokens if hasattr(chunk.usage, 'completion_tokens') else 0,
                        'total_tokens': chunk.usage.total_tokens if hasattr(chunk.usage, 'total_tokens') else 0
                    }

                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield {'type': 'token', 'content': delta.content}

            # Yield usage data as final chunk
            if last_usage:
                yield {'type': 'usage', 'usage': last_usage}

        except RateLimitError as e:
            logger.error(f"Doubao streaming rate limit: {e}")
            raise LLMRateLimitError(f"Doubao rate limit: {e}")

        except APIStatusError as e:
            error_msg = str(e)
            logger.error(f"Doubao streaming API error: {error_msg}")

            # Try to extract error code from OpenAI SDK error
            error_code = None
            status_code = getattr(e, 'status_code', None)

            if hasattr(e, 'code'):
                error_code = e.code
            elif hasattr(e, 'response') and hasattr(e.response, 'json'):
                try:
                    error_data = e.response.json()
                    if 'error' in error_data:
                        error_code = error_data['error'].get('code', 'Unknown')
                        error_msg = error_data['error'].get('message', error_msg)
                    # Also check for status_code in response
                    if status_code is None:
                        status_code = error_data.get('status_code')
                except:
                    pass

            # Try to extract from error message if code not found
            if not error_code:
                code_match = re.search(r'([A-Z][a-zA-Z0-9]+(?:\.[A-Z][a-zA-Z0-9]+)*)', error_msg)
                if code_match:
                    error_code = code_match.group(1)
                else:
                    error_code = 'Unknown'

            # Parse error using comprehensive Doubao error parser
            try:
                parse_and_raise_doubao_error(error_code, error_msg, status_code=status_code)
            except (LLMInvalidParameterError, LLMQuotaExhaustedError, LLMModelNotFoundError,
                    LLMAccessDeniedError, LLMContentFilterError, LLMRateLimitError, LLMTimeoutError):
                # Re-raise parsed exceptions
                raise
            except Exception:
                # Fallback to generic error if parsing fails
                raise LLMProviderError(f"Doubao stream error ({error_code}): {error_msg}", provider='doubao', error_code=error_code)

        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Doubao streaming error: {e}")
            raise


class VolcengineClient:
    """
    Volcengine ARK client using endpoint IDs for higher RPM.

    Uses OpenAI-compatible API with endpoint IDs instead of model names
    to achieve higher request limits.

    Supports: ark-deepseek, ark-kimi, ark-doubao
    """

    # Endpoint mapping for higher RPM
    # Maps model aliases to environment variable names for error messages
    ENDPOINT_MAP = {
        'ark-qwen': 'ARK_QWEN_ENDPOINT',
        'ark-deepseek': 'ARK_DEEPSEEK_ENDPOINT',
        'ark-kimi': 'ARK_KIMI_ENDPOINT',
        'ark-doubao': 'ARK_DOUBAO_ENDPOINT',
    }

    def __init__(self, model_alias: str):
        """
        Initialize Volcengine client.

        Args:
            model_alias: Model alias ('ark-deepseek', 'ark-kimi', 'ark-doubao')

        Raises:
            ValueError: If ARK_API_KEY is not configured
        """
        self.api_key = config.ARK_API_KEY
        self.base_url = config.ARK_BASE_URL
        self.model_alias = model_alias
        self.timeout = 60

        # Validate API key is configured
        if not self.api_key:
            raise ValueError(
                f"ARK_API_KEY not configured for {model_alias}. "
                "Please set ARK_API_KEY in your environment variables."
            )

        # Map alias to endpoint ID (higher RPM!)
        self.endpoint_id = self._get_endpoint_id(model_alias)

        # DIVERSITY FIX: Moderate temperature
        self.default_temperature = 0.8

        # Initialize AsyncOpenAI client
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )

        logger.debug(
            f"VolcengineClient initialized: {model_alias} → endpoint={self.endpoint_id}"
        )

    def _get_endpoint_id(self, alias: str) -> str:
        """
        Map model alias to Volcengine endpoint ID.

        Endpoint IDs provide higher RPM than direct model names!

        Uses config properties for consistency with other configuration values.
        Endpoint IDs must be configured in environment variables (see env.example).
        """
        endpoint_map = {
            'ark-deepseek': config.ARK_DEEPSEEK_ENDPOINT,
            'ark-kimi': config.ARK_KIMI_ENDPOINT,
            'ark-doubao': config.ARK_DOUBAO_ENDPOINT,
        }

        # Get endpoint from config (reads from env var)
        endpoint = endpoint_map.get(alias)


        # Validate endpoint is configured (not empty and not dummy value)
        if not endpoint or endpoint == 'ep-20250101000000-dummy':
            raise ValueError(
                f"ARK endpoint ID not configured for {alias}. "
                f"Please set {self.ENDPOINT_MAP.get(alias, 'ENDPOINT')} in your environment variables. "
                "See env.example for configuration details."
            )

        return endpoint

    async def async_chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:  # type: ignore[return-value]
        """
        Non-streaming chat completion using endpoint ID.

        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens

        Returns:
            Dict with 'content' and 'usage' keys
        """
        try:
            if temperature is None:
                temperature = self.default_temperature

            logger.debug(f"Volcengine {self.model_alias} request: endpoint={self.endpoint_id}")

            completion = await self.client.chat.completions.create(
                model=self.endpoint_id,  # Use endpoint ID for higher RPM!
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            content = completion.choices[0].message.content

            # Extract usage
            usage = {}
            if hasattr(completion, 'usage') and completion.usage:
                usage = {
                    'prompt_tokens': getattr(completion.usage, 'prompt_tokens', 0),
                    'completion_tokens': getattr(completion.usage, 'completion_tokens', 0),
                    'total_tokens': getattr(completion.usage, 'total_tokens', 0),
                }

            return {
                'content': content,
                'usage': usage
            }

        except RateLimitError as e:
            logger.error(f"Volcengine {self.model_alias} rate limit: {e}")
            raise LLMRateLimitError(f"Volcengine rate limit: {e}")

        except APIStatusError as e:
            logger.error(f"Volcengine {self.model_alias} API error: {e}")
            # Use doubao error parser for Volcengine errors
            error_msg = str(e)
            status_code = getattr(e, 'status_code', None)
            error_code = None

            if hasattr(e, 'code'):
                error_code = e.code
            elif hasattr(e, 'response') and hasattr(e.response, 'json'):
                try:
                    error_data = e.response.json()
                    if 'error' in error_data:
                        error_code = error_data['error'].get('code', 'Unknown')
                        error_msg = error_data['error'].get('message', error_msg)
                    if status_code is None:
                        status_code = error_data.get('status_code')
                except:
                    pass

            if not error_code:
                code_match = re.search(r'([A-Z][a-zA-Z0-9]+(?:\.[A-Z][a-zA-Z0-9]+)*)', error_msg)
                if code_match:
                    error_code = code_match.group(1)
                else:
                    error_code = 'Unknown'

            try:
                parse_and_raise_doubao_error(error_code, error_msg, status_code=status_code)
            except (LLMInvalidParameterError, LLMQuotaExhaustedError, LLMModelNotFoundError,
                    LLMAccessDeniedError, LLMContentFilterError, LLMRateLimitError, LLMTimeoutError):
                raise
            except Exception:
                raise LLMProviderError(f"Volcengine API error ({error_code}): {error_msg}", provider='volcengine', error_code=error_code)

        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Volcengine {self.model_alias} error: {e}")
            raise

    async def async_stream_chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        enable_thinking: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streaming chat completion using endpoint ID.

        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            enable_thinking: Whether to enable thinking mode (for DeepSeek/Kimi via Volcengine)

        Yields:
            Dict with 'type' and 'content' keys:
            - {'type': 'thinking', 'content': '...'} - Reasoning content
            - {'type': 'token', 'content': '...'} - Response content
            - {'type': 'usage', 'usage': {...}} - Token usage stats
        """
        try:
            if temperature is None:
                temperature = self.default_temperature

            logger.debug(f"Volcengine {self.model_alias} stream: endpoint={self.endpoint_id}")

            # Build extra params for thinking mode if enabled
            extra_body = {"enable_thinking": enable_thinking} if enable_thinking else {}

            stream = await self.client.chat.completions.create(
                model=self.endpoint_id,  # Use endpoint ID for higher RPM!
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},  # Request usage in stream
                extra_body=extra_body if extra_body else None
            )

            last_usage = None
            async for chunk in stream:
                # Check for usage data (usually in last chunk)
                if hasattr(chunk, 'usage') and chunk.usage:
                    last_usage = {
                        'prompt_tokens': chunk.usage.prompt_tokens if hasattr(chunk.usage, 'prompt_tokens') else 0,
                        'completion_tokens': chunk.usage.completion_tokens if hasattr(chunk.usage, 'completion_tokens') else 0,
                        'total_tokens': chunk.usage.total_tokens if hasattr(chunk.usage, 'total_tokens') else 0
                    }

                if chunk.choices:
                    delta = chunk.choices[0].delta

                    # Check for thinking/reasoning content (DeepSeek R1, Kimi K2 via Volcengine)
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        yield {'type': 'thinking', 'content': delta.reasoning_content}

                    # Check for regular content
                    if delta.content:
                        yield {'type': 'token', 'content': delta.content}

            # Yield usage data as final chunk
            if last_usage:
                yield {'type': 'usage', 'usage': last_usage}

        except RateLimitError as e:
            logger.error(f"Volcengine {self.model_alias} stream rate limit: {e}")
            raise LLMRateLimitError(f"Volcengine rate limit: {e}")

        except APIStatusError as e:
            error_msg = str(e)
            logger.error(f"Volcengine {self.model_alias} streaming API error: {error_msg}")

            status_code = getattr(e, 'status_code', None)
            error_code = None

            if hasattr(e, 'code'):
                error_code = e.code
            elif hasattr(e, 'response') and hasattr(e.response, 'json'):
                try:
                    error_data = e.response.json()
                    if 'error' in error_data:
                        error_code = error_data['error'].get('code', 'Unknown')
                        error_msg = error_data['error'].get('message', error_msg)
                    if status_code is None:
                        status_code = error_data.get('status_code')
                except:
                    pass

            if not error_code:
                code_match = re.search(r'([A-Z][a-zA-Z0-9]+(?:\.[A-Z][a-zA-Z0-9]+)*)', error_msg)
                if code_match:
                    error_code = code_match.group(1)
                else:
                    error_code = 'Unknown'

            try:
                parse_and_raise_doubao_error(error_code, error_msg, status_code=status_code)
            except (LLMInvalidParameterError, LLMQuotaExhaustedError, LLMModelNotFoundError,
                    LLMAccessDeniedError, LLMContentFilterError, LLMRateLimitError, LLMTimeoutError):
                raise
            except Exception:
                raise LLMProviderError(f"Volcengine stream error ({error_code}): {error_msg}", provider='volcengine', error_code=error_code)

        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Volcengine {self.model_alias} stream error: {e}")
            raise

    # Alias for compatibility with agents that call chat_completion
    async def chat_completion(self, messages: List[Dict], temperature: Optional[float] = None,
                             max_tokens: int = 2000) -> str:
        """Alias for async_chat_completion for API consistency"""
        result = await self.async_chat_completion(messages, temperature, max_tokens)
        return result.get('content', '') if isinstance(result, dict) else str(result)

# ============================================================================
# GLOBAL CLIENT INSTANCES
# ============================================================================

# Global client instances
try:
    qwen_client_classification = QwenClient(model_type='classification')  # qwen-plus-latest
    qwen_client_generation = QwenClient(model_type='generation')         # qwen-plus
    qwen_client = qwen_client_classification  # Legacy compatibility

    # Multi-LLM clients - Dedicated classes for each provider
    deepseek_client = DeepSeekClient()
    kimi_client = KimiClient()
    hunyuan_client = HunyuanClient()
    # Note: doubao_client uses VolcengineClient with endpoint for higher RPM
    # Fallback to DoubaoClient only if endpoint not configured (for backward compatibility)
    try:
        doubao_client = VolcengineClient('ark-doubao')
    except ValueError:
        # Endpoint not configured, fallback to legacy DoubaoClient
        logger.warning("[clients.llm] ARK_DOUBAO_ENDPOINT not configured, using legacy DoubaoClient")
        doubao_client = DoubaoClient()

    # Only log from main worker to avoid duplicate messages
    import os
    if os.getenv('UVICORN_WORKER_ID') is None or os.getenv('UVICORN_WORKER_ID') == '0':
        logger.info("LLM clients initialized successfully (Qwen, DeepSeek, Kimi, Hunyuan, Doubao)")
except Exception as e:  # pylint: disable=broad-except
    logger.warning(f"Failed to initialize LLM clients: {e}")
    qwen_client = None
    qwen_client_classification = None
    qwen_client_generation = None
    deepseek_client = None
    kimi_client = None
    hunyuan_client = None
    doubao_client = None

def get_llm_client(model_id='qwen'):
    """
    Get an LLM client by model ID.

    Args:
        model_id (str): 'qwen', 'deepseek', 'kimi', 'hunyuan', or 'doubao'

    Returns:
        LLM client instance
    """
    client_map = {
        'qwen': qwen_client_generation,
        'deepseek': deepseek_client,
        'kimi': kimi_client,
        'hunyuan': hunyuan_client,
        'doubao': doubao_client
    }

    client = client_map.get(model_id)

    if client is not None:
        logger.debug(f"Using {model_id} LLM client")
        return client
    else:
        logger.warning("Qwen client not available, using mock client for testing")
        # Return a mock client for testing when real client is not available
        class MockLLMClient:
            def chat_completion(self, messages, temperature=0.7, max_tokens=1000):
                """Mock LLM client that returns structured responses for testing."""
                # Handle the message format that agents use
                if isinstance(messages, list) and len(messages) > 0:
                    # Extract content from messages
                    content = ""
                    for msg in messages:
                        if msg.get('role') == 'user':
                            content += msg.get('content', '')
                        elif msg.get('role') == 'system':
                            content += msg.get('content', '')

                    # Generate appropriate mock responses based on the prompt content
                    if 'double bubble' in content.lower():
                        return {
                            "topic1": "Topic A",
                            "topic2": "Topic B",
                            "topic1_attributes": [
                                {"id": "la1", "text": "Unique to A", "category": "A-only"},
                                {"id": "la2", "text": "Another A trait", "category": "A-only"}
                            ],
                            "topic2_attributes": [
                                {"id": "ra1", "text": "Unique to B", "category": "B-only"},
                                {"id": "ra2", "text": "Another B trait", "category": "B-only"}
                            ],
                            "shared_attributes": [
                                {"id": "shared1", "text": "Common trait", "category": "Shared"},
                                {"id": "shared2", "text": "Another common trait", "category": "Shared"}
                            ],
                            "connections": [
                                {"from": "topic1", "to": "la1", "label": "has"},
                                {"from": "topic1", "to": "la2", "label": "has"},
                                {"from": "topic2", "to": "ra1", "label": "has"},
                                {"from": "topic2", "to": "ra2", "label": "has"},
                                {"from": "topic1", "to": "shared1", "label": "shares"},
                                {"from": "topic2", "to": "shared1", "label": "shares"},
                                {"from": "topic1", "to": "shared2", "label": "shares"},
                                {"from": "topic2", "to": "shared2", "label": "shares"}
                            ]
                        }
                    elif 'bubble map' in content.lower():
                        return {
                            "topic": "Test Topic",
                            "attributes": [
                                {"id": "attr1", "text": "Attribute 1", "category": "Category 1"},
                                {"id": "attr2", "text": "Attribute 2", "category": "Category 2"},
                                {"id": "attr3", "text": "Attribute 3", "category": "Category 3"}
                            ],
                            "connections": [
                                {"from": "topic", "to": "attr1", "label": "has"},
                                {"from": "topic", "to": "attr2", "label": "includes"},
                                {"from": "topic", "to": "attr3", "label": "contains"}
                            ]
                        }
                    elif 'circle map' in content.lower():
                        return {
                            "central_topic": "Central Concept",
                            "inner_circle": {"title": "Definition", "content": "A clear definition of the concept"},
                            "middle_circle": {"title": "Examples", "content": "Example 1, Example 2, Example 3"},
                            "outer_circle": {"title": "Context", "content": "The broader context where this concept applies"},
                            "context_elements": [
                                {"id": "elem1", "text": "Context Element 1"},
                                {"id": "elem2", "text": "Context Element 2"}
                            ],
                            "connections": [
                                {"from": "central_topic", "to": "elem1", "label": "relates to"},
                                {"from": "central_topic", "to": "elem2", "label": "connects to"}
                            ]
                        }
                    elif 'bridge map' in content.lower():
                        return {
                            "analogy_bridge": "Common relationship",
                            "left_side": {
                                "topic": "Source Topic",
                                "elements": [
                                    {"id": "source1", "text": "Source Element 1"},
                                    {"id": "source2", "text": "Source Element 2"}
                                ]
                            },
                            "right_side": {
                                "topic": "Target Topic",
                                "elements": [
                                    {"id": "target1", "text": "Target Element 1"},
                                    {"id": "target2", "text": "Target Element 2"}
                                ]
                            },
                            "bridge_connections": [
                                {"from": "source1", "to": "target1", "label": "relates to", "bridge_text": "Common relationship"},
                                {"from": "source2", "to": "target2", "label": "connects to", "bridge_text": "Common relationship"}
                            ]
                        }
                    elif 'concept map' in content.lower():
                        return {
                            "topic": "Central Topic",
                            "concepts": ["Concept 1", "Concept 2", "Concept 3", "Concept 4"],
                            "relationships": [
                                {"from": "Concept 1", "to": "Concept 2", "label": "relates to"},
                                {"from": "Concept 2", "to": "Concept 3", "label": "includes"},
                                {"from": "Concept 3", "to": "Concept 4", "label": "part of"}
                            ]
                        }
                    elif 'brace map' in content.lower():
                        return {
                            "topic": "Central Topic",
                            "parts": [
                                {"name": "Part 1", "subparts": [{"name": "Subpart 1"}]},
                                {"name": "Part 2", "subparts": [{"name": "Subpart 2"}]}
                            ]
                        }
                    elif 'multi-flow' in content.lower():
                        return {
                            "event": "Multi-Flow Event",
                            "causes": ["Cause 1", "Cause 2", "Cause 3"],
                            "effects": ["Effect 1", "Effect 2", "Effect 3"]
                        }
                    elif 'flow map' in content.lower() or 'flow maps' in content.lower():
                        return {
                            "title": "Flow Topic",
                            "steps": ["Step 1", "Step 2", "Step 3"]
                        }
                    elif 'mind map' in content.lower():
                        return {
                            "topic": "Central Topic",
                            "children": [
                                {"id": "branch1", "label": "Branch 1", "children": [{"id": "sub1", "label": "Sub-item 1"}]},
                                {"id": "branch2", "label": "Branch 2", "children": [{"id": "sub2", "label": "Sub-item 2"}]}
                            ]
                        }
                    elif 'tree map' in content.lower():
                        return {
                            "topic": "Root Topic",
                            "children": [
                                {"id": "branch1", "label": "Branch 1", "children": [{"id": "sub1", "label": "Sub-item 1"}]},
                                {"id": "branch2", "label": "Branch 2", "children": [{"id": "sub2", "label": "Sub-item 2"}]}
                            ]
                        }
                    else:
                        # Generic response for other diagram types
                        return {"result": "mock response", "type": "generic"}
                else:
                    # Fallback for other formats
                    return {"result": "mock response", "type": "fallback"}
        return MockLLMClient()