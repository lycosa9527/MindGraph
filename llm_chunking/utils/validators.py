"""
Chunk validation utilities.
"""

import logging
from typing import List
from llm_chunking.models import Chunk, ParentChunk

logger = logging.getLogger(__name__)


class ChunkValidator:
    """Validate chunk quality and structure."""

    def __init__(self, min_tokens: int = 10, max_tokens: int = 2000):
        """
        Initialize validator.

        Args:
            min_tokens: Minimum tokens per chunk
            max_tokens: Maximum tokens per chunk
        """
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens

    def validate_chunk(self, chunk: Chunk, token_count: int) -> bool:
        """
        Validate a single chunk.

        Args:
            chunk: Chunk to validate
            token_count: Token count of chunk

        Returns:
            True if valid
        """
        if token_count < self.min_tokens:
            logger.warning(
                f"Chunk {chunk.chunk_index} too small: {token_count} < {self.min_tokens} tokens"
            )
            return False

        if token_count > self.max_tokens:
            logger.warning(
                f"Chunk {chunk.chunk_index} too large: {token_count} > {self.max_tokens} tokens"
            )
            return False

        if not chunk.text or not chunk.text.strip():
            logger.warning("Chunk %s is empty", chunk.chunk_index)
            return False

        return True

    def validate_chunks(self, chunks: List[Chunk], token_counts: List[int]) -> List[Chunk]:
        """
        Validate multiple chunks.

        Args:
            chunks: List of chunks
            token_counts: List of token counts

        Returns:
            List of valid chunks
        """
        valid_chunks = []

        for chunk, token_count in zip(chunks, token_counts):
            if self.validate_chunk(chunk, token_count):
                valid_chunks.append(chunk)

        return valid_chunks

    def validate_parent_chunk(self, parent: ParentChunk, child_token_counts: List[int]) -> bool:
        """
        Validate parent chunk and its children.

        Args:
            parent: Parent chunk
            child_token_counts: Token counts for children

        Returns:
            True if valid
        """
        if not parent.children:
            logger.warning("Parent chunk %s has no children", parent.chunk_index)
            return False

        # Validate all children
        for child, token_count in zip(parent.children, child_token_counts):
            if not self.validate_chunk(child, token_count):
                return False

        return True
