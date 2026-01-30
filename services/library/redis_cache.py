"""
Redis Cache for Library Service
================================

Provides Redis-backed caching for library operations to reduce database load
and improve performance in multi-server deployments.

Uses cache-aside pattern:
- Read: Check Redis first, fallback to database, then cache result
- Write: Update database first, then invalidate/update Redis cache

Key Schema:
- library:doc:{document_id} -> JSON document metadata (TTL: 10 minutes)
- library:danmaku:doc:{document_id}:page:{page_number} -> JSON danmaku list (TTL: 5 minutes)
- library:danmaku:doc:{document_id}:text:{selected_text_hash} -> JSON danmaku list (TTL: 5 minutes)
- library:danmaku:recent:{limit} -> JSON recent danmaku list (TTL: 2 minutes)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import json
import logging
import hashlib
from typing import Optional, Dict, Any, List

from services.redis.redis_client import is_redis_available, RedisOps

logger = logging.getLogger(__name__)

# Redis key prefixes
DOCUMENT_KEY_PREFIX = "library:doc:"
DANMAKU_DOC_PAGE_PREFIX = "library:danmaku:doc:"
DANMAKU_DOC_TEXT_PREFIX = "library:danmaku:doc:text:"
DANMAKU_RECENT_PREFIX = "library:danmaku:recent:"

# Cache TTLs (in seconds)
DOCUMENT_CACHE_TTL = 600  # 10 minutes - document metadata changes infrequently
DANMAKU_CACHE_TTL = 300  # 5 minutes - danmaku can change frequently
DANMAKU_RECENT_TTL = 120  # 2 minutes - recent danmaku changes very frequently


class LibraryRedisCache:
    """
    Redis cache for library operations.
    
    Provides caching layer to reduce database load, especially for:
    - Document metadata (frequently accessed during image serving)
    - Danmaku lists (read-heavy, can be cached per document/page)
    - Document listings (can be cached with search invalidation)
    """
    
    def __init__(self):
        """Initialize library Redis cache."""
        self._use_redis = is_redis_available()
        if self._use_redis:
            logger.info("[LibraryCache] Redis cache enabled")
        else:
            logger.info("[LibraryCache] Redis unavailable, using database only")
    
    def _use_cache(self) -> bool:
        """Check if Redis cache should be used."""
        return self._use_redis
    
    def _get_document_key(self, document_id: int) -> str:
        """Get Redis key for document metadata."""
        return f"{DOCUMENT_KEY_PREFIX}{document_id}"
    
    def _get_danmaku_doc_page_key(self, document_id: int, page_number: int) -> str:
        """Get Redis key for danmaku by document and page."""
        return f"{DANMAKU_DOC_PAGE_PREFIX}{document_id}:page:{page_number}"
    
    def _get_danmaku_doc_text_key(self, document_id: int, selected_text: str) -> str:
        """Get Redis key for danmaku by document and selected text."""
        # Hash selected text to create shorter key
        text_hash = hashlib.md5(selected_text.encode('utf-8')).hexdigest()[:16]
        return f"{DANMAKU_DOC_TEXT_PREFIX}{document_id}:text:{text_hash}"
    
    def _get_danmaku_recent_key(self, limit: int) -> str:
        """Get Redis key for recent danmaku."""
        return f"{DANMAKU_RECENT_PREFIX}{limit}"
    
    def get_document_metadata(self, document_id: int) -> Optional[Dict[str, Any]]:
        """
        Get document metadata from Redis cache.
        
        Args:
            document_id: Document ID
            
        Returns:
            Cached metadata dict or None if not cached
        """
        if not self._use_cache():
            return None
        
        try:
            key = self._get_document_key(document_id)
            cached = RedisOps.get(key)
            
            if cached:
                try:
                    data = json.loads(cached)
                    logger.debug("[LibraryCache] Cache hit for document %s", document_id)
                    return data
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning("[LibraryCache] Corrupted cache for document %s: %s", document_id, e)
                    # Invalidate corrupted entry
                    RedisOps.delete(key)
                    return None
        except Exception as e:
            logger.warning("[LibraryCache] Redis error getting document %s: %s", document_id, e)
            return None
        
        return None
    
    def cache_document_metadata(self, document_id: int, metadata: Dict[str, Any]) -> bool:
        """
        Cache document metadata in Redis.
        
        Args:
            document_id: Document ID
            metadata: Metadata dict to cache
            
        Returns:
            True if cached successfully, False otherwise
        """
        if not self._use_cache():
            return False
        
        try:
            key = self._get_document_key(document_id)
            data = json.dumps(metadata, default=str)
            success = RedisOps.set_with_ttl(key, data, DOCUMENT_CACHE_TTL)
            
            if success:
                logger.debug("[LibraryCache] Cached document metadata for %s", document_id)
            return success
        except Exception as e:
            logger.warning("[LibraryCache] Redis error caching document %s: %s", document_id, e)
            return False
    
    def invalidate_document(self, document_id: int) -> bool:
        """
        Invalidate document cache and related caches.
        
        Args:
            document_id: Document ID
            
        Returns:
            True if invalidated successfully
        """
        if not self._use_cache():
            return False
        
        try:
            # Delete document metadata
            doc_key = self._get_document_key(document_id)
            RedisOps.delete(doc_key)
            
            # Note: Danmaku caches are TTL-based and will expire naturally
            # For immediate invalidation, we could use pattern matching, but it's expensive
            # TTL-based expiration is sufficient for most cases
            
            logger.debug("[LibraryCache] Invalidated cache for document %s", document_id)
            return True
        except Exception as e:
            logger.warning("[LibraryCache] Redis error invalidating document %s: %s", document_id, e)
            return False
    
    def get_danmaku_list(
        self,
        document_id: int,
        page_number: Optional[int] = None,
        selected_text: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached danmaku list.
        
        Args:
            document_id: Document ID
            page_number: Optional page number filter
            selected_text: Optional selected text filter
            
        Returns:
            Cached danmaku list or None if not cached
        """
        if not self._use_cache():
            return None
        
        try:
            if page_number is not None:
                key = self._get_danmaku_doc_page_key(document_id, page_number)
            elif selected_text:
                key = self._get_danmaku_doc_text_key(document_id, selected_text)
            else:
                # No cache key for unfiltered danmaku (too variable)
                return None
            
            cached = RedisOps.get(key)
            
            if cached:
                try:
                    data = json.loads(cached)
                    logger.debug("[LibraryCache] Cache hit for danmaku doc=%s", document_id)
                    return data
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning("[LibraryCache] Corrupted danmaku cache: %s", e)
                    RedisOps.delete(key)
                    return None
        except Exception as e:
            logger.warning("[LibraryCache] Redis error getting danmaku: %s", e)
            return None
        
        return None
    
    def cache_danmaku_list(
        self,
        document_id: int,
        danmaku_list: List[Dict[str, Any]],
        page_number: Optional[int] = None,
        selected_text: Optional[str] = None
    ) -> bool:
        """
        Cache danmaku list.
        
        Args:
            document_id: Document ID
            danmaku_list: List of danmaku dicts
            page_number: Optional page number filter
            selected_text: Optional selected text filter
            
        Returns:
            True if cached successfully
        """
        if not self._use_cache():
            return False
        
        try:
            if page_number is not None:
                key = self._get_danmaku_doc_page_key(document_id, page_number)
            elif selected_text:
                key = self._get_danmaku_doc_text_key(document_id, selected_text)
            else:
                # Don't cache unfiltered danmaku (too variable)
                return False
            
            data = json.dumps(danmaku_list, default=str)
            success = RedisOps.set_with_ttl(key, data, DANMAKU_CACHE_TTL)
            
            if success:
                logger.debug("[LibraryCache] Cached danmaku list doc=%s", document_id)
            return success
        except Exception as e:
            logger.warning("[LibraryCache] Redis error caching danmaku: %s", e)
            return False
    
    def invalidate_danmaku(self, document_id: int) -> bool:
        """
        Invalidate danmaku caches for a document.
        
        Note: This uses TTL-based expiration. For immediate invalidation,
        we would need pattern matching (expensive), so TTL is preferred.
        
        Args:
            document_id: Document ID
            
        Returns:
            True if operation succeeded
        """
        # TTL-based expiration is sufficient - danmaku caches expire in 5 minutes
        # Immediate invalidation would require pattern matching which is expensive
        logger.debug("[LibraryCache] Danmaku cache will expire via TTL for document %s", document_id)
        return True
    
    def get_recent_danmaku(self, limit: int) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached recent danmaku list.
        
        Args:
            limit: Limit for recent danmaku
            
        Returns:
            Cached list or None if not cached
        """
        if not self._use_cache():
            return None
        
        try:
            key = self._get_danmaku_recent_key(limit)
            cached = RedisOps.get(key)
            
            if cached:
                try:
                    data = json.loads(cached)
                    logger.debug("[LibraryCache] Cache hit for recent danmaku")
                    return data
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning("[LibraryCache] Corrupted recent danmaku cache: %s", e)
                    RedisOps.delete(key)
                    return None
        except Exception as e:
            logger.warning("[LibraryCache] Redis error getting recent danmaku: %s", e)
            return None
        
        return None
    
    def cache_recent_danmaku(self, limit: int, danmaku_list: List[Dict[str, Any]]) -> bool:
        """
        Cache recent danmaku list.
        
        Args:
            limit: Limit for recent danmaku
            danmaku_list: List of danmaku dicts
            
        Returns:
            True if cached successfully
        """
        if not self._use_cache():
            return False
        
        try:
            key = self._get_danmaku_recent_key(limit)
            data = json.dumps(danmaku_list, default=str)
            success = RedisOps.set_with_ttl(key, data, DANMAKU_RECENT_TTL)
            
            if success:
                logger.debug("[LibraryCache] Cached recent danmaku")
            return success
        except Exception as e:
            logger.warning("[LibraryCache] Redis error caching recent danmaku: %s", e)
            return False
