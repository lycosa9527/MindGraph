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
from typing import List, Dict, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

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
        language: Optional[str] = None
    ) -> List[Chunk]:
        """Chunk text into chunks."""
        pass
    
    @abstractmethod
    def estimate_chunk_count(self, text_length: int) -> int:
        """Estimate chunk count."""
        pass
    
    @abstractmethod
    def validate_chunk_count(self, chunk_count: int, user_id: int) -> bool:
        """Validate chunk count."""
        pass


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
    """
    
    # Automatic segmentation rules (like Dify's AUTOMATIC_RULES)
    AUTOMATIC_RULES = {
        "max_tokens": 500,
        "chunk_overlap": 50,
        "separator": "\n\n"
    }
    
    def __init__(self, chunk_size: Optional[int] = None, overlap: Optional[int] = None, mode: str = "automatic", strategy: str = "recursive"):
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
        metadata: Optional[Dict[str, Any]] = None,
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
        
        # Ensure chunk_texts is a list of strings
        if not isinstance(chunk_texts, list):
            chunk_texts = list(chunk_texts)
        
        chunks = []
        current_pos = 0
        
        for i, chunk_text in enumerate(chunk_texts):
            # Ensure chunk_text is a string
            if not isinstance(chunk_text, str):
                logger.warning(f"[ChunkingService] Unexpected chunk type: {type(chunk_text)}, skipping")
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
        metadata: Optional[Dict[str, Any]] = None,
        separator: Optional[str] = None,
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
_chunking_service: Optional[Union[ChunkingService, "MindChunkAdapter"]] = None


def get_chunking_service() -> Union[ChunkingService, "MindChunkAdapter"]:
    """
    Get global chunking service instance.
    
    Supports switching between semchunk and MindChunk (LLM-based) via CHUNKING_ENGINE env var.
    - CHUNKING_ENGINE=semchunk (default): Uses semchunk library
    - CHUNKING_ENGINE=mindchunk: Uses custom LLM-based chunking
    """
    global _chunking_service
    if _chunking_service is None:
        chunking_engine = os.getenv("CHUNKING_ENGINE", "semchunk").lower()
        logger.info(
            f"[ChunkingService] Initializing chunking service: CHUNKING_ENGINE={chunking_engine} "
            f"(env value: {os.getenv('CHUNKING_ENGINE', 'not set, using default: semchunk')})"
        )
        
        if chunking_engine == "mindchunk":
            logger.info(
                "[ChunkingService] ✓ Using MindChunk (LLM-based semantic chunking) - "
                "requires LLM service initialization"
            )
            # Verify LLM service is initialized, try to initialize if not
            try:
                from services.llm_service import llm_service as llm_svc
                from config.settings import config
                
                if not hasattr(llm_svc, 'client_manager'):
                    raise RuntimeError(
                        "[ChunkingService] LLM service missing client_manager attribute. "
                        "MindChunk cannot work without LLM service."
                    )
                
                if not llm_svc.client_manager.is_initialized():
                    logger.warning(
                        "[ChunkingService] LLM service not initialized. "
                        "Attempting to initialize now..."
                    )
                    
                    # Try to initialize if API key is available
                    if not config.QWEN_API_KEY:
                        raise RuntimeError(
                            "[ChunkingService] QWEN_API_KEY not configured. "
                            "MindChunk requires QWEN_API_KEY to be set in environment variables."
                        )
                    
                    try:
                        logger.info("[ChunkingService] Initializing LLM service...")
                        llm_svc.initialize()
                        if not llm_svc.client_manager.is_initialized():
                            raise RuntimeError(
                                "[ChunkingService] LLM service initialization failed - "
                                "is_initialized() returned False after initialize() call. "
                                "Check logs above for initialization errors."
                            )
                        logger.info("[ChunkingService] ✓ LLM service initialized successfully")
                    except Exception as init_error:
                        raise RuntimeError(
                            f"[ChunkingService] Failed to initialize LLM service: {init_error}. "
                            "MindChunk cannot work without LLM service. "
                            "Check logs above for detailed error information."
                        ) from init_error
            except RuntimeError:
                # Re-raise RuntimeError as-is
                raise
            except Exception as e:
                raise RuntimeError(
                    f"[ChunkingService] Failed to verify LLM service initialization: {e}. "
                    "MindChunk cannot work without LLM service."
                ) from e
            
            # Import here to avoid circular dependencies
            from services.llm_chunking_service import get_llm_chunking_service
            llm_service = get_llm_chunking_service()
            # Create adapter wrapper
            _chunking_service = MindChunkAdapter(llm_service)
        else:
            logger.info(f"[ChunkingService] Using semchunk (chunking_engine={chunking_engine})")
            _chunking_service = ChunkingService()
    
    # Type narrowing: _chunking_service is always initialized above
    assert _chunking_service is not None, "Chunking service should be initialized"
    return _chunking_service


class MindChunkAdapter(BaseChunkingService):
    """
    Adapter to make LLMChunkingService compatible with ChunkingService interface.
    
    Wraps async LLMChunkingService to provide synchronous interface.
    """
    
    def __init__(self, llm_chunking_service):
        """
        Initialize adapter.
        
        Args:
            llm_chunking_service: LLMChunkingService instance
        """
        self.llm_service = llm_chunking_service
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "500"))
        self.overlap = int(os.getenv("CHUNK_OVERLAP", "50"))
        self.mode = "automatic"
        self.strategy = "mindchunk"
        
        logger.info(
            f"[MindChunkAdapter] Initialized with LLM-based chunking "
            f"(chunk_size={self.chunk_size}, overlap={self.overlap})"
        )
    
    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        separator: Optional[str] = None,
        extract_structure: bool = False,
        page_info: Optional[List[Dict[str, Any]]] = None,
        language: Optional[str] = None
    ) -> List[Chunk]:
        """
        Chunk text using MindChunk (LLM-based chunking).
        
        Synchronous wrapper around async LLM chunking service.
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to chunks
            separator: Ignored (MindChunk uses semantic boundaries)
            extract_structure: If True, uses structure detection
            page_info: Optional page boundaries for PDFs
            language: Optional language hint
            
        Returns:
            List of Chunk objects
        """
        import asyncio
        
        # Async/sync bridge: This adapter provides synchronous interface for async LLM chunking.
        # In Flask/Quart sync context, we need to run the async coroutine in an event loop.
        # Strategy: Get existing loop if available, otherwise create new one.
        # Note: run_until_complete() works when called from sync context (Flask routes).
        try:
            # Try to get existing event loop (works in sync Flask context)
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running (async context), we can't use run_until_complete
                # This shouldn't happen in Flask sync routes, but handle gracefully
                logger.warning(
                    "[MindChunkAdapter] Event loop already running, "
                    "this may indicate async context issue"
                )
                # Create new loop for this operation
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            # No event loop exists, create new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run async chunking
        document_id = metadata.get("document_id", "unknown") if metadata else "unknown"
        
        logger.debug(
            f"[MindChunkAdapter] Starting chunking for doc_id={document_id}, "
            f"text_length={len(text)}, extract_structure={extract_structure}, "
            f"chunk_size={self.chunk_size}, overlap={self.overlap}"
        )
        
        # Determine structure type if extract_structure is True
        structure_type = None
        if extract_structure:
            structure_type = "general"  # Can be enhanced to detect structure
            logger.debug(f"[MindChunkAdapter] Structure extraction enabled, type={structure_type}")
        
        # Extract PDF outline from page_info if available
        pdf_outline = None
        if page_info:
            pdf_outline = [
                {"page": p["page"], "title": f"Page {p['page']}"}
                for p in page_info
            ]
        
        # Call async method
        logger.info(
            f"[MindChunkAdapter] Calling LLM chunking service: doc_id={document_id}, "
            f"text_length={len(text)}, structure_type={structure_type}, "
            f"chunk_size={self.chunk_size}, overlap={self.overlap}"
        )
        try:
            llm_chunks = loop.run_until_complete(
                self.llm_service.chunk_text(
                    text=text,
                    document_id=document_id,
                    metadata=metadata,
                    structure_type=structure_type,
                    pdf_outline=pdf_outline,
                    chunk_size=self.chunk_size,
                    overlap=self.overlap
                )
            )
            logger.info(
                f"[MindChunkAdapter] LLM chunking service returned: doc_id={document_id}, "
                f"chunks_count={len(llm_chunks) if llm_chunks else 0}, "
                f"chunks_type={type(llm_chunks).__name__ if llm_chunks else 'None'}"
            )
        except Exception as e:
            import traceback
            logger.error(
                f"[MindChunkAdapter] ✗ ERROR during LLM chunking for doc_id={document_id}: {e}"
            )
            logger.error(f"[MindChunkAdapter] Full traceback:")
            logger.error(traceback.format_exc())
            logger.error(f"[MindChunkAdapter] Exception type: {type(e).__name__}")
            logger.error(f"[MindChunkAdapter] Exception args: {e.args}")
            # Raise error instead of returning empty - we removed fallback
            raise RuntimeError(
                f"[MindChunkAdapter] LLM chunking failed for doc_id={document_id}: {e}. "
                "Check logs above for detailed error information."
            ) from e
        
        # Handle empty result
        if not llm_chunks:
            raise RuntimeError(
                f"[MindChunkAdapter] No chunks returned from LLM chunking for doc_id={document_id}. "
                "LLM chunking service returned empty result. This may indicate an issue with "
                "the LLM service, API configuration, or document content."
            )
        
        # Convert to Chunk format (already compatible)
        chunks = []
        for llm_chunk in llm_chunks:
            chunk = Chunk(
                text=llm_chunk.text,
                start_char=llm_chunk.start_char,
                end_char=llm_chunk.end_char,
                chunk_index=llm_chunk.chunk_index,
                metadata=llm_chunk.metadata
            )
            chunks.append(chunk)
        
        # Log detailed chunking results
        total_chars = sum(len(c.text) for c in chunks)
        avg_chunk_size = total_chars / len(chunks) if chunks else 0
        logger.debug(
            f"[MindChunkAdapter] Created {len(chunks)} chunks from {len(text)} chars "
            f"for doc_id={document_id}, avg_chunk_size={avg_chunk_size:.1f} chars"
        )
        
        # Log metadata presence for debugging vector storage compatibility
        if chunks:
            sample_metadata = chunks[0].metadata
            metadata_keys = list(sample_metadata.keys())
            logger.debug(
                f"[MindChunkAdapter] Chunk metadata keys for doc_id={document_id}: "
                f"{metadata_keys}"
            )
            # Verify critical metadata fields for vector storage
            required_fields = ['document_id', 'structure_type']
            missing_fields = [f for f in required_fields if f not in sample_metadata]
            if missing_fields:
                logger.warning(
                    f"[MindChunkAdapter] Missing metadata fields {missing_fields} "
                    f"for doc_id={document_id}, may affect vector storage"
                )
            else:
                logger.debug(
                    f"[MindChunkAdapter] All required metadata fields present "
                    f"for vector storage compatibility for doc_id={document_id}"
                )
        return chunks
    
    def estimate_chunk_count(self, text_length: int) -> int:
        """
        Estimate number of chunks for text length.
        
        Args:
            text_length: Length of text in characters
            
        Returns:
            Estimated chunk count
        """
        return self.llm_service.estimate_chunk_count(text_length, self.chunk_size)
    
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
                f"[MindChunkAdapter] User {user_id} would exceed chunk limit: "
                f"{chunk_count} > {max_chunks}"
            )
            return False
        
        return True
