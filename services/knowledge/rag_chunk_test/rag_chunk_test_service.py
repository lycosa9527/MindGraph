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
from typing import List, Dict, Any, Optional, Callable, TYPE_CHECKING
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
from services.knowledge.rag_chunk_test.metrics_calculator import MetricsCalculator
from services.knowledge.rag_chunk_test.summary_generator import SummaryGenerator
from services.knowledge.progress_tracking import (
    format_progress_string,
    get_progress_percent,
    validate_progress,
    ensure_completion_progress
)

if TYPE_CHECKING:
    from models.domain.knowledge_space import ChunkTestResult


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
        self.metrics_calculator = MetricsCalculator(
            self.chunk_comparator,
            self.answer_quality_evaluator,
            self.diversity_evaluator,
            self.cross_method_comparator
        )
        self.summary_generator = SummaryGenerator()

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
        modes: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[str, Optional[str], str, int, List[str]], Optional[bool]]] = None
    ) -> Dict[str, Any]:
        """
        Test chunking methods with benchmark dataset.

        Args:
            db: Database session
            user_id: User ID
            dataset_name: Benchmark dataset name
            custom_queries: Optional custom queries (uses dataset queries if not provided)
            modes: List of chunking methods to test (default: 5 methods)
            progress_callback: Optional callback function(status, method, stage, progress, completed_methods)

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
            answers_map=answers_map if answers_map else None,
            progress_callback=progress_callback
        )

    def test_user_documents(
        self,
        db: Session,
        user_id: int,
        document_ids: List[int],
        queries: List[str],
        modes: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[str, Optional[str], str, int, List[str]], Optional[bool]]] = None
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
        progress_callback: Optional[Callable[[str, Optional[str], str, int, List[str]], Optional[bool]]] = None
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
        previous_progress = 0

        def update_progress(status: str, method: Optional[str], stage: str, progress: int) -> bool:
            """Helper to update progress via callback. Returns False if cancelled."""
            nonlocal previous_progress
            
            # Validate progress to ensure it never decreases
            validated_progress, is_valid = validate_progress(
                progress,
                previous_progress,
                f'{stage} ({method})' if method else stage
            )
            previous_progress = validated_progress
            
            # Use standardized progress string format
            progress_string = format_progress_string(stage, method)
            logger.debug(
                "[RAGChunkTest] Updating progress: status=%s, method=%s, stage=%s, "
                "progress=%s%% (validated: %s%%), progress_string=%s, completed_methods=%s",
                status, method, stage, progress, validated_progress, progress_string, completed_methods
            )
            if progress_callback:
                try:
                    # Use validated progress in callback
                    result = progress_callback(status, method, stage, validated_progress, completed_methods.copy())
                    # If callback returns False, processing was cancelled
                    if result is False:
                        logger.info(
                            "[RAGChunkTest] Progress callback returned False, "
                            "indicating cancellation: stage=%s, method=%s",
                            stage, method
                        )
                        return False
                    logger.debug(
                        "[RAGChunkTest] Progress callback completed successfully: "
                        "stage=%s, method=%s, progress=%s%%, progress_string=%s",
                        stage, method, progress, progress_string
                    )
                except Exception as callback_error:
                    logger.error(
                        "[RAGChunkTest] Error in progress callback: %s",
                        callback_error,
                        exc_info=True
                    )
                    # Don't stop execution on callback errors, but log them
            return True

        # Initialize progress
        logger.info("[RAGChunkTest] Initializing test progress tracking")
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
            # Use standardized progress calculation
            progress_value = get_progress_percent(
                'chunking',
                method_index=method_idx,
                total_methods=total_methods
            )
            logger.info(
                "[RAGChunkTest] Starting chunking with method %s (%d/%d): progress=%s%%",
                mode, method_idx + 1, total_methods, progress_value
            )
            if not update_progress("processing", mode, "chunking", progress_value):
                logger.warning("[RAGChunkTest] Test cancelled before starting method %s", mode)
                raise RuntimeError("Test cancelled by user")

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

                # Update progress within method using standardized calculation
                # Interpolate between method start and end progress
                method_start = get_progress_percent('chunking', method_idx, total_methods)
                method_end = get_progress_percent('chunking', method_idx + 1, total_methods)
                doc_progress = method_start + int((method_end - method_start) * (doc_idx + 1) / total_docs)
                if not update_progress("processing", mode, "chunking", doc_progress):
                    raise RuntimeError("Test cancelled by user")

            completed_methods.append(mode)
            method_end_progress = get_progress_percent('chunking', method_idx + 1, total_methods)
            if not update_progress("processing", mode, "chunking", method_end_progress):
                raise RuntimeError("Test cancelled by user")

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
        logger.info("[RAGChunkTest] Starting retrieval testing phase: progress=50%%")
        if not update_progress("processing", None, "retrieval", 50):
            logger.warning("[RAGChunkTest] Test cancelled before retrieval phase")
            raise RuntimeError("Test cancelled by user")
        retrieval_results = {mode: [] for mode in modes}
        total_queries = len(queries)
        progress_per_query = 30 / (total_queries * total_methods) if total_queries > 0 else 0

        # Track all created collections for cleanup
        created_collections = []

        try:
            for query_idx, query in enumerate(queries):
                for method_idx, mode in enumerate(modes):
                    if all_chunks[mode]:
                        collection_name = None
                        try:
                            if not update_progress(
                                "processing",
                                mode,
                                "retrieval",
                                int(50 + progress_per_query * (query_idx * total_methods + method_idx))
                            ):
                                raise RuntimeError("Test cancelled by user")
                            collection_name = f"test_{mode}_{uuid.uuid4().hex[:8]}"
                            created_collections.append((test_user_id, collection_name))

                            # Create nested progress callback for retrieval stages
                            # Capture loop variables as default arguments to avoid
                            # cell-var-from-loop
                            def retrieval_progress_callback(
                                status: str,
                                method: Optional[str],
                                stage: str,
                                progress: int,
                                captured_query_idx: int = query_idx,
                                captured_method_idx: int = method_idx,
                                captured_mode: str = mode
                            ) -> None:
                                """Nested callback to report retrieval sub-stages."""
                                # Map internal progress (0-100) to overall progress
                                # range. Retrieval phase is 50-80%, so each
                                # query+method gets 30% / (total_queries *
                                # total_methods)
                                base_progress = (
                                    50 + progress_per_query *
                                    (captured_query_idx * total_methods +
                                     captured_method_idx)
                                )
                                stage_progress = int(
                                    base_progress +
                                    (progress_per_query * progress / 100)
                                )
                                # Use method parameter or fallback to mode from
                                # closure
                                callback_method = (
                                    method if method is not None else captured_mode
                                )
                                update_progress(
                                    status, callback_method, stage, stage_progress
                                )

                            result = self.retrieval_evaluator.test_retrieval(
                                all_chunks[mode],
                                query,
                                _method="hybrid",
                                top_k=5,
                                test_user_id=test_user_id,
                                collection_name=collection_name,
                                progress_callback=retrieval_progress_callback,
                                method_name=mode,
                                db=_db,
                                user_id=_user_id
                            )
                            retrieval_results[mode].append({
                                "query": query,
                                "result": result
                            })
                            # Cleanup immediately after successful test
                            self.retrieval_evaluator.cleanup_test_collection(test_user_id, collection_name)
                            created_collections.remove((test_user_id, collection_name))
                        except Exception as e:
                            logger.error(
                                "[RAGChunkTest] %s retrieval failed for query '%s': %s",
                                mode,
                                query[:50],
                                e
                            )
                            # Collection will be cleaned up in finally block
        finally:
            # Ensure all collections are cleaned up even if test fails or is cancelled
            for user_id, collection_name in created_collections:
                try:
                    self.retrieval_evaluator.cleanup_test_collection(user_id, collection_name)
                    logger.debug(
                        "[RAGChunkTest] Cleaned up test collection: %s (user_id=%s)",
                        collection_name,
                        user_id
                    )
                except Exception as cleanup_error:
                    logger.warning(
                        "[RAGChunkTest] Failed to cleanup collection %s (user_id=%s): %s",
                        collection_name,
                        user_id,
                        cleanup_error
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

            avg_metrics_result = self.metrics_calculator.calculate_average_metrics(
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
            avg_metrics_result = self.metrics_calculator.calculate_average_metrics_per_mode(
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
        logger.info("[RAGChunkTest] Starting evaluation phase: progress=80%%")
        if not update_progress("processing", None, "evaluation", 80):
            logger.warning("[RAGChunkTest] Test cancelled before evaluation phase")
            raise RuntimeError("Test cancelled by user")
        avg_metrics = results.get("retrieval_comparison", {}).get("average", {})
        results["evaluation_results"] = self.metrics_calculator.calculate_comprehensive_metrics(
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
        if not update_progress("processing", None, "evaluation", 95):
            raise RuntimeError("Test cancelled by user")

        # Step 4: Generate summary (95-100% progress)
        logger.info("[RAGChunkTest] Generating summary: progress=95%%")
        results["summary"] = self.summary_generator.generate_summary(
            chunk_stats,
            results.get("retrieval_comparison", {})
        )

        # Mark as completed - ensure progress reaches 100%
        logger.info("[RAGChunkTest] Marking test as completed: progress=100%%")
        final_progress = ensure_completion_progress(100, 100)
        if not update_progress("completed", None, "completed", final_progress):
            logger.warning("[RAGChunkTest] Test cancelled before completion")
            raise RuntimeError("Test cancelled by user")

        logger.info(
            "[RAGChunkTest] Test completed: chunks=%s",
            {mode: len(all_chunks[mode]) for mode in modes}
        )

        return results

    def get_chunks_for_test(
        self,
        db: Session,
        user_id: int,
        test_result: "ChunkTestResult",
        method: str
    ) -> List[Dict[str, Any]]:
        """
        Regenerate chunks for a test result using a specific method.

        Args:
            db: Database session
            user_id: User ID (for verification)
            test_result: ChunkTestResult instance
            method: Chunking method name ('spacy', 'semchunk', 'chonkie', 'langchain', 'mindchunk')

        Returns:
            List of chunks with text, metadata, and position info
        """
        if test_result.user_id != user_id:
            raise ValueError("Test does not belong to user")

        # Load documents based on test type
        if test_result.dataset_name and test_result.dataset_name != "user_documents":
            # Benchmark dataset
            loader = get_benchmark_loader(test_result.dataset_name)
            documents = loader.load_documents()
        elif test_result.document_ids:
            # User documents
            loader = UserDocumentLoader(db, user_id, test_result.document_ids)
            documents = loader.load_documents()
        else:
            raise ValueError("Test has no associated documents or dataset")

        if not documents:
            raise ValueError("No documents found")

        # Chunk all documents with the specified method
        all_chunks = []
        for doc in documents:
            doc_text = doc.get("text", "")
            doc_metadata = doc.get("metadata", {})
            doc_metadata["document_id"] = doc.get("id", "")

            try:
                chunks, _ = self.chunk_comparator.chunk_with_method(
                    doc_text,
                    method,
                    doc_metadata
                )
                all_chunks.extend(chunks)
            except Exception as e:
                logger.warning(
                    "[RAGChunkTest] Failed to chunk document %s with method %s: %s",
                    doc.get("id"),
                    method,
                    e
                )

        # Convert chunks to dict format
        result = []
        for idx, chunk in enumerate(all_chunks):
            chunk_dict = {
                "chunk_index": idx,
                "text": chunk.text,
                "metadata": chunk.metadata or {},
            }
            # Add position info if available
            if hasattr(chunk, 'start_char') and hasattr(chunk, 'end_char'):
                chunk_dict["start_char"] = chunk.start_char
                chunk_dict["end_char"] = chunk.end_char

            result.append(chunk_dict)

        return result


def get_rag_chunk_test_service() -> RAGChunkTestService:
    """Get global RAG chunk test service instance."""
    if not hasattr(get_rag_chunk_test_service, 'instance'):
        get_rag_chunk_test_service.instance = RAGChunkTestService()
    return get_rag_chunk_test_service.instance
