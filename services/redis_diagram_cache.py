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
DIRTY_SET_KEY = "diagrams:dirty"
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
        """Background worker that periodically syncs dirty diagrams to SQLite."""
        logger.debug("[DiagramCache] Sync worker started")
        
        while not self._shutting_down:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                if self._shutting_down:
                    break
                
                time_since_sync = time.time() - self._last_sync_time
                
                if time_since_sync >= SYNC_INTERVAL:
                    await self._sync_dirty_to_sqlite()
                    
            except asyncio.CancelledError:
                logger.debug("[DiagramCache] Sync worker cancelled")
                break
            except Exception as e:
                logger.error(f"[DiagramCache] Sync worker error: {e}", exc_info=True)
                await asyncio.sleep(5)
        
        # Final sync on shutdown
        await self._sync_dirty_to_sqlite()
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
        Save diagram to Redis and mark as dirty for SQLite sync.
        
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
        
        # Check user quota for new diagrams
        if diagram_id is None:
            current_count = await self.count_user_diagrams(user_id)
            if current_count >= MAX_PER_USER:
                return False, None, f"Diagram limit reached ({MAX_PER_USER} max)"
        
        now = datetime.utcnow()
        now_ts = now.timestamp()
        
        # For new diagrams, generate UUID and create in SQLite
        if diagram_id is None:
            diagram_id = str(uuid.uuid4())
            created = await self._create_in_sqlite(
                user_id, diagram_id, title, diagram_type, spec_json, language, thumbnail, now
            )
            if not created:
                return False, None, "Failed to create diagram in database"
        
        # Build diagram data
        diagram_data = {
            'id': diagram_id,
            'user_id': user_id,
            'title': title,
            'diagram_type': diagram_type,
            'spec': spec,
            'language': language,
            'thumbnail': thumbnail,
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
            'is_deleted': False
        }
        
        # Save to Redis
        if self._use_redis():
            redis = get_redis()
            if redis:
                try:
                    diagram_key = self._get_diagram_key(user_id, diagram_id)
                    meta_key = self._get_user_meta_key(user_id)
                    
                    pipe = redis.pipeline()
                    pipe.setex(diagram_key, CACHE_TTL, json.dumps(diagram_data))
                    pipe.zadd(meta_key, {str(diagram_id): now_ts})
                    pipe.sadd(DIRTY_SET_KEY, f"{user_id}:{diagram_id}")
                    pipe.execute()
                    
                    logger.debug(f"[DiagramCache] Saved diagram {diagram_id} for user {user_id}")
                    return True, diagram_id, None
                    
                except Exception as e:
                    logger.error(f"[DiagramCache] Redis save failed: {e}")
        
        # Fallback: sync immediately to SQLite
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
                    'is_deleted': diagram.is_deleted
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
        List user's diagrams with pagination.
        Pinned diagrams are sorted first, then by updated_at desc.
        
        Returns:
            Dict with 'diagrams', 'total', 'page', 'page_size', 'has_more', 'max_diagrams'
        """
        self._ensure_worker_started()
        
        # Always get from SQLite for accurate list (Redis may have stale data)
        try:
            from config.database import SessionLocal
            from models.diagrams import Diagram
            from sqlalchemy import desc
            
            db = SessionLocal()
            try:
                # Get total count
                total = db.query(Diagram).filter(
                    Diagram.user_id == user_id,
                    Diagram.is_deleted == False
                ).count()
                
                # Get paginated results - pinned first, then by updated_at desc
                offset = (page - 1) * page_size
                diagrams = db.query(Diagram).filter(
                    Diagram.user_id == user_id,
                    Diagram.is_deleted == False
                ).order_by(
                    desc(Diagram.is_pinned),
                    desc(Diagram.updated_at)
                ).offset(offset).limit(page_size).all()
                
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
                
                return {
                    'diagrams': items,
                    'total': total,
                    'page': page,
                    'page_size': page_size,
                    'has_more': offset + len(items) < total,
                    'max_diagrams': MAX_PER_USER
                }
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[DiagramCache] List diagrams failed: {e}")
            return {
                'diagrams': [],
                'total': 0,
                'page': page,
                'page_size': page_size,
                'has_more': False,
                'max_diagrams': MAX_PER_USER
            }
    
    async def delete_diagram(self, user_id: int, diagram_id: str) -> Tuple[bool, Optional[str]]:
        """
        Soft delete a diagram.
        
        Returns:
            Tuple of (success, error_message)
        """
        self._ensure_worker_started()
        
        # Update SQLite
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
                    return False, "Diagram not found"
                
                diagram.is_deleted = True
                diagram.updated_at = datetime.utcnow()
                db.commit()
                
                # Remove from Redis
                if self._use_redis():
                    redis = get_redis()
                    if redis:
                        try:
                            diagram_key = self._get_diagram_key(user_id, diagram_id)
                            meta_key = self._get_user_meta_key(user_id)
                            
                            pipe = redis.pipeline()
                            pipe.delete(diagram_key)
                            pipe.zrem(meta_key, str(diagram_id))
                            pipe.srem(DIRTY_SET_KEY, f"{user_id}:{diagram_id}")
                            pipe.execute()
                        except Exception:
                            pass
                
                logger.debug(f"[DiagramCache] Deleted diagram {diagram_id} for user {user_id}")
                return True, None
                
            except Exception as e:
                db.rollback()
                logger.error(f"[DiagramCache] Delete failed: {e}")
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
        Pin or unpin a diagram.
        
        Args:
            user_id: User ID
            diagram_id: Diagram ID
            pinned: True to pin, False to unpin
            
        Returns:
            Tuple of (success, error_message)
        """
        self._ensure_worker_started()
        
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
                    return False, "Diagram not found"
                
                diagram.is_pinned = pinned
                diagram.updated_at = datetime.utcnow()
                db.commit()
                
                # Update Redis cache if available
                if self._use_redis():
                    redis = get_redis()
                    if redis:
                        try:
                            diagram_key = self._get_diagram_key(user_id, diagram_id)
                            data = redis.get(diagram_key)
                            if data:
                                diagram_data = json.loads(data)
                                diagram_data['is_pinned'] = pinned
                                diagram_data['updated_at'] = diagram.updated_at.isoformat()
                                redis.setex(diagram_key, CACHE_TTL, json.dumps(diagram_data))
                        except Exception:
                            pass
                
                logger.debug(f"[DiagramCache] {'Pinned' if pinned else 'Unpinned'} diagram {diagram_id} for user {user_id}")
                return True, None
                
            except Exception as e:
                db.rollback()
                logger.error(f"[DiagramCache] Pin diagram failed: {e}")
                return False, "Failed to update diagram"
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[DiagramCache] Pin connection failed: {e}")
            return False, "Database error"
    
    async def _sync_dirty_to_sqlite(self):
        """Sync dirty diagrams from Redis to SQLite."""
        if not self._use_redis():
            self._last_sync_time = time.time()
            return
        
        with self._sync_lock:
            redis = get_redis()
            if not redis:
                return
            
            try:
                # Get dirty entries
                dirty_entries = redis.smembers(DIRTY_SET_KEY)
                if not dirty_entries:
                    self._last_sync_time = time.time()
                    return
                
                # Process in batches
                entries_list = list(dirty_entries)[:SYNC_BATCH_SIZE]
                synced = 0
                errors = 0
                
                from config.database import SessionLocal
                from models.diagrams import Diagram
                
                db = SessionLocal()
                try:
                    for entry in entries_list:
                        try:
                            user_id, diagram_id = entry.split(':')
                            user_id = int(user_id)
                            diagram_id = int(diagram_id)
                            
                            # Get from Redis
                            diagram_key = self._get_diagram_key(user_id, diagram_id)
                            data = redis.get(diagram_key)
                            
                            if not data:
                                redis.srem(DIRTY_SET_KEY, entry)
                                continue
                            
                            diagram_data = json.loads(data)
                            
                            # Update SQLite
                            diagram = db.query(Diagram).filter(
                                Diagram.id == diagram_id,
                                Diagram.user_id == user_id
                            ).first()
                            
                            if diagram:
                                diagram.title = diagram_data.get('title', diagram.title)
                                diagram.spec = json.dumps(diagram_data.get('spec', {}))
                                diagram.thumbnail = diagram_data.get('thumbnail')
                                diagram.is_deleted = diagram_data.get('is_deleted', False)
                                if diagram_data.get('updated_at'):
                                    diagram.updated_at = datetime.fromisoformat(diagram_data['updated_at'])
                                synced += 1
                            
                            # Remove from dirty set
                            redis.srem(DIRTY_SET_KEY, entry)
                            
                        except Exception as e:
                            logger.warning(f"[DiagramCache] Sync entry failed: {entry} - {e}")
                            errors += 1
                    
                    db.commit()
                    
                except Exception as e:
                    db.rollback()
                    logger.error(f"[DiagramCache] Batch sync failed: {e}")
                    errors += len(entries_list)
                finally:
                    db.close()
                
                self._total_synced += synced
                self._total_errors += errors
                self._last_sync_time = time.time()
                
                if synced > 0:
                    logger.info(f"[DiagramCache] Synced {synced} diagrams to SQLite (errors: {errors})")
                    
            except Exception as e:
                logger.error(f"[DiagramCache] Sync failed: {e}")
    
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
        await self._sync_dirty_to_sqlite()
        
        logger.info(
            f"[DiagramCache] Shutdown complete. "
            f"Total synced: {self._total_synced}, errors: {self._total_errors}"
        )
    
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
