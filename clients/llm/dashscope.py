"""
DashScope LLM Clients

Clients for Alibaba Cloud DashScope API:
- QwenClient: Qwen models (qwen-plus, qwen-plus-latest)
- DeepSeekClient: DeepSeek R1 via DashScope
- KimiClient: Kimi (Moonshot AI) via DashScope

All use httpx with HTTP/2 support and DashScope error parsing.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, List, Optional, Any, AsyncGenerator, Union
import json
import logging

import httpx

from config.settings import config
from services.infrastructure.http.error_handler import (
    LLMRateLimitError,
    LLMProviderError,
    LLMAccessDeniedError,
    LLMTimeoutError
)
from services.llm.error_parsers.dashscope_error_parser import parse_and_raise_dashscope_error

logger = logging.getLogger(__name__)


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
    ) -> Dict[str, Any]:
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
                logger.debug('[QwenClient] Additional kwargs passed through: %s', list(kwargs.keys()))
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
                    logger.error('Qwen API error %d: %s', response.status_code, error_text)

                    # Parse error using comprehensive DashScope error parser
                    try:
                        error_data = json.loads(error_text)
                        # This function always raises an exception, never returns
                        parse_and_raise_dashscope_error(response.status_code, error_text, error_data)
                    except json.JSONDecodeError as exc:
                        # Fallback for non-JSON errors
                        if response.status_code == 429:
                            raise LLMRateLimitError(f"Qwen rate limit: {error_text}") from exc
                        elif response.status_code == 401:
                            raise LLMAccessDeniedError(
                                f"Unauthorized: {error_text}",
                                provider='qwen',
                                error_code='Unauthorized'
                            ) from exc
                        else:
                            raise LLMProviderError(
                                f"Qwen API error ({response.status_code}): {error_text}",
                                provider='qwen',
                                error_code=f'HTTP{response.status_code}'
                            ) from exc

        except httpx.TimeoutException as e:
            logger.error('Qwen API timeout')
            raise LLMTimeoutError("Qwen API timeout") from e
        except httpx.HTTPError as e:
            logger.error('Qwen HTTP error: %s', e)
            raise LLMProviderError(f"Qwen HTTP error: {e}", provider='qwen', error_code='HTTPError') from e
        except Exception as e:
            logger.error('Qwen API error: %s', e)
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
                logger.debug('[QwenClient] Additional kwargs in stream: %s', list(kwargs.keys()))
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
                        logger.error('Qwen stream error %d: %s', response.status_code, error_text)

                        # Parse error using comprehensive DashScope error parser
                        try:
                            error_data = json.loads(error_text)
                            parse_and_raise_dashscope_error(response.status_code, error_text, error_data)
                        except json.JSONDecodeError as exc:
                            if response.status_code == 429:
                                raise LLMRateLimitError(f"Qwen rate limit: {error_text}") from exc
                            elif response.status_code == 401:
                                raise LLMAccessDeniedError(
                                    f"Unauthorized: {error_text}",
                                    provider='qwen',
                                    error_code='Unauthorized'
                                ) from exc
                            else:
                                raise LLMProviderError(
                                    f"Qwen stream error ({response.status_code}): {error_text}",
                                    provider='qwen',
                                    error_code=f'HTTP{response.status_code}'
                                ) from exc

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
            logger.error('Qwen streaming timeout')
            raise LLMTimeoutError("Qwen streaming timeout") from e
        except httpx.HTTPError as e:
            logger.error('Qwen streaming HTTP error: %s', e)
            raise LLMProviderError(
                f"Qwen streaming HTTP error: {e}",
                provider='qwen',
                error_code='HTTPError'
            ) from e
        except Exception as e:
            logger.error('Qwen streaming error: %s', e)
            raise


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
        logger.debug('[DeepSeekClient] DeepSeekClient initialized with model: %s', self.model_name)

    async def async_chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
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

            logger.debug('DeepSeek async API request: %s', self.model_name)

            # Use httpx with HTTP/2 support
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                http2=True
            ) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    logger.debug('DeepSeek response length: %d chars', len(content))
                    # Extract usage data
                    usage = data.get('usage', {})
                    return {
                        'content': content,
                        'usage': usage
                    }
                else:
                    error_text = response.text
                    logger.error('DeepSeek API error %d: %s', response.status_code, error_text)

                    # Parse error using comprehensive DashScope error parser
                    try:
                        error_data = json.loads(error_text)
                        parse_and_raise_dashscope_error(response.status_code, error_text, error_data)
                    except json.JSONDecodeError as exc:
                        if response.status_code == 429:
                            raise LLMRateLimitError(f"DeepSeek rate limit: {error_text}") from exc
                        elif response.status_code == 401:
                            raise LLMAccessDeniedError(
                                f"Unauthorized: {error_text}",
                                provider='deepseek',
                                error_code='Unauthorized'
                            ) from exc
                        else:
                            raise LLMProviderError(
                                f"DeepSeek API error ({response.status_code}): {error_text}",
                                provider='deepseek',
                                error_code=f'HTTP{response.status_code}'
                            ) from exc

        except httpx.TimeoutException as e:
            logger.error('DeepSeek API timeout')
            raise LLMTimeoutError("DeepSeek API timeout") from e
        except httpx.HTTPError as e:
            logger.error('DeepSeek HTTP error: %s', e)
            raise LLMProviderError(
                f"DeepSeek HTTP error: {e}",
                provider='deepseek',
                error_code='HTTPError'
            ) from e
        except Exception as e:
            logger.error('DeepSeek API error: %s', e)
            raise

    # Alias for compatibility with agents that call chat_completion
    async def chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
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
                        logger.error('DeepSeek stream error %d: %s', response.status_code, error_text)

                        try:
                            error_data = json.loads(error_text)
                            parse_and_raise_dashscope_error(response.status_code, error_text, error_data)
                        except json.JSONDecodeError as exc:
                            if response.status_code == 429:
                                raise LLMRateLimitError(f"DeepSeek rate limit: {error_text}") from exc
                            elif response.status_code == 401:
                                raise LLMAccessDeniedError(
                                    f"Unauthorized: {error_text}",
                                    provider='deepseek',
                                    error_code='Unauthorized'
                                ) from exc
                            else:
                                raise LLMProviderError(
                                    f"DeepSeek stream error ({response.status_code}): {error_text}",
                                    provider='deepseek',
                                    error_code=f'HTTP{response.status_code}'
                                ) from exc

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
            logger.error('DeepSeek streaming timeout')
            raise LLMTimeoutError("DeepSeek streaming timeout") from e
        except httpx.HTTPError as e:
            logger.error('DeepSeek streaming HTTP error: %s', e)
            raise LLMProviderError(
                f"DeepSeek streaming HTTP error: {e}",
                provider='deepseek',
                error_code='HTTPError'
            ) from e
        except Exception as e:
            logger.error('DeepSeek streaming error: %s', e)
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
        logger.debug('[KimiClient] KimiClient initialized with model: %s', self.model_name)

    async def async_chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
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

            logger.debug('Kimi async API request: %s', self.model_name)

            # Use httpx with HTTP/2 support
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                http2=True
            ) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    logger.debug('Kimi response length: %d chars', len(content))
                    # Extract usage data
                    usage = data.get('usage', {})
                    return {
                        'content': content,
                        'usage': usage
                    }
                else:
                    error_text = response.text
                    logger.error('Kimi API error %d: %s', response.status_code, error_text)

                    try:
                        error_data = json.loads(error_text)
                        parse_and_raise_dashscope_error(response.status_code, error_text, error_data)
                    except json.JSONDecodeError as exc:
                        if response.status_code == 429:
                            raise LLMRateLimitError(f"Kimi rate limit: {error_text}") from exc
                        elif response.status_code == 401:
                            raise LLMAccessDeniedError(
                                f"Unauthorized: {error_text}",
                                provider='kimi',
                                error_code='Unauthorized'
                            ) from exc
                        else:
                            raise LLMProviderError(
                                f"Kimi API error ({response.status_code}): {error_text}",
                                provider='kimi',
                                error_code=f'HTTP{response.status_code}'
                            ) from exc

        except httpx.TimeoutException as e:
            logger.error('Kimi API timeout')
            raise LLMTimeoutError("Kimi API timeout") from e
        except httpx.HTTPError as e:
            logger.error('Kimi HTTP error: %s', e)
            raise LLMProviderError(f"Kimi HTTP error: {e}", provider='kimi', error_code='HTTPError') from e
        except Exception as e:
            logger.error('Kimi API error: %s', e)
            raise

    # Alias for compatibility with agents that call chat_completion
    async def chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
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
                        logger.error('Kimi stream error %d: %s', response.status_code, error_text)

                        try:
                            error_data = json.loads(error_text)
                            parse_and_raise_dashscope_error(response.status_code, error_text, error_data)
                        except json.JSONDecodeError as exc:
                            if response.status_code == 429:
                                raise LLMRateLimitError(f"Kimi rate limit: {error_text}") from exc
                            elif response.status_code == 401:
                                raise LLMAccessDeniedError(
                                    f"Unauthorized: {error_text}",
                                    provider='kimi',
                                    error_code='Unauthorized'
                                ) from exc
                            else:
                                raise LLMProviderError(
                                    f"Kimi stream error ({response.status_code}): {error_text}",
                                    provider='kimi',
                                    error_code=f'HTTP{response.status_code}'
                                ) from exc

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
            logger.error('Kimi streaming timeout')
            raise LLMTimeoutError("Kimi streaming timeout") from e
        except httpx.HTTPError as e:
            logger.error('Kimi streaming HTTP error: %s', e)
            raise LLMProviderError(
                f"Kimi streaming HTTP error: {e}",
                provider='kimi',
                error_code='HTTPError'
            ) from e
        except Exception as e:
            logger.error('Kimi streaming error: %s', e)
            raise
