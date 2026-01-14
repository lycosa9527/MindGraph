"""
Main LLM-based semantic chunker.

Orchestrates the complete chunking workflow:
1. Check cache for structure
2. Sample 30 pages → LLM structure detection → Cache
3. Pattern-based chunking (80% of chunks)
4. LLM refinement for unclear boundaries (20% of chunks)
5. Validate and return chunks
"""

import logging
from typing import List, Dict, Any, Optional, Union
from llm_chunking.models import (
    Chunk,
    ParentChunk,
    ChildChunk,
    QAChunk,
    DocumentStructure,
)
from llm_chunking.structures import (
    GeneralStructure,
    ParentChildStructure,
    QAStructure,
    get_structure,
)
from llm_chunking.agents.structure_agent import StructureAgent
from llm_chunking.agents.boundary_agent import BoundaryAgent
from llm_chunking.patterns.pattern_matcher import PatternMatcher
from llm_chunking.patterns.toc_detector import TOCDetector
from llm_chunking.patterns.embedding_boundary_detector import EmbeddingBoundaryDetector
from llm_chunking.optimizations.sampler import DocumentSampler
from llm_chunking.optimizations.batch_processor import BatchProcessor
from llm_chunking.optimizations.cache_manager import CacheManager
from llm_chunking.utils.token_counter import TokenCounter
from llm_chunking.utils.validators import ChunkValidator

logger = logging.getLogger(__name__)


