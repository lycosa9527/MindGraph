"""
Retrieval Evaluator for RAG Chunk Testing
==========================================

Evaluates retrieval performance for different chunking methods.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from services.knowledge.chunking_service import Chunk
from services.knowledge.retrieval_test_service import RetrievalTestService

logger = logging.getLogger(__name__)


class RetrievalEvaluator:
    """Evaluate retrieval performance for chunked documents."""

    def __init__(self):
        """Initialize retrieval evaluator."""
        self.retrieval_test_service = RetrievalTestService()

    async def test_retrieval(
        self,
        chunks: List[Chunk],
        query: str,
        _method: str = "hybrid",
        top_k: int = 5,
        test_user_id: int = 0,
        collection_name: Optional[str] = None,
        progress_callback: Optional[Callable[[str, Optional[str], str, int], None]] = None,
        method_name: Optional[str] = None,
        db: Optional[object] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Test retrieval on chunked documents.

        Args:
            chunks: List of chunks to test retrieval on
            query: Test query
            _method: Retrieval method ('semantic', 'keyword', 'hybrid') (unused)
            top_k: Number of results to retrieve
            test_user_id: User ID for testing (uses 0 for test collections)
            collection_name: Optional collection name (auto-generated if None)
            progress_callback: Optional callback function(status, method, stage, progress)
            method_name: Optional chunking method name for progress reporting
            db: Optional async database session for embedding caching
            user_id: Optional user ID for embedding caching (uses test_user_id if not provided)

        Returns:
            Retrieval results with metrics
        """
        logger.debug(
            "[RetrievalEvaluator] No local index query=%s method=%s top_k=%s chunks=%s",
            query[:80],
            method_name or _method,
            top_k,
            len(chunks),
        )
        logger.debug(
            "[RetrievalEvaluator] user=%s collection=%s db=%s",
            user_id if user_id is not None else test_user_id,
            collection_name,
            db is not None,
        )
        if progress_callback:
            progress_callback("processing", method_name, "done", 100)
        return {
            "results": [],
            "metrics": {
                "precision": 0.0,
                "recall": 0.0,
                "mrr": 0.0,
                "ndcg": 0.0,
                "hit_rate": 0.0,
            },
            "timing": {},
        }

    def compare_retrieval_results(
        self,
        results_a: Dict[str, Any],
        results_b: Dict[str, Any],
        expected_chunk_ids: Optional[List[int]] = None,
        relevance_scores: Optional[Dict[int, float]] = None,
        mode_a: str = "semchunk",
        mode_b: str = "langchain",
    ) -> Dict[str, Any]:
        """
        Compare retrieval results between two chunking methods.

        Args:
            results_a: Retrieval results from first method
            results_b: Retrieval results from second method
            expected_chunk_ids: Expected relevant chunk IDs (for metrics)
            relevance_scores: Relevance scores for chunks (for NDCG)
            mode_a: Name of first method (default: "semchunk")
            mode_b: Name of second method (default: "langchain")

        Returns:
            Comparison metrics
        """
        chunk_ids_a = [r["chunk_id"] for r in results_a.get("results", [])]
        chunk_ids_b = [r["chunk_id"] for r in results_b.get("results", [])]

        comparison = {
            mode_a: {
                "retrieved_count": len(chunk_ids_a),
                "timing": results_a.get("timing", {}),
            },
            mode_b: {
                "retrieved_count": len(chunk_ids_b),
                "timing": results_b.get("timing", {}),
            },
            "comparison": {},
        }

        # Calculate metrics if expected chunks provided
        if expected_chunk_ids:
            metrics_a = self.retrieval_test_service.calculate_quality_metrics(
                retrieved_chunk_ids=chunk_ids_a,
                expected_chunk_ids=expected_chunk_ids,
                relevance_scores=relevance_scores,
            )
            metrics_b = self.retrieval_test_service.calculate_quality_metrics(
                retrieved_chunk_ids=chunk_ids_b,
                expected_chunk_ids=expected_chunk_ids,
                relevance_scores=relevance_scores,
            )

            comparison[mode_a]["metrics"] = metrics_a
            comparison[mode_b]["metrics"] = metrics_b

            # Compare metrics
            comparison["comparison"] = {
                "precision_diff": metrics_b["precision"] - metrics_a["precision"],
                "recall_diff": metrics_b["recall"] - metrics_a["recall"],
                "mrr_diff": metrics_b["mrr"] - metrics_a["mrr"],
                "ndcg_diff": metrics_b["ndcg"] - metrics_a["ndcg"],
                "f1_diff": metrics_b.get("f1", 0) - metrics_a.get("f1", 0),
                "precision_at_k_diff": {
                    k: metrics_b.get("precision_at_k", {}).get(k, 0) - metrics_a.get("precision_at_k", {}).get(k, 0)
                    for k in [1, 3, 5, 10]
                },
                "recall_at_k_diff": {
                    k: metrics_b.get("recall_at_k", {}).get(k, 0) - metrics_a.get("recall_at_k", {}).get(k, 0)
                    for k in [1, 3, 5, 10]
                },
                "winner": self._determine_winner(metrics_a, metrics_b, mode_a, mode_b),
            }

        # Compare timing
        total_a = results_a.get("timing", {}).get("total_ms", 0)
        total_b = results_b.get("timing", {}).get("total_ms", 0)
        comparison["comparison"]["timing_diff_ms"] = total_b - total_a

        return comparison

    def _determine_winner(
        self,
        metrics_a: Dict[str, float],
        metrics_b: Dict[str, float],
        mode_a: str = "semchunk",
        mode_b: str = "langchain",
    ) -> str:
        """
        Determine which method performed better.

        Args:
            metrics_a: Metrics for first method
            metrics_b: Metrics for second method
            mode_a: Name of first method (default: "semchunk")
            mode_b: Name of second method (default: "langchain")

        Returns:
            mode_a, mode_b, or 'tie'
        """
        # Weighted score: precision (0.3) + recall (0.3) + MRR (0.2) + NDCG (0.2)
        score_a = (
            metrics_a["precision"] * 0.3 + metrics_a["recall"] * 0.3 + metrics_a["mrr"] * 0.2 + metrics_a["ndcg"] * 0.2
        )
        score_b = (
            metrics_b["precision"] * 0.3 + metrics_b["recall"] * 0.3 + metrics_b["mrr"] * 0.2 + metrics_b["ndcg"] * 0.2
        )

        if score_b > score_a:
            return mode_b
        if score_a > score_b:
            return mode_a
        return "tie"

    async def cleanup_test_collection(self, test_user_id: int = 0, collection_name: Optional[str] = None):
        """Personal knowledge does not keep a temporary local index."""
        logger.debug(
            "[RetrievalEvaluator] No local index to clean user=%s collection=%s",
            test_user_id,
            collection_name,
        )
