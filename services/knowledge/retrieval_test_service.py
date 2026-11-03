"""
Retrieval Test Service for Knowledge Space
Author: lycosa9527
Made by: MindSpring Team

Service for testing retrieval functionality (hit testing).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import math
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.knowledge_space import EvaluationDataset, EvaluationResult
from services.utils.error_types import DATABASE_ERRORS

logger = logging.getLogger(__name__)


class RetrievalTestService:
    """
    Service for testing retrieval functionality.

    Allows users to test if their knowledge base works correctly.
    """

    async def test_retrieval(
        self,
        db: AsyncSession,
        user_id: int,
        query: str,
        method: str = "hybrid",
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> Dict[str, Any]:
        """Personal knowledge is retrieved by the diagram, not this lab search."""
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        if db is None:
            raise ValueError("Database session is required")
        logger.info(
            "[RetrievalTest] Folder retrieval is used instead user=%s method=%s top_k=%s threshold=%s",
            user_id,
            method,
            top_k,
            score_threshold,
        )
        return {"query": query, "method": method, "results": [], "timing": {}, "stats": {}}

    def calculate_precision(self, retrieved_chunk_ids: List[int], relevant_chunk_ids: List[int]) -> float:
        """
        Calculate precision: relevant retrieved / total retrieved.

        Args:
            retrieved_chunk_ids: List of retrieved chunk IDs
            relevant_chunk_ids: List of relevant chunk IDs

        Returns:
            Precision score (0-1)
        """
        if not retrieved_chunk_ids:
            return 0.0

        relevant_retrieved = len(set(retrieved_chunk_ids) & set(relevant_chunk_ids))
        return relevant_retrieved / len(retrieved_chunk_ids)

    def calculate_recall(self, retrieved_chunk_ids: List[int], relevant_chunk_ids: List[int]) -> float:
        """
        Calculate recall: relevant retrieved / total relevant.

        Args:
            retrieved_chunk_ids: List of retrieved chunk IDs
            relevant_chunk_ids: List of relevant chunk IDs

        Returns:
            Recall score (0-1)
        """
        if not relevant_chunk_ids:
            return 1.0  # No relevant items means perfect recall

        relevant_retrieved = len(set(retrieved_chunk_ids) & set(relevant_chunk_ids))
        return relevant_retrieved / len(relevant_chunk_ids)

    def calculate_mrr(self, retrieved_chunk_ids: List[int], relevant_chunk_ids: List[int]) -> float:
        """
        Calculate Mean Reciprocal Rank (MRR).

        MRR = 1 / rank of first relevant item, or 0 if no relevant item found.

        Args:
            retrieved_chunk_ids: List of retrieved chunk IDs (in order)
            relevant_chunk_ids: Set of relevant chunk IDs

        Returns:
            MRR score (0-1)
        """
        if not relevant_chunk_ids:
            return 0.0

        relevant_set = set(relevant_chunk_ids)
        for rank, chunk_id in enumerate(retrieved_chunk_ids, start=1):
            if chunk_id in relevant_set:
                return 1.0 / rank

        return 0.0

    def calculate_ndcg(
        self,
        retrieved_chunk_ids: List[int],
        relevance_scores: Dict[int, float],
        k: Optional[int] = None,
    ) -> float:
        """
        Calculate Normalized Discounted Cumulative Gain (NDCG).

        Args:
            retrieved_chunk_ids: List of retrieved chunk IDs (in order)
            relevance_scores: Dict mapping chunk_id -> relevance score
            k: Cutoff rank (if None, use all retrieved)

        Returns:
            NDCG score (0-1)
        """
        if not retrieved_chunk_ids:
            return 0.0

        k = k or len(retrieved_chunk_ids)
        retrieved_chunk_ids = retrieved_chunk_ids[:k]

        # Calculate DCG
        dcg = 0.0
        for i, chunk_id in enumerate(retrieved_chunk_ids, start=1):
            relevance = relevance_scores.get(chunk_id, 0.0)
            dcg += relevance / math.log2(i + 1)

        # Calculate IDCG (ideal DCG)
        ideal_scores = sorted(relevance_scores.values(), reverse=True)[:k]
        idcg = sum(score / math.log2(i + 1) for i, score in enumerate(ideal_scores, start=1))

        if idcg == 0:
            return 0.0

        return dcg / idcg

    def calculate_f1_score(self, precision: float, recall: float) -> float:
        """
        Calculate F1 score: harmonic mean of precision and recall.

        Args:
            precision: Precision score (0-1)
            recall: Recall score (0-1)

        Returns:
            F1 score (0-1)
        """
        if precision + recall == 0:
            return 0.0
        return 2 * (precision * recall) / (precision + recall)

    def calculate_precision_at_k(self, retrieved_chunk_ids: List[int], relevant_chunk_ids: List[int], k: int) -> float:
        """
        Calculate precision at K: relevant retrieved in top K / K.

        Args:
            retrieved_chunk_ids: List of retrieved chunk IDs (in order)
            relevant_chunk_ids: List of relevant chunk IDs
            k: Cutoff rank

        Returns:
            Precision@K score (0-1)
        """
        if not retrieved_chunk_ids or k == 0:
            return 0.0

        top_k = retrieved_chunk_ids[:k]
        relevant_set = set(relevant_chunk_ids)
        relevant_retrieved = len([cid for cid in top_k if cid in relevant_set])

        return relevant_retrieved / k

    def calculate_recall_at_k(self, retrieved_chunk_ids: List[int], relevant_chunk_ids: List[int], k: int) -> float:
        """
        Calculate recall at K: relevant retrieved in top K / total relevant.

        Args:
            retrieved_chunk_ids: List of retrieved chunk IDs (in order)
            relevant_chunk_ids: List of relevant chunk IDs
            k: Cutoff rank

        Returns:
            Recall@K score (0-1)
        """
        if not relevant_chunk_ids:
            return 1.0

        if not retrieved_chunk_ids or k == 0:
            return 0.0

        top_k = retrieved_chunk_ids[:k]
        relevant_set = set(relevant_chunk_ids)
        relevant_retrieved = len([cid for cid in top_k if cid in relevant_set])

        return relevant_retrieved / len(relevant_chunk_ids)

    def calculate_hit_rate_at_k(self, retrieved_chunk_ids: List[int], relevant_chunk_ids: List[int], k: int) -> float:
        """
        Calculate hit rate at K: 1.0 if at least one relevant in top K, else 0.0.

        Args:
            retrieved_chunk_ids: List of retrieved chunk IDs (in order)
            relevant_chunk_ids: List of relevant chunk IDs
            k: Cutoff rank

        Returns:
            Hit Rate@K score (0.0 or 1.0)
        """
        if not relevant_chunk_ids:
            return 1.0

        if not retrieved_chunk_ids or k == 0:
            return 0.0

        top_k = retrieved_chunk_ids[:k]
        relevant_set = set(relevant_chunk_ids)

        return 1.0 if any(cid in relevant_set for cid in top_k) else 0.0

    def calculate_map(self, retrieved_lists: List[List[int]], relevant_lists: List[List[int]]) -> float:
        """
        Calculate Mean Average Precision (MAP) across multiple queries.

        Args:
            retrieved_lists: List of retrieved chunk ID lists (one per query)
            relevant_lists: List of relevant chunk ID lists (one per query)

        Returns:
            MAP score (0-1)
        """
        if not retrieved_lists or not relevant_lists:
            return 0.0

        if len(retrieved_lists) != len(relevant_lists):
            raise ValueError("retrieved_lists and relevant_lists must have same length")

        average_precisions = []

        for retrieved_ids, relevant_ids in zip(retrieved_lists, relevant_lists):
            if not relevant_ids:
                continue

            relevant_set = set(relevant_ids)
            precisions_at_relevant = []
            relevant_found = 0

            for rank, chunk_id in enumerate(retrieved_ids, start=1):
                if chunk_id in relevant_set:
                    relevant_found += 1
                    precision_at_rank = relevant_found / rank
                    precisions_at_relevant.append(precision_at_rank)

            if precisions_at_relevant:
                average_precision = sum(precisions_at_relevant) / len(relevant_ids)
                average_precisions.append(average_precision)

        if not average_precisions:
            return 0.0

        return sum(average_precisions) / len(average_precisions)

    def calculate_quality_metrics(
        self,
        retrieved_chunk_ids: List[int],
        expected_chunk_ids: List[int],
        relevance_scores: Optional[Dict[int, float]] = None,
    ) -> Dict[str, Any]:
        """
        Calculate all quality metrics for retrieval results.

        Args:
            retrieved_chunk_ids: List of retrieved chunk IDs (in order)
            expected_chunk_ids: List of expected/relevant chunk IDs
            relevance_scores: Optional dict mapping chunk_id -> relevance score (for NDCG)

        Returns:
            Dict with precision, recall, mrr, ndcg, f1, precision_at_k, recall_at_k
        """
        precision = self.calculate_precision(retrieved_chunk_ids, expected_chunk_ids)
        recall = self.calculate_recall(retrieved_chunk_ids, expected_chunk_ids)
        mrr = self.calculate_mrr(retrieved_chunk_ids, expected_chunk_ids)
        f1 = self.calculate_f1_score(precision, recall)

        # NDCG requires relevance scores
        if relevance_scores:
            ndcg = self.calculate_ndcg(retrieved_chunk_ids, relevance_scores)
        else:
            # Use binary relevance (1 for relevant, 0 for irrelevant)
            binary_scores = {chunk_id: 1.0 for chunk_id in expected_chunk_ids}
            ndcg = self.calculate_ndcg(retrieved_chunk_ids, binary_scores)

        # Calculate Precision@K and Recall@K for different K values
        k_values = [1, 3, 5, 10]
        precision_at_k = {
            k: self.calculate_precision_at_k(retrieved_chunk_ids, expected_chunk_ids, k) for k in k_values
        }
        recall_at_k = {k: self.calculate_recall_at_k(retrieved_chunk_ids, expected_chunk_ids, k) for k in k_values}

        return {
            "precision": precision,
            "recall": recall,
            "mrr": mrr,
            "ndcg": ndcg,
            "f1": f1,
            "precision_at_k": precision_at_k,
            "recall_at_k": recall_at_k,
        }

    async def run_evaluation(
        self, db: AsyncSession, user_id: int, dataset_id: int, method: str = "hybrid"
    ) -> Dict[str, Any]:
        """
        Run evaluation on a dataset.

        Args:
            db: Async database session
            user_id: User ID
            dataset_id: Dataset ID
            method: Retrieval method to test

        Returns:
            Dict with evaluation results
        """
        result = await db.execute(
            select(EvaluationDataset).where(EvaluationDataset.id == dataset_id, EvaluationDataset.user_id == user_id)
        )
        dataset = result.scalars().first()

        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found")

        if not dataset.queries:
            raise ValueError("Dataset has no queries")

        results = []
        all_metrics = []

        for query_data in dataset.queries:
            query = query_data.get("query", "")
            expected_chunk_ids = query_data.get("expected_chunk_ids", [])
            relevance_scores = query_data.get("relevance_scores", {})

            if not query:
                continue

            try:
                logger.debug(
                    "[RetrievalTest] Personal folder is the source user=%s method=%s query=%s",
                    user_id,
                    method,
                    query[:80],
                )
                metrics = self.calculate_quality_metrics(
                    retrieved_chunk_ids=[],
                    expected_chunk_ids=expected_chunk_ids,
                    relevance_scores=relevance_scores if relevance_scores else None,
                )

                all_metrics.append(metrics)
                results.append({"query": query, "metrics": metrics})

                eval_result = EvaluationResult(dataset_id=dataset_id, method=method, metrics=metrics)
                db.add(eval_result)

            except DATABASE_ERRORS as e:
                logger.error("[RetrievalTest] Failed to evaluate query '%s': %s", query, e)
                continue

        await db.commit()

        if all_metrics:
            avg_metrics = {
                "precision": sum(m["precision"] for m in all_metrics) / len(all_metrics),
                "recall": sum(m["recall"] for m in all_metrics) / len(all_metrics),
                "mrr": sum(m["mrr"] for m in all_metrics) / len(all_metrics),
                "ndcg": sum(m["ndcg"] for m in all_metrics) / len(all_metrics),
            }
        else:
            avg_metrics = {"precision": 0.0, "recall": 0.0, "mrr": 0.0, "ndcg": 0.0}

        return {
            "dataset_id": dataset_id,
            "method": method,
            "total_queries": len(dataset.queries),
            "evaluated_queries": len(results),
            "average_metrics": avg_metrics,
            "query_results": results,
        }


def get_retrieval_test_service() -> RetrievalTestService:
    """Get global retrieval test service instance."""
    if not hasattr(get_retrieval_test_service, "instance"):
        get_retrieval_test_service.instance = RetrievalTestService()
    return get_retrieval_test_service.instance