class LLMSemanticChunker:
    """
    LLM-based semantic chunker with performance optimizations.
    
    Features:
    - 30-page sampling (94% cost reduction)
    - Batch processing (10x speedup)
    - Structure caching (instant reuse)
    - Hybrid approach (pattern + LLM + embeddings)
    - Support for General, Parent-Child, and Q&A structures
    - Optional embedding-only mode (fast, no LLM calls)
    """
    
    def __init__(
        self,
        llm_service=None,
        cache_manager: Optional[CacheManager] = None,
        sample_pages: int = 30,
        batch_size: int = 10,
        use_embeddings_only: bool = False
    ):
        """
        Initialize chunker.
        
        Args:
            llm_service: LLM service instance
            cache_manager: Optional cache manager
            sample_pages: Number of pages to sample (default: 30)
            batch_size: Batch size for LLM calls (default: 10)
            use_embeddings_only: Use embedding-only mode (no LLM calls, default: False)
        """
        self.llm_service = llm_service
        self.use_embeddings_only = use_embeddings_only
        self.sampler = DocumentSampler(sample_pages=sample_pages)
        self.batch_processor = BatchProcessor(batch_size=batch_size)
        self.cache_manager = cache_manager or CacheManager()
        self.token_counter = TokenCounter()
        self.validator = ChunkValidator()
        
        # Agents (only initialize if not using embeddings_only mode)
        if not self.use_embeddings_only:
            self.structure_agent = StructureAgent(llm_service=llm_service)
            self.boundary_agent = BoundaryAgent(
                llm_service=llm_service,
                use_embedding_filter=True  # Enable embedding pre-filtering
            )
        else:
            self.structure_agent = None
            self.boundary_agent = None
        
        # Pattern matchers (pass token_counter for length caching)
        self.pattern_matcher = PatternMatcher(token_counter=self.token_counter.get_counter())
        self.toc_detector = TOCDetector()
        
        # Embedding-based boundary detector (for embeddings_only mode or hybrid)
        try:
            self.embedding_detector = EmbeddingBoundaryDetector()
            if not self.embedding_detector.embedding_service.is_available():
                logger.warning(
                    "[LLMSemanticChunker] Embedding service not available, "
                    "embedding-based chunking will be disabled"
                )
                self.embedding_detector = None
        except Exception as e:
            logger.warning(f"[LLMSemanticChunker] Failed to initialize embedding detector: {e}")
            self.embedding_detector = None
        
        if self.use_embeddings_only and not self.embedding_detector:
            raise ValueError(
                "use_embeddings_only=True requires embedding service to be available"
            )
    
    async def chunk(
        self,
        text: str,
        document_id: str,
        structure_type: Optional[str] = None,
        pdf_outline: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Union[List[Chunk], List[ParentChunk], List[QAChunk]]:
        """
        Chunk text using LLM-based semantic chunking.
        
        Args:
            text: Text to chunk
            document_id: Document identifier (for caching)
            structure_type: Optional structure type override
            pdf_outline: Optional PDF outline
            **kwargs: Additional parameters
            
        Returns:
            List of chunks (type depends on structure)
        """
        # Step 1: Get or detect structure
        structure = await self._get_structure(
            text,
            document_id,
            structure_type,
            pdf_outline
        )
        
        # Step 2: Chunk according to structure
        if structure.structure_type == "general":
            return await self._chunk_general(text, structure, **kwargs)
        elif structure.structure_type == "parent_child":
            return await self._chunk_parent_child(text, structure, **kwargs)
        elif structure.structure_type == "qa":
            return await self._chunk_qa(text, structure, **kwargs)
        else:
            raise ValueError(f"Unknown structure type: {structure.structure_type}")
    
    async def _get_structure(
        self,
        text: str,
        document_id: str,
        structure_type: Optional[str],
        pdf_outline: Optional[List[Dict[str, Any]]]
    ) -> DocumentStructure:
        """Get or detect document structure."""
        # If embeddings_only mode, use simple general structure
        if self.use_embeddings_only:
            from llm_chunking.models import DocumentStructure
            return DocumentStructure(
                document_id=document_id,
                structure_type=structure_type or "general",
                toc=[],
                chunking_rules={},
                document_type=None
            )
        
        # Check cache first
        cached = self.cache_manager.get_structure(document_id)
        if cached:
            logger.info(f"Using cached structure for {document_id}")
            return DocumentStructure.from_dict(cached)
        
        # Detect structure from sample
        sample = self.sampler.sample(text)
        structure = await self.structure_agent.analyze_structure(
            sample,
            document_id,
            pdf_outline
        )
        
        # Cache structure
        self.cache_manager.set_structure(document_id, structure.to_dict())
        
        return structure
    
    async def _chunk_general(
        self,
        text: str,
        structure: DocumentStructure,
        chunk_size: int = 500,
        overlap: int = 50,
        **kwargs
    ) -> List[Chunk]:
        """Chunk using general (flat) structure."""
        # If embeddings_only mode, use embedding-based chunking
        if self.use_embeddings_only and self.embedding_detector:
            return await self._chunk_general_embeddings_only(
                text,
                structure,
                chunk_size,
                overlap,
                **kwargs
            )
        
        # Step 1: Pattern-based chunking (fast, 80% of chunks)
        # Pass token_counter for length caching
        boundaries = self.pattern_matcher.find_boundaries(
            text,
            max_tokens=chunk_size,
            prefer_paragraphs=True,
            token_counter=self.token_counter.get_counter()
        )
        
        # Step 2: Identify unclear boundaries
        unclear_boundaries = []
        clear_chunks = []
        
        # Phase 1: Pre-compute token counts for all boundaries (length caching)
        boundary_texts = [text[start:end] for start, end in boundaries]
        boundary_lengths = self.token_counter.count_batch(boundary_texts)
        
        for (start_pos, end_pos), token_count in zip(boundaries, boundary_lengths):
            if self.pattern_matcher.is_boundary_clear(text, start_pos, end_pos):
                clear_chunks.append((start_pos, end_pos, token_count))
            else:
                unclear_boundaries.append((start_pos, end_pos, token_count))
        
        # Step 3: LLM refinement for unclear boundaries (batched)
        if unclear_boundaries and self.llm_service:
            unclear_segments = [
                text[start:end] for start, end, _ in unclear_boundaries
            ]
            
            refined_boundaries = await self.boundary_agent.detect_boundaries_batch(
                unclear_segments
            )
            
            # Merge refined boundaries (recompute token counts for refined boundaries)
            for boundaries_list in refined_boundaries:
                for start, end in boundaries_list:
                    chunk_text = text[start:end]
                    token_count = self.token_counter.count(chunk_text)
                    clear_chunks.append((start, end, token_count))
        else:
            clear_chunks.extend(unclear_boundaries)
        
        # Step 4: Create chunks with overlap handling (Phase 3: Dify-style overlap)
        chunks = []
        # Sort by start position
        sorted_chunks = sorted(clear_chunks, key=lambda x: x[0])
        
        # Phase 3: Smart overlap handling (from Dify)
        if overlap > 0:
            # Group chunks and apply overlap
            current_part = ""
            current_length = 0
            current_start = None
            overlap_part = ""
            overlap_part_length = 0
            
            for start_pos, end_pos, token_count in sorted_chunks:
                chunk_text = text[start_pos:end_pos]
                
                if current_start is None:
                    current_start = start_pos
                
                # Check if adding this chunk would exceed size
                if current_length + token_count <= chunk_size - overlap:
                    # Can add without overlap concern
                    current_part += chunk_text
                    current_length += token_count
                elif current_length + token_count <= chunk_size:
                    # Can add but need to start building overlap
                    current_part += chunk_text
                    current_length += token_count
                    overlap_part += chunk_text
                    overlap_part_length += token_count
                else:
                    # Need to create chunk and carry overlap forward
                    if current_part:
                        chunk = Chunk(
                            text=current_part,
                            start_char=current_start,
                            end_char=end_pos - len(chunk_text),
                            chunk_index=len(chunks),
                            token_count=current_length,
                            metadata={
                                "structure_type": "general",
                                "document_id": structure.document_id,
                            }
                        )
                        if self.validator.validate_chunk(chunk, current_length):
                            chunks.append(chunk)
                    
                    # Carry overlap forward
                    current_part = overlap_part + chunk_text
                    current_length = token_count + overlap_part_length
                    current_start = start_pos - len(overlap_part) if overlap_part else start_pos
                    overlap_part = ""
                    overlap_part_length = 0
            
            # Add final chunk
            if current_part:
                final_end = sorted_chunks[-1][1] if sorted_chunks else current_start + len(current_part)
                chunk = Chunk(
                    text=current_part,
                    start_char=current_start,
                    end_char=final_end,
                    chunk_index=len(chunks),
                    token_count=current_length,
                    metadata={
                        "structure_type": "general",
                        "document_id": structure.document_id,
                    }
                )
                if self.validator.validate_chunk(chunk, current_length):
                    chunks.append(chunk)
        else:
            # No overlap: simple chunking
            for i, (start_pos, end_pos, token_count) in enumerate(sorted_chunks):
                chunk_text = text[start_pos:end_pos]
                
                chunk = Chunk(
                    text=chunk_text,
                    start_char=start_pos,
                    end_char=end_pos,
                    chunk_index=i,
                    token_count=token_count,  # Use cached token count
                    metadata={
                        "structure_type": "general",
                        "document_id": structure.document_id,
                    }
                )
                
                if self.validator.validate_chunk(chunk, token_count):
                    chunks.append(chunk)
        
        logger.info(f"Created {len(chunks)} general chunks")
        return chunks
    
    async def _chunk_general_embeddings_only(
        self,
        text: str,
        structure: DocumentStructure,
        chunk_size: int = 500,
        overlap: int = 50,
        **kwargs
    ) -> List[Chunk]:
        """
        Chunk using embedding-based semantic similarity only (no LLM calls).
        
        Uses LlamaIndex-style semantic chunking:
        1. Split into sentences
        2. Generate embeddings with buffer context
        3. Calculate cosine distances
        4. Use percentile threshold to find breakpoints
        """
        if not self.embedding_detector:
            # Fallback to pattern matching if embeddings unavailable
            logger.warning(
                "[LLMSemanticChunker] Embedding detector not available, "
                "falling back to pattern matching"
            )
            return await self._chunk_general(
                text,
                structure,
                chunk_size,
                overlap,
                **kwargs
            )
        
        # Use embedding-based boundary detection
        boundaries = self.embedding_detector.find_boundaries(text, max_tokens=chunk_size)
        
        if not boundaries:
            # No boundaries found, create single chunk
            token_count = self.token_counter.count(text)
            chunk = Chunk(
                text=text,
                start_char=0,
                end_char=len(text),
                chunk_index=0,
                token_count=token_count,
                metadata={
                    "structure_type": "general",
                    "document_id": structure.document_id,
                    "chunking_method": "embedding_only"
                }
            )
            if self.validator.validate_chunk(chunk, token_count):
                return [chunk]
            return []
        
        # Convert boundaries to chunks with overlap handling
        chunks = []
        sorted_boundaries = sorted(boundaries, key=lambda x: x[0])
        
        # Pre-compute token counts for all boundaries
        boundary_texts = [text[start:end] for start, end in sorted_boundaries]
        boundary_lengths = self.token_counter.count_batch(boundary_texts)
        
        if overlap > 0:
            # Smart overlap handling
            current_part = ""
            current_length = 0
            current_start = None
            overlap_part = ""
            overlap_part_length = 0
            
            for (start_pos, end_pos), token_count in zip(sorted_boundaries, boundary_lengths):
                chunk_text = text[start_pos:end_pos]
                
                if current_start is None:
                    current_start = start_pos
                
                # Check if adding this chunk would exceed size
                if current_length + token_count <= chunk_size - overlap:
                    # Can add without overlap concern
                    current_part += chunk_text
                    current_length += token_count
                elif current_length + token_count <= chunk_size:
                    # Can add but need to start building overlap
                    current_part += chunk_text
                    current_length += token_count
                    overlap_part += chunk_text
                    overlap_part_length += token_count
                else:
                    # Need to create chunk and carry overlap forward
                    if current_part:
                        chunk = Chunk(
                            text=current_part,
                            start_char=current_start,
                            end_char=end_pos - len(chunk_text),
                            chunk_index=len(chunks),
                            token_count=current_length,
                            metadata={
                                "structure_type": "general",
                                "document_id": structure.document_id,
                                "chunking_method": "embedding_only"
                            }
                        )
                        if self.validator.validate_chunk(chunk, current_length):
                            chunks.append(chunk)
                    
                    # Carry overlap forward
                    current_part = overlap_part + chunk_text
                    current_length = token_count + overlap_part_length
                    current_start = start_pos - len(overlap_part) if overlap_part else start_pos
                    overlap_part = ""
                    overlap_part_length = 0
            
            # Add final chunk
            if current_part:
                final_end = sorted_boundaries[-1][1] if sorted_boundaries else current_start + len(current_part)
                chunk = Chunk(
                    text=current_part,
                    start_char=current_start,
                    end_char=final_end,
                    chunk_index=len(chunks),
                    token_count=current_length,
                    metadata={
                        "structure_type": "general",
                        "document_id": structure.document_id,
                        "chunking_method": "embedding_only"
                    }
                )
                if self.validator.validate_chunk(chunk, current_length):
                    chunks.append(chunk)
        else:
            # No overlap: simple chunking
            for i, ((start_pos, end_pos), token_count) in enumerate(zip(sorted_boundaries, boundary_lengths)):
                chunk_text = text[start_pos:end_pos]
                
                chunk = Chunk(
                    text=chunk_text,
                    start_char=start_pos,
                    end_char=end_pos,
                    chunk_index=i,
                    token_count=token_count,
                    metadata={
                        "structure_type": "general",
                        "document_id": structure.document_id,
                        "chunking_method": "embedding_only"
                    }
                )
                
                if self.validator.validate_chunk(chunk, token_count):
                    chunks.append(chunk)
        
        logger.info(f"Created {len(chunks)} general chunks using embedding-only mode")
        return chunks
    
    async def _chunk_parent_child(
        self,
        text: str,
        structure: DocumentStructure,
        parent_max_tokens: int = 2000,
        child_max_tokens: int = 500,
        **kwargs
    ) -> List[ParentChunk]:
        """Chunk using parent-child structure."""
        parent_chunks = []
        
        # Use TOC to guide parent boundaries
        if structure.toc:
            sections = self.toc_detector.apply_toc_boundaries(text, structure.toc)
            
            for i, section in enumerate(sections):
                section_text = section["text"]
                
                # Create parent chunk
                parent = ParentChunk(
                    text=section_text,
                    start_char=section["start_pos"],
                    end_char=section["end_pos"],
                    chunk_index=i,
                    token_count=self.token_counter.count(section_text),
                    metadata={
                        "structure_type": "parent_child",
                        "title": section["title"],
                        "level": section["level"],
                    }
                )
                
                # Create child chunks (sentences or paragraphs)
                child_boundaries = self.pattern_matcher.find_boundaries(
                    section_text,
                    max_tokens=child_max_tokens,
                    prefer_paragraphs=False,  # Use sentences for children
                    token_counter=self.token_counter.get_counter()
                )
                
                # Phase 1: Pre-compute token counts for all child boundaries (length caching)
                child_texts = [section_text[start:end] for start, end in child_boundaries]
                child_lengths = self.token_counter.count_batch(child_texts)
                
                for j, ((child_start, child_end), token_count) in enumerate(zip(child_boundaries, child_lengths)):
                    child_text = section_text[child_start:child_end]
                    
                    child = ChildChunk(
                        text=child_text,
                        start_char=section["start_pos"] + child_start,
                        end_char=section["start_pos"] + child_end,
                        chunk_index=j,
                        token_count=token_count,
                        parent_id=f"parent_{i}",
                        parent_text=section_text,
                        parent_index=i,
                    )
                    
                    if self.validator.validate_chunk(child, token_count):
                        parent.add_child(child)
                
                if parent.children:
                    parent_chunks.append(parent)
        else:
            # No TOC: Use paragraph-based parents
            paragraphs = self.pattern_matcher.split_by_paragraphs(text)
            current_pos = 0
            
            for i, paragraph in enumerate(paragraphs):
                start_pos = text.find(paragraph, current_pos)
                if start_pos == -1:
                    start_pos = current_pos
                end_pos = start_pos + len(paragraph)
                current_pos = end_pos
                
                parent = ParentChunk(
                    text=paragraph,
                    start_char=start_pos,
                    end_char=end_pos,
                    chunk_index=i,
                    token_count=self.token_counter.count(paragraph),
                )
                
                # Create child chunks from sentences
                sentences = self.pattern_matcher.split_by_sentences(paragraph)
                
                # Phase 1: Pre-compute token counts for all sentences (length caching)
                sentence_lengths = self.token_counter.count_batch(sentences)
                
                for j, (sentence, token_count) in enumerate(zip(sentences, sentence_lengths)):
                    if token_count <= child_max_tokens:
                        child = ChildChunk(
                            text=sentence,
                            start_char=start_pos + paragraph.find(sentence),
                            end_char=start_pos + paragraph.find(sentence) + len(sentence),
                            chunk_index=j,
                            token_count=token_count,
                            parent_id=f"parent_{i}",
                            parent_text=paragraph,
                            parent_index=i,
                        )
                        parent.add_child(child)
                
                if parent.children:
                    parent_chunks.append(parent)
        
        logger.info(f"Created {len(parent_chunks)} parent chunks with children")
        return parent_chunks
    
    async def _chunk_qa(
        self,
        text: str,
        structure: DocumentStructure,
        **kwargs
    ) -> List[QAChunk]:
        """Chunk using Q&A structure."""
        from llm_chunking.patterns.question_detector import QuestionDetector
        
        question_detector = QuestionDetector()
        questions = question_detector.detect_questions(text)
        
        qa_chunks = []
        for i, question_data in enumerate(questions):
            question_text = question_data["text"]
            
            # For now, create Q&A chunk with question only
            # In full implementation, LLM would generate answers
            qa_chunk = QAChunk(
                text=question_text,
                start_char=question_data["start_pos"],
                end_char=question_data["end_pos"],
                chunk_index=i,
                question=question_text,
                answer="",  # Would be generated by LLM
                qa_index=i,
                metadata={
                    "structure_type": "qa",
                    "question_type": question_data.get("type", "short_answer"),
                }
            )
            
            qa_chunks.append(qa_chunk)
        
        logger.info(f"Created {len(qa_chunks)} Q&A chunks")
        return qa_chunks
