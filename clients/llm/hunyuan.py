"""
Hunyuan LLM Client

Client for Tencent Cloud Hunyuan (混元) using OpenAI-compatible API.

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
from services.llm.error_parsers.hunyuan_error_parser import parse_and_raise_hunyuan_error
from clients.llm.base import extract_usage_from_openai_completion, extract_usage_from_stream_chunk

logger = logging.getLogger(__name__)


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

        logger.debug('[HunyuanClient] HunyuanClient initialized with OpenAI-compatible API: %s', self.model_name)

    async def async_chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Send async chat completion request to Tencent Hunyuan (OpenAI-compatible)

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

            logger.debug('Hunyuan async API request: %s (temp: %s)', self.model_name, temperature)

            # Call OpenAI-compatible API
            completion = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            # Extract content from response
            content = completion.choices[0].message.content

            if not content:
                logger.error('Hunyuan API returned empty content')
                raise ValueError('Hunyuan API returned empty content')

            logger.debug('Hunyuan response length: %d chars', len(content))
            # Extract usage data
            usage = extract_usage_from_openai_completion(completion)
            return {
                'content': content,
                'usage': usage
            }

        except RateLimitError as e:
            logger.error('Hunyuan rate limit error: %s', e)
            raise LLMRateLimitError(f"Hunyuan rate limit: {e}") from e

        except APIStatusError as e:
            error_msg = str(e)
            logger.error('Hunyuan API status error: %s', error_msg)

            # Try to extract error code from OpenAI SDK error
            error_code: Optional[str] = None
            if hasattr(e, 'code'):
                error_code = e.code
            elif hasattr(e, 'response') and hasattr(e.response, 'json'):
                try:
                    error_data = e.response.json()
                    if 'error' in error_data:
                        error_code = error_data['error'].get('code', 'Unknown')
                        error_msg = error_data['error'].get('message', error_msg)
                except Exception as parse_error:
                    logger.debug('Failed to parse error response JSON: %s', parse_error)

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

            # Ensure error_code is always a string
            if not error_code:
                error_code = 'Unknown'

            # Parse error using comprehensive Hunyuan error parser
            try:
                parse_and_raise_hunyuan_error(error_code, error_msg, status_code=getattr(e, 'status_code', None))
            except (LLMInvalidParameterError, LLMQuotaExhaustedError, LLMModelNotFoundError,
                    LLMAccessDeniedError, LLMContentFilterError, LLMRateLimitError, LLMTimeoutError):
                # Re-raise parsed exceptions
                raise
            except Exception as exc:
                # Fallback to generic error if parsing fails
                raise LLMProviderError(
                    f"Hunyuan API error ({error_code}): {error_msg}",
                    provider='hunyuan',
                    error_code=error_code
                ) from exc

        except Exception as e:
            logger.error('Hunyuan API error: %s', e)
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

            logger.debug('Hunyuan stream API request: %s (temp: %s)', self.model_name, temperature)

            # Use OpenAI SDK's streaming with usage tracking
            # enable_thinking parameter is accepted for API consistency but not used
            _ = enable_thinking
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
            logger.error('Hunyuan streaming rate limit: %s', e)
            raise LLMRateLimitError(f"Hunyuan rate limit: {e}") from e

        except APIStatusError as e:
            error_msg = str(e)
            logger.error('Hunyuan streaming API error: %s', error_msg)

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
                except (KeyError, TypeError, ValueError):
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
            except Exception as exc:
                # Fallback to generic error if parsing fails
                raise LLMProviderError(
                    f"Hunyuan stream error ({error_code}): {error_msg}",
                    provider='hunyuan',
                    error_code=error_code
                ) from exc

        except Exception as e:
            logger.error('Hunyuan streaming error: %s', e)
            raise
