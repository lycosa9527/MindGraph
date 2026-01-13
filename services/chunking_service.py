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

import os
import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field

import semchunk
import tiktoken

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """Represents a text chunk."""
    text: str
    start_char: int
    end_char: int
    chunk_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class ChunkingService:
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
    """
    
    # Automatic segmentation rules (like Dify's AUTOMATIC_RULES)
    AUTOMATIC_RULES = {
        "max_tokens": 500,
        "chunk_overlap": 50,
        "separator": "\n\n"
    }
    
    def __init__(self, chunk_size: int = None, overlap: int = None, mode: str = "automatic", strategy: str = "recursive"):
        """
        Initialize chunking service with semchunk.
        
        Args:
            chunk_size: Tokens per chunk (default: 500)
            overlap: Overlap tokens (default: 50, used for metadata only)
            mode: Segmentation mode ('automatic', 'custom')
            strategy: Ignored - always uses semchunk
        """
        self.mode = mode
        self.strategy = "semchunk"  # Always use semchunk
        
        if mode == "automatic":
            self.chunk_size = chunk_size or self.AUTOMATIC_RULES["max_tokens"]
            self.overlap = overlap or self.AUTOMATIC_RULES["chunk_overlap"]
        else:
            self.chunk_size = chunk_size or int(os.getenv("CHUNK_SIZE", "500"))
            self.overlap = overlap or int(os.getenv("CHUNK_OVERLAP", "50"))
        
        # Validate chunk size
        max_segmentation_tokens = int(os.getenv("MAX_SEGMENTATION_TOKENS", "2000"))
        if self.chunk_size < 50 or self.chunk_size > max_segmentation_tokens:
            logger.warning(
                f"[ChunkingService] Chunk size {self.chunk_size} out of range [50, {max_segmentation_tokens}], "
                f"using default 500"
            )
            self.chunk_size = 500
        
        # Initialize tiktoken for accurate token counting
        self._encoding = tiktoken.get_encoding("cl100k_base")
        self._token_counter: Callable[[str], int] = lambda text: len(self._encoding.encode(text))
        
        # Create semchunk chunker
        # semchunk automatically handles Chinese punctuation (。！？) as sentence boundaries
        self._chunker = semchunk.chunkerify(
            self._token_counter,
            chunk_size=self.chunk_size,
        )
        
        logger.info(
            f"[ChunkingService] Initialized with mode={mode}, "
            f"chunk_size={self.chunk_size}, overlap={self.overlap}"
        )
    
    def _split(
        self,
        text: str,
        metadata: Dict[str, Any] = None,
        page_info: Optional[List[Dict[str, Any]]] = None
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
        
        chunks = []
        current_pos = 0
        
        for i, chunk_text in enumerate(chunk_texts):
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
                    if page_data['start'] <= start_pos < page_data['end']:
                        chunk_metadata['page_number'] = page_data['page']
                        break
            
            # Add token count
            chunk_metadata['token_count'] = self._token_counter(chunk_text)
            
            chunk = Chunk(
                text=chunk_text.strip(),
                start_char=start_pos,
                end_char=end_pos,
                chunk_index=i,
                metadata=chunk_metadata
            )
            chunks.append(chunk)
        
        logger.debug(
            f"[ChunkingService] Created {len(chunks)} chunks from {len(text)} chars "
            f"(avg {len(text) // max(len(chunks), 1)} chars/chunk)"
        )
        return chunks
    
    def chunk_text(
        self, 
        text: str, 
        metadata: Dict[str, Any] = None,
        separator: str = None,
        extract_structure: bool = False,
        page_info: Optional[List[Dict[str, Any]]] = None,
        language: Optional[str] = None
    ) -> List[Chunk]:
        """
        Split text into chunks using semchunk.
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to chunks
            separator: Ignored (semchunk uses its own separators)
            extract_structure: Ignored (semchunk handles structure)
            page_info: Optional list of page boundaries for PDFs
            language: Ignored (semchunk handles Chinese automatically)
            
        Returns:
            List of Chunk objects
        """
        return self._split(text, metadata, page_info)
    
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
            logger.warning(f"[ChunkingService] User {user_id} would exceed chunk limit: {chunk_count} > {max_chunks}")
            return False
        
        return True


# Global instance
_chunking_service: Optional[ChunkingService] = None


def get_chunking_service() -> ChunkingService:
    """Get global chunking service instance."""
    global _chunking_service
    if _chunking_service is None:
        _chunking_service = ChunkingService()
    return _chunking_service
