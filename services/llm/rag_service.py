"""
RAG Service for Knowledge Space
Author: lycosa9527
Made by: MindSpring Team

Orchestrates retrieval and reranking with hybrid search (vector + keyword).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
import os
import time

try:
    import numpy as np
except ImportError:
    np = None

from fastapi import HTTPException
from sqlalchemy.orm import Session

from clients.dashscope_embedding import get_embedding_client
from clients.dashscope_rerank import get_rerank_client
from models.domain.knowledge_space import (
    DocumentChunk,
    KnowledgeDocument,
    KnowledgeSpace,
    KnowledgeQuery,
    QueryFeedback,
    DocumentRelationship,
    ChunkAttachment
)
from services.infrastructure.rate_limiting.kb_rate_limiter import get_kb_rate_limiter
from services.knowledge.keyword_search_service import get_keyword_search_service
from services.llm.embedding_cache import get_embedding_cache
from services.llm.qdrant_service import get_qdrant_service


logger = logging.getLogger(__name__)


class RerankMode:
    """Reranking mode constants matching Dify's approach."""
    RERANKING_MODEL = "reranking_model"
    WEIGHTED_SCORE = "weighted_score"
    NONE = "none"


class RAGService:
    """
    RAG service for retrieval and context enhancement.

    Supports semantic search, keyword search, and hybrid search with reranking.
    """

    def __init__(self):
        """Initialize RAG service."""
        self.qdrant = get_qdrant_service()
        self.keyword_search = get_keyword_search_service()
        self.embedding_client = get_embedding_client()
        self.rerank_client = get_rerank_client()
        self.embedding_cache = get_embedding_cache()
        self.kb_rate_limiter = get_kb_rate_limiter()

        # Configuration
        self.default_method = os.getenv("DEFAULT_RETRIEVAL_METHOD", "hybrid")
        self.vector_weight = float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.5"))
        self.keyword_weight = float(os.getenv("HYBRID_KEYWORD_WEIGHT", "0.5"))
        self.reranking_mode = os.getenv("RERANKING_MODE", RerankMode.RERANKING_MODEL)
        self.rerank_threshold = float(os.getenv("RERANK_SCORE_THRESHOLD", "0.5"))
        self.parallel_workers = int(os.getenv("RETRIEVAL_PARALLEL_WORKERS", "2"))

        # Backward compatibility: if USE_RERANK_MODEL is set, use it
        use_rerank_model_env = os.getenv("USE_RERANK_MODEL")
        if use_rerank_model_env is not None:
            if use_rerank_model_env.lower() == "true":
                self.reranking_mode = RerankMode.RERANKING_MODEL
            else:
                self.reranking_mode = RerankMode.WEIGHTED_SCORE

        logger.info(
            "[RAGService] Initialized with method=%s, reranking_mode=%s, "
            "parallel_workers=%s",
            self.default_method,
            self.reranking_mode,
            self.parallel_workers
        )

    def has_knowledge_base(self, db: Session, user_id: int) -> bool:
        """
        Check if user has completed documents.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            True if user has completed documents
        """
        try:
            count = db.query(KnowledgeDocument).join(KnowledgeSpace).filter(
                KnowledgeSpace.user_id == user_id,
                KnowledgeDocument.status == 'completed'
            ).count()
            return count > 0
        except Exception as e:
            logger.error("[RAGService] Failed to check knowledge base for user %s: %s", user_id, e)
            return False

    def _apply_metadata_post_filter(
        self,
        db: Session,
        chunk_ids: List[int],
        metadata_filter: Optional[Dict[str, Any]]
    ) -> List[int]:
        """
        Apply metadata filters that Qdrant doesn't support directly.

        Filters by tags, date ranges, and custom fields at database level.

        Args:
            db: Database session
            chunk_ids: List of chunk IDs to filter
            metadata_filter: Metadata filter dict

        Returns:
            Filtered list of chunk IDs
        """
        if not metadata_filter or not chunk_ids:
            return chunk_ids

        # Get chunks with their documents
        chunks = db.query(DocumentChunk).filter(
            DocumentChunk.id.in_(chunk_ids)
        ).join(KnowledgeDocument).all()

        filtered_chunk_ids = []

        for chunk in chunks:
            document = chunk.document
            chunk_metadata = {}  # meta_data column removed to reduce database size

            # Filter by tags
            if "tags" in metadata_filter:
                filter_tags = metadata_filter["tags"]
                if isinstance(filter_tags, (list, tuple)):
                    document_tags = document.tags or []
                    # Check if any filter tag is in document tags
                    if not any(tag in document_tags for tag in filter_tags):
                        continue

            # Filter by category
            if "category" in metadata_filter:
                if document.category != metadata_filter["category"]:
                    continue

            # Filter by created_at date range
            if "created_at" in metadata_filter:
                date_filter = metadata_filter["created_at"]
                if isinstance(date_filter, dict):
                    doc_date = document.created_at
                    if "gte" in date_filter:
                        try:
                            gte_date = datetime.fromisoformat(date_filter["gte"].replace("Z", "+00:00"))
                            if doc_date < gte_date:
                                continue
                        except (ValueError, AttributeError):
                            pass
                    if "lte" in date_filter:
                        try:
                            lte_date = datetime.fromisoformat(date_filter["lte"].replace("Z", "+00:00"))
                            if doc_date > lte_date:
                                continue
                        except (ValueError, AttributeError):
                            pass

            # Filter by custom fields
            if "custom_fields" in metadata_filter:
                filter_custom = metadata_filter["custom_fields"]
                if isinstance(filter_custom, dict):
                    doc_custom = document.custom_fields or {}
                    # Check if all filter custom fields match
                    if not all(
                        doc_custom.get(k) == v
                        for k, v in filter_custom.items()
                    ):
                        continue

            # Filter by metadata fields
            if "metadata" in metadata_filter:
                filter_metadata = metadata_filter["metadata"]
                if isinstance(filter_metadata, dict):
                    doc_metadata = document.doc_metadata or {}
                    # Check if all filter metadata fields match
                    if not all(
                        doc_metadata.get(k) == v
                        for k, v in filter_metadata.items()
                    ):
                        continue

            # Structure-based filtering (chunk-level)
            # Filter by page_number
            if "page_number" in metadata_filter:
                filter_page = metadata_filter["page_number"]
                chunk_page = chunk_metadata.get('page_number')
                if isinstance(filter_page, dict):
                    # Range filter: {"gte": 1, "lte": 10}
                    if chunk_page is None:
                        continue
                    if "gte" in filter_page and chunk_page < filter_page["gte"]:
                        continue
                    if "lte" in filter_page and chunk_page > filter_page["lte"]:
                        continue
                    if "gt" in filter_page and chunk_page <= filter_page["gt"]:
                        continue
                    if "lt" in filter_page and chunk_page >= filter_page["lt"]:
                        continue
                else:
                    # Exact match
                    if chunk_page != filter_page:
                        continue

            # Filter by section_title
            if "section_title" in metadata_filter:
                chunk_section = chunk_metadata.get('section_title', '')
                if chunk_section != metadata_filter["section_title"]:
                    continue

            # Filter by section_level
            if "section_level" in metadata_filter:
                chunk_level = chunk_metadata.get('section_level')
                if chunk_level != metadata_filter["section_level"]:
                    continue

            # Filter by has_table
            if "has_table" in metadata_filter:
                chunk_has_table = chunk_metadata.get('has_table', False)
                if chunk_has_table != metadata_filter["has_table"]:
                    continue

            # Filter by has_code
            if "has_code" in metadata_filter:
                chunk_has_code = chunk_metadata.get('has_code', False)
                if chunk_has_code != metadata_filter["has_code"]:
                    continue

            filtered_chunk_ids.append(chunk.id)

        return filtered_chunk_ids

    def retrieve_with_relationships(
        self,
        db: Session,
        user_id: int,
        query: str,
        method: Optional[str] = None,
        top_k: int = 5,
        score_threshold: float = 0.0,
        include_related: bool = True,
        max_related: int = 3
    ) -> List[str]:
        """
        Retrieve context including related documents.

        Args:
            db: Database session
            user_id: User ID
            query: Query string
            method: Retrieval method
            top_k: Number of results
            score_threshold: Score threshold
            include_related: Whether to include related document chunks
            max_related: Maximum number of related documents to include

        Returns:
            List of chunk texts
        """
        # Get initial results (chunk texts)
        initial_texts = self.retrieve_context(
            db=db,
            user_id=user_id,
            query=query,
            method=method or 'hybrid',
            top_k=top_k,
            score_threshold=score_threshold
        )

        if not include_related:
            return initial_texts

        # Get chunk IDs from initial results by matching texts
        # This is a workaround - ideally retrieve_context would return IDs
        initial_chunks = db.query(DocumentChunk).filter(
            DocumentChunk.text.in_(initial_texts[:top_k])  # Limit to avoid too many matches
        ).all()
        document_ids = list(set(chunk.document_id for chunk in initial_chunks))

        # Find related documents
        related_doc_ids = set()
        for doc_id in document_ids:
            relationships = db.query(DocumentRelationship).filter(
                DocumentRelationship.source_document_id == doc_id
            ).limit(max_related).all()

            for rel in relationships:
                related_doc_ids.add(rel.target_document_id)

        # Retrieve chunks from related documents
        if related_doc_ids:
            related_texts = self.retrieve_context(
                db=db,
                user_id=user_id,
                query=query,
                method=method or 'hybrid',
                top_k=max_related * 2,  # Get more chunks from related docs
                score_threshold=score_threshold,
                metadata_filter={"document_id": list(related_doc_ids)}
            )

            # Combine initial and related texts (deduplicate)
            all_texts = list(dict.fromkeys(initial_texts + related_texts))  # Preserves order, removes duplicates
        else:
            all_texts = initial_texts

        return all_texts[:top_k + max_related * 2]  # Limit total results

    def retrieve_context(
        self,
        db: Session,
        user_id: int,
        query: Optional[str] = None,
        method: Optional[str] = None,
        top_k: int = 5,
        score_threshold: float = 0.0,
        source: str = 'api',
        source_context: Optional[Dict[str, Any]] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        attachment_ids: Optional[List[int]] = None  # NEW: For multimodal image queries
    ) -> List[str]:
        """
        Retrieve relevant context chunks for query.

        Args:
            db: Database session
            user_id: User ID
            query: Query string (optional for image-only queries)
            method: 'semantic', 'keyword', or 'hybrid' (default: self.default_method)
            top_k: Number of chunks to return
            score_threshold: Minimum relevance score
            source: Source of query (e.g., 'api', 'diagram_generation')
            source_context: Additional context (e.g., {'diagram_type': 'mindmap'})
            attachment_ids: List of attachment IDs for multimodal image queries

        Returns:
            List of text chunks
        """
        # Support multimodal queries (image-only or text+image)
        if attachment_ids and not query:
            # Image-only query
            return self._retrieve_by_images(db, user_id, attachment_ids, top_k, score_threshold, metadata_filter)

        if not query or not query.strip():
            return []

        method = method or self.default_method

        # Check KB rate limit for retrieval
        allowed, _, error_msg = self.kb_rate_limiter.check_retrieval_limit(user_id)
        if not allowed:
            logger.warning("[RAGService] Rate limit exceeded for user %s: %s", user_id, error_msg)
            raise HTTPException(
                status_code=429,
                detail=f"Knowledge base rate limit exceeded: {error_msg}"
            )

        start_time = time.time()
        timing: Dict[str, Optional[float]] = {
            'embedding_ms': None,
            'search_ms': None,
            'rerank_ms': None,
            'total_ms': None
        }

        try:
            # Get space_id for query recording
            space = db.query(KnowledgeSpace).filter(KnowledgeSpace.user_id == user_id).first()
            space_id = space.id if space else None

            # Get chunk IDs from search (with timing)
            # Note: embedding time is included in vector_search/hybrid_search
            search_start = time.time()
            if method == 'semantic':
                # Get more for reranking
                chunk_ids = self.vector_search(
                    db, user_id, query, top_k * 2,
                    metadata_filter=metadata_filter
                )
            elif method == 'keyword':
                chunk_ids = self.keyword_search_func(db, user_id, query, top_k * 2, metadata_filter=metadata_filter)
            else:  # hybrid
                chunk_ids = self.hybrid_search(db, user_id, query, top_k * 2, metadata_filter=metadata_filter)

            # Apply post-filtering for advanced metadata (tags, date ranges, etc.)
            chunk_ids = self._apply_metadata_post_filter(db, chunk_ids, metadata_filter)

            timing['search_ms'] = (time.time() - search_start) * 1000
            # Embedding time is included in search time for semantic/hybrid methods
            # For keyword-only, embedding_ms stays None
            if method != 'keyword':
                # Rough estimate: embedding is ~30-50% of search time for semantic/hybrid
                timing['embedding_ms'] = timing['search_ms'] * 0.4 if timing['search_ms'] else None

            if not chunk_ids:
                # Record query even if no results
                if space_id:
                    self._record_query(
                        db=db,
                        user_id=user_id,
                        space_id=space_id,
                        query=query,
                        method=method,
                        top_k=top_k,
                        score_threshold=score_threshold,
                        result_count=0,
                        timing=timing,
                        source=source,
                        source_context=source_context
                    )
                return []

            # Lookup text from database
            chunks = db.query(DocumentChunk).filter(
                DocumentChunk.id.in_(chunk_ids)
            ).all()

            # Extract text and metadata
            chunk_texts = [(chunk.text, chunk.id) for chunk in chunks]

            # Apply reranking based on mode (Dify's approach)
            rerank_start = time.time()
            results = []
            if method == 'hybrid' and len(chunk_texts) > 1:
                # Deduplicate before reranking (Dify's approach)
                deduplicated_texts = self._deduplicate_chunk_texts(chunk_texts)

                if self.reranking_mode == RerankMode.RERANKING_MODEL:
                    # Use rerank model
                    texts = [text for text, _ in deduplicated_texts]
                    try:
                        reranked = self.rerank_client.rerank(
                            query=query,
                            documents=texts,
                            top_n=top_k,
                            score_threshold=score_threshold
                        )
                        results = [item["document"] for item in reranked]
                    except Exception as rerank_error:
                        # If reranking fails, fall back to original results without reranking
                        logger.warning("[RAGService] Reranking failed, using original results: %s", rerank_error)
                        results = [text for text, _ in deduplicated_texts[:top_k]]
                elif self.reranking_mode == RerankMode.WEIGHTED_SCORE:
                    # Use weighted score (already done in hybrid_search)
                    # Just return top K
                    results = [text for text, _ in deduplicated_texts[:top_k]]
                else:  # NONE
                    results = [text for text, _ in deduplicated_texts[:top_k]]
            elif self.reranking_mode == RerankMode.RERANKING_MODEL and len(chunk_texts) > 1:
                # Non-hybrid search with rerank model
                texts = [text for text, _ in chunk_texts]
                try:
                    reranked = self.rerank_client.rerank(
                        query=query,
                        documents=texts,
                        top_n=top_k,
                        score_threshold=score_threshold
                    )
                    results = [item["document"] for item in reranked]
                except Exception as rerank_error:
                    # If reranking fails, fall back to original results without reranking
                    logger.warning("[RAGService] Reranking failed, using original results: %s", rerank_error)
                    results = [text for text, _ in chunk_texts[:top_k]]
            else:
                # Return top K without reranking
                results = [text for text, _ in chunk_texts[:top_k]]

            timing['rerank_ms'] = (time.time() - rerank_start) * 1000
            timing['total_ms'] = (time.time() - start_time) * 1000

            # Record query for analytics
            if space_id:
                self._record_query(
                    db=db,
                    user_id=user_id,
                    space_id=space_id,
                    query=query,
                    method=method,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    result_count=len(results),
                    timing=timing,
                    source=source,
                    source_context=source_context
                )

            return results

        except Exception as e:
            logger.error("[RAGService] Failed to retrieve context: %s", e)
            # Record failed query
            try:
                space = db.query(KnowledgeSpace).filter(KnowledgeSpace.user_id == user_id).first()
                if space:
                    timing['total_ms'] = (time.time() - start_time) * 1000
                    self._record_query(
                        db=db,
                        user_id=user_id,
                        space_id=space.id,
                        query=query,
                        method=method or self.default_method,
                        top_k=top_k,
                        score_threshold=score_threshold,
                        result_count=0,
                        timing=timing,
                        source=source,
                        source_context=source_context
                    )
            except Exception as record_error:
                logger.error("[RAGService] Failed to record query: %s", record_error)
            return []

    def vector_search(
        self,
        _db: Session,
        user_id: int,
        query: str,
        top_k: int,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[int]:
        """
        Semantic search using vector similarity.

        Args:
            _db: Database session (unused, kept for API consistency)
            user_id: User ID
            query: Query string
            top_k: Number of results

        Returns:
            List of chunk IDs
        """
        try:
            # Generate query embedding (with cache)
            query_embedding = self.embedding_cache.embed_query_cached(query)

            logger.debug(
                "[RAGService] vector_search: user=%s, query_len=%s, "
                "embedding_dim=%s",
                user_id,
                len(query),
                len(query_embedding)
            )

            # Search Qdrant with metadata filter
            results = self.qdrant.search(
                user_id=user_id,
                query_embedding=query_embedding,
                top_k=top_k,
                metadata_filter=metadata_filter
            )

            logger.debug("[RAGService] vector_search: Qdrant returned %s results", len(results))
            if results:
                logger.debug(
                    "[RAGService] vector_search: First result: id=%s, "
                    "score=%.4f",
                    results[0]['id'],
                    results[0]['score']
                )

            return [r["id"] for r in results]
        except Exception as e:
            logger.error("[RAGService] Vector search failed: %s", e)
            return []

    def keyword_search_func(
        self,
        db: Session,
        user_id: int,
        query: str,
        top_k: int,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[int]:
        """
        Keyword search using full-text search.

        Args:
            db: Database session
            user_id: User ID
            query: Query string
            top_k: Number of results

        Returns:
            List of chunk IDs
        """
        try:
            results = self.keyword_search.keyword_search(
                db=db,
                user_id=user_id,
                query=query,
                top_k=top_k,
                metadata_filter=metadata_filter
            )
            return [r["chunk_id"] for r in results]
        except Exception as e:
            logger.error("[RAGService] Keyword search failed: %s", e)
            return []

    def hybrid_search(
        self,
        db: Session,
        user_id: int,
        query: str,
        top_k: int,
        weights: Optional[Dict[str, float]] = None,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[int]:
        """
        Hybrid search combining vector and keyword search (Dify's approach).

        Runs both searches in parallel, then combines with weighted scores.

        Args:
            db: Database session
            user_id: User ID
            query: Query string
            top_k: Number of results
            weights: Optional weights dict with 'vector' and 'keyword' keys

        Returns:
            List of chunk IDs
        """
        if weights is None:
            weights = {"vector": self.vector_weight, "keyword": self.keyword_weight}

        try:
            # Run both searches in parallel (Dify's approach - 43% faster)
            vector_results = []
            keyword_results = []
            exceptions = []

            with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
                # Submit both searches in parallel
                vector_future = executor.submit(
                    self._vector_search_with_scores,
                    db, user_id, query, top_k * 2, metadata_filter
                )
                keyword_future = executor.submit(
                    self._keyword_search_with_scores,
                    db, user_id, query, top_k * 2, metadata_filter
                )

                # Wait for both to complete, handle errors (Dify's approach)
                # Use as_completed for early error propagation - cancel remaining futures on first error
                futures = [vector_future, keyword_future]
                try:
                    for future in as_completed(futures, timeout=300):
                        if future.exception():
                            # Cancel remaining futures to avoid unnecessary waiting
                            for f in futures:
                                if not f.done():
                                    f.cancel()
                            exceptions.append(str(future.exception()))
                            break

                    # Only get results if no exceptions occurred
                    if not exceptions:
                        vector_results = vector_future.result(timeout=0) if vector_future.done() else []
                        keyword_results = keyword_future.result(timeout=0) if keyword_future.done() else []
                    else:
                        # If we had exceptions, try to get any successful results
                        vector_results = []
                        keyword_results = []
                        if vector_future.done() and not vector_future.exception():
                            try:
                                vector_results = vector_future.result(timeout=0)
                            except Exception:
                                pass
                        if keyword_future.done() and not keyword_future.exception():
                            try:
                                keyword_results = keyword_future.result(timeout=0)
                            except Exception:
                                pass
                except Exception as e:
                    logger.error("[RAGService] Parallel search failed: %s", e)
                    # Cancel remaining futures on error
                    for f in futures:
                        if not f.done():
                            f.cancel()
                    exceptions.append(str(e))

            if exceptions:
                logger.warning("[RAGService] Some searches failed, falling back to vector search")
                return self.vector_search(db, user_id, query, top_k, metadata_filter)

            # Combine results with weighted scores
            combined_scores = {}

            # Add vector results with scores
            for result in vector_results:
                chunk_id = result.get("id") or result.get("chunk_id")
                score = result.get("score", 0.0)
                if chunk_id:
                    combined_scores[chunk_id] = combined_scores.get(chunk_id, 0.0) + weights["vector"] * score

            # Add keyword results with scores
            for result in keyword_results:
                chunk_id = result.get("chunk_id")
                score = result.get("score", 0.0)
                if chunk_id:
                    combined_scores[chunk_id] = combined_scores.get(chunk_id, 0.0) + weights["keyword"] * score

            # Sort by combined score
            sorted_chunks = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)

            # Return top K chunk IDs
            return [chunk_id for chunk_id, _ in sorted_chunks[:top_k]]

        except Exception as e:
            logger.error("[RAGService] Hybrid search failed: %s", e)
            # Fallback to vector search
            return self.vector_search(db, user_id, query, top_k, metadata_filter)

    def _vector_search_with_scores(
        self,
        _db: Session,
        user_id: int,
        query: str,
        top_k: int,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Vector search returning results with scores."""
        try:
            query_embedding = self.embedding_cache.embed_query_cached(query)
            results = self.qdrant.search(
                user_id=user_id,
                query_embedding=query_embedding,
                top_k=top_k,
                metadata_filter=metadata_filter
            )
            return [{"id": r["id"], "score": r["score"]} for r in results]
        except Exception as e:
            logger.error("[RAGService] Vector search with scores failed: %s", e)
            return []

    def _keyword_search_with_scores(
        self,
        db: Session,
        user_id: int,
        query: str,
        top_k: int,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Keyword search returning results with scores."""
        try:
            results = self.keyword_search.keyword_search(
                db=db,
                user_id=user_id,
                query=query,
                top_k=top_k,
                metadata_filter=metadata_filter
            )
            return [{"chunk_id": r["chunk_id"], "score": r["score"]} for r in results]
        except Exception as e:
            logger.error("[RAGService] Keyword search with scores failed: %s", e)
            return []

    def _deduplicate_chunk_texts(
        self,
        chunk_texts: List[tuple]
    ) -> List[tuple]:
        """
        Deduplicate chunks by text content, keeping first occurrence.

        Args:
            chunk_texts: List of (text, chunk_id) tuples

        Returns:
            Deduplicated list preserving first-seen order
        """
        if not chunk_texts:
            return chunk_texts

        seen = {}  # text -> (text, chunk_id)
        order = []  # Preserve order

        for text, chunk_id in chunk_texts:
            if text not in seen:
                seen[text] = (text, chunk_id)
                order.append(text)

        return [seen[text] for text in order]

    def _retrieve_by_images(
        self,
        db: Session,
        user_id: int,
        attachment_ids: List[int],
        top_k: int,
        score_threshold: float,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Retrieve chunks by image similarity (multimodal search).

        Args:
            db: Database session
            user_id: User ID
            attachment_ids: List of attachment IDs (images)
            top_k: Number of chunks to return
            score_threshold: Minimum relevance score
            metadata_filter: Optional metadata filter

        Returns:
            List of text chunks
        """
        try:
            # Get attachments
            attachments = db.query(ChunkAttachment).filter(
                ChunkAttachment.id.in_(attachment_ids),
                ChunkAttachment.attachment_type == 'image'
            ).all()

            if not attachments:
                logger.warning("[RAGService] No valid image attachments found for IDs: %s", attachment_ids)
                return []

            # Generate embeddings for images
            embedding_client = get_embedding_client()

            if not embedding_client.is_multimodal:
                logger.warning(
                    "[RAGService] Current embedding model %s does not support multimodal. "
                    "Cannot perform image search.",
                    embedding_client.model
                )
                return []

            # Embed images
            image_contents = []
            for attachment in attachments:
                if attachment.file_path.startswith(("http://", "https://")):
                    image_contents.append({"image": attachment.file_path})
                else:
                    # Local file path
                    image_contents.append({"image": attachment.file_path})

            image_embeddings = embedding_client.embed_multimodal(image_contents)

            if not image_embeddings:
                logger.warning("[RAGService] Failed to generate image embeddings")
                return []

            # Use average of image embeddings for search
            if len(image_embeddings) > 1:
                if np is None:
                    logger.error("[RAGService] numpy is required for multi-image search but not installed")
                    return []
                avg_embedding = np.mean(image_embeddings, axis=0).tolist()
            else:
                avg_embedding = image_embeddings[0]

            # Search using image embedding
            qdrant_service = get_qdrant_service()

            results = qdrant_service.search(
                user_id=user_id,
                query_embedding=avg_embedding,
                top_k=top_k,
                score_threshold=score_threshold,
                metadata_filter=metadata_filter
            )

            # Get chunk texts
            chunk_ids = [r["chunk_id"] for r in results]
            chunks = db.query(DocumentChunk).filter(DocumentChunk.id.in_(chunk_ids)).all()

            # Sort by score
            chunk_dict = {chunk.id: chunk for chunk in chunks}
            sorted_chunks = []
            for r in results:
                if r["chunk_id"] in chunk_dict:
                    sorted_chunks.append(chunk_dict[r["chunk_id"]])

            return [chunk.text for chunk in sorted_chunks]

        except Exception as e:
            logger.error("[RAGService] Error retrieving by images: %s", e)
            return []

    @staticmethod
    def _expand_query(query: str, db: Session, user_id: int) -> str:
        """
        Expand query using synonyms and related terms from successful queries.

        Args:
            query: Original query
            db: Database session
            user_id: User ID

        Returns:
            Expanded query string
        """
        # Get space_id for query history
        space = db.query(KnowledgeSpace).filter(KnowledgeSpace.user_id == user_id).first()
        if not space:
            return query

        # Get successful queries (with positive feedback) from last 30 days
        cutoff_date = datetime.utcnow() - timedelta(days=30)

        successful_queries = db.query(KnowledgeQuery).join(QueryFeedback).filter(
            KnowledgeQuery.space_id == space.id,
            KnowledgeQuery.created_at >= cutoff_date,
            QueryFeedback.feedback_type == 'positive',
            QueryFeedback.feedback_score >= 4
        ).distinct().limit(100).all()

        # Extract related terms from successful queries
        related_terms = set()
        query_words = set(query.lower().split())

        for sq in successful_queries:
            sq_words = set(sq.query.lower().split())
            # Find overlapping words (potential synonyms/related terms)
            if len(query_words & sq_words) > 0:
                # Add words from successful query that aren't in current query
                related_terms.update(sq_words - query_words)

        # Limit related terms to avoid query bloat
        if related_terms:
            # Use top 3 related terms
            expanded_terms = list(related_terms)[:3]
            expanded_query = f"{query} {' '.join(expanded_terms)}"
            logger.debug("[RAGService] Expanded query: %s -> %s", query, expanded_query)
            return expanded_query

        return query

    def analyze_query_performance(self, db: Session, user_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Analyze query performance patterns.

        Args:
            db: Database session
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dict with analytics:
            - common_queries: List of most common queries
            - low_performing_queries: List of queries with low success rates
            - average_scores: Average feedback scores by method
            - suggestions: List of query improvement suggestions
        """
        space = db.query(KnowledgeSpace).filter(KnowledgeSpace.user_id == user_id).first()
        if not space:
            return {
                "common_queries": [],
                "low_performing_queries": [],
                "average_scores": {},
                "suggestions": []
            }

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Get queries with feedback
        queries_with_feedback = db.query(KnowledgeQuery).join(QueryFeedback).filter(
            KnowledgeQuery.space_id == space.id,
            KnowledgeQuery.created_at >= cutoff_date
        ).all()

        # Analyze common queries
        query_counts = Counter(q.query for q in queries_with_feedback)
        common_queries = [
            {"query": query, "count": count}
            for query, count in query_counts.most_common(10)
        ]

        # Analyze query performance by method
        method_scores = {}
        for method in ['semantic', 'keyword', 'hybrid']:
            method_queries = [q for q in queries_with_feedback if q.method == method]
            if method_queries:
                feedbacks = []
                for q in method_queries:
                    q_feedbacks = db.query(QueryFeedback).filter(
                        QueryFeedback.query_id == q.id,
                        QueryFeedback.feedback_score.isnot(None)
                    ).all()
                    feedbacks.extend([f.feedback_score for f in q_feedbacks])

                if feedbacks:
                    method_scores[method] = sum(feedbacks) / len(feedbacks)

        # Identify low-performing queries
        low_performing = []
        for q in queries_with_feedback:
            q_feedbacks = db.query(QueryFeedback).filter(QueryFeedback.query_id == q.id).all()
            if q_feedbacks:
                avg_score = sum(f.feedback_score for f in q_feedbacks if f.feedback_score) / len(q_feedbacks)
                if avg_score < 3.0:
                    low_performing.append({
                        "query": q.query,
                        "method": q.method,
                        "average_score": avg_score,
                        "feedback_count": len(q_feedbacks)
                    })

        # Generate suggestions
        suggestions = []
        if method_scores:
            best_method = max(method_scores.items(), key=lambda x: x[1])[0]
            worst_method = min(method_scores.items(), key=lambda x: x[1])[0]
            if method_scores[best_method] - method_scores[worst_method] > 0.5:
                score_diff = (
                    method_scores[best_method] - method_scores[worst_method]
                )
                suggestions.append(
                    f"Consider using {best_method} method instead of "
                    f"{worst_method} for better results "
                    f"(score difference: {score_diff:.2f})"
                )

        if low_performing:
            suggestions.append(
                f"{len(low_performing)} queries have low performance scores. "
                f"Consider refining these queries or trying different retrieval methods."
            )

        return {
            "common_queries": common_queries,
            "low_performing_queries": low_performing[:10],  # Top 10
            "average_scores": method_scores,
            "suggestions": suggestions
        }

    @staticmethod
    def escape_query_for_search(query: str) -> str:
        """
        Escape query string for safe search (like Dify's escape_query_for_search).

        Escapes special characters that could cause issues in search queries.

        Args:
            query: Query string to escape

        Returns:
            Escaped query string
        """
        if not query:
            return query

        # Escape double quotes for PostgreSQL full-text search
        # Replace " with "" (PostgreSQL escaping)
        escaped = query.replace('"', '\\"')

        # Additional escaping for other special characters if needed
        # For now, just handle quotes (most common issue)

        return escaped

    def _record_query(
        self,
        db: Session,
        user_id: int,
        space_id: int,
        query: str,
        method: str,
        top_k: int,
        score_threshold: float,
        result_count: int,
        timing: Dict[str, Optional[float]],
        source: str = 'api',
        source_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record query for analytics (like Dify's DatasetQuery).

        Args:
            db: Database session
            user_id: User ID
            space_id: Knowledge space ID
            query: Query text
            method: Retrieval method (semantic/keyword/hybrid)
            top_k: Requested top_k
            score_threshold: Score threshold used
            result_count: Number of results returned
            timing: Timing metrics dict
            source: Source of query
            source_context: Additional context
        """
        try:
            query_record = KnowledgeQuery(
                user_id=user_id,
                space_id=space_id,
                query=query,
                method=method,
                top_k=top_k,
                score_threshold=score_threshold,
                result_count=result_count,
                embedding_ms=timing.get('embedding_ms'),
                search_ms=timing.get('search_ms'),
                rerank_ms=timing.get('rerank_ms'),
                total_ms=timing.get('total_ms'),
                source=source,
                source_context=source_context
            )
            db.add(query_record)
            db.commit()
            total_ms = timing.get('total_ms')
            logger.debug(
                "[RAGService] Recorded query for user %s: method=%s, "
                "results=%s, time=%.2fms",
                user_id,
                method,
                result_count,
                total_ms if total_ms else 0.0
            )
        except Exception as e:
            db.rollback()
            logger.warning("[RAGService] Failed to record query: %s", e)

    def enhance_prompt(
        self,
        _user_id: int,
        prompt: str,
        context_chunks: List[str],
        max_context_length: int = 2000
    ) -> str:
        """
        Enhance prompt with knowledge base context.

        Args:
            _user_id: User ID (unused, kept for API consistency)
            prompt: Original prompt
            context_chunks: Retrieved context chunks
            max_context_length: Maximum context length in characters

        Returns:
            Enhanced prompt
        """
        if not context_chunks:
            return prompt

        # Build context section
        context_text = "\n\n".join(context_chunks)

        # Truncate if too long
        if len(context_text) > max_context_length:
            context_text = context_text[:max_context_length] + "..."

        # Build enhanced prompt
        enhanced = f"""请参考以下知识库内容回答问题：

{context_text}

---

问题：{prompt}"""

        return enhanced


class RAGServiceSingleton:
    """Singleton wrapper for RAG service instance."""
    _instance: Optional[RAGService] = None

    @classmethod
    def get_instance(cls) -> RAGService:
        """Get singleton RAG service instance."""
        if cls._instance is None:
            cls._instance = RAGService()
        return cls._instance


def get_rag_service() -> RAGService:
    """Get global RAG service instance."""
    return RAGServiceSingleton.get_instance()
