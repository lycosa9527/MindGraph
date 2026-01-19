"""
Diversity & Efficiency Evaluator for RAG Chunk Testing
======================================================

Evaluates diversity and efficiency metrics for chunking methods.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import List, Dict
import logging
import statistics

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


class DiversityEvaluator:
    """Evaluate diversity and efficiency metrics."""

    def __init__(self):
        """Initialize diversity evaluator."""

    def calculate_intra_list_diversity(
        self,
        retrieved_chunks: List[Chunk]
    ) -> float:
        """
        Calculate intra-list diversity: average pairwise distance between chunks.

        Higher score = more diverse chunks.

        Args:
            retrieved_chunks: List of retrieved chunks

        Returns:
            Diversity score (0-1)
        """
        if len(retrieved_chunks) < 2:
            return 1.0

        if not HAS_EMBEDDING or not HAS_NUMPY:
            logger.warning(
                "[DiversityEvaluator] Embedding client or numpy not available"
            )
            return 0.0

        try:
            embedding_client = get_embedding_client()

            # Get embeddings for all chunks
            texts = [chunk.text for chunk in retrieved_chunks]
            embeddings = embedding_client.embed_texts(texts)

            if len(embeddings) != len(retrieved_chunks):
                logger.warning(
                    "[DiversityEvaluator] Embedding count mismatch"
                )
                return 0.0

            # Calculate pairwise cosine distances
            distances = []
            for i, emb_a_raw in enumerate(embeddings):
                for j in range(i + 1, len(embeddings)):
                    emb_a = np.array(emb_a_raw)
                    emb_b = np.array(embeddings[j])

                    # Cosine similarity
                    dot_product = np.dot(emb_a, emb_b)
                    norm_a = np.linalg.norm(emb_a)
                    norm_b = np.linalg.norm(emb_b)

                    if norm_a > 0 and norm_b > 0:
                        similarity = dot_product / (norm_a * norm_b)
                        # Distance = 1 - similarity
                        distance = 1.0 - similarity
                        distances.append(distance)

            if not distances:
                return 0.0

            # Average distance = diversity
            return float(np.mean(distances))

        except Exception as e:
            logger.warning(
                "[DiversityEvaluator] Failed to calculate diversity: %s",
                e
            )
            return 0.0

    def calculate_diversity_at_k(
        self,
        retrieved_chunks: List[Chunk],
        k: int
    ) -> float:
        """
        Calculate diversity of top K retrieved chunks.

        Args:
            retrieved_chunks: List of retrieved chunks (in order)
            k: Cutoff rank

        Returns:
            Diversity score (0-1)
        """
        top_k = retrieved_chunks[:k]
        return self.calculate_intra_list_diversity(top_k)

    def calculate_storage_efficiency(
        self,
        chunks: List[Chunk]
    ) -> Dict[str, float]:
        """
        Calculate storage efficiency metrics.

        Args:
            chunks: List of chunks

        Returns:
            Dictionary with efficiency metrics
        """
        if not chunks:
            return {
                "avg_chars_per_chunk": 0.0,
                "total_storage_chars": 0.0,
                "embedding_cost_estimate": 0.0
            }

        char_lengths = [len(chunk.text) for chunk in chunks]
        total_chars = sum(char_lengths)
        avg_chars = total_chars / len(chunks) if chunks else 0.0

        # Estimate embedding cost (rough estimate: assume cost per token)
        # This is a placeholder - actual cost depends on embedding service
        total_tokens_estimate = total_chars / 4  # Rough estimate: 4 chars per token
        embedding_cost_estimate = total_tokens_estimate * 0.0001  # Placeholder cost

        return {
            "avg_chars_per_chunk": round(avg_chars, 2),
            "total_storage_chars": total_chars,
            "embedding_cost_estimate": round(embedding_cost_estimate, 4)
        }

    def calculate_latency_metrics(
        self,
        timing_data: List[Dict[str, float]]
    ) -> Dict[str, float]:
        """
        Calculate latency metrics from timing data.

        Args:
            timing_data: List of timing dictionaries with 'total_ms' key

        Returns:
            Dictionary with latency metrics
        """
        if not timing_data:
            return {
                "avg_retrieval_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "p99_latency_ms": 0.0
            }

        latencies = [
            t.get("total_ms", 0.0) for t in timing_data
            if "total_ms" in t
        ]

        if not latencies:
            return {
                "avg_retrieval_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "p99_latency_ms": 0.0
            }

        avg_latency = statistics.mean(latencies)
        sorted_latencies = sorted(latencies)

        p95_idx = int(len(sorted_latencies) * 0.95)
        p99_idx = int(len(sorted_latencies) * 0.99)

        p95_latency = (
            sorted_latencies[p95_idx]
            if p95_idx < len(sorted_latencies)
            else sorted_latencies[-1]
        )
        p99_latency = (
            sorted_latencies[p99_idx]
            if p99_idx < len(sorted_latencies)
            else sorted_latencies[-1]
        )

        return {
            "avg_retrieval_latency_ms": round(avg_latency, 2),
            "p95_latency_ms": round(p95_latency, 2),
            "p99_latency_ms": round(p99_latency, 2)
        }
