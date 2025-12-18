"""
LLM Clients for Hybrid Agent Processing

This module provides async interfaces for Qwen LLM clients
used by diagram agents for layout optimization and style enhancement.
"""

import asyncio
import aiohttp
import json
import logging
import os
import re
from typing import Dict, List, Optional, Any, AsyncGenerator
from dotenv import load_dotenv
from openai import AsyncOpenAI, APIError, RateLimitError, APIStatusError
from config.settings import config
from services.error_handler import (
    LLMRateLimitError, 
    LLMContentFilterError, 
    LLMProviderError,
    LLMInvalidParameterError,
    LLMQuotaExhaustedError,
    LLMModelNotFoundError,
    LLMAccessDeniedError,
    LLMTimeoutError
)
from services.dashscope_error_parser import parse_and_raise_dashscope_error
from services.hunyuan_error_parser import parse_and_raise_hunyuan_error
from services.doubao_error_parser import parse_and_raise_doubao_error

# Load environment variables for logging configuration
load_dotenv()

logger = logging.getLogger(__name__)


class QwenClient:
    """Async client for Qwen LLM API"""
    
    def __init__(self, model_type='classification'):
        """
        Initialize QwenClient with specific model type
        
        Args:
            model_type (str): 'classification' for qwen-turbo, 'generation' for qwen-plus
        """
        self.api_url = config.QWEN_API_URL
        self.api_key = config.QWEN_API_KEY
        self.timeout = 30  # seconds
        self.model_type = model_type
        # DIVERSITY FIX: Use higher temperature for generation to increase variety
        self.default_temperature = 0.9 if model_type == 'generation' else 0.7
        
    async def chat_completion(self, messages: List[Dict], temperature: float = None,
                            max_tokens: int = 1000) -> str:
        """
        Send chat completion request to Qwen (async version)
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0), None uses default
            max_tokens: Maximum tokens in response
            
        Returns:
            Response content as string
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
                
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
                # Qwen3 models require enable_thinking: False when not using streaming
                # to avoid API errors. This is automatically included in all Qwen API calls.
                "extra_body": {"enable_thinking": False}
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                        # Extract usage data (Dashscope uses 'prompt_tokens'/'completion_tokens')
                        usage = data.get('usage', {})
                        # Return both content and usage for token tracking
                        return {
                            'content': content,
                            'usage': usage  # Contains prompt_tokens, completion_tokens, total_tokens
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Qwen API error {response.status}: {error_text}")
                        
                        # Parse error using comprehensive DashScope error parser
                        try:
                            error_data = json.loads(error_text)
                            # This function always raises an exception, never returns
                            parse_and_raise_dashscope_error(response.status, error_text, error_data)
                        except json.JSONDecodeError:
                            # Fallback for non-JSON errors
                            if response.status == 429:
                                raise LLMRateLimitError(f"Qwen rate limit: {error_text}")
                            elif response.status == 401:
                                raise LLMAccessDeniedError(f"Unauthorized: {error_text}", provider='qwen', error_code='Unauthorized')
                            else:
                                raise LLMProviderError(f"Qwen API error ({response.status}): {error_text}", provider='qwen', error_code=f'HTTP{response.status}')
                        
        except asyncio.TimeoutError as e:
            logger.error("Qwen API timeout")
            raise LLMTimeoutError("Qwen API timeout") from e
        except Exception as e:
            logger.error(f"Qwen API error: {e}")
            raise
    
    async def async_stream_chat_completion(
        self, 
        messages: List[Dict], 
        temperature: float = None,
        max_tokens: int = 1000
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion from Qwen API (async generator).
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0), None uses default
            max_tokens: Maximum tokens in response
            
        Yields:
            str: Content chunks as they arrive from Qwen API
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
            
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,  # Enable streaming
                "extra_body": {"enable_thinking": False}
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Stream with timeout
            timeout = aiohttp.ClientTimeout(
                total=None,  # No total timeout for streaming
                connect=10,
                sock_read=self.timeout
            )
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Qwen stream error {response.status}: {error_text}")
                        
                        # Parse error using comprehensive DashScope error parser
                        try:
                            error_data = json.loads(error_text)
                            # This function always raises an exception, never returns
                            parse_and_raise_dashscope_error(response.status, error_text, error_data)
                        except json.JSONDecodeError:
                            # Fallback for non-JSON errors
                            if response.status == 429:
                                raise LLMRateLimitError(f"Qwen rate limit: {error_text}")
                            elif response.status == 401:
                                raise LLMAccessDeniedError(f"Unauthorized: {error_text}", provider='qwen', error_code='Unauthorized')
                            else:
                                raise LLMProviderError(f"Qwen stream error ({response.status}): {error_text}", provider='qwen', error_code=f'HTTP{response.status}')
                    
                    # Read SSE stream line by line
                    last_usage = None
                    async for line_bytes in response.content:
                        line = line_bytes.decode('utf-8').strip()
                        
                        if not line or not line.startswith('data: '):
                            continue
                        
                        data_content = line[6:]  # Remove 'data: ' prefix
                        
                        # Handle [DONE] signal
                        if data_content.strip() == '[DONE]':
                            # Yield usage data as final chunk
                            if last_usage:
                                yield {'type': 'usage', 'usage': last_usage}
                            break
                        
                        try:
                            data = json.loads(data_content)
                            
                            # Check for usage data (in final chunk)
                            if 'usage' in data:
                                last_usage = data.get('usage', {})
                                # Continue to also yield content if present
                            
                            # Extract content delta from streaming response
                            delta = data.get('choices', [{}])[0].get('delta', {})
                            content = delta.get('content', '')
                            
                            if content:
                                yield {'type': 'token', 'content': content}
                        
                        except json.JSONDecodeError:
                            continue
                    
                    # If we didn't get [DONE] but stream ended, yield usage if we have it
                    if last_usage:
                        yield {'type': 'usage', 'usage': last_usage}
        
        except Exception as e:
            logger.error(f"Qwen streaming error: {e}")
            raise


# ============================================================================
# MULTI-LLM CLIENT (DeepSeek, Kimi, ChatGLM)
# ============================================================================

class DeepSeekClient:
    """Client for DeepSeek R1 via Dashscope API"""
    
    def __init__(self):
        """Initialize DeepSeek client"""
        self.api_url = config.QWEN_API_URL  # Dashscope uses same endpoint
        self.api_key = config.QWEN_API_KEY
        self.timeout = 60  # seconds (DeepSeek R1 can be slower for reasoning)
        self.model_id = 'deepseek'
        self.model_name = config.DEEPSEEK_MODEL
        # DIVERSITY FIX: Lower temperature for DeepSeek (reasoning model, more deterministic)
        self.default_temperature = 0.6
        logger.debug(f"DeepSeekClient initialized with model: {self.model_name}")
    
    async def async_chat_completion(self, messages: List[Dict], temperature: float = None,
                                   max_tokens: int = 2000) -> str:
        """
        Send async chat completion request to DeepSeek R1
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0), None uses default
            max_tokens: Maximum tokens in response
            
        Returns:
            Response content as string
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
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                        logger.debug(f"DeepSeek response length: {len(content)} chars")
                        # Extract usage data
                        usage = data.get('usage', {})
                        return {
                            'content': content,
                            'usage': usage
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"DeepSeek API error {response.status}: {error_text}")
                        
                        # Parse error using comprehensive DashScope error parser
                        try:
                            error_data = json.loads(error_text)
                            # This function always raises an exception, never returns
                            parse_and_raise_dashscope_error(response.status, error_text, error_data)
                        except json.JSONDecodeError:
                            # Fallback for non-JSON errors
                            if response.status == 429:
                                raise LLMRateLimitError(f"DeepSeek rate limit: {error_text}")
                            elif response.status == 401:
                                raise LLMAccessDeniedError(f"Unauthorized: {error_text}", provider='deepseek', error_code='Unauthorized')
                            else:
                                raise LLMProviderError(f"DeepSeek API error ({response.status}): {error_text}", provider='deepseek', error_code=f'HTTP{response.status}')
                        
        except asyncio.TimeoutError as e:
            logger.error("DeepSeek API timeout")
            raise LLMTimeoutError("DeepSeek API timeout") from e
        except Exception as e:
            logger.error(f"DeepSeek API error: {e}")
            raise
    
    # Alias for compatibility with agents that call chat_completion
    async def chat_completion(self, messages: List[Dict], temperature: float = None,
                             max_tokens: int = 2000) -> str:
        """Alias for async_chat_completion for API consistency"""
        return await self.async_chat_completion(messages, temperature, max_tokens)
    
    async def async_stream_chat_completion(
        self, 
        messages: List[Dict], 
        temperature: float = None,
        max_tokens: int = 2000
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion from DeepSeek R1 (async generator).
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0), None uses default
            max_tokens: Maximum tokens in response
            
        Yields:
            str: Content chunks as they arrive
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
            payload['stream'] = True  # Enable streaming
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            timeout = aiohttp.ClientTimeout(
                total=None,
                connect=10,
                sock_read=self.timeout
            )
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"DeepSeek stream error {response.status}: {error_text}")
                        
                        # Parse error using comprehensive DashScope error parser
                        try:
                            error_data = json.loads(error_text)
                            # This function always raises an exception, never returns
                            parse_and_raise_dashscope_error(response.status, error_text, error_data)
                        except json.JSONDecodeError:
                            # Fallback for non-JSON errors
                            if response.status == 429:
                                raise LLMRateLimitError(f"DeepSeek rate limit: {error_text}")
                            elif response.status == 401:
                                raise LLMAccessDeniedError(f"Unauthorized: {error_text}", provider='deepseek', error_code='Unauthorized')
                            else:
                                raise LLMProviderError(f"DeepSeek stream error ({response.status}): {error_text}", provider='deepseek', error_code=f'HTTP{response.status}')
                    
                    last_usage = None
                    async for line_bytes in response.content:
                        line = line_bytes.decode('utf-8').strip()
                        
                        if not line or not line.startswith('data: '):
                            continue
                        
                        data_content = line[6:]
                        
                        if data_content.strip() == '[DONE]':
                            # Yield usage data as final chunk
                            if last_usage:
                                yield {'type': 'usage', 'usage': last_usage}
                            break
                        
                        try:
                            data = json.loads(data_content)
                            
                            # Check for usage data (in final chunk)
                            if 'usage' in data:
                                last_usage = data.get('usage', {})
                            
                            delta = data.get('choices', [{}])[0].get('delta', {})
                            content = delta.get('content', '')
                            
                            if content:
                                yield {'type': 'token', 'content': content}
                        
                        except json.JSONDecodeError:
                            continue
                    
                    # If we didn't get [DONE] but stream ended, yield usage if we have it
                    if last_usage:
                        yield {'type': 'usage', 'usage': last_usage}
        
        except Exception as e:
            logger.error(f"DeepSeek streaming error: {e}")
            raise


