"""
Token counting utilities for chunking.
"""

import tiktoken
import logging
from typing import Callable
from functools import lru_cache

logger = logging.getLogger(__name__)


class TokenCounter:
    """Token counter using tiktoken with memoization."""

    def __init__(self, encoding_name: str = "cl100k_base", cache_size: int = 4096):
        """
        Initialize token counter.

        Args:
            encoding_name: Tiktoken encoding name (default: cl100k_base for GPT-4)
            cache_size: Maximum cache size for memoization (default: 4096)
        """
        self.encoding = tiktoken.get_encoding(encoding_name)
        self._base_counter: Callable[[str], int] = lambda text: len(self.encoding.encode(text))

        # Phase 4: Add memoization for token counter
        self._counter = lru_cache(maxsize=cache_size)(self._base_counter)

    def count(self, text: str) -> int:
        """
        Count tokens in text (with memoization).

        Args:
            text: Text to count

        Returns:
            Number of tokens
        """
        if not text:
            return 0
        return self._counter(text)

    def count_batch(self, texts: list[str]) -> list[int]:
        """
        Count tokens for multiple texts (with memoization).

        Args:
            texts: List of texts

        Returns:
            List of token counts
        """
        return [self.count(text) for text in texts]

    def get_counter(self) -> Callable[[str], int]:
        """
        Get token counter function (with memoization).

        Returns:
            Function that counts tokens
        """
        return self._counter

    def clear_cache(self):
        """Clear the token counter cache."""
        self._counter.cache_clear()
