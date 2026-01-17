from typing import List, Optional
import base64
import hashlib
import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import numpy as np

from clients.dashscope_embedding import DashScopeEmbeddingClient
from config.settings import config
from models.knowledge_space import DocumentChunk, Embedding
from services.redis.redis_client import get_redis, is_redis_available

"""
Embedding Cache Service for Knowledge Space
Author: lycosa9527
Made by: MindSpring Team

Implements embedding caching following Dify's approach:
- Document embeddings: SQLite (permanent cache)
- Query embeddings: Redis (10min TTL)

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""



logger = logging.getLogger(__name__)


class EmbeddingCache:
    """
    Embedding cache service following Dify's approach.

    - Document embeddings: Stored in SQLite (permanent, hash-based lookup)
    - Query embeddings: Stored in Redis (10min TTL)
    """

    def __init__(self, embedding_client: DashScopeEmbeddingClient):
        """
        Initialize embedding cache.

        Args:
            embedding_client: DashScope embedding client
        """
        self.embedding_client = embedding_client
        self.query_cache_ttl = 600  # 10 minutes

    def generate_text_hash(self, text: str) -> str:
        """Generate hash for text (for cache key)."""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def get_document_embedding(self, db: Session, text: str) -> Optional[List[float]]:
        """
        Get document embedding from SQLite cache (permanent cache).

        Args:
            db: Database session
            text: Text to embed

        Returns:
            Embedding vector or None if not cached
        """
        text_hash = self.generate_text_hash(text)
        model_name = config.DASHSCOPE_EMBEDDING_MODEL or 'text-embedding-v4'
        provider_name = 'dashscope'

        try:
            embedding_record = db.query(Embedding).filter_by(
                model_name=model_name,
                provider_name=provider_name,
                hash=text_hash
            ).first()

            if embedding_record:
                logger.debug(f"[EmbeddingCache] Document embedding cache hit for hash {text_hash[:8]}...")
                return embedding_record.get_embedding()
        except Exception as e:
            logger.warning(f"[EmbeddingCache] Failed to get document embedding from cache: {e}")

        return None

    def cache_document_embedding(self, db: Session, text: str, embedding: List[float]) -> None:
        """
        Cache document embedding in SQLite (permanent cache).

        Args:
            db: Database session
            text: Text that was embedded
            embedding: Embedding vector
        """
        text_hash = self.generate_text_hash(text)
        model_name = config.DASHSCOPE_EMBEDDING_MODEL or 'text-embedding-v4'
        provider_name = 'dashscope'

        try:
            # Check if already exists
            existing = db.query(Embedding).filter_by(
                model_name=model_name,
                provider_name=provider_name,
                hash=text_hash
            ).first()

            if existing:
                logger.debug(f"[EmbeddingCache] Embedding already cached for hash {text_hash[:8]}...")
                return

            # Create new embedding cache record
            embedding_record = Embedding(
                model_name=model_name,
                provider_name=provider_name,
                hash=text_hash
            )
            embedding_record.set_embedding(embedding)

            db.add(embedding_record)
            db.commit()
            logger.debug(f"[EmbeddingCache] Cached document embedding for hash {text_hash[:8]}...")

        except IntegrityError:
            # Race condition: another process cached it first
            db.rollback()
            logger.debug(f"[EmbeddingCache] Embedding already cached (race condition) for hash {text_hash[:8]}...")
        except Exception as e:
            db.rollback()
            logger.warning(f"[EmbeddingCache] Failed to cache document embedding: {e}")

    def get_query_embedding(self, query: str) -> Optional[List[float]]:
        """
        Get query embedding from Redis cache.

        Args:
            query: Query text

        Returns:
            Embedding vector or None if not cached
        """
        if not is_redis_available():
            return None

        redis = get_redis()
        if not redis:
            return None

        try:
            query_hash = self.generate_text_hash(query)
            model_name = config.DASHSCOPE_EMBEDDING_MODEL or 'text-embedding-v4'
            dimensions = config.EMBEDDING_DIMENSIONS
            dim_suffix = f":{dimensions}" if dimensions else ""
            cache_key = f"query_embedding:dashscope:{model_name}{dim_suffix}:{query_hash}"

            cached = redis.get(cache_key)
            if cached:
                # Refresh TTL
                redis.expire(cache_key, self.query_cache_ttl)

                # Decode from base64
                decoded_bytes = base64.b64decode(cached)
                decoded = np.frombuffer(decoded_bytes, dtype=np.float32)
                return [float(x) for x in decoded]
        except Exception as e:
            logger.warning(f"[EmbeddingCache] Failed to get query embedding from cache: {e}")

        return None

    def cache_query_embedding(self, query: str, embedding: List[float]) -> None:
        """
        Cache query embedding in Redis (10min TTL).

        Args:
            query: Query text
            embedding: Embedding vector
        """
        if not is_redis_available():
            return

        redis = get_redis()
        if not redis:
            return

        try:
            query_hash = self.generate_text_hash(query)
            model_name = config.DASHSCOPE_EMBEDDING_MODEL or 'text-embedding-v4'
            dimensions = config.EMBEDDING_DIMENSIONS
            dim_suffix = f":{dimensions}" if dimensions else ""
            cache_key = f"query_embedding:dashscope:{model_name}{dim_suffix}:{query_hash}"

            # Encode to base64
            embedding_array = np.array(embedding, dtype=np.float32)
            encoded = base64.b64encode(embedding_array.tobytes()).decode('utf-8')

            # Store with TTL
            redis.setex(cache_key, self.query_cache_ttl, encoded)
        except Exception as e:
            logger.warning(f"[EmbeddingCache] Failed to cache query embedding: {e}")

    def embed_query_cached(self, query: str) -> List[float]:
        """
        Embed query with caching and normalization.

        Args:
            query: Query text

        Returns:
            Normalized embedding vector
        """
        # Check cache first
        cached = self.get_query_embedding(query)
        if cached:
            logger.debug(f"[EmbeddingCache] Query embedding cache hit")
            # Validate cached embedding
            if self._validate_embedding(cached):
                return cached
            else:
                logger.warning(f"[EmbeddingCache] Cached embedding invalid, regenerating")

        # Generate embedding (already normalized by embedding_client)
        embedding = self.embedding_client.embed_query(query)

        # Validate embedding
        if not self._validate_embedding(embedding):
            raise ValueError("Generated embedding is invalid (contains NaN/Inf or zero norm)")

        # Cache it
        self.cache_query_embedding(query, embedding)

        return embedding

    def _validate_embedding(self, embedding: List[float]) -> bool:
        """
        Validate embedding vector (check for NaN, Inf, zero norm).

        Args:
            embedding: Embedding vector

        Returns:
            True if valid, False otherwise
        """
        try:
            embedding_array = np.array(embedding, dtype=np.float32)

            # Check for NaN or Inf
            if np.isnan(embedding_array).any() or np.isinf(embedding_array).any():
                return False

            # Check for zero norm
            norm = np.linalg.norm(embedding_array)
            if norm == 0:
                return False

            return True
        except Exception as e:
            logger.warning(f"[EmbeddingCache] Failed to validate embedding: {e}")
            return False


# Global instance
_embedding_cache: Optional[EmbeddingCache] = None


def get_embedding_cache() -> EmbeddingCache:
    """Get global embedding cache instance."""
    global _embedding_cache
    if _embedding_cache is None:
        from clients.dashscope_embedding import get_embedding_client
        _embedding_cache = EmbeddingCache(get_embedding_client())
    return _embedding_cache
