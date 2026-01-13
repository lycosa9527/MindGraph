"""
Retrieval Test Service for Knowledge Space
Author: lycosa9527
Made by: MindSpring Team

Service for testing retrieval functionality (hit testing).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import time
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from models.knowledge_space import DocumentChunk, KnowledgeDocument, KnowledgeSpace, KnowledgeQuery, EvaluationDataset, EvaluationResult
from services.rag_service import get_rag_service
import math

logger = logging.getLogger(__name__)


class RetrievalTestService:
    """
    Service for testing retrieval functionality.
    
    Allows users to test if their knowledge base works correctly.
    """
    
    def __init__(self):
        """Initialize retrieval test service."""
        self.rag_service = get_rag_service()
    
    def test_retrieval(
        self,
        db: Session,
        user_id: int,
        query: str,
        method: str = "hybrid",
        top_k: int = 5,
        score_threshold: float = 0.0
    ) -> Dict[str, Any]:
        """
        Test retrieval for user's knowledge base.
        
        Args:
            db: Database session
            user_id: User ID
            query: Test query
            method: 'semantic', 'keyword', or 'hybrid'
            top_k: Number of results
            score_threshold: Minimum score threshold
            
        Returns:
            Dict with results, timing, and stats
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        # Check if user has completed documents
        if not self.rag_service.has_knowledge_base(db, user_id):
            raise ValueError("No completed documents found. Please upload and process documents first.")
        
        start_time = time.time()
        timing = {}
        
        try:
            # Step 1: Generate query embedding
            embedding_start = time.time()
            try:
                query_embedding = self.rag_service.embedding_client.embed_query(query)
                timing["embedding_ms"] = (time.time() - embedding_start) * 1000
                logger.info(f"[RAG] ✓ Embedding: query='{query[:30]}...', dims={len(query_embedding)}, time={timing['embedding_ms']:.0f}ms")
            except Exception as emb_error:
                timing["embedding_ms"] = (time.time() - embedding_start) * 1000
                logger.error(f"[RAG] ✗ Embedding FAILED: {emb_error}")
                raise
            
            # Step 2: Vector/Keyword search
            search_start = time.time()
            try:
                if method == "semantic":
                    chunk_ids = self.rag_service.vector_search(db, user_id, query, top_k * 2)
                elif method == "keyword":
                    chunk_ids = self.rag_service.keyword_search_func(db, user_id, query, top_k * 2)
                else:  # hybrid
                    chunk_ids = self.rag_service.hybrid_search(db, user_id, query, top_k * 2)
                timing["search_ms"] = (time.time() - search_start) * 1000
                logger.info(f"[RAG] ✓ Search ({method}): found {len(chunk_ids)} chunks, time={timing['search_ms']:.0f}ms")
            except Exception as search_error:
                timing["search_ms"] = (time.time() - search_start) * 1000
                logger.error(f"[RAG] ✗ Search FAILED: {search_error}")
                raise
            
            # Lookup chunks
            chunks = db.query(DocumentChunk).filter(
                DocumentChunk.id.in_(chunk_ids)
            ).all()
            
            logger.debug(f"[RAG] SQLite lookup: {len(chunks)} chunks from {len(chunk_ids)} IDs")
            
            # Get document info
            document_ids = list(set(chunk.document_id for chunk in chunks))
            documents = {doc.id: doc for doc in db.query(KnowledgeDocument).filter(
                KnowledgeDocument.id.in_(document_ids)
            ).all()}
            
            # Prepare results
            results = []
            rerank_start = time.time()
            
            texts = [chunk.text for chunk in chunks]
            
            # Apply reranking based on mode (Dify's approach)
            from services.rag_service import RerankMode
            
            if self.rag_service.reranking_mode == RerankMode.RERANKING_MODEL and len(texts) > 1:
                # Step 3: Rerank
                try:
                    reranked = self.rag_service.rerank_client.rerank(
                        query=query,
                        documents=texts,
                        top_n=top_k,
                        score_threshold=score_threshold
                    )
                    timing["rerank_ms"] = (time.time() - rerank_start) * 1000
                    logger.info(f"[RAG] ✓ Rerank: {len(texts)} docs → {len(reranked)} results, time={timing['rerank_ms']:.0f}ms")
                except Exception as rerank_error:
                    timing["rerank_ms"] = (time.time() - rerank_start) * 1000
                    logger.error(f"[RAG] ✗ Rerank FAILED: {rerank_error}")
                    raise
                
                # Map reranked results back to chunks
                for item in reranked:
                    idx = item["index"]
                    if idx < len(chunks):
                        chunk = chunks[idx]
                        doc = documents.get(chunk.document_id)
                        results.append({
                            "chunk_id": chunk.id,
                            "text": chunk.text,
                            "score": item["score"],
                            "document_id": chunk.document_id,
                            "document_name": doc.file_name if doc else "Unknown",
                            "chunk_index": chunk.chunk_index,
                            "start_char": chunk.start_char,
                            "end_char": chunk.end_char,
                            "metadata": chunk.meta_data or {},
                        })
            else:
                timing["rerank_ms"] = 0
                # Use original order (weighted_score or none mode)
                # Scores already calculated in hybrid_search for weighted_score mode
                for i, chunk in enumerate(chunks[:top_k]):
                    doc = documents.get(chunk.document_id)
                    # Try to get score from chunk metadata if available
                    score = getattr(chunk, 'score', 0.5) if hasattr(chunk, 'score') else 0.5
                    results.append({
                        "chunk_id": chunk.id,
                        "text": chunk.text,
                        "score": score,
                        "document_id": chunk.document_id,
                        "document_name": doc.file_name if doc else "Unknown",
                        "chunk_index": chunk.chunk_index,
                        "start_char": chunk.start_char,
                        "end_char": chunk.end_char,
                        "metadata": chunk.metadata or {},
                    })
            
            timing["total_ms"] = (time.time() - start_time) * 1000
            
            # Log final summary
            logger.info(
                f"[RAG] ✓ Complete: query='{query[:30]}...', results={len(results)}, "
                f"total={timing['total_ms']:.0f}ms (embed={timing.get('embedding_ms', 0):.0f}ms, "
                f"search={timing.get('search_ms', 0):.0f}ms, rerank={timing.get('rerank_ms', 0):.0f}ms)"
            )
            
            # Stats
            stats = {
                "total_chunks_searched": len(chunk_ids),
                "chunks_before_rerank": len(chunks),
                "chunks_after_rerank": len(results),
                "chunks_filtered_by_threshold": len(chunks) - len(results),
            }
            
            # Record query for analytics
            # Only keep the most recent 10 retrieval test queries to save server resources
            try:
                space = db.query(KnowledgeSpace).filter(KnowledgeSpace.user_id == user_id).first()
                if space:
                    query_record = KnowledgeQuery(
                        user_id=user_id,
                        space_id=space.id,
                        query=query,
                        method=method,
                        top_k=top_k,
                        score_threshold=score_threshold,
                        result_count=len(results),
                        embedding_ms=timing.get("embedding_ms"),
                        search_ms=timing.get("search_ms"),
                        rerank_ms=timing.get("rerank_ms"),
                        total_ms=timing.get("total_ms"),
                        source='retrieval_test',
                        source_context={'test': True}
                    )
                    db.add(query_record)
                    db.flush()  # Flush to get the ID
                    
                    # Keep only the most recent 10 retrieval test queries
                    # Delete older ones to save server resources
                    # Get all retrieval test queries except the one we just added, ordered by newest first
                    all_old_queries = db.query(KnowledgeQuery).filter(
                        KnowledgeQuery.space_id == space.id,
                        KnowledgeQuery.source == 'retrieval_test',
                        KnowledgeQuery.id != query_record.id  # Exclude the one we just added
                    ).order_by(KnowledgeQuery.created_at.desc()).all()
                    
                    # Keep the first 9 (most recent), delete the rest
                    if len(all_old_queries) > 9:
                        queries_to_delete = all_old_queries[9:]  # Skip first 9, delete the rest
                        for old_query in queries_to_delete:
                            db.delete(old_query)
                    
                    db.commit()
                    logger.debug(f"[RetrievalTest] Recorded query and cleaned up old queries. Total retrieval test queries: {10}")
            except Exception as e:
                db.rollback()
                logger.warning(f"[RetrievalTest] Failed to record query: {e}")
            
            return {
                "query": query,
                "method": method,
                "results": results,
                "timing": timing,
                "stats": stats,
            }
            
        except Exception as e:
            logger.error(f"[RetrievalTest] Test failed for user {user_id}: {e}")
            raise
    
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
    
    def calculate_ndcg(self, retrieved_chunk_ids: List[int], relevance_scores: Dict[int, float], k: int = None) -> float:
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
    
    def calculate_quality_metrics(
        self,
        retrieved_chunk_ids: List[int],
        expected_chunk_ids: List[int],
        relevance_scores: Optional[Dict[int, float]] = None
    ) -> Dict[str, float]:
        """
        Calculate all quality metrics for retrieval results.
        
        Args:
            retrieved_chunk_ids: List of retrieved chunk IDs (in order)
            expected_chunk_ids: List of expected/relevant chunk IDs
            relevance_scores: Optional dict mapping chunk_id -> relevance score (for NDCG)
            
        Returns:
            Dict with precision, recall, mrr, ndcg
        """
        precision = self.calculate_precision(retrieved_chunk_ids, expected_chunk_ids)
        recall = self.calculate_recall(retrieved_chunk_ids, expected_chunk_ids)
        mrr = self.calculate_mrr(retrieved_chunk_ids, expected_chunk_ids)
        
        # NDCG requires relevance scores
        if relevance_scores:
            ndcg = self.calculate_ndcg(retrieved_chunk_ids, relevance_scores)
        else:
            # Use binary relevance (1 for relevant, 0 for irrelevant)
            binary_scores = {chunk_id: 1.0 for chunk_id in expected_chunk_ids}
            ndcg = self.calculate_ndcg(retrieved_chunk_ids, binary_scores)
        
        return {
            "precision": precision,
            "recall": recall,
            "mrr": mrr,
            "ndcg": ndcg
        }
    
    def run_evaluation(
        self,
        db: Session,
        user_id: int,
        dataset_id: int,
        method: str = "hybrid"
    ) -> Dict[str, Any]:
        """
        Run evaluation on a dataset.
        
        Args:
            db: Database session
            user_id: User ID
            dataset_id: Dataset ID
            method: Retrieval method to test
            
        Returns:
            Dict with evaluation results
        """
        dataset = db.query(EvaluationDataset).filter(
            EvaluationDataset.id == dataset_id,
            EvaluationDataset.user_id == user_id
        ).first()
        
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
            
            # Perform retrieval
            try:
                chunk_ids = []
                if method == "semantic":
                    chunk_ids = self.rag_service.vector_search(db, user_id, query, len(expected_chunk_ids) * 2)
                elif method == "keyword":
                    chunk_ids = self.rag_service.keyword_search_func(db, user_id, query, len(expected_chunk_ids) * 2)
                else:  # hybrid
                    chunk_ids = self.rag_service.hybrid_search(db, user_id, query, len(expected_chunk_ids) * 2)
                
                # Calculate metrics
                metrics = self.calculate_quality_metrics(
                    retrieved_chunk_ids=chunk_ids,
                    expected_chunk_ids=expected_chunk_ids,
                    relevance_scores=relevance_scores if relevance_scores else None
                )
                
                all_metrics.append(metrics)
                results.append({
                    "query": query,
                    "metrics": metrics
                })
                
                # Record evaluation result
                eval_result = EvaluationResult(
                    dataset_id=dataset_id,
                    method=method,
                    metrics=metrics
                )
                db.add(eval_result)
                
            except Exception as e:
                logger.error(f"[RetrievalTest] Failed to evaluate query '{query}': {e}")
                continue
        
        db.commit()
        
        # Calculate average metrics
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
            "query_results": results
        }


# Global instance
_retrieval_test_service: Optional[RetrievalTestService] = None


def get_retrieval_test_service() -> RetrievalTestService:
    """Get global retrieval test service instance."""
    global _retrieval_test_service
    if _retrieval_test_service is None:
        _retrieval_test_service = RetrievalTestService()
    return _retrieval_test_service
