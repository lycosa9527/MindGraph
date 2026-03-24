"""
Redis Diagram Cache
====================

Shared diagram storage using Redis with database persistence (write-through pattern).
Provides fast reads via Redis cache, immediate durability via database writes.

Features:
- Write-through pattern: Database first, then Redis cache (immediate durability)
- Redis for fast reads (cache-aside pattern)
- Database fallback for cache misses
- 20 diagrams per user limit

Key Schema:
- diagram:{user_id}:{diagram_id} -> JSON diagram data
- diagrams:user:{user_id}:meta -> Sorted set (score=updated_at, member=diagram_id)
- diagrams:user:{user_id}:list -> Cached list for fast fetching

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import json
import logging
import time
import uuid
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.dialects.postgresql import insert as pg_insert

from services.redis.redis_client import is_redis_available, get_redis
from services.redis.cache._redis_diagram_cache_helpers import (
    _redis_json_set_paths, count_diagrams_from_db,
    CACHE_TTL, SYNC_INTERVAL, SYNC_BATCH_SIZE, MAX_PER_USER, MAX_SPEC_SIZE_KB,
    DIAGRAM_KEY, USER_META_KEY, USER_LIST_KEY, DIRTY_SET_KEY,
)
from config.database import SessionLocal
from models.domain.diagrams import Diagram

logger = logging.getLogger(__name__)



class RedisDiagramCache:
    """
    Redis-based diagram caching with PostgreSQL persistence (write-through pattern).

    Pattern:
    - Write-through: Database first, then Redis cache (immediate durability)
    - Cache-aside: Redis for fast reads, database fallback for cache misses
    - Requires PostgreSQL: uses pg_insert with RETURNING and JSONB spec column
    """

    def __init__(self):
        self._total_synced: int = 0
        self._total_errors: int = 0
        logger.info(
            "[DiagramCache] Initialized: cache_ttl=%ss, max_per_user=%s (write-through pattern)",
            CACHE_TTL, MAX_PER_USER
        )

    def _use_redis(self) -> bool:
        """Check if Redis is available."""
        return is_redis_available()

    def _get_diagram_key(self, user_id: int, diagram_id: str) -> str:
        """Get Redis key for a diagram."""
        return DIAGRAM_KEY.format(user_id=user_id, diagram_id=diagram_id)

    def _get_user_meta_key(self, user_id: int) -> str:
        """Get Redis key for user's diagram metadata."""
        return USER_META_KEY.format(user_id=user_id)

    def _get_user_list_key(self, user_id: int) -> str:
        """Get Redis key for user's cached diagram list."""
        return USER_LIST_KEY.format(user_id=user_id)


    async def count_user_diagrams(self, user_id: int) -> int:
        """
        Count user's diagrams (non-deleted).

        Uses Redis only when the meta sorted-set key exists, ensuring
        an evicted / expired key does not report 0 and bypass the quota.
        Falls back to database when Redis is unavailable or key is missing.
        """
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    meta_key = self._get_user_meta_key(user_id)
                    if redis.exists(meta_key):
                        count = redis.zcard(meta_key)
                        if count is not None:
                            return count
                except Exception as exc:
                    logger.warning("[DiagramCache] Redis count failed: %s", exc)

        return await count_diagrams_from_db(user_id)

    async def save_diagram(
        self,
        user_id: int,
        diagram_id: Optional[str],
        title: str,
        diagram_type: str,
        spec: Dict[str, Any],
        language: str = 'zh',
        thumbnail: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Save diagram using write-through pattern: Database first, then Redis cache.

        Write-through pattern ensures immediate durability:
        1. Write to database (PostgreSQL)
        2. Then update Redis cache for fast reads

        Args:
            user_id: User ID
            diagram_id: Diagram UUID (None for new diagrams)
            title: Diagram title
            diagram_type: Type of diagram
            spec: Diagram specification
            language: Language code
            thumbnail: Base64 thumbnail

        Returns:
            Tuple of (success, diagram_id, error_message)
        """
        # Validate spec size — serialize once for the byte-length check only.
        spec_json = json.dumps(spec)
        spec_size_kb = len(spec_json.encode('utf-8')) / 1024
        if spec_size_kb > MAX_SPEC_SIZE_KB:
            return False, None, f"Diagram spec too large ({spec_size_kb:.1f}KB > {MAX_SPEC_SIZE_KB}KB)"
        # spec_json is not used further; SQLAlchemy handles JSONB serialization.

        is_new = diagram_id is None

        # Check user quota for new diagrams
        if is_new:
            current_count = await self.count_user_diagrams(user_id)
            if current_count >= MAX_PER_USER:
                return False, None, f"Diagram limit reached ({MAX_PER_USER} max)"
            # Generate UUID for new diagram
            diagram_id = str(uuid.uuid4())

        now = datetime.utcnow()
        now_ts = now.timestamp()

        # For updates, get existing data to preserve created_at and is_pinned
        existing_data = None
        if not is_new:
            existing_data = await self.get_diagram(user_id, diagram_id)
            if not existing_data:
                return False, None, "Diagram not found"

        # Write-through: Write to database FIRST.
        # Pass the dict directly — SQLAlchemy serialises JSONB columns automatically.
        if is_new:
            db_success = await self._create_in_database(
                user_id, diagram_id, title, diagram_type, spec, language, thumbnail, now
            )
        else:
            db_success = await self._update_in_database(
                diagram_id, user_id, title, spec, thumbnail, now
            )

        if not db_success:
            return False, diagram_id, "Failed to save diagram to database"

        # Build diagram data for Redis cache
        diagram_data = {
            'id': diagram_id,
            'user_id': user_id,
            'title': title,
            'diagram_type': diagram_type,
            'spec': spec,
            'language': language,
            'thumbnail': thumbnail,
            'created_at': existing_data['created_at'] if existing_data else now.isoformat(),
            'updated_at': now.isoformat(),
            'is_deleted': False,
            'is_pinned': existing_data.get('is_pinned', False) if existing_data else False
        }

        # Then update Redis cache — all four Redis operations in a single pipeline.
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    diagram_key = self._get_diagram_key(user_id, diagram_id)
                    meta_key = self._get_user_meta_key(user_id)
                    list_key = self._get_user_list_key(user_id)

                    pipe = redis.pipeline()
                    # DELETE before JSON.SET to clear any stale key with wrong type.
                    pipe.delete(diagram_key)
                    pipe.json().set(diagram_key, "$", diagram_data)
                    pipe.expire(diagram_key, CACHE_TTL)
                    pipe.zadd(meta_key, {str(diagram_id): now_ts})
                    pipe.expire(meta_key, CACHE_TTL)
                    pipe.delete(list_key)
                    pipe.execute()

                    action = 'Created' if is_new else 'Updated'
                    logger.debug(
                        "[DiagramCache] %s diagram %s for user %s (write-through)",
                        action, diagram_id, user_id
                    )
                except Exception as e:
                    logger.warning("[DiagramCache] Redis cache update failed (diagram saved to database): %s", e)

        return True, diagram_id, None

    async def _create_in_database(
        self,
        user_id: int,
        diagram_id: str,
        title: str,
        diagram_type: str,
        spec: Dict[str, Any],
        language: str,
        thumbnail: Optional[str],
        created_at: datetime
    ) -> bool:
        """Create new diagram in database using INSERT … RETURNING to confirm in one query."""
        try:
            db = SessionLocal()
            try:
                stmt = (
                    pg_insert(Diagram)
                    .values(
                        id=diagram_id,
                        user_id=user_id,
                        title=title,
                        diagram_type=diagram_type,
                        spec=spec,
                        language=language,
                        thumbnail=thumbnail,
                        created_at=created_at,
                        updated_at=created_at,
                        is_deleted=False,
                    )
                    .returning(Diagram.id)
                )
                result = db.execute(stmt)
                db.commit()
                return result.scalar_one_or_none() == diagram_id
            except Exception as exc:
                db.rollback()
                logger.error("[DiagramCache] Database create failed: %s", exc)
                return False
            finally:
                db.close()
        except Exception as exc:
            logger.error("[DiagramCache] Database connection failed: %s", exc)
            return False

    async def _update_in_database(
        self,
        diagram_id: str,
        user_id: int,
        title: str,
        spec: Dict[str, Any],
        thumbnail: Optional[str],
        updated_at: datetime
    ) -> bool:
        """Update diagram in database."""
        try:
            db = SessionLocal()
            try:
                rows = db.query(Diagram).filter(
                    Diagram.id == diagram_id,
                    Diagram.user_id == user_id
                ).update(
                    {
                        Diagram.title: title,
                        Diagram.spec: spec,
                        Diagram.thumbnail: thumbnail,
                        Diagram.updated_at: updated_at,
                    },
                    synchronize_session=False
                )
                if rows == 0:
                    return False
                db.commit()
                return True
            except Exception as e:
                db.rollback()
                logger.error("[DiagramCache] Database update failed: %s", e)
                return False
            finally:
                db.close()
        except Exception as e:
            logger.error("[DiagramCache] Database connection failed: %s", e)
            return False

    async def get_diagram(self, user_id: int, diagram_id: str) -> Optional[Dict[str, Any]]:
        """
        Get diagram from Redis cache, fallback to database if not cached (cache-aside pattern).

        Returns diagram data or None if not found.
        """
        # Try Redis first (cache-aside pattern)
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    diagram_key = self._get_diagram_key(user_id, diagram_id)

                    # Pipeline JSON.GET + EXPIRE in a single round-trip.
                    pipe = redis.pipeline()
                    pipe.json().get(diagram_key, "$")
                    pipe.expire(diagram_key, CACHE_TTL)
                    results = pipe.execute()

                    json_result = results[0]
                    if json_result:
                        diagram = json_result[0] if isinstance(json_result, list) else json_result
                        if diagram is not None:
                            if not diagram.get('is_deleted', False):
                                return diagram
                            return None

                except Exception as exc:
                    logger.warning("[DiagramCache] Redis get failed: %s", exc)
                    # Stale key with wrong type — remove it so the cache-aside
                    # write in _load_from_database can succeed with JSON type.
                    try:
                        redis.delete(diagram_key)
                    except Exception:
                        pass

        # Fallback to database (cache-aside pattern)
        return await self._load_from_database(user_id, diagram_id)

    async def _load_from_database(self, user_id: int, diagram_id: str) -> Optional[Dict[str, Any]]:
        """Load diagram from database and cache in Redis."""
        try:
            db = SessionLocal()
            try:
                diagram = db.query(Diagram).filter(
                    Diagram.id == diagram_id,
                    Diagram.user_id == user_id,
                    Diagram.is_deleted.is_(False)
                ).first()

                if not diagram:
                    return None

                # JSONB columns are returned as dicts by SQLAlchemy.
                # Rows written before the JSONB migration may still carry a string value;
                # parse those transparently so callers always receive a dict.
                raw_spec = getattr(diagram, 'spec', None)
                if isinstance(raw_spec, dict):
                    spec = raw_spec
                elif isinstance(raw_spec, str):
                    try:
                        spec = json.loads(raw_spec)
                    except (ValueError, TypeError):
                        spec = {}
                else:
                    spec = {}

                created_at_val = getattr(diagram, 'created_at', None)
                updated_at_val = getattr(diagram, 'updated_at', None)
                diagram_data = {
                    'id': getattr(diagram, 'id', ''),
                    'user_id': getattr(diagram, 'user_id', 0),
                    'title': getattr(diagram, 'title', ''),
                    'diagram_type': getattr(diagram, 'diagram_type', ''),
                    'spec': spec,
                    'language': getattr(diagram, 'language', 'zh'),
                    'thumbnail': getattr(diagram, 'thumbnail', None),
                    'created_at': (
                        created_at_val.isoformat()
                        if created_at_val is not None else None
                    ),
                    'updated_at': (
                        updated_at_val.isoformat()
                        if updated_at_val is not None else None
                    ),
                    'is_deleted': getattr(diagram, 'is_deleted', False),
                    'is_pinned': getattr(diagram, 'is_pinned', False)
                }

                # Cache in Redis — JSON.SET + EXPIRE + ZADD in a single pipeline.
                if self._use_redis():
                    redis = get_redis()
                    if redis:
                        try:
                            diagram_key = self._get_diagram_key(user_id, diagram_id)
                            meta_key = self._get_user_meta_key(user_id)
                            updated_ts = (
                                updated_at_val.timestamp()
                                if updated_at_val is not None else time.time()
                            )

                            pipe = redis.pipeline()
                            # DELETE before JSON.SET to clear any stale key with wrong type.
                            pipe.delete(diagram_key)
                            pipe.json().set(diagram_key, "$", diagram_data)
                            pipe.expire(diagram_key, CACHE_TTL)
                            pipe.zadd(meta_key, {str(diagram_id): updated_ts})
                            pipe.expire(meta_key, CACHE_TTL)
                            pipe.execute()
                        except Exception as exc:
                            logger.debug("[DiagramCache] Redis cache-aside write failed: %s", exc)

                return diagram_data

            finally:
                db.close()
        except Exception as e:
            logger.error("[DiagramCache] Database load failed: %s", e)
            return None

    async def list_diagrams(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """
        List user's diagrams with pagination (cache-aside pattern).

        Checks Redis cache first. On cache miss, loads from database and caches in Redis.
        Pinned diagrams are sorted first, then by updated_at desc.

        Returns:
            Dict with 'diagrams', 'total', 'page', 'page_size', 'has_more', 'max_diagrams'
        """
        list_key = self._get_user_list_key(user_id)

        # Try Redis cache first
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    cached = redis.get(list_key)
                    if cached:
                        data = json.loads(cached)
                        items = data.get('items', [])
                        total = data.get('total', len(items))

                        # Paginate cached results
                        offset = (page - 1) * page_size
                        paginated = items[offset:offset + page_size]

                        return {
                            'diagrams': paginated,
                            'total': total,
                            'page': page,
                            'page_size': page_size,
                            'has_more': offset + len(paginated) < total,
                            'max_diagrams': MAX_PER_USER
                        }
                except Exception as e:
                    logger.warning("[DiagramCache] Redis list cache read failed: %s", e)

        # Cache miss: Load from database
        items = await self._load_list_from_database(user_id)

        # Sort: pinned first (desc), then by updated_at desc
        # Tuple key: (is_pinned descending, updated_at descending)
        items.sort(
            key=lambda x: (
                x.get('is_pinned', False),
                x.get('updated_at', '') or ''
            ),
            reverse=True
        )

        total = len(items)

        # Cache the full list in Redis
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    cache_data = {'items': items, 'total': total}
                    redis.setex(list_key, CACHE_TTL, json.dumps(cache_data))
                except Exception as e:
                    logger.warning("[DiagramCache] Redis list cache write failed: %s", e)

        # Paginate
        offset = (page - 1) * page_size
        paginated = items[offset:offset + page_size]

        return {
            'diagrams': paginated,
            'total': total,
            'page': page,
            'page_size': page_size,
            'has_more': offset + len(paginated) < total,
            'max_diagrams': MAX_PER_USER
        }

    async def _load_list_from_database(self, user_id: int) -> List[Dict[str, Any]]:
        """Load diagram list metadata from database."""
        try:
            db = SessionLocal()
            try:
                diagrams = db.query(Diagram).filter(
                    Diagram.user_id == user_id,
                    Diagram.is_deleted.is_(False)
                ).order_by(
                    desc(Diagram.is_pinned),
                    desc(Diagram.updated_at)
                ).all()

                items = []
                for d in diagrams:
                    updated_at_val = getattr(d, 'updated_at', None)
                    items.append({
                        'id': getattr(d, 'id', ''),
                        'title': getattr(d, 'title', ''),
                        'diagram_type': getattr(d, 'diagram_type', ''),
                        'thumbnail': getattr(d, 'thumbnail', None),
                        'updated_at': (
                            updated_at_val.isoformat()
                            if updated_at_val is not None else None
                        ),
                        'is_pinned': getattr(d, 'is_pinned', False)
                    })
                return items
            finally:
                db.close()
        except Exception as e:
            logger.error("[DiagramCache] Database list load failed: %s", e)
            return []


    async def delete_diagram(self, user_id: int, diagram_id: str) -> Tuple[bool, Optional[str]]:
        """
        Soft delete a diagram using write-through pattern: Database first, then Redis cache.

        Returns:
            Tuple of (success, error_message)
        """
        now = datetime.utcnow()

        # Write-through: Update database FIRST
        try:
            db = SessionLocal()
            try:
                diagram = db.query(Diagram).filter(
                    Diagram.id == diagram_id,
                    Diagram.user_id == user_id
                ).first()

                if not diagram:
                    return False, "Diagram not found"

                # If already deleted, return success (idempotent delete)
                if getattr(diagram, 'is_deleted', False):
                    return True, None

                db.query(Diagram).filter(
                    Diagram.id == diagram_id,
                    Diagram.user_id == user_id
                ).update(
                    {
                        Diagram.is_deleted: True,
                        Diagram.updated_at: now,
                    },
                    synchronize_session=False
                )
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error("[DiagramCache] Database delete failed: %s", e)
                return False, "Failed to delete diagram"
            finally:
                db.close()
        except Exception as e:
            logger.error("[DiagramCache] Database connection failed: %s", e)
            return False, "Database error"

        # Then update Redis cache
        diagram_key = self._get_diagram_key(user_id, diagram_id)
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    meta_key = self._get_user_meta_key(user_id)
                    list_key = self._get_user_list_key(user_id)

                    # Attempt targeted JSON field update — avoids reading the full blob.
                    # If the key doesn't exist as JSON (cache miss) we skip the update;
                    # the next read will load from DB with is_deleted=True and skip caching.
                    _redis_json_set_paths(
                        redis,
                        diagram_key,
                        [("$.is_deleted", True), ("$.updated_at", now.isoformat())],
                        CACHE_TTL,
                    )

                    pipe = redis.pipeline()
                    pipe.zrem(meta_key, str(diagram_id))
                    pipe.delete(list_key)
                    pipe.execute()

                    logger.debug(
                        "[DiagramCache] Deleted diagram %s for user %s (write-through)",
                        diagram_id, user_id
                    )
                except Exception as e:
                    logger.warning("[DiagramCache] Redis cache update failed (diagram deleted in database): %s", e)

        return True, None

    async def duplicate_diagram(self, user_id: int, diagram_id: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Duplicate an existing diagram.

        Returns:
            Tuple of (success, new_diagram_id, error_message)
        """
        # Check quota first
        current_count = await self.count_user_diagrams(user_id)
        if current_count >= MAX_PER_USER:
            return False, None, f"Diagram limit reached ({MAX_PER_USER} max)"

        # Get original diagram
        original = await self.get_diagram(user_id, diagram_id)
        if not original:
            return False, None, "Original diagram not found"

        # Create copy with new title
        new_title = f"{original['title']} (Copy)"
        if len(new_title) > 200:
            new_title = new_title[:197] + "..."

        success, new_id, error = await self.save_diagram(
            user_id=user_id,
            diagram_id=None,  # Create new
            title=new_title,
            diagram_type=original['diagram_type'],
            spec=original['spec'],
            language=original.get('language', 'zh'),
            thumbnail=original.get('thumbnail')
        )

        return success, new_id, error

    async def pin_diagram(self, user_id: int, diagram_id: str, pinned: bool) -> Tuple[bool, Optional[str]]:
        """
        Pin or unpin a diagram using write-through pattern: Database first, then Redis cache.

        Args:
            user_id: User ID
            diagram_id: Diagram ID
            pinned: True to pin, False to unpin

        Returns:
            Tuple of (success, error_message)
        """
        now = datetime.utcnow()

        # Write-through: Update database FIRST
        try:
            db = SessionLocal()
            try:
                rows = db.query(Diagram).filter(
                    Diagram.id == diagram_id,
                    Diagram.user_id == user_id,
                    Diagram.is_deleted.is_(False)
                ).update(
                    {
                        Diagram.is_pinned: pinned,
                        Diagram.updated_at: now,
                    },
                    synchronize_session=False
                )
                if rows == 0:
                    return False, "Diagram not found"
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error("[DiagramCache] Database pin failed: %s", e)
                return False, "Failed to update diagram"
            finally:
                db.close()
        except Exception as e:
            logger.error("[DiagramCache] Pin connection failed: %s", e)
            return False, "Database error"

        # Then update Redis cache using targeted JSON path updates — no full blob read needed.
        diagram_key = self._get_diagram_key(user_id, diagram_id)
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    list_key = self._get_user_list_key(user_id)

                    _redis_json_set_paths(
                        redis,
                        diagram_key,
                        [("$.is_pinned", pinned), ("$.updated_at", now.isoformat())],
                        CACHE_TTL,
                    )
                    redis.delete(list_key)

                    action = 'Pinned' if pinned else 'Unpinned'
                    logger.debug(
                        "[DiagramCache] %s diagram %s for user %s (write-through)",
                        action, diagram_id, user_id
                    )
                except Exception as e:
                    logger.warning("[DiagramCache] Redis cache update failed (pin saved to database): %s", e)

        return True, None

    async def flush(self):
        """No-op for write-through pattern (no background sync needed)."""
        logger.debug("[DiagramCache] Flush called (write-through pattern, no-op)")

    async def preload_user_diagrams(self, user_id: int) -> bool:
        """
        Preload user's diagram list into Redis cache.

        Called after login for instant library access.
        Non-blocking - should be called as fire-and-forget.

        Args:
            user_id: User ID to preload diagrams for

        Returns:
            True if preload succeeded, False otherwise
        """
        list_key = self._get_user_list_key(user_id)

        # Skip if already cached
        if self._use_redis():
            redis = get_redis()
            if redis and redis.exists(list_key):
                logger.debug(
                    "[DiagramCache] Preload skipped for user %s - already cached",
                    user_id
                )
                return True

        # Load from database and cache
        try:
            items = await self._load_list_from_database(user_id)

            # Cache in Redis
            if self._use_redis():
                redis = get_redis()
                if redis:
                    cache_data = {'items': items, 'total': len(items)}
                    redis.setex(list_key, CACHE_TTL, json.dumps(cache_data))
                    logger.debug(
                        "[DiagramCache] Preloaded %s diagrams for user %s",
                        len(items), user_id
                    )

            return True
        except Exception as e:
            logger.warning("[DiagramCache] Preload failed for user %s: %s", user_id, e)
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {
            'storage': 'redis' if self._use_redis() else 'database_only',
            'total_synced': self._total_synced,
            'total_errors': self._total_errors,
            'config': {
                'cache_ttl': CACHE_TTL,
                'sync_interval': SYNC_INTERVAL,
                'sync_batch_size': SYNC_BATCH_SIZE,
                'max_per_user': MAX_PER_USER,
                'max_spec_size_kb': MAX_SPEC_SIZE_KB,
            }
        }

        # Add Redis stats
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    dirty_count = redis.scard(DIRTY_SET_KEY)
                    stats['dirty_count'] = dirty_count or 0
                except Exception as exc:
                    logger.debug("Redis dirty set count retrieval failed: %s", exc)

        return stats


def get_diagram_cache() -> RedisDiagramCache:
    """Get or create global diagram cache instance."""
    if not hasattr(get_diagram_cache, 'cache_instance'):
        get_diagram_cache.cache_instance = RedisDiagramCache()
    return get_diagram_cache.cache_instance