class KimiClient:
    """Client for Kimi (Moonshot AI) via Dashscope API"""
    
    def __init__(self):
        """Initialize Kimi client"""
        self.api_url = config.QWEN_API_URL  # Dashscope uses same endpoint
        self.api_key = config.QWEN_API_KEY
        self.timeout = 60  # seconds
        self.model_id = 'kimi'
        self.model_name = config.KIMI_MODEL
        # DIVERSITY FIX: Higher temperature for Kimi to increase creative variation
        self.default_temperature = 1.0
        logger.debug(f"KimiClient initialized with model: {self.model_name}")
    
    async def async_chat_completion(self, messages: List[Dict], temperature: float = None,
                                   max_tokens: int = 2000) -> str:
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
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                        logger.debug(f"Kimi response length: {len(content)} chars")
                        # Extract usage data
                        usage = data.get('usage', {})
                        return {
                            'content': content,
                            'usage': usage
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Kimi API error {response.status}: {error_text}")
                        
                        # Parse error using comprehensive DashScope error parser
                        try:
                            error_data = json.loads(error_text)
                            # This function always raises an exception, never returns
                            parse_and_raise_dashscope_error(response.status, error_text, error_data)
                        except json.JSONDecodeError:
                            # Fallback for non-JSON errors
                            if response.status == 429:
                                raise LLMRateLimitError(f"Kimi rate limit: {error_text}")
                            elif response.status == 401:
                                raise LLMAccessDeniedError(f"Unauthorized: {error_text}", provider='kimi', error_code='Unauthorized')
                            else:
                                raise LLMProviderError(f"Kimi API error ({response.status}): {error_text}", provider='kimi', error_code=f'HTTP{response.status}')
                        
        except asyncio.TimeoutError as e:
            logger.error("Kimi API timeout")
            raise LLMTimeoutError("Kimi API timeout") from e
        except Exception as e:
            logger.error(f"Kimi API error: {e}")
            raise
    
    # Alias for compatibility with agents that call chat_completion
    async def chat_completion(self, messages: List[Dict], temperature: float = None,
                             max_tokens: int = 2000) -> str:
        """Alias for async_chat_completion for API consistency"""
        return await self.async_chat_completion(messages, temperature, max_tokens)
    
    async def async_stream_chat_completion(
        self, 
        messages: List[Dict], 
        temperature: float = None,
        max_tokens: int = 2000
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion from Kimi (async generator).
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0), None uses default
            max_tokens: Maximum tokens in response
            
        Yields:
            str: Content chunks as they arrive
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
            payload['stream'] = True  # Enable streaming
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            timeout = aiohttp.ClientTimeout(
                total=None,
                connect=10,
                sock_read=self.timeout
            )
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Kimi stream error {response.status}: {error_text}")
                        
                        # Parse error using comprehensive DashScope error parser
                        try:
                            error_data = json.loads(error_text)
                            # This function always raises an exception, never returns
                            parse_and_raise_dashscope_error(response.status, error_text, error_data)
                        except json.JSONDecodeError:
                            # Fallback for non-JSON errors
                            if response.status == 429:
                                raise LLMRateLimitError(f"Kimi rate limit: {error_text}")
                            elif response.status == 401:
                                raise LLMAccessDeniedError(f"Unauthorized: {error_text}", provider='kimi', error_code='Unauthorized')
                            else:
                                raise LLMProviderError(f"Kimi stream error ({response.status}): {error_text}", provider='kimi', error_code=f'HTTP{response.status}')
                    
                    last_usage = None
                    async for line_bytes in response.content:
                        line = line_bytes.decode('utf-8').strip()
                        
                        if not line or not line.startswith('data: '):
                            continue
                        
                        data_content = line[6:]
                        
                        if data_content.strip() == '[DONE]':
                            # Yield usage data as final chunk
                            if last_usage:
                                yield {'type': 'usage', 'usage': last_usage}
                            break
                        
                        try:
                            data = json.loads(data_content)
                            
                            # Check for usage data (in final chunk)
                            if 'usage' in data:
                                last_usage = data.get('usage', {})
                            
                            delta = data.get('choices', [{}])[0].get('delta', {})
                            content = delta.get('content', '')
                            
                            if content:
                                yield {'type': 'token', 'content': content}
                        
                        except json.JSONDecodeError:
                            continue
                    
                    # If we didn't get [DONE] but stream ended, yield usage if we have it
                    if last_usage:
                        yield {'type': 'usage', 'usage': last_usage}
        
        except Exception as e:
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
    
    async def async_chat_completion(self, messages: List[Dict], temperature: float = None,
                                   max_tokens: int = 2000) -> str:
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
                
        except Exception as e:
            logger.error(f"Hunyuan API error: {e}")
            raise
    
    # Alias for compatibility with agents that call chat_completion
    async def chat_completion(self, messages: List[Dict], temperature: float = None,
                             max_tokens: int = 2000) -> str:
        """Alias for async_chat_completion for API consistency"""
        return await self.async_chat_completion(messages, temperature, max_tokens)
    
    async def async_stream_chat_completion(
        self, 
        messages: List[Dict], 
        temperature: float = None,
        max_tokens: int = 2000
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion from Hunyuan using OpenAI-compatible API.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0), None uses default
            max_tokens: Maximum tokens in response
            
        Yields:
            str: Content chunks as they arrive
        """
        try:
            if temperature is None:
                temperature = self.default_temperature
            
            logger.debug(f"Hunyuan stream API request: {self.model_name} (temp: {temperature})")
            
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
        
        except Exception as e:
            logger.error(f"Hunyuan streaming error: {e}")
            raise


class DoubaoClient:
    """Client for Volcengine Doubao (豆包) using OpenAI-compatible API"""
    
    def __init__(self):
        """Initialize Doubao client with OpenAI SDK"""
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
    
    async def async_chat_completion(self, messages: List[Dict], temperature: float = None,
                                   max_tokens: int = 2000) -> str:
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
                
        except Exception as e:
            logger.error(f"Doubao API error: {e}")
            raise
    
    # Alias for compatibility with agents that call chat_completion
    async def chat_completion(self, messages: List[Dict], temperature: float = None,
                             max_tokens: int = 2000) -> str:
        """Alias for async_chat_completion for API consistency"""
        return await self.async_chat_completion(messages, temperature, max_tokens)
    
    async def async_stream_chat_completion(
        self, 
        messages: List[Dict], 
        temperature: float = None,
        max_tokens: int = 2000
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion from Doubao using OpenAI-compatible API.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0), None uses default
            max_tokens: Maximum tokens in response
            
        Yields:
            str: Content chunks as they arrive
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
        
        except Exception as e:
            logger.error(f"Doubao streaming error: {e}")
            raise

# ============================================================================
# GLOBAL CLIENT INSTANCES
# ============================================================================

# Global client instances
try:
    qwen_client_classification = QwenClient(model_type='classification')  # qwen-turbo
    qwen_client_generation = QwenClient(model_type='generation')         # qwen-plus
    qwen_client = qwen_client_classification  # Legacy compatibility
    
    # Multi-LLM clients - Dedicated classes for each provider
    deepseek_client = DeepSeekClient()
    kimi_client = KimiClient()
    hunyuan_client = HunyuanClient()
    doubao_client = DoubaoClient()
    
    # Only log from main worker to avoid duplicate messages
    import os
    if os.getenv('UVICORN_WORKER_ID') is None or os.getenv('UVICORN_WORKER_ID') == '0':
        logger.info("LLM clients initialized successfully (Qwen, DeepSeek, Kimi, Hunyuan, Doubao)")
except Exception as e:
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