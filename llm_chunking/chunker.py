"""
Main LLM-based semantic chunker.

Orchestrates the complete chunking workflow:
1. Check cache for structure
2. Sample 30 pages → LLM structure detection → Cache
3. Pattern-based chunking (80% of chunks)
4. LLM refinement for unclear boundaries (20% of chunks)
5. Validate and return chunks
"""
from typing import List, Dict, Any, Optional, Union
import logging
import traceback

from llm_chunking.agents.boundary_agent import BoundaryAgent
from llm_chunking.agents.structure_agent import StructureAgent
from llm_chunking.models import (
    Chunk,
    ParentChunk,
    ChildChunk,
    QAChunk,
    DocumentStructure,
)
from llm_chunking.optimizations.batch_processor import BatchProcessor
from llm_chunking.optimizations.cache_manager import CacheManager
from llm_chunking.optimizations.sampler import DocumentSampler
from llm_chunking.patterns.embedding_boundary_detector import EmbeddingBoundaryDetector
from llm_chunking.patterns.pattern_matcher import PatternMatcher
from llm_chunking.patterns.question_detector import QuestionDetector
from llm_chunking.patterns.toc_detector import TOCDetector
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
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("[LLMSemanticChunker] Failed to initialize embedding detector: %s", e)
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
        # Validate input
        if not text or not text.strip():
            raise ValueError(
                f"[LLMSemanticChunker] Empty text provided for doc_id={document_id}. "
                "Cannot chunk empty text."
            )

        logger.info(
            "[LLMSemanticChunker] ===== Starting chunking for doc_id=%s =====",
            document_id
        )
        logger.info(
            "[LLMSemanticChunker] Input: text_length=%s, structure_type=%s, use_embeddings_only=%s, has_pdf_outline=%s",
            len(text),
            structure_type,
            self.use_embeddings_only,
            pdf_outline is not None
        )

        try:
            # Step 1: Get or detect structure
            logger.info("[LLMSemanticChunker] Step 1: Getting structure for doc_id=%s...", document_id)
            structure = await self._get_structure(
                text,
                document_id,
                structure_type,
                pdf_outline
            )
            logger.info(
                "[LLMSemanticChunker] ✓ Structure detected: type=%s, doc_type=%s, toc_entries=%s",
                structure.structure_type,
                structure.document_type,
                len(structure.toc)
            )

            # Step 2: Chunk according to structure
            logger.info(
                "[LLMSemanticChunker] Step 2: Chunking with structure_type=%s for doc_id=%s...",
                structure.structure_type,
                document_id
            )
            if structure.structure_type == "general":
                chunks = await self._chunk_general(text, structure, **kwargs)
            elif structure.structure_type == "parent_child":
                chunks = await self._chunk_parent_child(text, structure, **kwargs)
            elif structure.structure_type == "qa":
                chunks = await self._chunk_qa(text, structure, **kwargs)
            else:
                logger.error(
                    "[LLMSemanticChunker] ✗ Unknown structure type: %s for doc_id=%s",
                    structure.structure_type,
                    document_id
                )
                raise ValueError(f"Unknown structure type: {structure.structure_type}")

            logger.info(
                "[LLMSemanticChunker] Step 2 complete: doc_id=%s, chunks_count=%s",
                document_id,
                len(chunks) if chunks else 0
            )

            # Validate chunks
            if not chunks:
                raise RuntimeError(
                    f"[LLMSemanticChunker] ✗ No chunks created for doc_id={document_id}, "
                    f"structure_type={structure.structure_type}, text_length={len(text)}. "
                    "Chunking process completed but returned empty result."
                )

            logger.info(
                "[LLMSemanticChunker] ===== Chunking complete: doc_id=%s, created %s chunks =====",
                document_id,
                len(chunks)
            )

            return chunks

        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "[LLMSemanticChunker] ✗ Error during chunking for doc_id=%s: %s",
                document_id,
                e
            )
            logger.error("[LLMSemanticChunker] Full traceback:")
            logger.error(traceback.format_exc())
            logger.error("[LLMSemanticChunker] Exception type: %s", type(e).__name__)
            logger.error("[LLMSemanticChunker] Exception args: %s", e.args)
            # Re-raise to let caller handle (they may want to fallback)
            raise

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
            logger.info("[LLMSemanticChunker] Using cached structure for doc_id=%s", document_id)
            return DocumentStructure.from_dict(cached)

        # Detect structure from sample
        logger.info(
            "[LLMSemanticChunker] No cached structure, detecting from sample for doc_id=%s, text_length=%s",
            document_id,
            len(text)
        )
        sample = self.sampler.sample(text)
        logger.info(
            "[LLMSemanticChunker] Sampled %s chars from %s total for doc_id=%s",
            len(sample),
            len(text),
            document_id
        )

        if not self.structure_agent:
            raise RuntimeError(
                f"[LLMSemanticChunker] Structure agent not initialized for doc_id={document_id}. "
                "Cannot detect structure without LLM service."
            )

        logger.info("[LLMSemanticChunker] Calling structure_agent.analyze_structure() for doc_id=%s...", document_id)
        structure = await self.structure_agent.analyze_structure(
            sample,
            document_id,
            pdf_outline
        )
        logger.info(
            "[LLMSemanticChunker] ✓ Structure detected: type=%s, doc_type=%s for doc_id=%s",
            structure.structure_type,
            structure.document_type,
            document_id
        )

        # Cache structure
        self.cache_manager.set_structure(document_id, structure.to_dict())
        logger.info(
            "[LLMSemanticChunker] ✓ Structure cached for doc_id=%s, type=%s",
            document_id,
            structure.structure_type
        )

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
        logger.info(
            "[LLMSemanticChunker] Pattern-based chunking: doc_id=%s, chunk_size=%s, overlap=%s, text_length=%s",
            structure.document_id,
            chunk_size,
            overlap,
            len(text)
        )
        # Pass token_counter for length caching
        boundaries = self.pattern_matcher.find_boundaries(
            text,
            max_tokens=chunk_size,
            prefer_paragraphs=True,
            token_counter=self.token_counter.get_counter()
        )
        logger.info(
            "[LLMSemanticChunker] ✓ Found %s pattern-based boundaries for doc_id=%s",
            len(boundaries),
            structure.document_id
        )

        if not boundaries:
            raise RuntimeError(
                f"[LLMSemanticChunker] ✗ Pattern matcher found 0 boundaries for doc_id={structure.document_id}, "
                f"text_length={len(text)}. This may indicate an issue with text content or pattern matching."
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

        logger.info(
            "[LLMSemanticChunker] Boundary analysis: %s clear, %s unclear for doc_id=%s",
            len(clear_chunks),
            len(unclear_boundaries),
            structure.document_id
        )

        # Step 3: LLM refinement for unclear boundaries (batched)
        if unclear_boundaries and self.boundary_agent and self.boundary_agent.llm_service:
            logger.info(
                "[LLMSemanticChunker] Sending %s unclear boundaries to LLM for refinement for doc_id=%s...",
                len(unclear_boundaries),
                structure.document_id
            )
            unclear_segments = [
                text[start:end] for start, end, _ in unclear_boundaries
            ]

            refined_boundaries = await self.boundary_agent.detect_boundaries_batch(
                unclear_segments
            )
            logger.info(
                "[LLMSemanticChunker] ✓ LLM refined %s boundary sets for doc_id=%s",
                len(refined_boundaries),
                structure.document_id
            )

            # Merge refined boundaries (recompute token counts for refined boundaries)
            refined_count = 0
            for boundaries_list in refined_boundaries:
                for start, end in boundaries_list:
                    chunk_text = text[start:end]
                    token_count = self.token_counter.count(chunk_text)
                    clear_chunks.append((start, end, token_count))
                    refined_count += 1
            logger.info(
                "[LLMSemanticChunker] ✓ Added %s LLM-refined chunks for doc_id=%s",
                refined_count,
                structure.document_id
            )
        else:
            if unclear_boundaries:
                logger.warning(
                    "[LLMSemanticChunker] ⚠ %s unclear boundaries but no LLM service "
                    "for doc_id=%s, using pattern boundaries only",
                    len(unclear_boundaries),
                    structure.document_id
                )
            else:
                logger.info(
                    "[LLMSemanticChunker] All boundaries clear, using pattern boundaries only for doc_id=%s",
                    structure.document_id
                )
            clear_chunks.extend(unclear_boundaries)

        # Step 4: Create chunks with overlap handling (Phase 3: Dify-style overlap)
        logger.info(
            "[LLMSemanticChunker] Step 4: Creating chunks with overlap=%s for doc_id=%s, total_boundaries=%s...",
            overlap,
            structure.document_id,
            len(clear_chunks)
        )
        chunks = []
        # Sort by start position
        sorted_chunks = sorted(clear_chunks, key=lambda x: x[0])
        logger.info(
            "[LLMSemanticChunker] Sorted %s boundaries for doc_id=%s",
            len(sorted_chunks),
            structure.document_id
        )

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
                if current_start is None:
                    current_start = 0
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

        avg_tokens = sum(c.token_count for c in chunks) / len(chunks) if chunks else 0.0
        logger.info(
            "[LLMSemanticChunker] ✓ Created %s general chunks for doc_id=%s, "
            "avg_tokens=%.1f, total_boundaries=%s, validated=%s",
            len(chunks),
            structure.document_id,
            avg_tokens,
            len(sorted_chunks),
            len(chunks)
        )
        if chunks:
            logger.info(
                "[LLMSemanticChunker] Chunk metadata: structure_type=%s, document_id=%s",
                chunks[0].metadata.get('structure_type'),
                chunks[0].metadata.get('document_id')
            )
        else:
            raise RuntimeError(
                f"[LLMSemanticChunker] ✗ No chunks created after processing {len(sorted_chunks)} boundaries "
                f"for doc_id={structure.document_id}. All chunks may have failed validation. "
                f"Check validator settings."
            )
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
                if current_start is None:
                    current_start = 0
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

        logger.info("Created %s general chunks using embedding-only mode", len(chunks))
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
        del parent_max_tokens, kwargs  # Unused parameters
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

        logger.info("Created %s parent chunks with children", len(parent_chunks))
        return parent_chunks

    async def _chunk_qa(
        self,
        text: str,
        structure: DocumentStructure,
        **kwargs
    ) -> List[QAChunk]:
        """Chunk using Q&A structure."""
        del structure, kwargs  # Unused parameters
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

        logger.info("Created %s Q&A chunks", len(qa_chunks))
        return qa_chunks
