"""
Embedding Cache Service for Knowledge Space
Author: lycosa9527
Made by: MindSpring Team

Implements embedding caching following Dify's approach:
- Document embeddings: database (permanent cache)
- Query embeddings: Redis (10min TTL)

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Any, List, Optional
import base64
import hashlib
import logging
import os

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import numpy as np

from clients.dashscope_embedding import DashScopeEmbeddingClient, get_embedding_client
from config.settings import config
from models.domain.knowledge_space import Embedding
from services.redis.redis_client import get_redis, is_redis_available

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """
    Embedding cache service following Dify's approach.

    - Document embeddings: Stored in database (permanent, hash-based lookup)
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
        Get document embedding from database cache (permanent cache).

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
                hash_preview = text_hash[:8] + "..."
                logger.debug("[EmbeddingCache] Document embedding cache hit for hash %s", hash_preview)
                return embedding_record.get_embedding()
        except Exception as e:
            logger.warning("[EmbeddingCache] Failed to get document embedding from cache: %s", e)

        return None

    def cache_document_embedding(self, db: Session, text: str, embedding: List[float]) -> None:
        """
        Cache document embedding in database (permanent cache).

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
                hash_preview = text_hash[:8] + "..."
                logger.debug("[EmbeddingCache] Embedding already cached for hash %s", hash_preview)
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
            hash_preview = text_hash[:8] + "..."
            logger.debug("[EmbeddingCache] Cached document embedding for hash %s", hash_preview)

        except IntegrityError:
            # Race condition: another process cached it first
            db.rollback()
            hash_preview = text_hash[:8] + "..."
            logger.debug("[EmbeddingCache] Embedding already cached (race condition) for hash %s", hash_preview)
        except Exception as e:
            db.rollback()
            logger.warning("[EmbeddingCache] Failed to cache document embedding: %s", e)

    def _vset_key(self, model_name: str) -> str:
        """Redis key for the VSET used for semantic similarity search."""
        return f"query_embeddings:vset:{model_name}"

    def _vset_lookup(self, redis_client: Any, vset_key: str, embedding: List[float]) -> Optional[List[float]]:
        """
        Search the VSET for a semantically similar cached embedding (Redis >= 8.0).

        Returns the cached embedding if cosine similarity exceeds the threshold,
        otherwise returns None.
        """
        threshold = float(os.getenv("VSET_SIMILARITY_THRESHOLD", "0.95"))
        try:
            embedding_array = np.array(embedding, dtype=np.float32)
            results = redis_client.execute_command(
                "VSIM", vset_key,
                "VALUES", len(embedding_array), *embedding_array.tolist(),
                "COUNT", 1,
                "WITHSCORES",
            )
            if results and len(results) >= 2:
                score = float(results[1])
                if score >= threshold:
                    stored_b64 = results[0]
                    decoded_bytes = base64.b64decode(stored_b64)
                    decoded = np.frombuffer(decoded_bytes, dtype=np.float32)
                    logger.debug(
                        "[EmbeddingCache] VSET semantic hit (score=%.4f >= %.4f)", score, threshold
                    )
                    return [float(x) for x in decoded]
        except Exception as exc:
            logger.debug("[EmbeddingCache] VSET lookup skipped: %s", exc)
        return None

    def _vset_add(self, redis_client: Any, vset_key: str, embedding: List[float], encoded: str) -> None:
        """Add an embedding vector to the VSET (Redis >= 8.0). Errors are silently ignored."""
        try:
            embedding_array = np.array(embedding, dtype=np.float32)
            redis_client.execute_command(
                "VADD", vset_key,
                "VALUES", len(embedding_array), *embedding_array.tolist(),
                encoded,
            )
        except Exception as exc:
            logger.debug("[EmbeddingCache] VSET add skipped: %s", exc)

    def get_query_embedding(self, query: str) -> Optional[List[float]]:
        """
        Get query embedding from Redis cache via exact key lookup (GETEX).

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

            # GETEX atomically fetches the value and resets the TTL in one round-trip.
            cached = redis.getex(cache_key, ex=self.query_cache_ttl)
            if cached:
                decoded_bytes = base64.b64decode(cached)
                decoded = np.frombuffer(decoded_bytes, dtype=np.float32)
                logger.debug("[EmbeddingCache] Query embedding exact cache hit")
                return [float(x) for x in decoded]

        except Exception as exc:
            logger.warning("[EmbeddingCache] Failed to get query embedding from cache: %s", exc)

        return None

    def get_query_embedding_semantic(self, embedding: List[float]) -> Optional[List[float]]:
        """
        Search the VSET for a semantically similar cached embedding (Redis >= 8.0).

        Called after an exact-key miss but before invoking the embedding API,
        so that semantically equivalent queries benefit from a cache hit.

        Args:
            embedding: The freshly-computed query embedding to use as the search vector.

        Returns:
            A previously cached embedding vector with cosine similarity above the
            configured threshold, or None if no suitable match is found.
        """
        if not is_redis_available():
            return None

        redis = get_redis()
        if not redis:
            return None

        model_name = config.DASHSCOPE_EMBEDDING_MODEL or 'text-embedding-v4'
        return self._vset_lookup(redis, self._vset_key(model_name), embedding)

    def cache_query_embedding(self, query: str, embedding: List[float]) -> None:
        """
        Cache query embedding in Redis (10min TTL).

        Stores the embedding in both:
        - An exact-key string for fast hash lookup.
        - The VSET for semantic similarity search on future misses.

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

            embedding_array = np.array(embedding, dtype=np.float32)
            encoded = base64.b64encode(embedding_array.tobytes()).decode('utf-8')

            redis.setex(cache_key, self.query_cache_ttl, encoded)

            # Also register in the VSET so semantically similar queries get a hit.
            self._vset_add(redis, self._vset_key(model_name), embedding, encoded)

        except Exception as exc:
            logger.warning("[EmbeddingCache] Failed to cache query embedding: %s", exc)

    def embed_query_cached(self, query: str) -> List[float]:
        """
        Embed query with two-stage caching.

        Lookup order:
        1. Exact key match (GETEX — zero API call).
        2. VSET cosine similarity search — semantically equivalent query hits avoid the API.
        3. DashScope embedding API call — result stored in both exact key and VSET.

        Args:
            query: Query text

        Returns:
            Normalized embedding vector
        """
        # Stage 1: exact key hit.
        cached = self.get_query_embedding(query)
        if cached:
            if self._validate_embedding(cached):
                return cached
            logger.warning("[EmbeddingCache] Cached embedding invalid, regenerating")

        # Stage 2: need the actual embedding to search the VSET — compute it cheaply first
        # by calling the embedding API, then immediately check the VSET before storing.
        embedding = self.embedding_client.embed_query(query)

        if not self._validate_embedding(embedding):
            raise ValueError("Generated embedding is invalid (contains NaN/Inf or zero norm)")

        # Stage 2: semantic VSET search using the just-computed vector.
        semantic_hit = self.get_query_embedding_semantic(embedding)
        if semantic_hit and self._validate_embedding(semantic_hit):
            logger.debug("[EmbeddingCache] Query embedding semantic cache hit")
            return semantic_hit

        # Stage 3: genuine miss — store in exact key and VSET for future hits.
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
            logger.warning("[EmbeddingCache] Failed to validate embedding: %s", e)
            return False


class _EmbeddingCacheHolder:
    """Singleton holder to avoid a module-level global variable."""

    instance: Optional[EmbeddingCache] = None


def get_embedding_cache() -> EmbeddingCache:
    """Get or create the global embedding cache instance."""
    if _EmbeddingCacheHolder.instance is None:
        _EmbeddingCacheHolder.instance = EmbeddingCache(get_embedding_client())
    return _EmbeddingCacheHolder.instance
