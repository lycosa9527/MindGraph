"""
Embedding-based boundary detection using semantic similarity.

Implements LlamaIndex-style semantic chunking using DashScope/Qwen embeddings:
1. Split text into sentences
2. Generate embeddings for sentence groups (with buffer_size context)
3. Calculate cosine distance between adjacent sentences
4. Use percentile threshold (default 95th) to find breakpoints
5. Create chunks at high-distance breakpoints

Author: MindSpring Team
Copyright 2024-2025 北京思源智教科技有限公司
All Rights Reserved
Proprietary License
"""

import re
import logging
from typing import List, Tuple, Optional
import numpy as np
from llm_chunking.utils.embedding_service import get_embedding_service, EmbeddingService

logger = logging.getLogger(__name__)


def combine_sentences(sentences: List[dict], buffer_size: int = 1) -> List[dict]:
    """
    Combine sentences with buffer context for embedding.

    For each sentence, create a combined sentence that includes:
    - buffer_size sentences before
    - current sentence
    - buffer_size sentences after

    This provides context for better semantic similarity calculation.

    Args:
        sentences: List of sentence dicts with 'sentence' and 'index' keys
        buffer_size: Number of sentences to include before/after

    Returns:
        List of sentence dicts with 'combined_sentence' added
    """
    for i in range(len(sentences)):
        combined_sentence = ""

        # Add sentences before current one
        for j in range(i - buffer_size, i):
            if j >= 0:
                combined_sentence += sentences[j]["sentence"] + " "

        # Add current sentence
        combined_sentence += sentences[i]["sentence"]

        # Add sentences after current one
        for j in range(i + 1, i + 1 + buffer_size):
            if j < len(sentences):
                combined_sentence += " " + sentences[j]["sentence"]

        sentences[i]["combined_sentence"] = combined_sentence

    return sentences


def calculate_cosine_distances(
    sentences: List[dict],
    embedding_service: EmbeddingService
) -> List[float]:
    """
    Calculate cosine distances between adjacent sentence groups.

    Args:
        sentences: List of sentence dicts with 'combined_sentence_embedding'
        embedding_service: EmbeddingService instance

    Returns:
        List of cosine distances (one less than input length)
    """
    distances = []

    for i in range(len(sentences) - 1):
        embedding_current = sentences[i].get("combined_sentence_embedding")
        embedding_next = sentences[i + 1].get("combined_sentence_embedding")

        if embedding_current and embedding_next:
            # Calculate cosine distance
            distance = embedding_service.cosine_distance(embedding_current, embedding_next)
            distances.append(distance)
        else:
            # If embeddings missing, use high distance (force breakpoint)
            distances.append(1.0)

    # Add last distance (always 0, no next sentence)
    distances.append(0.0)

    return distances


def get_indices_above_threshold(distances: List[float], threshold: float) -> List[int]:
    """
    Get indices where distance exceeds percentile threshold.

    Args:
        distances: List of cosine distances
        threshold: Percentile threshold (e.g., 95.0 for 95th percentile)

    Returns:
        List of indices where distance exceeds threshold
    """
    if not distances:
        return []

    # Calculate percentile threshold
    breakpoint_distance_threshold = np.percentile(distances, threshold)

    # Get indices above threshold
    indices_above_threshold = [
        i for i, x in enumerate(distances) if x > breakpoint_distance_threshold
    ]

    return indices_above_threshold


def make_chunks(sentences: List[dict], indices_above_thresh: List[int]) -> List[str]:
    """
    Create chunks from sentences using breakpoint indices.

    Args:
        sentences: List of sentence dicts with 'sentence' key
        indices_above_thresh: List of breakpoint indices

    Returns:
        List of chunk texts
    """
    if not sentences:
        return []

    chunks = []
    start_index = 0

    # Create chunks at breakpoints
    for index in indices_above_thresh:
        end_index = index

        # Combine sentences from start to end
        group = sentences[start_index:end_index + 1]
        combined_text = " ".join([d["sentence"] for d in group])
        chunks.append(combined_text)

        start_index = index + 1

    # Add final chunk if any sentences remain
    if start_index < len(sentences):
        combined_text = " ".join([d["sentence"] for d in sentences[start_index:]])
        chunks.append(combined_text)

    return chunks


