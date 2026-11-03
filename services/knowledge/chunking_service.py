"""
Chunking Service for Knowledge Space
Author: lycosa9527
Made by: MindSpring Team

Splits documents into semantic chunks for vector storage.
Uses semchunk for intelligent, token-aware chunking with Chinese support.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import semchunk
import tiktoken

from services.knowledge.document_structure import StructureHeading
from services.knowledge.section_parser import split_into_sections

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """Represents a text chunk."""

    text: str
    start_char: int
    end_char: int
    chunk_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseChunkingService(ABC):
    """Base interface for chunking services."""

    @abstractmethod
    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        separator: Optional[str] = None,
        extract_structure: bool = False,
        page_info: Optional[List[Dict[str, Any]]] = None,
        language: Optional[str] = None,
    ) -> List[Chunk]:
        """Chunk text into chunks."""

    @abstractmethod
    def estimate_chunk_count(self, text_length: int) -> int:
        """Estimate chunk count."""

    @abstractmethod
    def validate_chunk_count(self, chunk_count: int, user_id: int) -> bool:
        """Validate chunk count."""


class ChunkingService(BaseChunkingService):
    """
    Text chunking service using semchunk for intelligent, token-aware chunking.

    Features:
    - Token-aware splitting (respects chunk_size in tokens)
    - Chinese-aware separators (。！？；)
    - Semantic boundary detection (paragraphs > sentences > words)
    - Fast processing (~87% faster than alternatives)

    Supports modes:
    - Automatic: 500 tokens, 50 overlap (default)
    - Custom: User-defined chunk size and overlap
    - Hierarchical: split on chapter/heading boundaries, then semchunk per section
    """

    # Automatic segmentation rules (like Dify's AUTOMATIC_RULES)
    AUTOMATIC_RULES = {"max_tokens": 500, "chunk_overlap": 50, "separator": "\n\n"}

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        overlap: Optional[int] = None,
        mode: str = "automatic",
    ):
        """
        Initialize chunking service with semchunk.

        Args:
            chunk_size: Tokens per chunk (default: 500)
            overlap: Overlap tokens (default: 50, used for metadata only)
            mode: Segmentation mode ('automatic', 'custom', 'hierarchical')
        """
        self.mode = mode
        self.strategy = "semchunk"  # Always use semchunk

        if mode in {"automatic", "hierarchical"}:
            self.chunk_size = chunk_size or self.AUTOMATIC_RULES["max_tokens"]
            self.overlap = overlap or self.AUTOMATIC_RULES["chunk_overlap"]
        else:
            self.chunk_size = chunk_size or int(os.getenv("CHUNK_SIZE", "500"))
            self.overlap = overlap or int(os.getenv("CHUNK_OVERLAP", "50"))

        # Validate chunk size
        max_segmentation_tokens = int(os.getenv("MAX_SEGMENTATION_TOKENS", "2000"))
        if self.chunk_size < 50 or self.chunk_size > max_segmentation_tokens:
            logger.warning(
                "[ChunkingService] Chunk size %s out of range [50, %s], using default 500",
                self.chunk_size,
                max_segmentation_tokens,
            )
            self.chunk_size = 500

        # Initialize tiktoken for accurate token counting
        self._encoding = tiktoken.get_encoding("cl100k_base")
        self._token_counter: Callable[[str], int] = lambda text: len(self._encoding.encode(text))

        # Create semchunk chunker
        # semchunk automatically handles Chinese punctuation (。！？) as sentence boundaries
        chunkerify = getattr(semchunk, "chunkerify")
        self._chunker = chunkerify(
            self._token_counter,
            chunk_size=self.chunk_size,
        )

        logger.info(
            "[ChunkingService] Initialized with mode=%s, chunk_size=%s, overlap=%s",
            mode,
            self.chunk_size,
            self.overlap,
        )

    def _split(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        page_info: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Chunk]:
        """
        Split text using semchunk.

        Args:
            text: Text to chunk
            metadata: Optional metadata
            page_info: Optional page boundaries for PDFs

        Returns:
            List of Chunk objects
        """
        if not text or not text.strip():
            return []

        # Use semchunk for splitting
        chunk_texts = self._chunker(text)

        # Ensure chunk_texts is a list of strings
        if not isinstance(chunk_texts, list):
            chunk_texts = list(chunk_texts)

        chunks = []
        current_pos = 0

        for i, chunk_text in enumerate(chunk_texts):
            # Ensure chunk_text is a string
            if not isinstance(chunk_text, str):
                logger.warning(
                    "[ChunkingService] Unexpected chunk type: %s, skipping",
                    type(chunk_text),
                )
                continue

            # Find position in original text
            start_pos = text.find(chunk_text, current_pos)
            if start_pos == -1:
                start_pos = current_pos
            end_pos = start_pos + len(chunk_text)
            current_pos = end_pos

            # Build metadata
            chunk_metadata = dict(metadata or {})

            # Add page number if available
            if page_info:
                for page_data in page_info:
                    if page_data["start"] <= start_pos < page_data["end"]:
                        chunk_metadata["page_number"] = page_data["page"]
                        break

            # Add token count
            chunk_metadata["token_count"] = self._token_counter(chunk_text)

            chunk = Chunk(
                text=chunk_text.strip(),
                start_char=start_pos,
                end_char=end_pos,
                chunk_index=i,
                metadata=chunk_metadata,
            )
            chunks.append(chunk)

        logger.debug(
            "[ChunkingService] Created %s chunks from %s chars (avg %s chars/chunk)",
            len(chunks),
            len(text),
            len(text) // max(len(chunks), 1),
        )
        return chunks

    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        separator: Optional[str] = None,
        extract_structure: bool = False,
        page_info: Optional[List[Dict[str, Any]]] = None,
        language: Optional[str] = None,
        structure_headings: Optional[List[StructureHeading]] = None,
    ) -> List[Chunk]:
        """
        Split text into chunks using semchunk.

        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to chunks
            separator: Ignored (semchunk uses its own separators)
            extract_structure: When True, split on headings before semchunk
            page_info: Optional list of page boundaries for PDFs
            language: Ignored (semchunk handles Chinese automatically)
            structure_headings: PDF outline / DOCX style headings

        Returns:
            List of Chunk objects
        """
        if self.mode == "hierarchical" or extract_structure:
            return self._chunk_hierarchical(text, metadata, page_info, structure_headings)
        return self._split(text, metadata, page_info)

    def _chunk_hierarchical(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        page_info: Optional[List[Dict[str, Any]]] = None,
        structure_headings: Optional[List[StructureHeading]] = None,
    ) -> List[Chunk]:
        """Split on detected headings, then semchunk each section body."""
        sections = split_into_sections(text, structure_headings, page_info)
        if not sections:
            return self._split(text, metadata, page_info)

        all_chunks: List[Chunk] = []
        chunk_index = 0
        for section in sections:
            section_meta = dict(metadata or {})
            section_meta.update(
                {
                    "section_title": section.title,
                    "section_level": section.level,
                    "section_key": section.section_key,
                    "section_number": section.section_number,
                }
            )
            section_chunks = self._split(section.body, section_meta, page_info)
            for chunk in section_chunks:
                chunk.chunk_index = chunk_index
                chunk.start_char += section.start
                chunk.end_char += section.start
                chunk_index += 1
                all_chunks.append(chunk)

        logger.info(
            "[ChunkingService] Hierarchical semchunk: %s sections → %s chunks",
            len(sections),
            len(all_chunks),
        )
        return all_chunks

    def estimate_chunk_count(self, text_length: int) -> int:
        """
        Estimate number of chunks for text length.

        Args:
            text_length: Length of text in characters

        Returns:
            Estimated chunk count
        """
        char_size = self.chunk_size * 4
        char_overlap = self.overlap * 4
        effective_size = char_size - char_overlap

        if effective_size <= 0:
            return 1

        count = max(1, (text_length + effective_size - 1) // effective_size)
        return count

    def validate_chunk_count(self, chunk_count: int, user_id: int) -> bool:
        """
        Validate chunk count doesn't exceed limits.

        Args:
            chunk_count: Number of chunks
            user_id: User ID (for logging)

        Returns:
            True if valid
        """
        max_chunks = int(os.getenv("MAX_CHUNKS_PER_USER", "1000"))

        if chunk_count > max_chunks:
            logger.warning(
                "[ChunkingService] User %s would exceed chunk limit: %s > %s",
                user_id,
                chunk_count,
                max_chunks,
            )
            return False

        return True


_chunking_service_container: Dict[str, Optional[ChunkingService]] = {"instance": None}


def get_chunking_service() -> ChunkingService:
    """Return the process-wide semchunk service."""
    if _chunking_service_container["instance"] is None:
        logger.info("[ChunkingService] Using semchunk")
        _chunking_service_container["instance"] = ChunkingService()
    instance = _chunking_service_container["instance"]
    assert instance is not None, "Chunking service should be initialized"
    return instance
