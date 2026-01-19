"""
Cross-Method Comparator for RAG Chunk Testing
==============================================

Compares chunking methods across different dimensions.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import List, Dict, Any
import logging

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

from services.knowledge.chunking_service import Chunk


logger = logging.getLogger(__name__)


class CrossMethodComparator:
    """Compare chunking methods across different dimensions."""

    def __init__(self):
        """Initialize cross-method comparator."""

    def calculate_chunk_alignment(
        self,
        chunks_a: List[Chunk],
        chunks_b: List[Chunk]
    ) -> float:
        """
        Calculate semantic alignment between chunks from two methods.

        Uses embeddings to find best-matching chunks and calculates average similarity.

        Args:
            chunks_a: Chunks from first method
            chunks_b: Chunks from second method

        Returns:
            Alignment score (0-1), higher = better alignment
        """
        if not chunks_a or not chunks_b:
            return 0.0

        if not HAS_EMBEDDING or not HAS_NUMPY:
            logger.warning(
                "[CrossMethodComparator] Embedding client or numpy not available"
            )
            return 0.0

        try:
            embedding_client = get_embedding_client()

            # Get embeddings for both sets
            texts_a = [chunk.text for chunk in chunks_a]
            texts_b = [chunk.text for chunk in chunks_b]

            embeddings_a = embedding_client.embed_texts(texts_a)
            embeddings_b = embedding_client.embed_texts(texts_b)

            if len(embeddings_a) != len(chunks_a) or len(embeddings_b) != len(chunks_b):
                logger.warning(
                    "[CrossMethodComparator] Embedding count mismatch"
                )
                return 0.0

            # For each chunk in A, find best match in B
            best_matches = []
            for emb_a in embeddings_a:
                best_similarity = -1.0
                for emb_b in embeddings_b:
                    emb_a_np = np.array(emb_a)
                    emb_b_np = np.array(emb_b)

                    dot_product = np.dot(emb_a_np, emb_b_np)
                    norm_a = np.linalg.norm(emb_a_np)
                    norm_b = np.linalg.norm(emb_b_np)

                    if norm_a > 0 and norm_b > 0:
                        similarity = dot_product / (norm_a * norm_b)
                        best_similarity = max(best_similarity, similarity)

                if best_similarity >= 0:
                    best_matches.append(best_similarity)

            if not best_matches:
                return 0.0

            # Average of best matches = alignment score
            return float(np.mean(best_matches))

        except Exception as e:
            logger.warning(
                "[CrossMethodComparator] Failed to calculate alignment: %s",
                e
            )
            return 0.0

    def calculate_complementarity(
        self,
        retrieved_a: List[int],
        retrieved_b: List[int],
        relevant_chunks: List[int]
    ) -> float:
        """
        Calculate complementarity: how well methods complement each other.

        Formula: (Unique relevant found by A ∪ B) / (Relevant found by A ∩ B + 1)
        Higher = more complementary (less overlap)

        Args:
            retrieved_a: Retrieved chunk IDs from method A
            retrieved_b: Retrieved chunk IDs from method B
            relevant_chunks: List of relevant chunk IDs

        Returns:
            Complementarity score (0-1)
        """
        if not relevant_chunks:
            return 0.0

        relevant_set = set(relevant_chunks)
        retrieved_a_set = set(retrieved_a)
        retrieved_b_set = set(retrieved_b)

        # Find relevant chunks retrieved by each method
        relevant_a = retrieved_a_set & relevant_set
        relevant_b = retrieved_b_set & relevant_set

        # Union and intersection
        union_relevant = relevant_a | relevant_b
        intersection_relevant = relevant_a & relevant_b

        if not union_relevant:
            return 0.0

        # Complementarity: unique relevant / (overlap + 1 to avoid division by zero)
        complementarity = len(union_relevant) / (len(intersection_relevant) + 1)

        # Normalize to 0-1 range (max complementarity = all unique)
        max_complementarity = len(relevant_set)
        normalized = min(complementarity / max_complementarity, 1.0) if max_complementarity > 0 else 0.0

        return normalized

    def analyze_method_overlap(
        self,
        chunks_a: List[Chunk],
        chunks_b: List[Chunk]
    ) -> Dict[str, Any]:
        """
        Analyze overlap between chunks from two methods.

        Args:
            chunks_a: Chunks from first method
            chunks_b: Chunks from second method

        Returns:
            Dictionary with overlap analysis
        """
        if not chunks_a and not chunks_b:
            return {
                "character_overlap_percent": 0.0,
                "unique_chunks_a": 0,
                "unique_chunks_b": 0,
                "shared_chunks": 0
            }

        # Character-level overlap
        chars_a = set()
        for chunk in chunks_a:
            chars_a.update(chunk.text)

        chars_b = set()
        for chunk in chunks_b:
            chars_b.update(chunk.text)

        overlap_chars = chars_a & chars_b
        union_chars = chars_a | chars_b

        character_overlap = (
            len(overlap_chars) / len(union_chars) * 100
            if union_chars else 0.0
        )

        # Chunk-level overlap (using text similarity threshold)
        # Simple approach: exact text matches
        texts_a = {chunk.text for chunk in chunks_a}
        texts_b = {chunk.text for chunk in chunks_b}

        shared_texts = texts_a & texts_b
        unique_a = texts_a - texts_b
        unique_b = texts_b - texts_a

        return {
            "character_overlap_percent": round(character_overlap, 2),
            "unique_chunks_a": len(unique_a),
            "unique_chunks_b": len(unique_b),
            "shared_chunks": len(shared_texts)
        }
