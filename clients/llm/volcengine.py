"""
Volcengine LLM Clients

Clients for Volcengine ARK API:
- DoubaoClient: Deprecated client using direct model names
- VolcengineClient: Preferred client using endpoint IDs for higher RPM

Both use OpenAI-compatible API with Volcengine error parsing.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, List, Optional, Any, AsyncGenerator
import logging
import re

from openai import AsyncOpenAI, RateLimitError, APIStatusError

from config.settings import config
from services.infrastructure.http.error_handler import (
    LLMRateLimitError,
    LLMProviderError,
    LLMInvalidParameterError,
    LLMQuotaExhaustedError,
    LLMModelNotFoundError,
    LLMAccessDeniedError,
    LLMContentFilterError,
    LLMTimeoutError
)
from services.llm.error_parsers.doubao_error_parser import parse_and_raise_doubao_error
from clients.llm.base import extract_usage_from_openai_completion, extract_usage_from_stream_chunk

logger = logging.getLogger(__name__)


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

        logger.debug('DoubaoClient initialized with OpenAI-compatible API: %s', self.model_name)

    async def async_chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Send async chat completion request to Volcengine Doubao (OpenAI-compatible)

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0), None uses default
            max_tokens: Maximum tokens in response

        Returns:
            Dict with 'content' and 'usage' keys
        """
        try:
            # Use instance default if not specified
            if temperature is None:
                temperature = self.default_temperature

            logger.debug('Doubao async API request: %s (temp: %s)', self.model_name, temperature)

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
                logger.debug('Doubao response length: %d chars', len(content))
                # Extract usage data
                usage = extract_usage_from_openai_completion(completion)
                return {
                    'content': content,
                    'usage': usage
                }
            else:
                logger.error('Doubao API returned empty content')
                raise ValueError('Doubao API returned empty content')

        except RateLimitError as e:
            logger.error('Doubao rate limit error: %s', e)
            raise LLMRateLimitError(f"Doubao rate limit: {e}") from e

        except APIStatusError as e:
            error_msg = str(e)
            logger.error('Doubao API status error: %s', error_msg)

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
                except (KeyError, TypeError, ValueError):
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
                # If parse_and_raise_doubao_error doesn't raise, fallback to generic error
                raise LLMProviderError(
                    f"Doubao API error ({error_code}): {error_msg}",
                    provider='doubao',
                    error_code=error_code
                ) from e
            except (LLMInvalidParameterError, LLMQuotaExhaustedError, LLMModelNotFoundError,
                    LLMAccessDeniedError, LLMContentFilterError, LLMRateLimitError, LLMTimeoutError):
                # Re-raise parsed exceptions
                raise
            except Exception as exc:
                # Fallback to generic error if parsing fails
                raise LLMProviderError(
                    f"Doubao API error ({error_code}): {error_msg}",
                    provider='doubao',
                    error_code=error_code
                ) from exc

        except Exception as e:
            logger.error('Doubao API error: %s', e)
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

            logger.debug('Doubao stream API request: %s (temp: %s)', self.model_name, temperature)

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
                usage_data = extract_usage_from_stream_chunk(chunk)
                if usage_data:
                    last_usage = usage_data

                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield {'type': 'token', 'content': delta.content}

            # Yield usage data as final chunk
            if last_usage:
                yield {'type': 'usage', 'usage': last_usage}

        except RateLimitError as e:
            logger.error('Doubao streaming rate limit: %s', e)
            raise LLMRateLimitError(f"Doubao rate limit: {e}") from e

        except APIStatusError as e:
            error_msg = str(e)
            logger.error('Doubao streaming API error: %s', error_msg)

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
                except (KeyError, TypeError, ValueError):
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
            except Exception as exc:
                # Fallback to generic error if parsing fails
                raise LLMProviderError(
                    f"Doubao stream error ({error_code}): {error_msg}",
                    provider='doubao',
                    error_code=error_code
                ) from exc

        except Exception as e:
            logger.error('Doubao streaming error: %s', e)
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
            '[VolcengineClient] VolcengineClient initialized: %s → endpoint=%s',
            model_alias,
            self.endpoint_id
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
    ) -> Dict[str, Any]:
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

            logger.debug('Volcengine %s request: endpoint=%s', self.model_alias, self.endpoint_id)

            completion = await self.client.chat.completions.create(
                model=self.endpoint_id,  # Use endpoint ID for higher RPM!
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            content = completion.choices[0].message.content

            # Extract usage
            usage = extract_usage_from_openai_completion(completion)

            return {
                'content': content,
                'usage': usage
            }

        except RateLimitError as e:
            logger.error('Volcengine %s rate limit: %s', self.model_alias, e)
            raise LLMRateLimitError(f"Volcengine rate limit: {e}") from e

        except APIStatusError as e:
            logger.error('Volcengine %s API error: %s', self.model_alias, e)
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
                except (KeyError, TypeError, ValueError):
                    pass

            if not error_code:
                code_match = re.search(r'([A-Z][a-zA-Z0-9]+(?:\.[A-Z][a-zA-Z0-9]+)*)', error_msg)
                if code_match:
                    error_code = code_match.group(1)
                else:
                    error_code = 'Unknown'

            try:
                parse_and_raise_doubao_error(error_code, error_msg, status_code=status_code)
                # If parse_and_raise_doubao_error doesn't raise, fallback to generic error
                raise LLMProviderError(
                    f"Volcengine API error ({error_code}): {error_msg}",
                    provider='volcengine',
                    error_code=error_code
                ) from e
            except (LLMInvalidParameterError, LLMQuotaExhaustedError, LLMModelNotFoundError,
                    LLMAccessDeniedError, LLMContentFilterError, LLMRateLimitError, LLMTimeoutError):
                raise
            except Exception as exc:
                raise LLMProviderError(
                    f"Volcengine API error ({error_code}): {error_msg}",
                    provider='volcengine',
                    error_code=error_code
                ) from exc

        except Exception as e:
            logger.error('Volcengine %s error: %s', self.model_alias, e)
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

            logger.debug('Volcengine %s stream: endpoint=%s', self.model_alias, self.endpoint_id)

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
                usage_data = extract_usage_from_stream_chunk(chunk)
                if usage_data:
                    last_usage = usage_data

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
            logger.error('Volcengine %s stream rate limit: %s', self.model_alias, e)
            raise LLMRateLimitError(f"Volcengine rate limit: {e}") from e

        except APIStatusError as e:
            error_msg = str(e)
            logger.error('Volcengine %s streaming API error: %s', self.model_alias, error_msg)

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
                except (KeyError, TypeError, ValueError):
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
            except Exception as exc:
                raise LLMProviderError(
                    f"Volcengine stream error ({error_code}): {error_msg}",
                    provider='volcengine',
                    error_code=error_code
                ) from exc

        except Exception as e:
            logger.error('Volcengine %s stream error: %s', self.model_alias, e)
            raise

    # Alias for compatibility with agents that call chat_completion
    async def chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 2000
    ) -> str:
        """Alias for async_chat_completion for API consistency"""
        result = await self.async_chat_completion(messages, temperature, max_tokens)
        return result.get('content', '') if isinstance(result, dict) else str(result)
