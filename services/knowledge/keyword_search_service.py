"""Keyword Search Service for Knowledge Space.

Author: lycosa9527
Made by: MindSpring Team

Full-text search using PostgreSQL full-text search.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import List, Dict, Any, Optional
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from config.database import engine


logger = logging.getLogger(__name__)


class KeywordSearchService:
    """
    Keyword search service using PostgreSQL full-text search.
    """

    def __init__(self):
        """Initialize keyword search service."""
        logger.info("[KeywordSearch] Initialized with database=%s", engine.url.drivername)

    def extract_keywords(self, text_content: str) -> List[str]:
        """
        Extract keywords from text (for Chinese, uses Jieba).

        Args:
            text_content: Text to extract keywords from

        Returns:
            List of keywords
        """
        try:
            import jieba3
            # Extract keywords using jieba3 (modern Python 3 rewrite)
            tokenizer = jieba3.jieba3()
            words = tokenizer.cut_text(text_content)
            keywords = [w.strip() for w in words if len(w.strip()) > 1]
            return keywords
        except ImportError:
            # Fallback: simple word splitting for English
            import re
            words = re.findall(r'\b\w+\b', text_content.lower())
            return list(set(words))

    def keyword_search(
        self,
        db: Session,
        user_id: int,
        query: str,
        top_k: int = 5,
        document_id: Optional[int] = None,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for chunks using keyword/full-text search.

        Args:
            db: Database session
            user_id: User ID
            query: Search query
            top_k: Number of results
            document_id: Optional document ID to filter by (deprecated, use metadata_filter)
            metadata_filter: Optional metadata filter dict (e.g., {'document_id': 1, 'document_type': 'pdf'})

        Returns:
            List of dicts with 'chunk_id', 'score', 'text'
        """
        if not query or not query.strip():
            return []

        # Extract document_id from metadata_filter if provided
        if metadata_filter and 'document_id' in metadata_filter:
            document_id = metadata_filter['document_id']

        try:
            return self._search_postgresql(db, user_id, query, top_k, document_id, metadata_filter)
        except Exception as e:
            logger.error("[KeywordSearch] Search failed: %s", e)
            # Fallback to LIKE query
            return self._search_like(db, user_id, query, top_k, document_id, metadata_filter)

    def _search_postgresql(
        self,
        db: Session,
        user_id: int,
        query: str,
        top_k: int,
        document_id: Optional[int] = None,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search using PostgreSQL full-text search."""
        # Extract keywords for PostgreSQL tsquery
        self.extract_keywords(query)

        sql = """
            SELECT
                dc.id as chunk_id,
                dc.text,
                dc.document_id,
                ts_rank(to_tsvector('simple', dc.text), plainto_tsquery('simple', :query)) as score
            FROM document_chunks dc
            JOIN knowledge_documents kd ON dc.document_id = kd.id
            JOIN knowledge_spaces ks ON kd.space_id = ks.id
            WHERE ks.user_id = :user_id
            AND to_tsvector('simple', dc.text) @@ plainto_tsquery('simple', :query)
        """

        params: Dict[str, Any] = {"user_id": user_id, "query": query}

        # Apply metadata filters
        if document_id:
            sql += " AND dc.document_id = :document_id"
            params["document_id"] = document_id

        if metadata_filter:
            if 'document_id' in metadata_filter and not document_id:
                sql += " AND dc.document_id = :document_id"
                params["document_id"] = metadata_filter['document_id']
            if 'document_type' in metadata_filter:
                sql += " AND kd.file_type = :document_type"
                params["document_type"] = metadata_filter['document_type']
            if 'category' in metadata_filter:
                sql += " AND kd.category = :category"
                params["category"] = metadata_filter['category']

        sql += " ORDER BY score DESC LIMIT :top_k"
        params["top_k"] = top_k

        result = db.execute(text(sql), params)
        results = []
        for row in result:
            results.append({
                "chunk_id": row.chunk_id,
                "text": row.text,
                "document_id": row.document_id,
                "score": float(row.score) if row.score else 0.0,
            })
        return results

    def _search_like(
        self,
        db: Session,
        user_id: int,
        query: str,
        top_k: int,
        document_id: Optional[int] = None,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Fallback search using LIKE queries."""
        # Extract keywords
        keywords = self.extract_keywords(query)
        if not keywords:
            return []

        # Build LIKE conditions
        like_conditions = " OR ".join([f"dc.text LIKE :keyword{i}" for i in range(len(keywords))])

        sql = f"""
            SELECT DISTINCT
                dc.id as chunk_id,
                dc.text,
                dc.document_id,
                0.5 as score
            FROM document_chunks dc
            JOIN knowledge_documents kd ON dc.document_id = kd.id
            JOIN knowledge_spaces ks ON kd.space_id = ks.id
            WHERE ks.user_id = :user_id
            AND ({like_conditions})
        """

        params: Dict[str, Any] = {"user_id": user_id}
        for i, keyword in enumerate(keywords):
            params[f"keyword{i}"] = f"%{keyword}%"

        # Apply metadata filters
        if document_id:
            sql += " AND dc.document_id = :document_id"
            params["document_id"] = document_id

        if metadata_filter:
            if 'document_id' in metadata_filter and not document_id:
                sql += " AND dc.document_id = :document_id"
                params["document_id"] = metadata_filter['document_id']
            if 'document_type' in metadata_filter:
                sql += " AND kd.file_type = :document_type"
                params["document_type"] = metadata_filter['document_type']
            if 'category' in metadata_filter:
                sql += " AND kd.category = :category"
                params["category"] = metadata_filter['category']

        sql += " LIMIT :top_k"
        params["top_k"] = top_k

        result = db.execute(text(sql), params)
        results = []
        for row in result:
            results.append({
                "chunk_id": row.chunk_id,
                "text": row.text,
                "document_id": row.document_id,
                "score": 0.5,  # Default score for LIKE
            })
        return results

    def calculate_tfidf_score(self, query: str, document: str) -> float:
        """
        Calculate TF-IDF score (simplified).

        Args:
            query: Query text
            document: Document text

        Returns:
            TF-IDF score (0.0-1.0)
        """
        # Simplified TF-IDF calculation
        query_words = set(self.extract_keywords(query.lower()))
        doc_words = self.extract_keywords(document.lower())

        if not query_words or not doc_words:
            return 0.0

        # Count matches
        matches = sum(1 for word in doc_words if word in query_words)

        # Simple score: matches / total query words
        score = min(1.0, matches / len(query_words))
        return score


# Global instance
_keyword_search_service: Optional[KeywordSearchService] = None


def get_keyword_search_service() -> KeywordSearchService:
    """Get global keyword search service instance."""
    global _keyword_search_service
    if _keyword_search_service is None:
        _keyword_search_service = KeywordSearchService()
    return _keyword_search_service
