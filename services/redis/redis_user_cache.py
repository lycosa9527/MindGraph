from datetime import datetime
from typing import Optional, Dict
import logging

from config.database import SessionLocal
from models.auth import User
from services.redis.redis_client import is_redis_available, redis_ops, get_redis

"""
Redis User Cache Service
========================

High-performance user caching using Redis with write-through pattern.
SQLite remains source of truth, Redis provides fast read cache.

Features:
- O(1) user lookups by ID or phone
- Automatic SQLite fallback on cache miss
- Write-through pattern (SQLite first, then Redis)
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



logger = logging.getLogger(__name__)

# Redis key prefixes
USER_KEY_PREFIX = "user:"
USER_PHONE_INDEX_PREFIX = "user:phone:"


class UserCache:
    """
    Redis-based user caching service.

    Provides fast user lookups with automatic SQLite fallback.
    Uses write-through pattern: SQLite is source of truth, Redis is cache.
    """

    def __init__(self):
        """Initialize UserCache instance."""
        pass

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

    def _load_from_sqlite(self, user_id: Optional[int] = None, phone: Optional[str] = None) -> Optional[User]:
        """
        Load user from SQLite database.

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
                    logger.debug(f"[UserCache] Failed to cache user loaded from SQLite: {e}")

            return user
        except Exception as e:
            logger.error(f"[UserCache] Database query failed: {e}", exc_info=True)
            raise
        finally:
            db.close()

    def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Get user by ID with cache lookup and SQLite fallback.

        Args:
            user_id: User ID

        Returns:
            User object or None if not found
        """
        # Check Redis availability
        if not is_redis_available():
            logger.debug(f"[UserCache] Redis unavailable, loading user ID {user_id} from SQLite")
            return self._load_from_sqlite(user_id=user_id)

        try:
            # Try cache read
            key = f"{USER_KEY_PREFIX}{user_id}"
            cached = redis_ops.hash_get_all(key)

            if cached:
                try:
                    user = self._deserialize_user(cached)
                    logger.debug(f"[UserCache] Cache hit for user ID {user_id}")
                    return user
                except (KeyError, ValueError, TypeError) as e:
                    # Corrupted cache entry
                    logger.error(f"[UserCache] Corrupted cache for user ID {user_id}: {e}", exc_info=True)
                    # Invalidate corrupted entry
                    try:
                        redis_ops.delete(key)
                    except Exception:
                        pass
                    # Fallback to SQLite
                    return self._load_from_sqlite(user_id=user_id)
        except Exception as e:
            # Transient Redis errors - fallback to SQLite
            logger.warning(f"[UserCache] Redis error for user ID {user_id}, falling back to SQLite: {e}")
            return self._load_from_sqlite(user_id=user_id)

        # Cache miss - load from SQLite
        logger.debug(f"[UserCache] Cache miss for user ID {user_id}, loading from SQLite")
        return self._load_from_sqlite(user_id=user_id)

    def get_by_phone(self, phone: str) -> Optional[User]:
        """
        Get user by phone number with cache lookup and SQLite fallback.

        Args:
            phone: Phone number

        Returns:
            User object or None if not found
        """
        # Check Redis availability
        if not is_redis_available():
            logger.debug(f"[UserCache] Redis unavailable, loading user by phone {phone[:3]}***{phone[-4:]} from SQLite")
            return self._load_from_sqlite(phone=phone)

        try:
            # Try cache index lookup
            index_key = f"{USER_PHONE_INDEX_PREFIX}{phone}"
            user_id_str = redis_ops.get(index_key)

            if user_id_str:
                try:
                    user_id = int(user_id_str)
                    # Load user by ID (will use cache)
                    return self.get_by_id(user_id)
                except (ValueError, TypeError) as e:
                    logger.error(f"[UserCache] Invalid user ID in phone index for {phone[:3]}***{phone[-4:]}: {e}")
                    # Invalidate corrupted index
                    try:
                        redis_ops.delete(index_key)
                    except Exception:
                        pass
                    # Fallback to SQLite
                    return self._load_from_sqlite(phone=phone)
        except Exception as e:
            # Transient Redis errors - fallback to SQLite
            logger.warning(f"[UserCache] Redis error for phone {phone[:3]}***{phone[-4:]}, falling back to SQLite: {e}")
            return self._load_from_sqlite(phone=phone)

        # Cache miss - load from SQLite
        logger.debug(f"[UserCache] Cache miss for phone {phone[:3]}***{phone[-4:]}, loading from SQLite")
        return self._load_from_sqlite(phone=phone)

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
            success = redis_ops.hash_set(user_key, user_dict)

            if not success:
                logger.warning(f"[UserCache] Failed to cache user ID {user.id}")
                return False

            # Store phone index (permanent, no TTL)
            if user.phone:
                phone_index_key = f"{USER_PHONE_INDEX_PREFIX}{user.phone}"
                redis = get_redis()
                if redis:
                    redis.set(phone_index_key, str(user.id))  # Permanent storage, no TTL

            logger.debug(f"[UserCache] Cached user ID {user.id} (phone: {user.phone[:3] if user.phone and len(user.phone) >= 3 else '***'}***{user.phone[-4:] if user.phone and len(user.phone) >= 4 else ''})")
            logger.debug(f"[UserCache] Cached user index: phone {user.phone[:3] if user.phone and len(user.phone) >= 3 else '***'}***{user.phone[-4:] if user.phone and len(user.phone) >= 4 else ''} -> ID {user.id}")

            return True
        except Exception as e:
            # Log but don't raise - cache failures are non-critical
            logger.warning(f"[UserCache] Failed to cache user ID {user.id}: {e}")
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
            redis_ops.delete(user_key)

            # Delete phone index
            if phone:
                phone_index_key = f"{USER_PHONE_INDEX_PREFIX}{phone}"
                redis_ops.delete(phone_index_key)

            logger.info(f"[UserCache] Invalidated cache for user ID {user_id}")
            logger.debug(f"[UserCache] Deleted cache keys: user:{user_id}, user:phone:{phone}")

            return True
        except Exception as e:
            # Log but don't raise - invalidation failures are non-critical
            logger.warning(f"[UserCache] Failed to invalidate cache for user ID {user_id}: {e}")
            return False


# Global singleton instance
_user_cache: Optional[UserCache] = None


def get_user_cache() -> UserCache:
    """Get or create global UserCache instance."""
    global _user_cache
    if _user_cache is None:
        _user_cache = UserCache()
        logger.info("[UserCache] Initialized")
    return _user_cache


# Convenience alias
user_cache = get_user_cache()

