"""
Chunk Comparator for RAG Chunk Testing
=======================================

Compares chunking results between different methods (semchunk vs mindchunk).

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import List, Dict, Any, Optional
import logging
import time

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from clients.dashscope_embedding import get_embedding_client
    HAS_EMBEDDING = True
except ImportError:
    HAS_EMBEDDING = False

try:
    import spacy
    HAS_SPACY = True
except ImportError:
    HAS_SPACY = False

try:
    from chonkie import TokenChunker
    HAS_CHONKIE = True
except ImportError:
    HAS_CHONKIE = False

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False

try:
    from llm_chunking.chunker import LLMSemanticChunker
    HAS_LLM_CHUNKING = True
except ImportError:
    HAS_LLM_CHUNKING = False
    LLMSemanticChunker = None  # type: ignore

import tiktoken

from services.knowledge.chunking_service import (
    Chunk
)
from services.knowledge.rag_chunk_test.qa_generator import QAGenerator


logger = logging.getLogger(__name__)


class ChunkComparator:
    """Compare chunking methods and their results."""

    def __init__(self):
        """Initialize chunk comparator."""
        self.semchunk_service = None
        self.mindchunk_service = None
        self._spacy_model = None  # Lazy-loaded spaCy model

    def chunk_with_method(
        self,
        text: str,
        method: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> tuple[List[Chunk], float]:
        """
        Chunk text using specified method.

        Args:
            text: Text to chunk
            method: 'spacy', 'semchunk', 'chonkie', 'langchain', 'mindchunk', or 'qa'
            metadata: Optional metadata

        Returns:
            Tuple of (chunks, chunking_time_ms)
        """
        start_time = time.time()

        # Default chunk size and overlap (matching semchunk defaults)
        chunk_size = 500  # tokens
        chunk_overlap = 50  # tokens

        # Handle QA mode separately
        if method == "qa":
            qa_generator = QAGenerator()
            qa_chunks = qa_generator.generate_qa_chunks(text, metadata=metadata or {})
            chunking_time = (time.time() - start_time) * 1000
            logger.debug(
                "[ChunkComparator] Chunked with %s: %s chunks in %.2fms",
                method,
                len(qa_chunks),
                chunking_time
            )
            return qa_chunks, chunking_time

        # Handle spaCy chunking
        if method == "spacy":
            if not HAS_SPACY:
                raise ValueError("spaCy chunking requires spacy library. Install with: pip install spacy")

            # Lazy load spaCy model (cache it)
            if self._spacy_model is None:
                try:
                    self._spacy_model = spacy.load("en_core_web_sm")
                except OSError:
                    logger.warning(
                        "[ChunkComparator] spaCy model 'en_core_web_sm' not found, "
                        "using blank English model. Install with: python -m spacy download en_core_web_sm"
                    )
                    self._spacy_model = spacy.blank("en")

            # Initialize tokenizer for token counting
            encoding = tiktoken.get_encoding("cl100k_base")

            def token_counter(text: str) -> int:
                """Count tokens in text."""
                return len(encoding.encode(text))

            # Process text with spaCy
            doc = self._spacy_model(text)
            sentences = [sent.text for sent in doc.sents]

            # Group sentences into chunks respecting token limits
            chunks = []
            current_chunk_sentences = []
            current_tokens = 0
            chunk_index = 0
            current_pos = 0

            for sentence in sentences:
                sentence_tokens = token_counter(sentence)

                # If adding this sentence exceeds chunk size, finalize current chunk
                if current_tokens + sentence_tokens > chunk_size and current_chunk_sentences:
                    chunk_text = " ".join(current_chunk_sentences)
                    chunk_start = text.find(chunk_text, current_pos)
                    chunk_end = chunk_start + len(chunk_text)

                    chunks.append(Chunk(
                        text=chunk_text.strip(),
                        start_char=chunk_start,
                        end_char=chunk_end,
                        chunk_index=chunk_index,
                        metadata=dict(metadata or {})
                    ))
                    chunk_index += 1
                    current_pos = chunk_end

                    # Start new chunk with overlap (last sentence from previous chunk)
                    if chunk_overlap > 0 and current_chunk_sentences:
                        overlap_sentences = current_chunk_sentences[-1:]
                        current_chunk_sentences = overlap_sentences
                        current_tokens = token_counter(" ".join(overlap_sentences))
                    else:
                        current_chunk_sentences = []
                        current_tokens = 0

                current_chunk_sentences.append(sentence)
                current_tokens += sentence_tokens

            # Add final chunk
            if current_chunk_sentences:
                chunk_text = " ".join(current_chunk_sentences)
                chunk_start = text.find(chunk_text, current_pos)
                chunk_end = chunk_start + len(chunk_text)

                chunks.append(Chunk(
                    text=chunk_text.strip(),
                    start_char=chunk_start,
                    end_char=chunk_end,
                    chunk_index=chunk_index,
                    metadata=dict(metadata or {})
                ))

            chunking_time = (time.time() - start_time) * 1000
            logger.debug(
                "[ChunkComparator] Chunked with %s: %s chunks in %.2fms",
                method,
                len(chunks),
                chunking_time
            )
            return chunks, chunking_time

        # Handle Chonkie chunking
        if method == "chonkie":
            if not HAS_CHONKIE:
                raise ValueError("Chonkie chunking requires chonkie library. Install with: pip install chonkie")

            # Initialize tokenizer
            encoding = tiktoken.get_encoding("cl100k_base")

            def chonkie_token_counter(text: str) -> int:
                """Count tokens in text for Chonkie."""
                return len(encoding.encode(text))

            # Create Chonkie TokenChunker
            chunker = TokenChunker(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                token_counter=chonkie_token_counter
            )

            # Chunk the text
            chunk_texts = chunker.chunk(text)

            # Convert to Chunk objects
            chunks = []
            current_pos = 0

            for i, chunk_text in enumerate(chunk_texts):
                chunk_start = text.find(chunk_text, current_pos)
                if chunk_start == -1:
                    chunk_start = current_pos
                chunk_end = chunk_start + len(chunk_text)
                current_pos = chunk_end

                chunks.append(Chunk(
                    text=chunk_text.strip(),
                    start_char=chunk_start,
                    end_char=chunk_end,
                    chunk_index=i,
                    metadata=dict(metadata or {})
                ))

            chunking_time = (time.time() - start_time) * 1000
            logger.debug(
                "[ChunkComparator] Chunked with %s: %s chunks in %.2fms",
                method,
                len(chunks),
                chunking_time
            )
            return chunks, chunking_time

        # Handle LangChain RecursiveCharacterTextSplitter
        if method == "langchain":
            if not HAS_LANGCHAIN:
                raise ValueError(
                    "LangChain chunking requires langchain-text-splitters library. "
                    "Install with: pip install langchain-text-splitters"
                )

            # Use RecursiveCharacterTextSplitter with token-aware mode
            splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                encoding_name="cl100k_base",
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )

            # Split text into LangChain Document objects
            langchain_docs = splitter.create_documents([text])

            # Convert to Chunk objects
            chunks = []
            current_pos = 0

            for i, doc in enumerate(langchain_docs):
                chunk_text = doc.page_content
                chunk_start = text.find(chunk_text, current_pos)
                if chunk_start == -1:
                    chunk_start = current_pos
                chunk_end = chunk_start + len(chunk_text)
                current_pos = chunk_end

                chunks.append(Chunk(
                    text=chunk_text.strip(),
                    start_char=chunk_start,
                    end_char=chunk_end,
                    chunk_index=i,
                    metadata={
                        **(metadata or {}),
                        **(doc.metadata or {})
                    }
                ))

            chunking_time = (time.time() - start_time) * 1000
            logger.debug(
                "[ChunkComparator] Chunked with %s: %s chunks in %.2fms",
                method,
                len(chunks),
                chunking_time
            )
            return chunks, chunking_time

        # Get chunking service for semchunk/mindchunk methods
        # Create separate service instances instead of modifying global state (thread-safe)
        if method == "semchunk":
            # Create semchunk service instance directly (thread-safe)
            from services.knowledge.chunking_service import ChunkingService
            service = ChunkingService(mode="automatic")
        elif method == "mindchunk":
            # Create mindchunk service instance directly (thread-safe)
            # Need to create LLMSemanticChunker first, then wrap it
            if not HAS_LLM_CHUNKING:
                raise ValueError(
                    "MindChunk chunking requires llm_chunking library. "
                    "Install with: pip install llm-chunking"
                )
            from services.knowledge.chunking_service import MindChunkAdapter
            from llm_chunking.chunker import LLMSemanticChunker
            chunker = LLMSemanticChunker()
            service = MindChunkAdapter(chunker)
        else:
            raise ValueError(
                f"Unknown chunking method: {method}. "
                f"Supported methods: 'spacy', 'semchunk', 'chonkie', 'langchain', 'mindchunk', 'qa'"
            )

        # Chunk the text
        chunks = service.chunk_text(text, metadata=metadata or {})
        chunking_time = (time.time() - start_time) * 1000

        logger.debug(
            "[ChunkComparator] Chunked with %s: %s chunks in %.2fms",
            method,
            len(chunks),
            chunking_time
        )

        return chunks, chunking_time

    def compare_chunk_stats(
        self,
        chunks_semchunk: List[Chunk],
        chunks_mindchunk: List[Chunk]
    ) -> Dict[str, Any]:
        """
        Compare chunk statistics between two methods.

        Args:
            chunks_semchunk: Chunks from semchunk method
            chunks_mindchunk: Chunks from mindchunk method

        Returns:
            Comparison metrics dictionary
        """
        stats = {
            "semchunk": self.calculate_chunk_stats(chunks_semchunk),
            "mindchunk": self.calculate_chunk_stats(chunks_mindchunk),
            "comparison": {}
        }

        # Compare counts
        stats["comparison"]["chunk_count_diff"] = (
            len(chunks_mindchunk) - len(chunks_semchunk)
        )
        stats["comparison"]["chunk_count_ratio"] = (
            len(chunks_mindchunk) / len(chunks_semchunk)
            if len(chunks_semchunk) > 0 else 0
        )

        # Compare sizes
        stats["comparison"]["avg_size_diff"] = (
            stats["mindchunk"]["avg_chars"] - stats["semchunk"]["avg_chars"]
        )
        stats["comparison"]["total_chars_diff"] = (
            stats["mindchunk"]["total_chars"] - stats["semchunk"]["total_chars"]
        )

        # Size distribution comparison
        stats["comparison"]["size_distribution"] = {
            "semchunk": stats["semchunk"]["size_distribution"],
            "mindchunk": stats["mindchunk"]["size_distribution"]
        }

        return stats

    def calculate_chunk_stats(self, chunks: List[Chunk]) -> Dict[str, Any]:
        """
        Calculate statistics for a list of chunks.

        Args:
            chunks: List of chunks

        Returns:
            Statistics dictionary
        """
        if not chunks:
            return {
                "count": 0,
                "total_chars": 0,
                "avg_chars": 0,
                "min_chars": 0,
                "max_chars": 0,
                "size_distribution": {}
            }

        char_lengths = [len(chunk.text) for chunk in chunks]
        total_chars = sum(char_lengths)
        avg_chars = total_chars / len(chunks) if chunks else 0

        # Size distribution (buckets)
        size_buckets = {
            "tiny": 0,      # < 100 chars
            "small": 0,     # 100-500 chars
            "medium": 0,    # 500-1000 chars
            "large": 0,     # 1000-2000 chars
            "xlarge": 0     # > 2000 chars
        }

        for length in char_lengths:
            if length < 100:
                size_buckets["tiny"] += 1
            elif length < 500:
                size_buckets["small"] += 1
            elif length < 1000:
                size_buckets["medium"] += 1
            elif length < 2000:
                size_buckets["large"] += 1
            else:
                size_buckets["xlarge"] += 1

        return {
            "count": len(chunks),
            "total_chars": total_chars,
            "avg_chars": round(avg_chars, 2),
            "min_chars": min(char_lengths) if char_lengths else 0,
            "max_chars": max(char_lengths) if char_lengths else 0,
            "size_distribution": size_buckets
        }

    def compare_two_modes(
        self,
        chunks_a: List[Chunk],
        chunks_b: List[Chunk],
        mode_a: str,
        mode_b: str
    ) -> Dict[str, Any]:
        """
        Compare two chunking modes.

        Args:
            chunks_a: Chunks from first mode
            chunks_b: Chunks from second mode
            mode_a: Name of first mode
            mode_b: Name of second mode

        Returns:
            Comparison metrics dictionary
        """
        stats_a = self.calculate_chunk_stats(chunks_a)
        stats_b = self.calculate_chunk_stats(chunks_b)

        return {
            "chunk_count_diff": len(chunks_b) - len(chunks_a),
            "chunk_count_ratio": (
                len(chunks_b) / len(chunks_a)
                if len(chunks_a) > 0 else 0
            ),
            "avg_size_diff": stats_b["avg_chars"] - stats_a["avg_chars"],
            "total_chars_diff": stats_b["total_chars"] - stats_a["total_chars"],
            "size_distribution": {
                mode_a: stats_a["size_distribution"],
                mode_b: stats_b["size_distribution"]
            }
        }

    def calculate_coverage_score(
        self,
        retrieved_chunks: List[Chunk],
        document_text: str
    ) -> float:
        """
        Calculate coverage score: percentage of document covered by retrieved chunks.

        Args:
            retrieved_chunks: List of retrieved chunks
            document_text: Full document text

        Returns:
            Coverage score (0-1)
        """
        if not document_text:
            return 0.0

        if not retrieved_chunks:
            return 0.0

        total_chars_in_chunks = sum(len(chunk.text) for chunk in retrieved_chunks)
        total_doc_chars = len(document_text)

        if total_doc_chars == 0:
            return 0.0

        return min(total_chars_in_chunks / total_doc_chars, 1.0)

    def calculate_chunk_coherence(
        self,
        chunks: List[Chunk]
    ) -> float:
        """
        Calculate semantic coherence of chunks using embeddings.

        Args:
            chunks: List of chunks

        Returns:
            Coherence score (0-1), higher = more coherent
        """
        if len(chunks) < 2:
            return 1.0

        if not HAS_EMBEDDING or not HAS_NUMPY:
            logger.warning(
                "[ChunkComparator] Embedding client or numpy not available for coherence calculation"
            )
            return 0.0

        try:
            embedding_client = get_embedding_client()

            # Get embeddings for all chunks
            texts = [chunk.text for chunk in chunks]
            embeddings = embedding_client.embed_texts(texts)

            if len(embeddings) != len(chunks):
                logger.warning(
                    "[ChunkComparator] Embedding count mismatch for coherence calculation"
                )
                return 0.0

            # Calculate pairwise cosine similarity within each chunk
            # For simplicity, calculate average similarity between adjacent chunks

            similarities = []
            for i in range(len(embeddings) - 1):
                emb_a = np.array(embeddings[i])
                emb_b = np.array(embeddings[i + 1])

                # Cosine similarity
                dot_product = np.dot(emb_a, emb_b)
                norm_a = np.linalg.norm(emb_a)
                norm_b = np.linalg.norm(emb_b)

                if norm_a > 0 and norm_b > 0:
                    similarity = dot_product / (norm_a * norm_b)
                    similarities.append(similarity)

            if not similarities:
                return 0.0

            return float(np.mean(similarities))

        except Exception as e:
            logger.warning(
                "[ChunkComparator] Failed to calculate coherence: %s",
                e
            )
            return 0.0

    def calculate_chunk_overlap(
        self,
        chunks_a: List[Chunk],
        chunks_b: List[Chunk]
    ) -> Dict[str, float]:
        """
        Calculate character-level overlap between chunks from two methods.

        Args:
            chunks_a: Chunks from first method
            chunks_b: Chunks from second method

        Returns:
            Dictionary with overlap_ratio, unique_chars_a, unique_chars_b
        """
        if not chunks_a and not chunks_b:
            return {
                "overlap_ratio": 0.0,
                "unique_chars_a": 0.0,
                "unique_chars_b": 0.0
            }

        # Get all unique characters from each method
        chars_a = set()
        for chunk in chunks_a:
            chars_a.update(chunk.text)

        chars_b = set()
        for chunk in chunks_b:
            chars_b.update(chunk.text)

        # Calculate overlap
        overlap_chars = chars_a & chars_b
        union_chars = chars_a | chars_b

        if not union_chars:
            overlap_ratio = 0.0
        else:
            overlap_ratio = len(overlap_chars) / len(union_chars)

        unique_chars_a = len(chars_a - chars_b)
        unique_chars_b = len(chars_b - chars_a)

        return {
            "overlap_ratio": overlap_ratio,
            "unique_chars_a": float(unique_chars_a),
            "unique_chars_b": float(unique_chars_b)
        }

    def calculate_boundary_quality(
        self,
        chunks: List[Chunk],
        _document_text: str
    ) -> float:
        """
        Calculate boundary quality: how well chunk boundaries align with semantic breaks.

        Uses embedding similarity at boundaries - lower similarity = better boundaries.

        Args:
            chunks: List of chunks
            document_text: Full document text

        Returns:
            Boundary quality score (0-1), higher = better boundaries
        """
        if len(chunks) < 2:
            return 1.0

        if not HAS_EMBEDDING or not HAS_NUMPY:
            logger.warning(
                "[ChunkComparator] Embedding client or numpy not available for boundary quality"
            )
            return 0.0

        try:
            embedding_client = get_embedding_client()

            # Get embeddings for chunks
            texts = [chunk.text for chunk in chunks]
            embeddings = embedding_client.embed_texts(texts)

            if len(embeddings) != len(chunks):
                logger.warning(
                    "[ChunkComparator] Embedding count mismatch for boundary quality"
                )
                return 0.0

            # Calculate similarity at boundaries (adjacent chunks)
            boundary_similarities = []
            for i in range(len(embeddings) - 1):
                emb_a = np.array(embeddings[i])
                emb_b = np.array(embeddings[i + 1])

                dot_product = np.dot(emb_a, emb_b)
                norm_a = np.linalg.norm(emb_a)
                norm_b = np.linalg.norm(emb_b)

                if norm_a > 0 and norm_b > 0:
                    similarity = dot_product / (norm_a * norm_b)
                    boundary_similarities.append(similarity)

            if not boundary_similarities:
                return 0.0

            # Lower similarity at boundaries = better boundaries
            # Convert to quality score: 1 - average_similarity
            avg_similarity = float(np.mean(boundary_similarities))
            quality_score = max(0.0, 1.0 - avg_similarity)

            return quality_score

        except Exception as e:
            logger.warning(
                "[ChunkComparator] Failed to calculate boundary quality: %s",
                e
            )
            return 0.0