class EmbeddingBoundaryDetector:
    """
    Embedding-based boundary detector using semantic similarity.

    Implements LlamaIndex-style semantic chunking:
    - Splits text into sentences
    - Generates embeddings with buffer context
    - Calculates cosine distances
    - Uses percentile threshold to find breakpoints
    """

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        buffer_size: int = 1,
        breakpoint_percentile_threshold: float = 95.0
    ):
        """
        Initialize embedding boundary detector.

        Args:
            embedding_service: Optional EmbeddingService instance
            buffer_size: Number of sentences to include in context (default: 1)
            breakpoint_percentile_threshold: Percentile threshold for breakpoints (default: 95.0)
        """
        self.embedding_service = embedding_service or get_embedding_service()
        self.buffer_size = buffer_size
        self.breakpoint_percentile_threshold = breakpoint_percentile_threshold

        if not self.embedding_service.is_available():
            logger.warning(
                "[EmbeddingBoundaryDetector] Embedding service not available, "
                "boundary detection will be disabled"
            )

    def find_boundaries(
        self,
        text: str,
        max_tokens: Optional[int] = None
    ) -> List[Tuple[int, int]]:
        """
        Find semantic boundaries in text using embedding similarity.

        Args:
            text: Text to analyze
            max_tokens: Optional maximum tokens per chunk (not enforced, informational)

        Returns:
            List of (start_pos, end_pos) tuples representing chunk boundaries
        """
        if not self.embedding_service.is_available():
            logger.warning(
                "[EmbeddingBoundaryDetector] Embedding service not available, "
                "returning empty boundaries"
            )
            return []

        # Step 1: Split text into sentences
        sentences = self._split_into_sentences(text)

        if len(sentences) < 2:
            # Too few sentences, return single chunk
            if sentences:
                return [(0, len(text))]
            return []

        # Step 2: Combine sentences with buffer context
        combined_sentences = combine_sentences(sentences, self.buffer_size)

        # Step 3: Generate embeddings for combined sentences
        combined_texts = [s["combined_sentence"] for s in combined_sentences]

        try:
            embeddings = self.embedding_service.embed_texts(combined_texts)

            # Assign embeddings to sentences
            for i, embedding in enumerate(embeddings):
                combined_sentences[i]["combined_sentence_embedding"] = embedding
        except Exception as e:
            logger.error("[EmbeddingBoundaryDetector] Failed to generate embeddings: %s", e)
            return []

        # Step 4: Calculate cosine distances
        distances = calculate_cosine_distances(combined_sentences, self.embedding_service)

        # Assign distances to sentences
        for i, distance in enumerate(distances):
            combined_sentences[i]["dist_to_next"] = distance

        # Step 5: Get breakpoint indices
        indices_above_thresh = get_indices_above_threshold(
            distances,
            self.breakpoint_percentile_threshold
        )

        # Step 6: Convert breakpoint indices to character positions
        boundaries = self._indices_to_boundaries(
            combined_sentences,
            indices_above_thresh,
            text
        )

        logger.debug(
            f"[EmbeddingBoundaryDetector] Found {len(boundaries)} boundaries "
            f"from {len(sentences)} sentences"
        )

        return boundaries

    def _split_into_sentences(self, text: str) -> List[dict]:
        """
        Split text into sentences.

        Supports both Chinese and English punctuation:
        - Chinese: 。！？
        - English: . ! ?

        Args:
            text: Text to split

        Returns:
            List of sentence dicts with 'sentence' and 'index' keys
        """
        # Pattern for sentence endings (Chinese and English)
        sentence_pattern = r'(?<=[。！？.!?])\s+'

        # Split text
        sentence_texts = re.split(sentence_pattern, text)

        # Filter empty sentences
        sentence_texts = [s.strip() for s in sentence_texts if s.strip()]

        # Build sentence dicts with positions
        sentences = []
        current_pos = 0

        for i, sentence_text in enumerate(sentence_texts):
            # Find position in original text
            pos = text.find(sentence_text, current_pos)
            if pos == -1:
                pos = current_pos

            sentences.append({
                "sentence": sentence_text,
                "index": i,
                "start_pos": pos,
                "end_pos": pos + len(sentence_text)
            })

            current_pos = pos + len(sentence_text)

        return sentences

    def _indices_to_boundaries(
        self,
        sentences: List[dict],
        indices_above_thresh: List[int],
        original_text: str
    ) -> List[Tuple[int, int]]:
        """
        Convert sentence indices to character position boundaries.

        Args:
            sentences: List of sentence dicts with position info
            indices_above_thresh: List of breakpoint indices
            original_text: Original text for validation

        Returns:
            List of (start_pos, end_pos) tuples
        """
        if not sentences:
            return []

        boundaries = []
        start_pos = sentences[0]["start_pos"]

        for index in indices_above_thresh:
            if index < len(sentences):
                end_pos = sentences[index]["end_pos"]
                boundaries.append((start_pos, end_pos))
                start_pos = end_pos

        # Add final boundary
        if start_pos < len(original_text):
            boundaries.append((start_pos, len(original_text)))

        return boundaries

    def get_boundary_confidence(
        self,
        text: str,
        start_pos: int,
        end_pos: int
    ) -> float:
        """
        Get confidence score for a boundary using embedding similarity.

        Higher confidence = more likely to be a good boundary.

        Args:
            text: Full text
            start_pos: Start position of potential chunk
            end_pos: End position of potential chunk

        Returns:
            Confidence score (0.0 to 1.0)
        """
        if not self.embedding_service.is_available():
            return 0.5  # Neutral confidence if embeddings unavailable

        chunk_text = text[start_pos:end_pos]

        # Get context before and after
        context_before = text[max(0, start_pos - 200):start_pos]
        context_after = text[end_pos:min(len(text), end_pos + 200)]

        try:
            # Embed chunk and contexts
            texts_to_embed = [context_before, chunk_text, context_after]
            embeddings = self.embedding_service.embed_texts(texts_to_embed)

            if len(embeddings) < 3:
                return 0.5

            # Calculate similarity between chunk and contexts
            similarity_before = self.embedding_service.cosine_similarity(
                embeddings[0], embeddings[1]
            )
            similarity_after = self.embedding_service.cosine_similarity(
                embeddings[1], embeddings[2]
            )

            # Lower similarity = higher confidence (chunk is distinct)
            confidence = 1.0 - (similarity_before + similarity_after) / 2.0

            return float(np.clip(confidence, 0.0, 1.0))
        except Exception as e:
            logger.warning("[EmbeddingBoundaryDetector] Failed to calculate confidence: %s", e)
            return 0.5
