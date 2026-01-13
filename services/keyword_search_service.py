"""
Keyword Search Service for Knowledge Space
Author: lycosa9527
Made by: MindSpring Team

Full-text search using SQLite FTS5 or PostgreSQL full-text search.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from models.knowledge_space import DocumentChunk, KnowledgeDocument, KnowledgeSpace
from config.database import engine

logger = logging.getLogger(__name__)


class KeywordSearchService:
    """
    Keyword search service using database full-text search.
    
    Supports SQLite FTS5 and PostgreSQL full-text search.
    """
    
    def __init__(self):
        """Initialize keyword search service."""
        self.is_sqlite = "sqlite" in str(engine.url)
        self._ensure_fts5_table()
        if self.is_sqlite:
            self._backfill_fts5_table()
        logger.info(f"[KeywordSearch] Initialized with database={engine.url.drivername}")
    
    def _ensure_fts5_table(self):
        """Ensure FTS5 virtual table exists (SQLite only)."""
        if not self.is_sqlite:
            return  # PostgreSQL uses native full-text search
        
        try:
            with engine.connect() as conn:
                # Check if FTS5 table exists
                result = conn.execute(text("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='document_chunks_fts5'
                """))
                if result.fetchone():
                    return                 
                
                # Create FTS5 virtual table
                conn.execute(text("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts5 
                    USING fts5(
                        id UNINDEXED,
                        text,
                        document_id UNINDEXED,
                        content='document_chunks',
                        content_rowid='id'
                    )
                """))
                
                # Create triggers to sync FTS5 with main table
                conn.execute(text("""
                    CREATE TRIGGER IF NOT EXISTS document_chunks_fts5_insert AFTER INSERT ON document_chunks
                    BEGIN
                        INSERT INTO document_chunks_fts5(rowid, id, text, document_id)
                        VALUES (new.id, new.id, new.text, new.document_id);
                    END
                """))
                
                conn.execute(text("""
                    CREATE TRIGGER IF NOT EXISTS document_chunks_fts5_delete AFTER DELETE ON document_chunks
                    BEGIN
                        DELETE FROM document_chunks_fts5 WHERE rowid = old.id;
                    END
                """))
                
                conn.execute(text("""
                    CREATE TRIGGER IF NOT EXISTS document_chunks_fts5_update AFTER UPDATE ON document_chunks
                    BEGIN
                        DELETE FROM document_chunks_fts5 WHERE rowid = old.id;
                        INSERT INTO document_chunks_fts5(rowid, id, text, document_id)
                        VALUES (new.id, new.id, new.text, new.document_id);
                    END
                """))
                
                conn.commit()
                logger.info("[KeywordSearch] Created FTS5 table and triggers")
        except Exception as e:
            logger.error(f"[KeywordSearch] Failed to create FTS5 table: {e}")
            # Don't raise - search will fallback to LIKE queries
    
    def _backfill_fts5_table(self):
        """Backfill FTS5 table with existing chunks (SQLite only)."""
        if not self.is_sqlite:
            return
        
        try:
            with engine.connect() as conn:
                # Check if FTS5 table exists
                result = conn.execute(text("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='document_chunks_fts5'
                """))
                if not result.fetchone():
                    return  # FTS5 table doesn't exist, skip backfill
                
                # Count existing chunks in FTS5
                result = conn.execute(text("SELECT COUNT(*) FROM document_chunks_fts5"))
                fts5_count = result.scalar() or 0
                
                # Count total chunks
                result = conn.execute(text("SELECT COUNT(*) FROM document_chunks"))
                total_count = result.scalar() or 0
                
                if fts5_count >= total_count:
                    logger.debug(f"[KeywordSearch] FTS5 table already indexed ({fts5_count}/{total_count} chunks)")
                    return
                
                # Backfill missing chunks
                logger.info(f"[KeywordSearch] Backfilling FTS5 table ({fts5_count}/{total_count} chunks indexed)")
                
                # Insert missing chunks into FTS5
                conn.execute(text("""
                    INSERT INTO document_chunks_fts5(rowid, id, text, document_id)
                    SELECT id, id, text, document_id
                    FROM document_chunks
                    WHERE id NOT IN (SELECT rowid FROM document_chunks_fts5)
                """))
                
                conn.commit()
                result = conn.execute(text("SELECT COUNT(*) FROM document_chunks_fts5"))
                new_count = result.scalar() or 0
                logger.info(f"[KeywordSearch] FTS5 backfill complete ({new_count}/{total_count} chunks indexed)")
        except Exception as e:
            logger.warning(f"[KeywordSearch] FTS5 backfill failed (non-critical): {e}")
            # Don't raise - search will still work with triggers for new chunks
    
    def extract_keywords(self, text: str) -> List[str]:
        """
        Extract keywords from text (for Chinese, uses Jieba).
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            List of keywords
        """
        try:
            import jieba3
            # Extract keywords using jieba3 (modern Python 3 rewrite)
            tokenizer = jieba3.jieba3()
            words = tokenizer.cut_text(text)
            keywords = [w.strip() for w in words if len(w.strip()) > 1]
            return keywords
        except ImportError:
            # Fallback: simple word splitting for English
            import re
            words = re.findall(r'\b\w+\b', text.lower())
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
            if self.is_sqlite:
                return self._search_sqlite_fts5(db, user_id, query, top_k, document_id, metadata_filter)
            else:
                return self._search_postgresql(db, user_id, query, top_k, document_id, metadata_filter)
        except Exception as e:
            logger.error(f"[KeywordSearch] Search failed: {e}")
            # Fallback to LIKE query
            return self._search_like(db, user_id, query, top_k, document_id, metadata_filter)
    
    def _search_sqlite_fts5(
        self,
        db: Session,
        user_id: int,
        query: str,
        top_k: int,
        document_id: Optional[int] = None,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search using SQLite FTS5."""
        # Escape query for FTS5 (SQLite FTS5 uses "" for escaping quotes)
        # Also escape backslashes to prevent injection
        escaped_query = query.replace('\\', '\\\\').replace('"', '""')
        
        # Join with document_chunks to get user_id
        sql = """
            SELECT 
                dc.id as chunk_id,
                dc.text,
                dc.document_id,
                bm25(document_chunks_fts5) as score
            FROM document_chunks_fts5
            JOIN document_chunks dc ON document_chunks_fts5.rowid = dc.id
            JOIN knowledge_documents kd ON dc.document_id = kd.id
            JOIN knowledge_spaces ks ON kd.space_id = ks.id
            WHERE ks.user_id = :user_id
            AND document_chunks_fts5 MATCH :query
        """
        
        params = {"user_id": user_id, "query": escaped_query}
        
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
            # Tags and custom fields will be filtered post-query (JSON filtering is complex in SQLite)
        
        sql += " ORDER BY score LIMIT :top_k"
        params["top_k"] = top_k
        
        try:
            result = db.execute(text(sql), params)
            results = []
            for row in result:
                # BM25 scores are negative (lower is better), convert to 0-1
                bm25_score = row.score if row.score else 0.0
                # Normalize: convert negative BM25 to positive score (0-1)
                normalized_score = max(0.0, min(1.0, 1.0 / (1.0 + abs(bm25_score))))
                results.append({
                    "chunk_id": row.chunk_id,
                    "text": row.text,
                    "document_id": row.document_id,
                    "score": normalized_score,
                })
            return results
        except Exception as e:
            logger.warning(f"[KeywordSearch] FTS5 search failed, falling back to LIKE: {e}")
            return self._search_like(db, user_id, query, top_k, document_id)
    
    def _search_postgresql(
        self,
        db: Session,
        user_id: int,
        query: str,
        top_k: int,
        document_id: Optional[int]
    ) -> List[Dict[str, Any]]:
        """Search using PostgreSQL full-text search."""
        # Extract keywords for PostgreSQL tsquery
        keywords = self.extract_keywords(query)
        tsquery = " | ".join(keywords)
        
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
        
        params = {"user_id": user_id, "query": query}
        
        if document_id:
            sql += " AND dc.document_id = :document_id"
            params["document_id"] = document_id
        
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
        document_id: Optional[int]
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
        
        params = {"user_id": user_id}
        for i, keyword in enumerate(keywords):
            params[f"keyword{i}"] = f"%{keyword}%"
        
        if document_id:
            sql += " AND dc.document_id = :document_id"
            params["document_id"] = document_id
        
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
