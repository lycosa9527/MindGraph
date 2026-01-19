"""
RAG Chunk Test Service
=======================

Main service for testing and comparing chunking methods.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import List, Dict, Any, Optional, Callable
import logging
import uuid

from sqlalchemy.orm import Session

from services.knowledge.rag_chunk_test.benchmark_loaders import (
    get_benchmark_loader,
    UserDocumentLoader
)
from services.knowledge.rag_chunk_test.chunk_comparator import ChunkComparator
from services.knowledge.rag_chunk_test.retrieval_evaluator import RetrievalEvaluator
from services.knowledge.rag_chunk_test.answer_quality_evaluator import AnswerQualityEvaluator
from services.knowledge.rag_chunk_test.diversity_evaluator import DiversityEvaluator
from services.knowledge.rag_chunk_test.cross_method_comparator import CrossMethodComparator
from services.knowledge.retrieval_test_service import RetrievalTestService


logger = logging.getLogger(__name__)


class RAGChunkTestService:
    """Service for testing and comparing chunking methods."""

    def __init__(self):
        """Initialize RAG chunk test service."""
        self.chunk_comparator = ChunkComparator()
        self.retrieval_evaluator = RetrievalEvaluator()
        self.answer_quality_evaluator = AnswerQualityEvaluator()
        self.diversity_evaluator = DiversityEvaluator()
        self.cross_method_comparator = CrossMethodComparator()

    def run_chunk_test(
        self,
        db: Session,
        user_id: int,
        dataset_name: Optional[str] = None,
        document_ids: Optional[List[int]] = None,
        queries: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run chunk test with benchmark dataset or user documents.

        Args:
            db: Database session
            user_id: User ID
            dataset_name: Benchmark dataset name ('FinanceBench', 'KG-RAG', etc.)
            document_ids: List of user document IDs (if testing user documents)
            queries: List of test queries (required for user documents)

        Returns:
            Test results with comparison metrics
        """
        if dataset_name:
            return self.test_benchmark_dataset(db, user_id, dataset_name, queries)
        elif document_ids:
            if not queries:
                raise ValueError("Queries are required when testing user documents")
            return self.test_user_documents(db, user_id, document_ids, queries)
        else:
            raise ValueError("Either dataset_name or document_ids must be provided")

    def test_benchmark_dataset(
        self,
        db: Session,
        user_id: int,
        dataset_name: str,
        custom_queries: Optional[List[str]] = None,
        modes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Test chunking methods with benchmark dataset.

        Args:
            db: Database session
            user_id: User ID
            dataset_name: Benchmark dataset name
            custom_queries: Optional custom queries (uses dataset queries if not provided)

        Returns:
            Test results
        """
        logger.info(
            "[RAGChunkTest] Starting benchmark test: dataset=%s, user=%s",
            dataset_name,
            user_id
        )

        # Load dataset
        loader = get_benchmark_loader(dataset_name)
        documents = loader.load_documents()
        dataset_queries = loader.load_queries()

        # Use custom queries if provided, otherwise use dataset queries
        if custom_queries:
            queries = custom_queries
            answers_map = {}
        else:
            queries = [q.get("query", "") for q in dataset_queries if q.get("query")]
            answers_map = {
                q.get("query", ""): q.get("answer", "")
                for q in dataset_queries
                if q.get("query") and q.get("answer")
            }

        if not queries:
            raise ValueError(f"No queries found in dataset {dataset_name}")

        # Extract expected chunks and relevance scores
        expected_chunks_map = {
            q.get("query", ""): q.get("expected_chunk_ids", [])
            for q in dataset_queries
            if q.get("query")
        }
        relevance_scores_map = {
            q.get("query", ""): q.get("relevance_scores", {})
            for q in dataset_queries
            if q.get("query") and q.get("relevance_scores")
        }

        # Run comparison
        return self.compare_chunking_methods(
            _db=db,
            _user_id=user_id,
            documents=documents,
            queries=queries,
            expected_chunks_map=expected_chunks_map if expected_chunks_map else None,
            relevance_scores_map=relevance_scores_map if relevance_scores_map else None,
            modes=modes,
            answers_map=answers_map if answers_map else None
        )

    def test_user_documents(
        self,
        db: Session,
        user_id: int,
        document_ids: List[int],
        queries: List[str],
        modes: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[str, Optional[str], str, int, List[str]], None]] = None
    ) -> Dict[str, Any]:
        """
        Test chunking methods with user's uploaded documents.

        Args:
            db: Database session
            user_id: User ID
            document_ids: List of document IDs to test
            queries: List of test queries
            modes: List of chunking methods to test (default: 5 methods)
            progress_callback: Optional callback function(status, method, stage, progress, completed_methods)

        Returns:
            Test results
        """
        # Ensure 5 methods are used
        if modes is None:
            modes = ["spacy", "semchunk", "chonkie", "langchain", "mindchunk"]

        logger.info(
            "[RAGChunkTest] Starting user documents test: "
            "documents=%s, queries=%s, user=%s, modes=%s",
            len(document_ids),
            len(queries),
            user_id,
            modes
        )

        # Load user documents
        loader = UserDocumentLoader(db, user_id, document_ids)
        documents = loader.load_documents()

        if not documents:
            raise ValueError("No documents found or access denied")

        # Run comparison with progress tracking
        return self.compare_chunking_methods(
            _db=db,
            _user_id=user_id,
            documents=documents,
            queries=queries,
            modes=modes,
            progress_callback=progress_callback
        )

    def compare_chunking_methods(
        self,
        _db: Session,
        _user_id: int,
        documents: List[Dict[str, Any]],
        queries: List[str],
        expected_chunks_map: Optional[Dict[str, List[int]]] = None,
        relevance_scores_map: Optional[Dict[str, Dict[int, float]]] = None,
        modes: Optional[List[str]] = None,
        answers_map: Optional[Dict[str, str]] = None,
        progress_callback: Optional[Callable[[str, Optional[str], str, int, List[str]], None]] = None
    ) -> Dict[str, Any]:
        """
        Compare chunking methods (semchunk vs mindchunk vs qa).

        Args:
            _db: Database session (unused, kept for interface compatibility)
            _user_id: User ID (unused, kept for interface compatibility)
            documents: List of documents with format {id, text, metadata}
            queries: List of test queries
            expected_chunks_map: Optional map of query -> expected chunk IDs
            relevance_scores_map: Optional map of query -> relevance scores
            modes: List of modes to compare (default: 5 methods)
            answers_map: Optional map of query -> answer
            progress_callback: Optional callback function(status, method, stage, progress, completed_methods)

        Returns:
            Comprehensive comparison results
        """
        # Default modes if not specified
        if modes is None:
            modes = ["spacy", "semchunk", "chonkie", "langchain", "mindchunk"]

        logger.info(
            "[RAGChunkTest] Comparing chunking methods: "
            "documents=%s, queries=%s, modes=%s",
            len(documents),
            len(queries),
            modes
        )

        # Use test user ID to avoid interfering with real user data
        test_user_id = 0  # Special test user ID

        completed_methods = []

        def update_progress(status: str, method: Optional[str], stage: str, progress: int):
            """Helper to update progress via callback."""
            if progress_callback:
                progress_callback(status, method, stage, progress, completed_methods.copy())

        # Initialize progress
        update_progress("processing", None, "chunking", 0)

        results = {
            "dataset_info": {
                "document_count": len(documents),
                "query_count": len(queries),
                "modes": modes
            },
            "chunking_comparison": {},
            "retrieval_comparison": {},
            "summary": {}
        }

        # Step 1: Chunk all documents with specified methods (0-50% progress)
        all_chunks = {mode: [] for mode in modes}
        chunking_times = {mode: [] for mode in modes}
        total_docs = len(documents)
        total_methods = len(modes)

        for method_idx, mode in enumerate(modes):
            update_progress("processing", mode, "chunking", int(10 * method_idx))
            logger.info("[RAGChunkTest] Chunking with method: %s", mode)

            for doc_idx, doc in enumerate(documents):
                doc_text = doc.get("text", "")
                doc_metadata = doc.get("metadata", {})
                doc_metadata["document_id"] = doc.get("id", "")

                try:
                    chunks, time_ms = self.chunk_comparator.chunk_with_method(
                        doc_text,
                        mode,
                        doc_metadata
                    )
                    all_chunks[mode].extend(chunks)
                    chunking_times[mode].append(time_ms)
                except Exception as e:
                    logger.warning(
                        "[RAGChunkTest] %s failed for document %s: %s",
                        mode,
                        doc.get("id"),
                        e
                    )
                    # Continue with other modes
                    all_chunks[mode].extend([])

                # Update progress within method (each doc adds ~2% per method)
                progress = int(10 * method_idx + (10 * doc_idx / total_docs))
                update_progress("processing", mode, "chunking", progress)

            completed_methods.append(mode)
            update_progress("processing", mode, "chunking", int(10 * (method_idx + 1)))

        # Step 2: Compare chunk statistics
        # Build stats for each mode
        chunk_stats = {}
        for mode in modes:
            chunk_stats[mode] = self.chunk_comparator.calculate_chunk_stats(all_chunks[mode])
            chunk_stats[mode]["chunking_times"] = {
                "total_ms": sum(chunking_times[mode]),
                "avg_ms": (
                    sum(chunking_times[mode]) / len(chunking_times[mode])
                    if chunking_times[mode] else 0
                )
            }

        # Add comparison if we have exactly 2 modes
        if len(modes) == 2:
            chunk_stats["comparison"] = self.chunk_comparator.compare_two_modes(
                all_chunks[modes[0]],
                all_chunks[modes[1]],
                modes[0],
                modes[1]
            )

        results["chunking_comparison"] = chunk_stats

        # Step 2: Test retrieval for each query (50-80% progress)
        update_progress("processing", None, "retrieval", 50)
        retrieval_results = {mode: [] for mode in modes}
        total_queries = len(queries)
        progress_per_query = 30 / (total_queries * total_methods) if total_queries > 0 else 0

        for query_idx, query in enumerate(queries):
            for method_idx, mode in enumerate(modes):
                if all_chunks[mode]:
                    try:
                        update_progress(
                            "processing",
                            mode,
                            "retrieval",
                            int(50 + progress_per_query * (query_idx * total_methods + method_idx))
                        )
                        collection_name = f"test_{mode}_{uuid.uuid4().hex[:8]}"
                        result = self.retrieval_evaluator.test_retrieval(
                            all_chunks[mode],
                            query,
                            _method="hybrid",
                            top_k=5,
                            test_user_id=test_user_id,
                            collection_name=collection_name
                        )
                        retrieval_results[mode].append({
                            "query": query,
                            "result": result
                        })
                        # Cleanup
                        self.retrieval_evaluator.cleanup_test_collection(test_user_id)
                    except Exception as e:
                        logger.error(
                            "[RAGChunkTest] %s retrieval failed for query '%s': %s",
                            mode,
                            query[:50],
                            e
                        )

        # Step 4: Compare retrieval results
        # If we have exactly 2 modes, compare them
        if len(modes) == 2 and retrieval_results[modes[0]] and retrieval_results[modes[1]]:
            comparison_results = []
            for idx, query in enumerate(queries):
                if (idx < len(retrieval_results[modes[0]]) and
                    idx < len(retrieval_results[modes[1]])):
                    result_a = retrieval_results[modes[0]][idx]["result"]
                    result_b = retrieval_results[modes[1]][idx]["result"]

                    expected_chunks = expected_chunks_map.get(query, []) if expected_chunks_map else []
                    relevance_scores = relevance_scores_map.get(query, {}) if relevance_scores_map else None

                    comparison = self.retrieval_evaluator.compare_retrieval_results(
                        result_a,
                        result_b,
                        expected_chunks,
                        relevance_scores,
                        mode_a=modes[0],
                        mode_b=modes[1]
                    )
                    comparison["query"] = query
                    comparison_results.append(comparison)

            avg_metrics_result = self._calculate_average_metrics(
                comparison_results,
                modes,
                retrieval_results,
                queries,
                expected_chunks_map
            )
            results["retrieval_comparison"] = {
                "per_query": comparison_results,
                "average": avg_metrics_result,
                "query_count": len(queries),
                "note": "Metrics are averaged across all queries"
            }
        else:
            avg_metrics_result = self._calculate_average_metrics_per_mode(
                retrieval_results,
                modes,
                queries,
                expected_chunks_map
            )
            # Store individual results for each mode
            results["retrieval_comparison"] = {
                "per_mode": {
                    mode: [
                        {"query": r["query"], "result": r["result"]}
                        for r in retrieval_results[mode]
                    ]
                    for mode in modes
                },
                "average": avg_metrics_result,
                "query_count": len(queries),
                "note": "Metrics are averaged across all queries"
            }

        # Step 3: Calculate comprehensive metrics by dimension (80-95% progress)
        update_progress("processing", None, "evaluation", 80)
        avg_metrics = results.get("retrieval_comparison", {}).get("average", {})
        results["evaluation_results"] = self._calculate_comprehensive_metrics(
            all_chunks,
            retrieval_results,
            documents,
            queries,
            modes,
            expected_chunks_map,
            chunk_stats,
            avg_metrics,
            answers_map
        )
        update_progress("processing", None, "evaluation", 95)

        # Step 4: Generate summary (95-100% progress)
        results["summary"] = self._generate_summary(
            chunk_stats,
            results.get("retrieval_comparison", {})
        )

        # Mark as completed
        update_progress("completed", None, "completed", 100)

        logger.info(
            "[RAGChunkTest] Test completed: chunks=%s",
            {mode: len(all_chunks[mode]) for mode in modes}
        )

        return results

    def _calculate_average_metrics(
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

    def _calculate_average_metrics_per_mode(
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

    def _generate_summary(
        self,
        chunk_stats: Dict[str, Any],
        retrieval_comparison: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate summary of comparison results."""
        summary = {
            "chunking_winner": "tie",
            "retrieval_winner": "tie",
            "recommendations": []
        }

        # Get modes from chunk_stats
        modes = [k for k in chunk_stats.keys() if k != "comparison"]
        if len(modes) < 2:
            return summary

        # Determine chunking winner
        mode_a_count = chunk_stats.get(modes[0], {}).get("count", 0)
        mode_b_count = chunk_stats.get(modes[1], {}).get("count", 0)
        if mode_b_count > mode_a_count:
            summary["chunking_winner"] = modes[1]
            summary["recommendations"].append(
                f"{modes[1]} produces more chunks, potentially better granularity"
            )
        elif mode_a_count > mode_b_count:
            summary["chunking_winner"] = modes[0]
            summary["recommendations"].append(
                f"{modes[0]} produces fewer chunks, potentially more efficient"
            )

        # Determine retrieval winner
        if "average" in retrieval_comparison:
            avg = retrieval_comparison["average"]
            if "comparison" in avg and "winner" in avg.get("comparison", {}):
                summary["retrieval_winner"] = avg["comparison"]["winner"]
            elif modes[0] in avg and modes[1] in avg:
                # Compare average metrics
                score_a = (
                    avg[modes[0]].get("precision", 0) * 0.3 +
                    avg[modes[0]].get("recall", 0) * 0.3 +
                    avg[modes[0]].get("mrr", 0) * 0.2 +
                    avg[modes[0]].get("ndcg", 0) * 0.2
                )
                score_b = (
                    avg[modes[1]].get("precision", 0) * 0.3 +
                    avg[modes[1]].get("recall", 0) * 0.3 +
                    avg[modes[1]].get("mrr", 0) * 0.2 +
                    avg[modes[1]].get("ndcg", 0) * 0.2
                )
                if score_b > score_a:
                    summary["retrieval_winner"] = modes[1]
                elif score_a > score_b:
                    summary["retrieval_winner"] = modes[0]

        # Add recommendations
        if summary["retrieval_winner"] != "tie":
            summary["recommendations"].append(
                f"{summary['retrieval_winner']} shows better retrieval performance"
            )

        return summary

    def _calculate_comprehensive_metrics(
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


def get_rag_chunk_test_service() -> RAGChunkTestService:
    """Get global RAG chunk test service instance."""
    if not hasattr(get_rag_chunk_test_service, 'instance'):
        get_rag_chunk_test_service.instance = RAGChunkTestService()
    return get_rag_chunk_test_service.instance
