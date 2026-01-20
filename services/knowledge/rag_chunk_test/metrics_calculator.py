"""
Metrics Calculator for RAG Chunk Test Service
==============================================

Module for calculating various metrics for chunking method comparison.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import List, Dict, Any, Optional
import logging

from services.knowledge.rag_chunk_test.chunk_comparator import ChunkComparator
from services.knowledge.rag_chunk_test.answer_quality_evaluator import AnswerQualityEvaluator
from services.knowledge.rag_chunk_test.diversity_evaluator import DiversityEvaluator
from services.knowledge.rag_chunk_test.cross_method_comparator import CrossMethodComparator
from services.knowledge.retrieval_test_service import RetrievalTestService

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """Calculator for various chunking and retrieval metrics."""

    def __init__(
        self,
        chunk_comparator: ChunkComparator,
        answer_quality_evaluator: AnswerQualityEvaluator,
        diversity_evaluator: DiversityEvaluator,
        cross_method_comparator: CrossMethodComparator
    ):
        """Initialize metrics calculator with required evaluators."""
        self.chunk_comparator = chunk_comparator
        self.answer_quality_evaluator = answer_quality_evaluator
        self.diversity_evaluator = diversity_evaluator
        self.cross_method_comparator = cross_method_comparator

    def calculate_average_metrics(
        self,
        comparison_results: List[Dict[str, Any]],
        modes: Optional[List[str]] = None,
        retrieval_results: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        queries: Optional[List[str]] = None,
        expected_chunks_map: Optional[Dict[str, List[int]]] = None
    ) -> Dict[str, Any]:
        """
        Calculate average metrics across all queries.

        Args:
            comparison_results: List of comparison results per query
            modes: List of chunking modes
            retrieval_results: Optional raw retrieval results (for MAP/Hit Rate calculation)
            queries: Optional list of queries (for MAP/Hit Rate calculation)
            expected_chunks_map: Optional map of query -> expected chunk IDs

        Returns:
            Dictionary with average metrics per mode
        """
        if not comparison_results:
            return {}

        if modes is None:
            modes = ["spacy", "semchunk", "chonkie", "langchain", "mindchunk"]

        metrics_by_mode = {mode: [] for mode in modes}

        for result in comparison_results:
            for mode in modes:
                if mode in result and "metrics" in result[mode]:
                    metrics_by_mode[mode].append(result[mode]["metrics"])

        avg_metrics = {}
        k_values = [1, 3, 5, 10]

        for mode in modes:
            if metrics_by_mode[mode]:
                mode_metrics = metrics_by_mode[mode]
                avg_metrics[mode] = {
                    "precision": sum(m.get("precision", 0) for m in mode_metrics) / len(mode_metrics),
                    "recall": sum(m.get("recall", 0) for m in mode_metrics) / len(mode_metrics),
                    "mrr": sum(m.get("mrr", 0) for m in mode_metrics) / len(mode_metrics),
                    "ndcg": sum(m.get("ndcg", 0) for m in mode_metrics) / len(mode_metrics),
                    "f1": sum(m.get("f1", 0) for m in mode_metrics) / len(mode_metrics),
                    "precision_at_k": {
                        k: sum(m.get("precision_at_k", {}).get(k, 0) for m in mode_metrics) / len(mode_metrics)
                        for k in k_values
                    },
                    "recall_at_k": {
                        k: sum(m.get("recall_at_k", {}).get(k, 0) for m in mode_metrics) / len(mode_metrics)
                        for k in k_values
                    }
                }

        # Calculate Hit Rate@K and MAP if we have retrieval results
        if retrieval_results and queries and expected_chunks_map:
            retrieval_service = RetrievalTestService()

            for mode in modes:
                if mode not in avg_metrics:
                    continue

                retrieved_lists = []
                relevant_lists = []

                for query in queries:
                    query_results = [
                        r for r in retrieval_results.get(mode, [])
                        if r.get("query") == query
                    ]
                    if query_results:
                        result = query_results[0]["result"]
                        retrieved_ids = [r["chunk_id"] for r in result.get("results", [])]
                        expected_ids = expected_chunks_map.get(query, [])

                        retrieved_lists.append(retrieved_ids)
                        relevant_lists.append(expected_ids)

                if retrieved_lists and relevant_lists:
                    # Calculate Hit Rate@K
                    hit_rates = {k: [] for k in k_values}
                    for retrieved_ids, relevant_ids in zip(retrieved_lists, relevant_lists):
                        for k in k_values:
                            hit_rate = retrieval_service.calculate_hit_rate_at_k(
                                retrieved_ids, relevant_ids, k
                            )
                            hit_rates[k].append(hit_rate)

                    avg_metrics[mode]["hit_rate_at_k"] = {
                        k: sum(hit_rates[k]) / len(hit_rates[k])
                        if hit_rates[k] else 0.0
                        for k in k_values
                    }

                    # Calculate MAP
                    map_score = retrieval_service.calculate_map(retrieved_lists, relevant_lists)
                    avg_metrics[mode]["map"] = map_score

        return avg_metrics

    def calculate_average_metrics_per_mode(
        self,
        retrieval_results: Dict[str, List[Dict[str, Any]]],
        modes: List[str],
        _queries: List[str],
        expected_chunks_map: Optional[Dict[str, List[int]]] = None
    ) -> Dict[str, Any]:
        """
        Calculate average metrics per mode from individual retrieval results.

        Args:
            retrieval_results: Dict mapping mode -> list of query results
            modes: List of chunking modes
            queries: List of queries
            expected_chunks_map: Optional map of query -> expected chunk IDs

        Returns:
            Dictionary with average metrics per mode
        """
        retrieval_service = RetrievalTestService()

        avg_metrics = {}
        k_values = [1, 3, 5, 10]

        for mode in modes:
            mode_results = retrieval_results.get(mode, [])
            if not mode_results:
                continue

            all_metrics = []
            retrieved_lists = []
            relevant_lists = []

            for query_result in mode_results:
                query = query_result.get("query", "")
                result = query_result.get("result", {})
                retrieved_ids = [r["chunk_id"] for r in result.get("results", [])]
                expected_ids = expected_chunks_map.get(query, []) if expected_chunks_map else []

                if expected_ids:
                    metrics = retrieval_service.calculate_quality_metrics(
                        retrieved_ids, expected_ids
                    )
                    all_metrics.append(metrics)
                    retrieved_lists.append(retrieved_ids)
                    relevant_lists.append(expected_ids)

            if all_metrics:
                avg_metrics[mode] = {
                    "precision": sum(m.get("precision", 0) for m in all_metrics) / len(all_metrics),
                    "recall": sum(m.get("recall", 0) for m in all_metrics) / len(all_metrics),
                    "mrr": sum(m.get("mrr", 0) for m in all_metrics) / len(all_metrics),
                    "ndcg": sum(m.get("ndcg", 0) for m in all_metrics) / len(all_metrics),
                    "f1": sum(m.get("f1", 0) for m in all_metrics) / len(all_metrics),
                    "precision_at_k": {
                        k: sum(m.get("precision_at_k", {}).get(k, 0) for m in all_metrics) / len(all_metrics)
                        for k in k_values
                    },
                    "recall_at_k": {
                        k: sum(m.get("recall_at_k", {}).get(k, 0) for m in all_metrics) / len(all_metrics)
                        for k in k_values
                    }
                }

                # Calculate Hit Rate@K and MAP
                if retrieved_lists and relevant_lists:
                    hit_rates = {k: [] for k in k_values}
                    for retrieved_ids, relevant_ids in zip(retrieved_lists, relevant_lists):
                        for k in k_values:
                            hit_rate = retrieval_service.calculate_hit_rate_at_k(
                                retrieved_ids, relevant_ids, k
                            )
                            hit_rates[k].append(hit_rate)

                    avg_metrics[mode]["hit_rate_at_k"] = {
                        k: sum(hit_rates[k]) / len(hit_rates[k])
                        if hit_rates[k] else 0.0
                        for k in k_values
                    }

                    map_score = retrieval_service.calculate_map(retrieved_lists, relevant_lists)
                    avg_metrics[mode]["map"] = map_score

        return avg_metrics

    def calculate_comprehensive_metrics(
        self,
        all_chunks: Dict[str, List],
        retrieval_results: Dict[str, List[Dict[str, Any]]],
        documents: List[Dict[str, Any]],
        queries: List[str],
        modes: List[str],
        expected_chunks_map: Optional[Dict[str, List[int]]],
        _chunk_stats: Dict[str, Any],
        avg_metrics: Optional[Dict[str, Any]] = None,
        answers_map: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive metrics organized by dimension.

        Args:
            all_chunks: Dict mapping mode -> list of all chunks
            retrieval_results: Dict mapping mode -> list of retrieval results per query
            documents: List of documents
            queries: List of queries
            modes: List of chunking modes
            expected_chunks_map: Optional map of query -> expected chunk IDs
            chunk_stats: Chunk statistics
            avg_metrics: Pre-calculated average metrics
            answers_map: Optional map of query -> answer

        Returns:
            Dictionary organized by evaluation dimension
        """
        evaluation_results = {
            "standard_ir": {},
            "chunk_quality": {},
            "answer_quality": {},
            "diversity_efficiency": {},
            "cross_method": {},
            "query_count": len(queries),
            "note": "All metrics are averaged across queries unless otherwise specified"
        }

        # Create document text map for coverage calculation
        doc_text_map = {doc.get("id", ""): doc.get("text", "") for doc in documents}

        # Calculate metrics per mode
        for mode in modes:
            mode_chunks = all_chunks.get(mode, [])
            mode_retrieval_results = retrieval_results.get(mode, [])

            # Standard IR Metrics (use pre-calculated average metrics)
            if avg_metrics and mode in avg_metrics:
                evaluation_results["standard_ir"][mode] = avg_metrics[mode].copy()
            else:
                evaluation_results["standard_ir"][mode] = {}

            # Chunk Quality Metrics
            evaluation_results["chunk_quality"][mode] = {}
            if mode_chunks:
                # Coverage score (average across documents)
                coverage_scores = []
                for doc in documents:
                    doc_id = doc.get("id", "")
                    doc_text = doc_text_map.get(doc_id, "")
                    # Find chunks for this document
                    doc_chunks = [
                        c for c in mode_chunks
                        if c.metadata.get("document_id") == doc_id
                    ]
                    if doc_text and doc_chunks:
                        coverage = self.chunk_comparator.calculate_coverage_score(
                            doc_chunks, doc_text
                        )
                        coverage_scores.append(coverage)

                evaluation_results["chunk_quality"][mode]["coverage_score"] = (
                    sum(coverage_scores) / len(coverage_scores)
                    if coverage_scores else 0.0
                )

                # Semantic coherence
                try:
                    coherence = self.chunk_comparator.calculate_chunk_coherence(mode_chunks)
                    evaluation_results["chunk_quality"][mode]["semantic_coherence"] = coherence
                except Exception as e:
                    logger.warning(
                        "[RAGChunkTest] Failed to calculate coherence for %s: %s",
                        mode,
                        e
                    )
                    evaluation_results["chunk_quality"][mode]["semantic_coherence"] = 0.0

            # Answer Quality Metrics (if answers available)
            evaluation_results["answer_quality"][mode] = {}
            if answers_map:
                answer_coverage_scores = []
                answer_completeness_scores = []
                context_recall_scores = []

                for query in queries:
                    answer = answers_map.get(query, "")
                    if not answer:
                        continue

                    query_results = [
                        r for r in mode_retrieval_results
                        if r.get("query") == query
                    ]
                    if query_results:
                        result = query_results[0]["result"]
                        retrieved_chunk_ids = [r["chunk_id"] for r in result.get("results", [])]
                        retrieved_chunks = [
                            c for c in mode_chunks
                            if c.chunk_index in retrieved_chunk_ids
                        ]

                        if retrieved_chunks:
                            # Find document text for context recall
                            doc_id = retrieved_chunks[0].metadata.get("document_id", "")
                            doc_text = doc_text_map.get(doc_id, "")

                            # Calculate answer coverage
                            coverage = self.answer_quality_evaluator.calculate_answer_coverage(
                                retrieved_chunks, answer
                            )
                            answer_coverage_scores.append(coverage)

                            # Calculate answer completeness
                            completeness = self.answer_quality_evaluator.calculate_answer_completeness(
                                retrieved_chunks, answer
                            )
                            answer_completeness_scores.append(completeness)

                            # Calculate context recall
                            if doc_text:
                                context_recall = self.answer_quality_evaluator.calculate_context_recall(
                                    retrieved_chunks, answer, doc_text
                                )
                                context_recall_scores.append(context_recall)

                evaluation_results["answer_quality"][mode]["answer_coverage"] = (
                    sum(answer_coverage_scores) / len(answer_coverage_scores)
                    if answer_coverage_scores else 0.0
                )
                evaluation_results["answer_quality"][mode]["answer_completeness"] = (
                    sum(answer_completeness_scores) / len(answer_completeness_scores)
                    if answer_completeness_scores else 0.0
                )
                evaluation_results["answer_quality"][mode]["context_recall"] = (
                    sum(context_recall_scores) / len(context_recall_scores)
                    if context_recall_scores else 0.0
                )

            # Diversity & Efficiency Metrics
            evaluation_results["diversity_efficiency"][mode] = {}
            if mode_chunks:
                # Storage efficiency
                storage_eff = self.diversity_evaluator.calculate_storage_efficiency(mode_chunks)
                evaluation_results["diversity_efficiency"][mode]["storage_efficiency"] = storage_eff

                # Semantic diversity (for retrieved chunks)
                if mode_retrieval_results:
                    diversity_scores = []
                    for query_result in mode_retrieval_results:
                        result = query_result.get("result", {})
                        retrieved_chunk_ids = [r["chunk_id"] for r in result.get("results", [])]
                        retrieved_chunks = [
                            c for c in mode_chunks
                            if c.chunk_index in retrieved_chunk_ids
                        ]
                        if len(retrieved_chunks) > 1:
                            diversity = self.diversity_evaluator.calculate_intra_list_diversity(
                                retrieved_chunks
                            )
                            diversity_scores.append(diversity)

                    evaluation_results["diversity_efficiency"][mode]["semantic_diversity"] = (
                        sum(diversity_scores) / len(diversity_scores)
                        if diversity_scores else 0.0
                    )

                    # Diversity at K
                    k_values = [1, 3, 5]
                    diversity_at_k = {}
                    for k in k_values:
                        k_diversity_scores = []
                        for query_result in mode_retrieval_results:
                            result = query_result.get("result", {})
                            retrieved_chunk_ids = [r["chunk_id"] for r in result.get("results", [])[:k]]
                            retrieved_chunks = [
                                c for c in mode_chunks
                                if c.chunk_index in retrieved_chunk_ids
                            ]
                            if len(retrieved_chunks) > 1:
                                diversity = self.diversity_evaluator.calculate_diversity_at_k(
                                    retrieved_chunks, k
                                )
                                k_diversity_scores.append(diversity)
                        diversity_at_k[k] = (
                            sum(k_diversity_scores) / len(k_diversity_scores)
                            if k_diversity_scores else 0.0
                        )
                    evaluation_results["diversity_efficiency"][mode]["diversity_at_k"] = diversity_at_k

                    # Latency metrics
                    timing_data = [
                        r.get("result", {}).get("timing", {})
                        for r in mode_retrieval_results
                    ]
                    latency_metrics = self.diversity_evaluator.calculate_latency_metrics(timing_data)
                    evaluation_results["diversity_efficiency"][mode].update(latency_metrics)

        # Cross-Method Comparison (only if 2 modes)
        if len(modes) == 2:
            mode_a, mode_b = modes[0], modes[1]
            chunks_a = all_chunks.get(mode_a, [])
            chunks_b = all_chunks.get(mode_b, [])

            if chunks_a and chunks_b:
                # Chunk alignment
                alignment = self.cross_method_comparator.calculate_chunk_alignment(
                    chunks_a, chunks_b
                )
                evaluation_results["cross_method"]["chunk_alignment"] = alignment

                # Overlap analysis
                overlap = self.cross_method_comparator.analyze_method_overlap(
                    chunks_a, chunks_b
                )
                evaluation_results["cross_method"]["overlap_analysis"] = overlap

                # Complementarity (if we have retrieval results and expected chunks)
                if expected_chunks_map and retrieval_results.get(mode_a) and retrieval_results.get(mode_b):
                    complementarity_scores = []
                    for query in queries:
                        result_a = [
                            r for r in retrieval_results[mode_a]
                            if r.get("query") == query
                        ]
                        result_b = [
                            r for r in retrieval_results[mode_b]
                            if r.get("query") == query
                        ]
                        if result_a and result_b:
                            retrieved_a = [r["chunk_id"] for r in result_a[0]["result"].get("results", [])]
                            retrieved_b = [r["chunk_id"] for r in result_b[0]["result"].get("results", [])]
                            relevant = expected_chunks_map.get(query, [])
                            if relevant:
                                comp = self.cross_method_comparator.calculate_complementarity(
                                    retrieved_a, retrieved_b, relevant
                                )
                                complementarity_scores.append(comp)

                    evaluation_results["cross_method"]["complementarity"] = (
                        sum(complementarity_scores) / len(complementarity_scores)
                        if complementarity_scores else 0.0
                    )

        return evaluation_results
