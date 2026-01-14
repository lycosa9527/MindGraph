"""
LLM Chunking Service Wrapper

Service wrapper for LLM-based semantic chunking module.
Integrates with existing ChunkingService interface.

Author: MindSpring Team
Copyright 2024-2025 北京思源智教科技有限公司
All Rights Reserved
Proprietary License
"""

import logging
from typing import List, Dict, Any, Optional, Union
from llm_chunking.chunker import LLMSemanticChunker
from llm_chunking.models import Chunk, ParentChunk, QAChunk
from services.chunking_service import Chunk as LegacyChunk

logger = logging.getLogger(__name__)


class LLMChunkingService:
    """
    Service wrapper for LLM-based semantic chunking.
    
    Provides interface compatible with existing ChunkingService
    while using LLM-based semantic chunking.
    """
    
    def __init__(
        self,
        llm_service=None,
        sample_pages: int = 30,
        batch_size: int = 10
    ):
        """
        Initialize LLM chunking service.
        
        Args:
            llm_service: LLM service instance
            sample_pages: Number of pages to sample (default: 30)
            batch_size: Batch size for LLM calls (default: 10)
        """
        self.chunker = LLMSemanticChunker(
            llm_service=llm_service,
            sample_pages=sample_pages,
            batch_size=batch_size
        )
        logger.info(
            f"[LLMChunkingService] Initialized "
            f"(sample_pages={sample_pages}, batch_size={batch_size})"
        )
    
    async def chunk_text(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        structure_type: Optional[str] = None,
        pdf_outline: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> List[LegacyChunk]:
        """
        Chunk text using LLM-based semantic chunking.
        
        Compatible with existing ChunkingService.chunk_text() interface.
        
        Args:
            text: Text to chunk
            document_id: Document identifier (for caching)
            metadata: Optional metadata to attach to chunks
            structure_type: Optional structure type override
            pdf_outline: Optional PDF outline
            **kwargs: Additional parameters
            
        Returns:
            List of Chunk objects (compatible with existing interface)
        """
        # Chunk using LLM chunker
        chunks = await self.chunker.chunk(
            text=text,
            document_id=document_id,
            structure_type=structure_type,
            pdf_outline=pdf_outline,
            **kwargs
        )
        
        # Convert to legacy Chunk format
        legacy_chunks = []
        
        if isinstance(chunks[0], ParentChunk):
            # Parent-child structure: extract child chunks
            for parent in chunks:
                for child in parent.children:
                    legacy_chunk = LegacyChunk(
                        text=child.text,
                        start_char=child.start_char,
                        end_char=child.end_char,
                        chunk_index=len(legacy_chunks),
                        metadata={
                            **(metadata or {}),
                            **(child.metadata or {}),
                            "parent_text": parent.text,
                            "parent_index": parent.chunk_index,
                            "structure_type": "parent_child",
                        }
                    )
                    legacy_chunks.append(legacy_chunk)
        elif isinstance(chunks[0], QAChunk):
            # Q&A structure: convert to chunks
            for qa in chunks:
                legacy_chunk = LegacyChunk(
                    text=qa.text,
                    start_char=qa.start_char,
                    end_char=qa.end_char,
                    chunk_index=len(legacy_chunks),
                    metadata={
                        **(metadata or {}),
                        **(qa.metadata or {}),
                        "question": qa.question,
                        "answer": qa.answer,
                        "structure_type": "qa",
                    }
                )
                legacy_chunks.append(legacy_chunk)
        else:
            # General structure: direct conversion
            for chunk in chunks:
                legacy_chunk = LegacyChunk(
                    text=chunk.text,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    chunk_index=chunk.chunk_index,
                    metadata={
                        **(metadata or {}),
                        **(chunk.metadata or {}),
                        "token_count": chunk.token_count,
                        "structure_type": "general",
                    }
                )
                legacy_chunks.append(legacy_chunk)
        
        logger.info(
            f"[LLMChunkingService] Created {len(legacy_chunks)} chunks "
            f"from {len(chunks)} LLM chunks"
        )
        
        return legacy_chunks
    
    async def chunk_with_structure(
        self,
        text: str,
        document_id: str,
        structure_type: str = "general",
        **kwargs
    ) -> Union[List[Chunk], List[ParentChunk], List[QAChunk]]:
        """
        Chunk text and return native chunk objects.
        
        Args:
            text: Text to chunk
            document_id: Document identifier
            structure_type: Structure type ("general", "parent_child", "qa")
            **kwargs: Additional parameters
            
        Returns:
            List of chunk objects (type depends on structure)
        """
        return await self.chunker.chunk(
            text=text,
            document_id=document_id,
            structure_type=structure_type,
            **kwargs
        )
    
    def estimate_chunk_count(self, text_length: int, chunk_size: int = 500) -> int:
        """
        Estimate number of chunks.
        
        Args:
            text_length: Length of text in characters
            chunk_size: Approximate chunk size in tokens
            
        Returns:
            Estimated chunk count
        """
        # Rough estimate: 4 chars per token
        chars_per_chunk = chunk_size * 4
        count = max(1, (text_length + chars_per_chunk - 1) // chars_per_chunk)
        return count


# Global instance
_llm_chunking_service: Optional[LLMChunkingService] = None


def get_llm_chunking_service() -> LLMChunkingService:
    """Get global LLM chunking service instance."""
    global _llm_chunking_service
    if _llm_chunking_service is None:
        _llm_chunking_service = LLMChunkingService()
    return _llm_chunking_service
