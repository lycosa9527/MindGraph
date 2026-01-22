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
from typing import List, Dict, Any, Optional, Callable
import logging
import time
import uuid

from sqlalchemy.orm import Session

from clients.dashscope_embedding import get_embedding_client
from services.infrastructure.rate_limiting.kb_rate_limiter import get_kb_rate_limiter
from services.knowledge.chunking_service import Chunk
from services.knowledge.retrieval_test_service import RetrievalTestService
from services.knowledge.document_processing import generate_embeddings_with_cache
from services.llm.qdrant_service import get_qdrant_service


logger = logging.getLogger(__name__)


class RetrievalEvaluator:
    """Evaluate retrieval performance for chunked documents."""

    def __init__(self):
        """Initialize retrieval evaluator."""
        self.qdrant = get_qdrant_service()
        self.embedding_client = get_embedding_client()
        self.rate_limiter = get_kb_rate_limiter()
        self.retrieval_test_service = RetrievalTestService()

    def test_retrieval(
        self,
        chunks: List[Chunk],
        query: str,
        _method: str = "hybrid",
        top_k: int = 5,
        test_user_id: int = 0,
        collection_name: Optional[str] = None,
        progress_callback: Optional[Callable[[str, Optional[str], str, int], None]] = None,
        method_name: Optional[str] = None,
        db: Optional[Session] = None,
        user_id: Optional[int] = None
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
            db: Optional database session for embedding caching
            user_id: Optional user ID for embedding caching (uses test_user_id if not provided)

        Returns:
            Retrieval results with metrics
        """
        if not chunks:
            return {
                "results": [],
                "metrics": {
                    "precision": 0.0,
                    "recall": 0.0,
                    "mrr": 0.0,
                    "ndcg": 0.0,
                    "hit_rate": 0.0
                },
                "timing": {}
            }

        # Generate collection name if not provided
        if not collection_name:
            collection_name = f"test_{uuid.uuid4().hex[:8]}"

        start_time = time.time()
        timing = {}

        try:
            # Step 1: Generate embeddings for chunks
            if progress_callback:
                progress_callback("processing", method_name, "embedding", 0)
            embedding_start = time.time()
            texts = [chunk.text for chunk in chunks]

            # Use cached embedding generation if db and user_id provided, otherwise direct embedding
            if db is not None:
                cache_user_id = user_id if user_id is not None else test_user_id
                embeddings = generate_embeddings_with_cache(
                    self.embedding_client,
                    self.rate_limiter,
                    texts,
                    cache_user_id,
                    db
                )
            else:
                # Fallback to direct embedding for backward compatibility
                embeddings = self.embedding_client.embed_texts(texts)

            timing["embedding_ms"] = (time.time() - embedding_start) * 1000
            if progress_callback:
                progress_callback("processing", method_name, "embedding", 50)

            if len(embeddings) != len(chunks):
                raise ValueError(f"Embedding count ({len(embeddings)}) != chunk count ({len(chunks)})")

            # Step 2: Store in temporary Qdrant collection
            if progress_callback:
                progress_callback("processing", method_name, "indexing", 50)
            store_start = time.time()
            # Generate unique chunk IDs (Qdrant requires positive integers)
            # Use hash of chunk text + index to create unique IDs
            chunk_ids = []
            seen_ids = set()
            for idx, chunk in enumerate(chunks):
                chunk_id = hash(f"{chunk.text}_{idx}") % (2**31 - 1)  # Ensure positive int
                while chunk_id in seen_ids or chunk_id <= 0:
                    chunk_id = (chunk_id + 1) % (2**31 - 1)
                seen_ids.add(chunk_id)
                chunk_ids.append(chunk_id)

            document_ids = [chunk.metadata.get("document_id", 0) for chunk in chunks]

            # Prepare metadata
            qdrant_metadata = []
            for chunk in chunks:
                meta = {
                    "chunk_id": chunk.chunk_index,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                    **(chunk.metadata or {})
                }
                qdrant_metadata.append(meta)

            # Store in Qdrant (using test user_id)
            # Note: Using test_user_id to create isolated test collection
            self.qdrant.add_documents(
                user_id=test_user_id,
                chunk_ids=chunk_ids,
                embeddings=embeddings,
                document_ids=document_ids,
                metadata=qdrant_metadata
            )
            timing["store_ms"] = (time.time() - store_start) * 1000
            if progress_callback:
                progress_callback("processing", method_name, "indexing", 100)

            # Step 3: Perform retrieval
            if progress_callback:
                progress_callback("processing", method_name, "retrieval", 0)
            retrieval_start = time.time()
            query_embedding = self.embedding_client.embed_query(query)

            # Use Qdrant to search
            search_results = self.qdrant.search(
                user_id=test_user_id,
                query_embedding=query_embedding,
                top_k=top_k
            )
            timing["retrieval_ms"] = (time.time() - retrieval_start) * 1000
            if progress_callback:
                progress_callback("processing", method_name, "retrieval", 100)

            # Step 4: Format results
            # Create mapping from chunk_id to chunk index
            chunk_id_to_index = {chunk_ids[i]: i for i in range(len(chunks))}

            results = []
            for result in search_results:
                chunk_id = result.get("id", 0)
                chunk_idx = chunk_id_to_index.get(chunk_id)
                if chunk_idx is not None and chunk_idx < len(chunks):
                    chunk = chunks[chunk_idx]
                    results.append({
                        "chunk_id": chunk_id,
                        "chunk_index": chunk_idx,
                        "text": chunk.text,
                        "score": result.get("score", 0.0),
                        "start_char": chunk.start_char,
                        "end_char": chunk.end_char,
                        "metadata": chunk.metadata or {}
                    })

            timing["total_ms"] = (time.time() - start_time) * 1000

            return {
                "results": results,
                "metrics": {
                    "retrieved_count": len(results),
                    "total_chunks": len(chunks)
                },
                "timing": timing,
                "collection_name": collection_name
            }

        except Exception as e:
            logger.error(
                "[RetrievalEvaluator] Retrieval test failed: %s",
                e,
                exc_info=True
            )
            raise

    def compare_retrieval_results(
        self,
        results_a: Dict[str, Any],
        results_b: Dict[str, Any],
        expected_chunk_ids: Optional[List[int]] = None,
        relevance_scores: Optional[Dict[int, float]] = None,
        mode_a: str = "semchunk",
        mode_b: str = "mindchunk"
    ) -> Dict[str, Any]:
        """
        Compare retrieval results between two chunking methods.

        Args:
            results_a: Retrieval results from first method
            results_b: Retrieval results from second method
            expected_chunk_ids: Expected relevant chunk IDs (for metrics)
            relevance_scores: Relevance scores for chunks (for NDCG)
            mode_a: Name of first method (default: "semchunk")
            mode_b: Name of second method (default: "mindchunk")

        Returns:
            Comparison metrics
        """
        chunk_ids_a = [r["chunk_id"] for r in results_a.get("results", [])]
        chunk_ids_b = [r["chunk_id"] for r in results_b.get("results", [])]

        comparison = {
            mode_a: {
                "retrieved_count": len(chunk_ids_a),
                "timing": results_a.get("timing", {})
            },
            mode_b: {
                "retrieved_count": len(chunk_ids_b),
                "timing": results_b.get("timing", {})
            },
            "comparison": {}
        }

        # Calculate metrics if expected chunks provided
        if expected_chunk_ids:
            metrics_a = self.retrieval_test_service.calculate_quality_metrics(
                retrieved_chunk_ids=chunk_ids_a,
                expected_chunk_ids=expected_chunk_ids,
                relevance_scores=relevance_scores
            )
            metrics_b = self.retrieval_test_service.calculate_quality_metrics(
                retrieved_chunk_ids=chunk_ids_b,
                expected_chunk_ids=expected_chunk_ids,
                relevance_scores=relevance_scores
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
                "winner": self._determine_winner(metrics_a, metrics_b, mode_a, mode_b)
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
        mode_b: str = "mindchunk"
    ) -> str:
        """
        Determine which method performed better.

        Args:
            metrics_a: Metrics for first method
            metrics_b: Metrics for second method
            mode_a: Name of first method (default: "semchunk")
            mode_b: Name of second method (default: "mindchunk")

        Returns:
            mode_a, mode_b, or 'tie'
        """
        # Weighted score: precision (0.3) + recall (0.3) + MRR (0.2) + NDCG (0.2)
        score_a = (
            metrics_a["precision"] * 0.3 +
            metrics_a["recall"] * 0.3 +
            metrics_a["mrr"] * 0.2 +
            metrics_a["ndcg"] * 0.2
        )
        score_b = (
            metrics_b["precision"] * 0.3 +
            metrics_b["recall"] * 0.3 +
            metrics_b["mrr"] * 0.2 +
            metrics_b["ndcg"] * 0.2
        )

        if score_b > score_a:
            return mode_b
        elif score_a > score_b:
            return mode_a
        else:
            return "tie"

    def cleanup_test_collection(self, test_user_id: int = 0, collection_name: Optional[str] = None):
        """
        Clean up temporary test collection.

        Args:
            test_user_id: User ID for test collection
            collection_name: Optional specific collection name to delete.
                           If None, deletes all collections for test_user_id.
        """
        try:
            if collection_name:
                # Delete specific collection by name
                try:
                    self.qdrant.client.delete_collection(collection_name=collection_name)
                    logger.debug(
                        "[RetrievalEvaluator] Cleaned up test collection: %s (user_id=%s)",
                        collection_name,
                        test_user_id
                    )
                except Exception as e:
                    # Collection might not exist, log but don't fail
                    logger.debug(
                        "[RetrievalEvaluator] Collection %s not found or already deleted: %s",
                        collection_name,
                        e
                    )
            else:
                # Delete all collections for test user (fallback)
                self.qdrant.delete_user_collection(test_user_id)
                logger.debug(
                    "[RetrievalEvaluator] Cleaned up all test collections for user %s",
                    test_user_id
                )
        except Exception as e:
            logger.warning(
                "[RetrievalEvaluator] Failed to cleanup test collection (user_id=%s, collection=%s): %s",
                test_user_id,
                collection_name,
                e
            )
