"""
Redis User Cache Service
========================

High-performance user caching using Redis with write-through pattern.
Database remains source of truth, Redis provides fast read cache.

Features:
- O(1) user lookups by ID or phone
- Automatic database fallback on cache miss
- Write-through pattern (database first, then Redis)
- Non-blocking cache operations
- Comprehensive error handling

Key Schema:
- user:{id} -> Hash with user data
- user:phone:{phone} -> String pointing to user ID (index)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import datetime
from typing import Optional, Dict
import logging

from config.database import SessionLocal
from models.domain.auth import User
from services.redis.redis_client import is_redis_available, RedisOps, get_redis



logger = logging.getLogger(__name__)

# Redis key prefixes
USER_KEY_PREFIX = "user:"
USER_PHONE_INDEX_PREFIX = "user:phone:"


class UserCache:
    """
    Redis-based user caching service.

    Provides fast user lookups with automatic database fallback.
    Uses write-through pattern: database is source of truth, Redis is cache.
    """

    def __init__(self):
        """Initialize UserCache instance."""

    def _serialize_user(self, user: User) -> Dict[str, str]:
        """
        Serialize User object to dict for Redis hash storage.

        Args:
            user: User SQLAlchemy model instance

        Returns:
            Dict with string values for Redis hash
        """
        return {
            'id': str(user.id),
            'phone': user.phone or '',
            'password_hash': user.password_hash or '',
            'name': user.name or '',
            'organization_id': str(user.organization_id) if user.organization_id else '',
            'avatar': user.avatar or '',
            'failed_login_attempts': str(user.failed_login_attempts) if user.failed_login_attempts else '0',
            'locked_until': user.locked_until.isoformat() if user.locked_until else '',
            'created_at': user.created_at.isoformat() if user.created_at else '',
            'last_login': user.last_login.isoformat() if user.last_login else '',
        }

    def _deserialize_user(self, data: Dict[str, str]) -> User:
        """
        Deserialize dict from Redis hash to User object.

        Args:
            data: Dict from Redis hash_get_all()

        Returns:
            User SQLAlchemy model instance (detached from session)
        """
        user = User()
        user.id = int(data.get('id', '0'))
        user.phone = data.get('phone') or None
        user.password_hash = data.get('password_hash') or None
        user.name = data.get('name') or None
        user.organization_id = int(data['organization_id']) if data.get('organization_id') else None
        user.avatar = data.get('avatar') or None
        user.failed_login_attempts = int(data.get('failed_login_attempts', '0'))

        # Parse datetime fields
        if data.get('locked_until'):
            try:
                user.locked_until = datetime.fromisoformat(data['locked_until'])
            except (ValueError, TypeError):
                user.locked_until = None
        else:
            user.locked_until = None

        if data.get('created_at'):
            try:
                user.created_at = datetime.fromisoformat(data['created_at'])
            except (ValueError, TypeError):
                user.created_at = datetime.utcnow()
        else:
            user.created_at = datetime.utcnow()

        if data.get('last_login'):
            try:
                user.last_login = datetime.fromisoformat(data['last_login'])
            except (ValueError, TypeError):
                user.last_login = None
        else:
            user.last_login = None

        return user

    def _load_from_database(self, user_id: Optional[int] = None, phone: Optional[str] = None) -> Optional[User]:
        """
        Load user from database.

        Args:
            user_id: User ID to load (if provided)
            phone: Phone number to load (if provided)

        Returns:
            User object or None if not found
        """
        db = SessionLocal()
        try:
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
            elif phone:
                user = db.query(User).filter(User.phone == phone).first()
            else:
                return None

            if user:
                # Detach from session so it can be used after close
                db.expunge(user)
                # Cache it for next time (non-blocking)
                try:
                    self.cache_user(user)
                except Exception as e:
                    logger.debug("[UserCache] Failed to cache user loaded from database: %s", e)

            return user
        except Exception as e:
            logger.error("[UserCache] Database query failed: %s", e, exc_info=True)
            raise
        finally:
            db.close()

    def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Get user by ID with cache lookup and database fallback.

        Args:
            user_id: User ID

        Returns:
            User object or None if not found
        """
        # Check Redis availability
        if not is_redis_available():
            logger.debug("[UserCache] Redis unavailable, loading user ID %s from database", user_id)
            return self._load_from_database(user_id=user_id)

        try:
            # Try cache read
            key = f"{USER_KEY_PREFIX}{user_id}"
            cached = RedisOps.hash_get_all(key)

            if cached:
                try:
                    user = self._deserialize_user(cached)
                    logger.debug("[UserCache] Cache hit for user ID %s", user_id)
                    return user
                except (KeyError, ValueError, TypeError) as e:
                    # Corrupted cache entry
                    logger.error("[UserCache] Corrupted cache for user ID %s: %s", user_id, e, exc_info=True)
                    # Invalidate corrupted entry
                    try:
                        RedisOps.delete(key)
                    except Exception:
                        pass
                    # Fallback to database
                    return self._load_from_database(user_id=user_id)
        except Exception as e:
            # Transient Redis errors - fallback to database
            logger.warning("[UserCache] Redis error for user ID %s, falling back to database: %s", user_id, e)
            return self._load_from_database(user_id=user_id)

        # Cache miss - load from database
        logger.debug("[UserCache] Cache miss for user ID %s, loading from database", user_id)
        return self._load_from_database(user_id=user_id)

    def get_by_phone(self, phone: str) -> Optional[User]:
        """
        Get user by phone number with cache lookup and database fallback.

        Args:
            phone: Phone number

        Returns:
            User object or None if not found
        """
        # Check Redis availability
        if not is_redis_available():
            phone_masked = phone[:3] + "***" + phone[-4:]
            logger.debug("[UserCache] Redis unavailable, loading user by phone %s from database", phone_masked)
            return self._load_from_database(phone=phone)

        try:
            # Try cache index lookup
            index_key = f"{USER_PHONE_INDEX_PREFIX}{phone}"
            user_id_str = RedisOps.get(index_key)

            if user_id_str:
                try:
                    user_id = int(user_id_str)
                    # Load user by ID (will use cache)
                    return self.get_by_id(user_id)
                except (ValueError, TypeError) as e:
                    phone_masked = phone[:3] + "***" + phone[-4:]
                    logger.error("[UserCache] Invalid user ID in phone index for %s: %s", phone_masked, e)
                    # Invalidate corrupted index
                    try:
                        RedisOps.delete(index_key)
                    except Exception:
                        pass
                    # Fallback to database
                    return self._load_from_database(phone=phone)
        except Exception as e:
            # Transient Redis errors - fallback to database
            phone_masked = phone[:3] + "***" + phone[-4:]
            logger.warning("[UserCache] Redis error for phone %s, falling back to database: %s", phone_masked, e)
            return self._load_from_database(phone=phone)

        # Cache miss - load from database
        phone_masked = phone[:3] + "***" + phone[-4:]
        logger.debug("[UserCache] Cache miss for phone %s, loading from database", phone_masked)
        return self._load_from_database(phone=phone)

    def cache_user(self, user: User) -> bool:
        """
        Cache user in Redis (non-blocking).

        Args:
            user: User SQLAlchemy model instance

        Returns:
            True if cached successfully, False otherwise
        """
        if not is_redis_available():
            logger.debug("[UserCache] Redis unavailable, skipping cache write")
            return False

        try:
            # Serialize user
            user_dict = self._serialize_user(user)

            # Store user hash
            user_key = f"{USER_KEY_PREFIX}{user.id}"
            success = RedisOps.hash_set(user_key, user_dict)

            if not success:
                logger.warning("[UserCache] Failed to cache user ID %s", user.id)
                return False

            # Store phone index (permanent, no TTL)
            if user.phone:
                phone_index_key = f"{USER_PHONE_INDEX_PREFIX}{user.phone}"
                redis = get_redis()
                if redis:
                    redis.set(phone_index_key, str(user.id))  # Permanent storage, no TTL

            phone_prefix = user.phone[:3] if user.phone and len(user.phone) >= 3 else "***"
            phone_suffix = user.phone[-4:] if user.phone and len(user.phone) >= 4 else ""
            phone_masked = phone_prefix + "***" + phone_suffix
            logger.debug("[UserCache] Cached user ID %s (phone: %s)", user.id, phone_masked)
            logger.debug("[UserCache] Cached user index: phone %s -> ID %s", phone_masked, user.id)

            return True
        except Exception as e:
            # Log but don't raise - cache failures are non-critical
            logger.warning("[UserCache] Failed to cache user ID %s: %s", user.id, e)
            return False

    def invalidate(self, user_id: int, phone: Optional[str] = None) -> bool:
        """
        Invalidate user cache entries (non-blocking).

        Args:
            user_id: User ID
            phone: Phone number

        Returns:
            True if invalidated successfully, False otherwise
        """
        if not is_redis_available():
            logger.debug("[UserCache] Redis unavailable, skipping cache invalidation")
            return False

        try:
            # Delete user hash
            user_key = f"{USER_KEY_PREFIX}{user_id}"
            RedisOps.delete(user_key)

            # Delete phone index
            if phone:
                phone_index_key = f"{USER_PHONE_INDEX_PREFIX}{phone}"
                RedisOps.delete(phone_index_key)

            logger.info("[UserCache] Invalidated cache for user ID %s", user_id)
            logger.debug("[UserCache] Deleted cache keys: user:%s, user:phone:%s", user_id, phone)

            return True
        except Exception as e:
            # Log but don't raise - invalidation failures are non-critical
            logger.warning("[UserCache] Failed to invalidate cache for user ID %s: %s", user_id, e)
            return False


def get_user_cache() -> UserCache:
    """Get or create global UserCache instance."""
    if not hasattr(get_user_cache, 'cache_instance'):
        get_user_cache.cache_instance = UserCache()
        logger.info("[UserCache] Initialized")
    return get_user_cache.cache_instance


# Convenience alias
user_cache = get_user_cache()
