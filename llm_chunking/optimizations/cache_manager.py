"""
Structure caching for document chunking.

Caches detected document structures in Redis + in-memory fallback
for instant reuse without re-analysis.
"""

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# In-memory fallback cache
_memory_cache: Dict[str, Dict[str, Any]] = {}


class CacheManager:
    """
    Cache manager for document structures.
    
    Uses Redis for distributed caching with in-memory fallback.
    """
    
    CACHE_PREFIX = "llm_chunking:structure:"
    CACHE_TTL = 86400 * 7  # 7 days
    
    def __init__(self, redis_client=None):
        """
        Initialize cache manager.
        
        Args:
            redis_client: Optional Redis client (uses services.redis_client if None)
        """
        self.redis_client = redis_client
        if redis_client is None:
            try:
                from services.redis_client import get_redis_client
                self.redis_client = get_redis_client()
            except Exception as e:
                logger.warning(f"Redis client not available, using memory cache only: {e}")
                self.redis_client = None
    
    def _get_cache_key(self, document_id: str) -> str:
        """Get cache key for document."""
        return f"{self.CACHE_PREFIX}{document_id}"
    
    def get_structure(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached structure.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Cached structure dict or None
        """
        cache_key = self._get_cache_key(document_id)
        
        # Try Redis first
        if self.redis_client:
            try:
                from services.redis_client import RedisOperations
                cached_data = RedisOperations.get(cache_key)
                if cached_data:
                    if isinstance(cached_data, bytes):
                        cached_data = cached_data.decode('utf-8')
                    structure = json.loads(cached_data)
                    logger.info(f"Retrieved structure from Redis cache: {document_id}")
                    return structure
            except Exception as e:
                logger.warning(f"Redis cache get failed: {e}, trying memory cache")
        
        # Fallback to memory cache
        if document_id in _memory_cache:
            logger.info(f"Retrieved structure from memory cache: {document_id}")
            return _memory_cache[document_id]
        
        return None
    
    def set_structure(
        self,
        document_id: str,
        structure: Dict[str, Any],
        ttl: Optional[int] = None
    ):
        """
        Cache structure.
        
        Args:
            document_id: Document identifier
            structure: Structure dict to cache
            ttl: Optional TTL in seconds (default: 7 days)
        """
        cache_key = self._get_cache_key(document_id)
        ttl = ttl or self.CACHE_TTL
        
        # Add timestamp
        structure["cached_at"] = datetime.now().isoformat()
        
        # Try Redis first
        if self.redis_client:
            try:
                from services.redis_client import RedisOperations
                structure_json = json.dumps(structure)
                RedisOperations.set_with_ttl(cache_key, structure_json, ttl)
                logger.info(f"Cached structure in Redis: {document_id} (TTL: {ttl}s)")
            except Exception as e:
                logger.warning(f"Redis cache set failed: {e}, using memory cache")
        
        # Always update memory cache as fallback
        _memory_cache[document_id] = structure
        logger.info(f"Cached structure in memory: {document_id}")
    
    def delete_structure(self, document_id: str):
        """
        Delete cached structure.
        
        Args:
            document_id: Document identifier
        """
        cache_key = self._get_cache_key(document_id)
        
        # Delete from Redis
        if self.redis_client:
            try:
                from services.redis_client import RedisOperations
                RedisOperations.delete(cache_key)
                logger.info(f"Deleted structure from Redis cache: {document_id}")
            except Exception as e:
                logger.warning(f"Redis cache delete failed: {e}")
        
        # Delete from memory cache
        if document_id in _memory_cache:
            del _memory_cache[document_id]
            logger.info(f"Deleted structure from memory cache: {document_id}")
    
    def clear_cache(self):
        """Clear all cached structures."""
        # Clear memory cache
        _memory_cache.clear()
        logger.info("Cleared memory cache")
        
        # Clear Redis cache (if available)
        if self.redis_client:
            try:
                from services.redis_client import get_redis
                redis = get_redis()
                if redis:
                    # Get all keys with prefix
                    pattern = f"{self.CACHE_PREFIX}*"
                    keys = redis.keys(pattern)
                    if keys:
                        redis.delete(*keys)
                        logger.info(f"Cleared {len(keys)} structures from Redis cache")
            except Exception as e:
                logger.warning(f"Redis cache clear failed: {e}")
