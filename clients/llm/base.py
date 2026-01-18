"""
Base Classes and Common Utilities for LLM Clients

Provides base classes and shared functionality for all LLM client implementations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, List, Optional, Any, AsyncGenerator
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    """
    Base class for LLM clients.

    Provides common interface and shared functionality.
    """

    def __init__(self, default_temperature: float = 0.7):
        """
        Initialize base LLM client.

        Args:
            default_temperature: Default temperature for sampling
        """
        self.default_temperature = default_temperature

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 1000,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send chat completion request.

        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            **kwargs: Additional parameters

        Returns:
            Dict with 'content' and 'usage' keys
        """

    @abstractmethod
    async def async_stream_chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 1000,
        enable_thinking: bool = False,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat completion.

        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            enable_thinking: Whether to enable thinking mode
            **kwargs: Additional parameters

        Yields:
            Dict with 'type' and 'content' keys
        """

    def _get_temperature(self, temperature: Optional[float]) -> float:
        """
        Get temperature value, using default if not specified.

        Args:
            temperature: Optional temperature value

        Returns:
            Temperature value to use
        """
        return temperature if temperature is not None else self.default_temperature


def extract_usage_from_openai_completion(completion: Any) -> Dict[str, int]:
    """
    Extract usage data from OpenAI SDK completion object.

    Args:
        completion: OpenAI completion object

    Returns:
        Dict with usage statistics
    """
    usage = {}
    if hasattr(completion, 'usage') and completion.usage:
        usage = {
            'prompt_tokens': getattr(completion.usage, 'prompt_tokens', 0),
            'completion_tokens': getattr(completion.usage, 'completion_tokens', 0),
            'total_tokens': getattr(completion.usage, 'total_tokens', 0)
        }
    return usage


def extract_usage_from_stream_chunk(chunk: Any) -> Optional[Dict[str, int]]:
    """
    Extract usage data from OpenAI SDK stream chunk.

    Args:
        chunk: OpenAI stream chunk object

    Returns:
        Dict with usage statistics or None if not present
    """
    if hasattr(chunk, 'usage') and chunk.usage:
        return {
            'prompt_tokens': getattr(chunk.usage, 'prompt_tokens', 0),
            'completion_tokens': getattr(chunk.usage, 'completion_tokens', 0),
            'total_tokens': getattr(chunk.usage, 'total_tokens', 0)
        }
    return None
