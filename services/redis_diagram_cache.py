"""
Redis Diagram Cache
====================

Shared diagram storage using Redis with SQLite persistence.
Provides fast reads/writes via Redis with background sync to SQLite.

Features:
- Redis for fast reads/writes (sub-ms latency)
- Background worker for periodic SQLite sync
- Dirty tracking for efficient batch writes
- SQLite fallback for cache misses
- 20 diagrams per user limit

Key Schema:
- diagram:{user_id}:{diagram_id} -> JSON diagram data
- diagrams:user:{user_id}:meta -> Sorted set (score=updated_at, member=diagram_id)
- diagrams:dirty -> Set of "user_id:diagram_id" pending sync

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
import json
import logging
import time
import asyncio
import threading
import uuid
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

from services.redis_client import is_redis_available, get_redis

logger = logging.getLogger(__name__)

# Configuration from environment
CACHE_TTL = int(os.getenv('DIAGRAM_CACHE_TTL', '604800'))  # 7 days
SYNC_INTERVAL = float(os.getenv('DIAGRAM_SYNC_INTERVAL', '300'))  # 5 minutes
SYNC_BATCH_SIZE = int(os.getenv('DIAGRAM_SYNC_BATCH_SIZE', '100'))
MAX_PER_USER = int(os.getenv('DIAGRAM_MAX_PER_USER', '20'))
MAX_SPEC_SIZE_KB = int(os.getenv('DIAGRAM_MAX_SPEC_SIZE_KB', '500'))

# Redis key patterns
DIAGRAM_KEY = "diagram:{user_id}:{diagram_id}"
USER_META_KEY = "diagrams:user:{user_id}:meta"
USER_LIST_KEY = "diagrams:user:{user_id}:list"  # Cached list for fast fetching
DIRTY_SET_KEY = "diagrams:dirty"
PENDING_CREATE_KEY = "diagrams:pending_create"  # New diagrams not yet in SQLite
STATS_KEY = "diagrams:stats"


class RedisDiagramCache:
    """
    Redis-based diagram caching with SQLite persistence.
    
    Follows the same pattern as RedisTokenBuffer:
    - Redis for fast reads/writes
    - Background worker for SQLite sync
    - Dirty tracking for efficient batch writes
    """
    
    def __init__(self):
        self._worker_task: Optional[asyncio.Task] = None
        self._initialized = False
        self._shutting_down = False
        self._last_sync_time = time.time()
        self._sync_lock = threading.Lock()
        
        # Local stats
        self._total_synced = 0
        self._total_errors = 0
        
        logger.info(
            f"[DiagramCache] Initialized: cache_ttl={CACHE_TTL}s, "
            f"sync_interval={SYNC_INTERVAL}s, max_per_user={MAX_PER_USER}"
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
    
    def _ensure_worker_started(self):
        """Start background sync worker if not already running."""
        if self._initialized:
            return
        
        try:
            loop = asyncio.get_running_loop()
            self._worker_task = loop.create_task(self._sync_worker())
            self._initialized = True
            self._last_sync_time = time.time()
            logger.debug("[DiagramCache] Background sync worker started")
        except RuntimeError:
            pass
    
    async def _sync_worker(self):
        """Background worker that periodically syncs pending diagrams to SQLite."""
        logger.debug("[DiagramCache] Sync worker started")
        
        while not self._shutting_down:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                if self._shutting_down:
                    break
                
                time_since_sync = time.time() - self._last_sync_time
                
                if time_since_sync >= SYNC_INTERVAL:
                    await self._sync_to_sqlite()
                    
            except asyncio.CancelledError:
                logger.debug("[DiagramCache] Sync worker cancelled")
                break
            except Exception as e:
                logger.error(f"[DiagramCache] Sync worker error: {e}", exc_info=True)
                await asyncio.sleep(5)
        
        # Final sync on shutdown
        await self._sync_to_sqlite()
        logger.debug("[DiagramCache] Sync worker stopped")
    
    async def count_user_diagrams(self, user_id: int) -> int:
        """
        Count user's diagrams (non-deleted).
        
        Uses Redis if available, falls back to SQLite.
        """
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    meta_key = self._get_user_meta_key(user_id)
                    count = redis.zcard(meta_key)
                    if count is not None:
                        return count
                except Exception as e:
                    logger.warning(f"[DiagramCache] Redis count failed: {e}")
        
        # Fallback to SQLite
        return await self._count_from_sqlite(user_id)
    
    async def _count_from_sqlite(self, user_id: int) -> int:
        """Count diagrams from SQLite."""
        try:
            from config.database import SessionLocal
            from models.diagrams import Diagram
            
            db = SessionLocal()
            try:
                count = db.query(Diagram).filter(
                    Diagram.user_id == user_id,
                    Diagram.is_deleted == False
                ).count()
                return count
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[DiagramCache] SQLite count failed: {e}")
            return 0
    
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
        Save diagram to Redis (Redis-first) and mark for background SQLite sync.
        
        All writes go to Redis first for sub-millisecond response.
        Background worker syncs to SQLite for durability.
        
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
        self._ensure_worker_started()
        
        # Validate spec size
        spec_json = json.dumps(spec)
        spec_size_kb = len(spec_json.encode('utf-8')) / 1024
        if spec_size_kb > MAX_SPEC_SIZE_KB:
            return False, None, f"Diagram spec too large ({spec_size_kb:.1f}KB > {MAX_SPEC_SIZE_KB}KB)"
        
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
        
        # Build diagram data
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
        
        # Redis-first: Save to Redis and mark for background sync
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    diagram_key = self._get_diagram_key(user_id, diagram_id)
                    meta_key = self._get_user_meta_key(user_id)
                    list_key = self._get_user_list_key(user_id)
                    
                    pipe = redis.pipeline()
                    # Store full diagram data
                    pipe.setex(diagram_key, CACHE_TTL, json.dumps(diagram_data))
                    # Update sorted set for ordering
                    pipe.zadd(meta_key, {str(diagram_id): now_ts})
                    # Invalidate list cache (will rebuild on next list request)
                    pipe.delete(list_key)
                    # Mark for background sync
                    if is_new:
                        pipe.sadd(PENDING_CREATE_KEY, f"{user_id}:{diagram_id}")
                    else:
                        pipe.sadd(DIRTY_SET_KEY, f"{user_id}:{diagram_id}")
                    pipe.execute()
                    
                    logger.debug(f"[DiagramCache] {'Created' if is_new else 'Updated'} diagram {diagram_id} for user {user_id}")
                    return True, diagram_id, None
                    
                except Exception as e:
                    logger.error(f"[DiagramCache] Redis save failed: {e}")
        
        # Fallback: Write directly to SQLite if Redis unavailable
        if is_new:
            success = await self._create_in_sqlite(
                user_id, diagram_id, title, diagram_type, spec_json, language, thumbnail, now
            )
        else:
            success = await self._update_in_sqlite(
                diagram_id, user_id, title, spec_json, thumbnail, now
            )
        return success, diagram_id, None if success else "Failed to save diagram"
    
    async def _create_in_sqlite(
        self,
        user_id: int,
        diagram_id: str,
        title: str,
        diagram_type: str,
        spec_json: str,
        language: str,
        thumbnail: Optional[str],
        created_at: datetime
    ) -> bool:
        """Create new diagram in SQLite with the given UUID."""
        try:
            from config.database import SessionLocal
            from models.diagrams import Diagram
            
            db = SessionLocal()
            try:
                diagram = Diagram(
                    id=diagram_id,
                    user_id=user_id,
                    title=title,
                    diagram_type=diagram_type,
                    spec=spec_json,
                    language=language,
                    thumbnail=thumbnail,
                    created_at=created_at,
                    updated_at=created_at,
                    is_deleted=False
                )
                db.add(diagram)
                db.commit()
                return True
            except Exception as e:
                db.rollback()
                logger.error(f"[DiagramCache] SQLite create failed: {e}")
                return False
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[DiagramCache] SQLite connection failed: {e}")
            return False
    
    async def _update_in_sqlite(
        self,
        diagram_id: str,
        user_id: int,
        title: str,
        spec_json: str,
        thumbnail: Optional[str],
        updated_at: datetime
    ) -> bool:
        """Update diagram in SQLite."""
        try:
            from config.database import SessionLocal
            from models.diagrams import Diagram
            
            db = SessionLocal()
            try:
                diagram = db.query(Diagram).filter(
                    Diagram.id == diagram_id,
                    Diagram.user_id == user_id
                ).first()
                
                if not diagram:
                    return False
                
                diagram.title = title
                diagram.spec = spec_json
                diagram.thumbnail = thumbnail
                diagram.updated_at = updated_at
                db.commit()
                return True
            except Exception as e:
                db.rollback()
                logger.error(f"[DiagramCache] SQLite update failed: {e}")
                return False
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[DiagramCache] SQLite connection failed: {e}")
            return False
    
    async def get_diagram(self, user_id: int, diagram_id: str) -> Optional[Dict[str, Any]]:
        """
        Get diagram from Redis, fallback to SQLite if not cached.
        
        Returns diagram data or None if not found.
        """
        self._ensure_worker_started()
        
        # Try Redis first
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    diagram_key = self._get_diagram_key(user_id, diagram_id)
                    data = redis.get(diagram_key)
                    
                    if data:
                        diagram = json.loads(data)
                        if not diagram.get('is_deleted', False):
                            # Refresh TTL on access
                            redis.expire(diagram_key, CACHE_TTL)
                            return diagram
                        return None
                        
                except Exception as e:
                    logger.warning(f"[DiagramCache] Redis get failed: {e}")
        
        # Fallback to SQLite
        return await self._load_from_sqlite(user_id, diagram_id)
    
    async def _load_from_sqlite(self, user_id: int, diagram_id: str) -> Optional[Dict[str, Any]]:
        """Load diagram from SQLite and cache in Redis."""
        try:
            from config.database import SessionLocal
            from models.diagrams import Diagram
            
            db = SessionLocal()
            try:
                diagram = db.query(Diagram).filter(
                    Diagram.id == diagram_id,
                    Diagram.user_id == user_id,
                    Diagram.is_deleted == False
                ).first()
                
                if not diagram:
                    return None
                
                # Parse spec JSON
                try:
                    spec = json.loads(diagram.spec)
                except json.JSONDecodeError:
                    spec = {}
                
                diagram_data = {
                    'id': diagram.id,
                    'user_id': diagram.user_id,
                    'title': diagram.title,
                    'diagram_type': diagram.diagram_type,
                    'spec': spec,
                    'language': diagram.language,
                    'thumbnail': diagram.thumbnail,
                    'created_at': diagram.created_at.isoformat() if diagram.created_at else None,
                    'updated_at': diagram.updated_at.isoformat() if diagram.updated_at else None,
                    'is_deleted': diagram.is_deleted,
                    'is_pinned': diagram.is_pinned if hasattr(diagram, 'is_pinned') else False
                }
                
                # Cache in Redis
                if self._use_redis():
                    redis = get_redis()
                    if redis:
                        try:
                            diagram_key = self._get_diagram_key(user_id, diagram_id)
                            meta_key = self._get_user_meta_key(user_id)
                            updated_ts = diagram.updated_at.timestamp() if diagram.updated_at else time.time()
                            
                            pipe = redis.pipeline()
                            pipe.setex(diagram_key, CACHE_TTL, json.dumps(diagram_data))
                            pipe.zadd(meta_key, {str(diagram_id): updated_ts})
                            pipe.execute()
                        except Exception:
                            pass
                
                return diagram_data
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[DiagramCache] SQLite load failed: {e}")
            return None
    
    async def list_diagrams(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """
        List user's diagrams with pagination (Redis-first).
        
        Checks Redis cache first. On cache miss, loads from SQLite and
        merges with any pending creates from Redis.
        Pinned diagrams are sorted first, then by updated_at desc.
        
        Returns:
            Dict with 'diagrams', 'total', 'page', 'page_size', 'has_more', 'max_diagrams'
        """
        self._ensure_worker_started()
        
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
                    logger.warning(f"[DiagramCache] Redis list cache read failed: {e}")
        
        # Cache miss: Load from SQLite and merge with pending creates
        items = await self._load_list_from_sqlite(user_id)
        
        # Merge with pending creates from Redis (not yet in SQLite)
        pending_items = await self._get_pending_creates_for_user(user_id)
        for p in pending_items:
            if not any(i['id'] == p['id'] for i in items):
                items.append(p)
        
        # Sort: pinned first (desc), then by updated_at desc
        # Tuple key: (is_pinned descending, updated_at descending)
        items.sort(
            key=lambda x: (x.get('is_pinned', False), x.get('updated_at', '') or ''),
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
                    logger.warning(f"[DiagramCache] Redis list cache write failed: {e}")
        
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
    
    async def _load_list_from_sqlite(self, user_id: int) -> List[Dict[str, Any]]:
        """Load diagram list metadata from SQLite."""
        try:
            from config.database import SessionLocal
            from models.diagrams import Diagram
            from sqlalchemy import desc
            
            db = SessionLocal()
            try:
                diagrams = db.query(Diagram).filter(
                    Diagram.user_id == user_id,
                    Diagram.is_deleted == False
                ).order_by(
                    desc(Diagram.is_pinned),
                    desc(Diagram.updated_at)
                ).all()
                
                items = []
                for d in diagrams:
                    items.append({
                        'id': d.id,
                        'title': d.title,
                        'diagram_type': d.diagram_type,
                        'thumbnail': d.thumbnail,
                        'updated_at': d.updated_at.isoformat() if d.updated_at else None,
                        'is_pinned': d.is_pinned if hasattr(d, 'is_pinned') else False
                    })
                return items
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[DiagramCache] SQLite list load failed: {e}")
            return []
    
    async def _get_pending_creates_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Get pending create diagrams for a user from Redis."""
        if not self._use_redis():
            return []
        
        redis = get_redis()
        if not redis:
            return []
        
        try:
            pending = redis.smembers(PENDING_CREATE_KEY)
            items = []
            
            for entry in pending:
                try:
                    entry_user_id, diagram_id = entry.split(':', 1)
                    if int(entry_user_id) != user_id:
                        continue
                    
                    # Get diagram data from Redis
                    diagram_key = self._get_diagram_key(user_id, diagram_id)
                    data = redis.get(diagram_key)
                    if data:
                        diagram_data = json.loads(data)
                        if not diagram_data.get('is_deleted'):
                            items.append({
                                'id': diagram_data['id'],
                                'title': diagram_data['title'],
                                'diagram_type': diagram_data['diagram_type'],
                                'thumbnail': diagram_data.get('thumbnail'),
                                'updated_at': diagram_data.get('updated_at'),
                                'is_pinned': diagram_data.get('is_pinned', False)
                            })
                except Exception as e:
                    logger.warning(f"[DiagramCache] Failed to get pending diagram: {e}")
            
            return items
        except Exception as e:
            logger.warning(f"[DiagramCache] Failed to get pending creates: {e}")
            return []
    
    async def delete_diagram(self, user_id: int, diagram_id: str) -> Tuple[bool, Optional[str]]:
        """
        Soft delete a diagram (Redis-first).
        
        Marks diagram as deleted in Redis, background worker syncs to SQLite.
        
        Returns:
            Tuple of (success, error_message)
        """
        self._ensure_worker_started()
        
        diagram_key = self._get_diagram_key(user_id, diagram_id)
        
        # Get diagram from Redis or SQLite
        diagram_data = await self.get_diagram(user_id, diagram_id)
        if not diagram_data:
            return False, "Diagram not found"
        
        # Mark as deleted
        now = datetime.utcnow()
        diagram_data['is_deleted'] = True
        diagram_data['updated_at'] = now.isoformat()
        
        # Redis-first: Update in Redis and mark for background sync
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    meta_key = self._get_user_meta_key(user_id)
                    list_key = self._get_user_list_key(user_id)
                    
                    pipe = redis.pipeline()
                    # Update diagram with is_deleted=True
                    pipe.setex(diagram_key, CACHE_TTL, json.dumps(diagram_data))
                    # Remove from meta set (won't appear in lists)
                    pipe.zrem(meta_key, str(diagram_id))
                    # Invalidate list cache
                    pipe.delete(list_key)
                    # Mark for background sync
                    pipe.sadd(DIRTY_SET_KEY, f"{user_id}:{diagram_id}")
                    # Remove from pending_create if it was there
                    pipe.srem(PENDING_CREATE_KEY, f"{user_id}:{diagram_id}")
                    pipe.execute()
                    
                    logger.debug(f"[DiagramCache] Deleted diagram {diagram_id} for user {user_id}")
                    return True, None
                    
                except Exception as e:
                    logger.error(f"[DiagramCache] Redis delete failed: {e}")
        
        # Fallback: Write directly to SQLite if Redis unavailable
        try:
            from config.database import SessionLocal
            from models.diagrams import Diagram
            
            db = SessionLocal()
            try:
                diagram = db.query(Diagram).filter(
                    Diagram.id == diagram_id,
                    Diagram.user_id == user_id
                ).first()
                
                if diagram:
                    diagram.is_deleted = True
                    diagram.updated_at = now
                    db.commit()
                    return True, None
                return False, "Diagram not found"
            except Exception as e:
                db.rollback()
                logger.error(f"[DiagramCache] SQLite delete failed: {e}")
                return False, "Failed to delete diagram"
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[DiagramCache] Delete connection failed: {e}")
            return False, "Database error"
    
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
        Pin or unpin a diagram (Redis-first).
        
        Updates pin state in Redis, background worker syncs to SQLite.
        
        Args:
            user_id: User ID
            diagram_id: Diagram ID
            pinned: True to pin, False to unpin
            
        Returns:
            Tuple of (success, error_message)
        """
        self._ensure_worker_started()
        
        diagram_key = self._get_diagram_key(user_id, diagram_id)
        
        # Get diagram from Redis or SQLite
        diagram_data = await self.get_diagram(user_id, diagram_id)
        if not diagram_data:
            return False, "Diagram not found"
        
        # Check if deleted
        if diagram_data.get('is_deleted'):
            return False, "Diagram not found"
        
        # Update pin state
        now = datetime.utcnow()
        diagram_data['is_pinned'] = pinned
        diagram_data['updated_at'] = now.isoformat()
        
        # Redis-first: Update in Redis and mark for background sync
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    list_key = self._get_user_list_key(user_id)
                    
                    pipe = redis.pipeline()
                    # Update diagram with new pin state
                    pipe.setex(diagram_key, CACHE_TTL, json.dumps(diagram_data))
                    # Invalidate list cache (order changes with pin)
                    pipe.delete(list_key)
                    # Mark for background sync
                    pipe.sadd(DIRTY_SET_KEY, f"{user_id}:{diagram_id}")
                    pipe.execute()
                    
                    logger.debug(f"[DiagramCache] {'Pinned' if pinned else 'Unpinned'} diagram {diagram_id} for user {user_id}")
                    return True, None
                    
                except Exception as e:
                    logger.error(f"[DiagramCache] Redis pin failed: {e}")
        
        # Fallback: Write directly to SQLite if Redis unavailable
        try:
            from config.database import SessionLocal
            from models.diagrams import Diagram
            
            db = SessionLocal()
            try:
                diagram = db.query(Diagram).filter(
                    Diagram.id == diagram_id,
                    Diagram.user_id == user_id,
                    Diagram.is_deleted == False
                ).first()
                
                if diagram:
                    diagram.is_pinned = pinned
                    diagram.updated_at = now
                    db.commit()
                    return True, None
                return False, "Diagram not found"
            except Exception as e:
                db.rollback()
                logger.error(f"[DiagramCache] SQLite pin failed: {e}")
                return False, "Failed to update diagram"
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[DiagramCache] Pin connection failed: {e}")
            return False, "Database error"
    
    async def _sync_to_sqlite(self):
        """Sync all pending diagrams from Redis to SQLite."""
        if not self._use_redis():
            self._last_sync_time = time.time()
            return
        
        # Sync pending creates first, then dirty updates
        created = await self._sync_pending_creates_to_sqlite()
        updated = await self._sync_dirty_updates_to_sqlite()
        
        self._last_sync_time = time.time()
        
        if created > 0 or updated > 0:
            logger.info(f"[DiagramCache] Synced to SQLite: {created} created, {updated} updated")
    
    async def _sync_pending_creates_to_sqlite(self) -> int:
        """INSERT new diagrams from Redis into SQLite."""
        redis = get_redis()
        if not redis:
            return 0
        
        with self._sync_lock:
            try:
                pending = redis.smembers(PENDING_CREATE_KEY)
                if not pending:
                    return 0
                
                entries_list = list(pending)[:SYNC_BATCH_SIZE]
                created = 0
                
                from config.database import SessionLocal
                from models.diagrams import Diagram
                
                db = SessionLocal()
                try:
                    for entry in entries_list:
                        try:
                            user_id, diagram_id = entry.split(':', 1)
                            user_id = int(user_id)
                            
                            # Get from Redis
                            diagram_key = self._get_diagram_key(user_id, diagram_id)
                            data = redis.get(diagram_key)
                            
                            if not data:
                                redis.srem(PENDING_CREATE_KEY, entry)
                                continue
                            
                            diagram_data = json.loads(data)
                            
                            # Check if already exists (edge case: duplicate sync)
                            existing = db.query(Diagram).filter(Diagram.id == diagram_id).first()
                            if existing:
                                redis.srem(PENDING_CREATE_KEY, entry)
                                continue
                            
                            # INSERT new diagram
                            diagram = Diagram(
                                id=diagram_id,
                                user_id=user_id,
                                title=diagram_data['title'],
                                diagram_type=diagram_data['diagram_type'],
                                spec=json.dumps(diagram_data.get('spec', {})),
                                language=diagram_data.get('language', 'zh'),
                                thumbnail=diagram_data.get('thumbnail'),
                                is_pinned=diagram_data.get('is_pinned', False),
                                is_deleted=diagram_data.get('is_deleted', False),
                                created_at=datetime.fromisoformat(diagram_data['created_at']) if diagram_data.get('created_at') else datetime.utcnow(),
                                updated_at=datetime.fromisoformat(diagram_data['updated_at']) if diagram_data.get('updated_at') else datetime.utcnow()
                            )
                            db.add(diagram)
                            created += 1
                            
                            redis.srem(PENDING_CREATE_KEY, entry)
                            
                        except Exception as e:
                            logger.warning(f"[DiagramCache] Create sync failed: {entry} - {e}")
                            self._total_errors += 1
                    
                    db.commit()
                    self._total_synced += created
                    return created
                    
                except Exception as e:
                    db.rollback()
                    logger.error(f"[DiagramCache] Batch create sync failed: {e}")
                    return 0
                finally:
                    db.close()
                    
            except Exception as e:
                logger.error(f"[DiagramCache] Create sync failed: {e}")
                return 0
    
    async def _sync_dirty_updates_to_sqlite(self) -> int:
        """UPDATE existing diagrams in SQLite (includes is_deleted, is_pinned)."""
        redis = get_redis()
        if not redis:
            return 0
        
        with self._sync_lock:
            try:
                dirty_entries = redis.smembers(DIRTY_SET_KEY)
                if not dirty_entries:
                    return 0
                
                entries_list = list(dirty_entries)[:SYNC_BATCH_SIZE]
                synced = 0
                
                from config.database import SessionLocal
                from models.diagrams import Diagram
                
                db = SessionLocal()
                try:
                    for entry in entries_list:
                        try:
                            user_id, diagram_id = entry.split(':', 1)
                            user_id = int(user_id)
                            
                            diagram_key = self._get_diagram_key(user_id, diagram_id)
                            data = redis.get(diagram_key)
                            
                            if not data:
                                redis.srem(DIRTY_SET_KEY, entry)
                                continue
                            
                            diagram_data = json.loads(data)
                            
                            # UPDATE or INSERT (if moved from pending_create)
                            diagram = db.query(Diagram).filter(
                                Diagram.id == diagram_id,
                                Diagram.user_id == user_id
                            ).first()
                            
                            if diagram:
                                # Update ALL fields including is_deleted and is_pinned
                                diagram.title = diagram_data.get('title', diagram.title)
                                diagram.spec = json.dumps(diagram_data.get('spec', {}))
                                diagram.thumbnail = diagram_data.get('thumbnail')
                                diagram.is_deleted = diagram_data.get('is_deleted', False)
                                diagram.is_pinned = diagram_data.get('is_pinned', False)
                                if diagram_data.get('updated_at'):
                                    diagram.updated_at = datetime.fromisoformat(diagram_data['updated_at'])
                                synced += 1
                            else:
                                # Edge case: diagram was in pending_create, moved to dirty
                                # This can happen if diagram was created then deleted before sync
                                new_diagram = Diagram(
                                    id=diagram_id,
                                    user_id=user_id,
                                    title=diagram_data['title'],
                                    diagram_type=diagram_data['diagram_type'],
                                    spec=json.dumps(diagram_data.get('spec', {})),
                                    language=diagram_data.get('language', 'zh'),
                                    thumbnail=diagram_data.get('thumbnail'),
                                    is_pinned=diagram_data.get('is_pinned', False),
                                    is_deleted=diagram_data.get('is_deleted', False),
                                    created_at=datetime.fromisoformat(diagram_data['created_at']) if diagram_data.get('created_at') else datetime.utcnow(),
                                    updated_at=datetime.fromisoformat(diagram_data['updated_at']) if diagram_data.get('updated_at') else datetime.utcnow()
                                )
                                db.add(new_diagram)
                                synced += 1
                            
                            redis.srem(DIRTY_SET_KEY, entry)
                            
                        except Exception as e:
                            logger.warning(f"[DiagramCache] Update sync failed: {entry} - {e}")
                            self._total_errors += 1
                    
                    db.commit()
                    self._total_synced += synced
                    return synced
                    
                except Exception as e:
                    db.rollback()
                    logger.error(f"[DiagramCache] Batch update sync failed: {e}")
                    return 0
                finally:
                    db.close()
                    
            except Exception as e:
                logger.error(f"[DiagramCache] Update sync failed: {e}")
                return 0
    
    async def flush(self):
        """Manually flush pending diagrams (called on shutdown)."""
        self._shutting_down = True
        
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        # Final sync
        await self._sync_to_sqlite()
        
        logger.info(
            f"[DiagramCache] Shutdown complete. "
            f"Total synced: {self._total_synced}, errors: {self._total_errors}"
        )
    
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
                logger.debug(f"[DiagramCache] Preload skipped for user {user_id} - already cached")
                return True
        
        # Load from SQLite and cache
        try:
            items = await self._load_list_from_sqlite(user_id)
            
            # Cache in Redis
            if self._use_redis():
                redis = get_redis()
                if redis:
                    cache_data = {'items': items, 'total': len(items)}
                    redis.setex(list_key, CACHE_TTL, json.dumps(cache_data))
                    logger.debug(f"[DiagramCache] Preloaded {len(items)} diagrams for user {user_id}")
            
            return True
        except Exception as e:
            logger.warning(f"[DiagramCache] Preload failed for user {user_id}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {
            'storage': 'redis' if self._use_redis() else 'sqlite_only',
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
                except Exception:
                    pass
        
        return stats


# Global singleton
_diagram_cache: Optional[RedisDiagramCache] = None


def get_diagram_cache() -> RedisDiagramCache:
    """Get or create global diagram cache instance."""
    global _diagram_cache
    if _diagram_cache is None:
        _diagram_cache = RedisDiagramCache()
    return _diagram_cache
