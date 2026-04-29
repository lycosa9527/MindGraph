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

from datetime import UTC, datetime
from typing import Optional, Dict, List
import logging

from sqlalchemy import select

from config.database import AsyncSessionLocal
from models.domain.auth import User
from services.redis.cache.redis_cache_stampede import with_stampede_lock
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available


logger = logging.getLogger(__name__)

from services.redis import keys as _keys

USER_CACHE_TTL = _keys.TTL_USER


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
            "id": str(user.id),
            "phone": user.phone or "",
            "email": getattr(user, "email", None) or "",
            "password_hash": user.password_hash or "",
            "name": user.name or "",
            "organization_id": str(user.organization_id) if user.organization_id else "",
            "avatar": user.avatar or "",
            "role": getattr(user, "role", "user") or "user",
            "failed_login_attempts": str(user.failed_login_attempts) if user.failed_login_attempts else "0",
            "locked_until": user.locked_until.isoformat() if user.locked_until else "",
            "created_at": user.created_at.isoformat() if user.created_at else "",
            "last_login": user.last_login.isoformat() if user.last_login else "",
            "ui_language": getattr(user, "ui_language", None) or "",
            "prompt_language": getattr(user, "prompt_language", None) or "",
            "match_prompt_to_ui": "1" if getattr(user, "match_prompt_to_ui", True) else "0",
            "allows_simplified_chinese": "1" if getattr(user, "allows_simplified_chinese", True) else "0",
            "email_login_whitelisted_from_cn": "1" if getattr(user, "email_login_whitelisted_from_cn", False) else "0",
            "login_password_set": "1" if getattr(user, "login_password_set", True) else "0",
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
        user.id = int(data.get("id", "0"))
        user.phone = data.get("phone") or None
        if user.phone == "":
            user.phone = None
        user.email = data.get("email") or None
        if user.email == "":
            user.email = None
        user.password_hash = data.get("password_hash") or ""
        user.name = data.get("name") or None
        org_id_val = data.get("organization_id")
        user.organization_id = int(org_id_val) if org_id_val else None
        user.avatar = data.get("avatar") or None
        user.role = data.get("role") or "user"
        user.failed_login_attempts = int(data.get("failed_login_attempts", "0"))

        # Parse datetime fields
        if data.get("locked_until"):
            try:
                user.locked_until = datetime.fromisoformat(data["locked_until"])
            except (ValueError, TypeError):
                user.locked_until = None
        else:
            user.locked_until = None

        if data.get("created_at"):
            try:
                user.created_at = datetime.fromisoformat(data["created_at"])
            except (ValueError, TypeError):
                user.created_at = datetime.now(UTC)
        else:
            user.created_at = datetime.now(UTC)

        if data.get("last_login"):
            try:
                user.last_login = datetime.fromisoformat(data["last_login"])
            except (ValueError, TypeError):
                user.last_login = None
        else:
            user.last_login = None

        user.ui_language = data.get("ui_language") or None
        user.prompt_language = data.get("prompt_language") or None
        mp = data.get("match_prompt_to_ui", "1")
        user.match_prompt_to_ui = mp not in ("0", "false", "False")
        asc = data.get("allows_simplified_chinese", "1")
        user.allows_simplified_chinese = asc not in ("0", "false", "False")

        wl = data.get("email_login_whitelisted_from_cn", "0")
        user.email_login_whitelisted_from_cn = wl in ("1", "true", "True")

        lp = data.get("login_password_set", "1")
        user.login_password_set = lp not in ("0", "false", "False")

        return user

    async def _read_cached_by_id(self, user_id: int) -> Optional[User]:
        """Re-read cached user hash by ID without DB fallback (G6 loser path)."""
        redis = get_async_redis()
        if redis is None:
            return None
        try:
            cached = await redis.hgetall(_keys.USER_BY_ID.format(user_id=user_id))
        except Exception:  # pylint: disable=broad-except
            return None
        if not cached:
            return None
        try:
            return self._deserialize_user(cached)
        except Exception:  # pylint: disable=broad-except
            return None

    async def _read_cached_by_phone(self, phone: str) -> Optional[User]:
        """Re-read cached user via phone index (G6 loser path)."""
        redis = get_async_redis()
        if redis is None:
            return None
        try:
            user_id_str = await redis.get(_keys.USER_BY_PHONE.format(phone=phone))
        except Exception:  # pylint: disable=broad-except
            return None
        if not user_id_str:
            return None
        try:
            return await self._read_cached_by_id(int(user_id_str))
        except (ValueError, TypeError):
            return None

    async def _read_cached_by_email(self, email: str) -> Optional[User]:
        """Re-read cached user via email index (G6 loser path)."""
        redis = get_async_redis()
        if redis is None:
            return None
        try:
            user_id_str = await redis.get(_keys.USER_BY_EMAIL.format(email=email))
        except Exception:  # pylint: disable=broad-except
            return None
        if not user_id_str:
            return None
        try:
            return await self._read_cached_by_id(int(user_id_str))
        except (ValueError, TypeError):
            return None

    async def _query_database(
        self,
        user_id: Optional[int] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Optional[User]:
        """Inner DB load — runs under the stampede lock when one was acquired."""
        try:
            async with AsyncSessionLocal() as db:
                if user_id:
                    result = await db.execute(select(User).where(User.id == user_id))
                    user = result.scalar_one_or_none()
                elif phone:
                    result = await db.execute(select(User).where(User.phone == phone))
                    user = result.scalar_one_or_none()
                elif email:
                    result = await db.execute(select(User).where(User.email == email))
                    user = result.scalar_one_or_none()
                else:
                    return None

                if user:
                    try:
                        await self.cache_user(user)
                    except Exception as e:
                        logger.debug("[UserCache] Failed to cache user loaded from database: %s", e)

                return user
        except Exception as e:
            logger.error("[UserCache] Database query failed: %s", e, exc_info=True)
            raise

    async def _load_from_database(
        self,
        user_id: Optional[int] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Optional[User]:
        """
        Load user from database, protected against cache stampedes (G6).

        Args:
            user_id: User ID to load (if provided)
            phone: Phone number to load (if provided)
            email: Normalized email to load (if provided)

        Returns:
            User object or None if not found
        """
        if user_id:
            cache_key = _keys.USER_BY_ID.format(user_id=user_id)

            async def _reader() -> Optional[User]:
                return await self._read_cached_by_id(user_id)

        elif phone:
            cache_key = _keys.USER_BY_PHONE.format(phone=phone)

            async def _reader() -> Optional[User]:
                return await self._read_cached_by_phone(phone)

        elif email:
            cache_key = _keys.USER_BY_EMAIL.format(email=email)

            async def _reader() -> Optional[User]:
                return await self._read_cached_by_email(email)

        else:
            return None

        async def _loader() -> Optional[User]:
            return await self._query_database(user_id=user_id, phone=phone, email=email)

        return await with_stampede_lock(cache_key, _loader, _reader)

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Get user by ID with cache lookup and database fallback.

        Args:
            user_id: User ID

        Returns:
            User object or None if not found
        """
        if not is_redis_available():
            logger.debug(
                "[UserCache] Redis unavailable, loading user ID %s from database",
                user_id,
            )
            return await self._load_from_database(user_id=user_id)

        redis = get_async_redis()
        if not redis:
            return await self._load_from_database(user_id=user_id)

        try:
            key = _keys.USER_BY_ID.format(user_id=user_id)
            cached = await redis.hgetall(key)

            if cached:
                try:
                    user = self._deserialize_user(cached)
                    logger.debug("[UserCache] Cache hit for user ID %s", user_id)
                    return user
                except (KeyError, ValueError, TypeError) as e:
                    logger.error(
                        "[UserCache] Corrupted cache for user ID %s: %s",
                        user_id,
                        e,
                        exc_info=True,
                    )
                    try:
                        await redis.delete(key)
                    except Exception as exc:
                        logger.debug(
                            "Corrupted user cache entry deletion failed for user ID %s: %s",
                            user_id,
                            exc,
                        )
                    return await self._load_from_database(user_id=user_id)
        except Exception as exc:
            logger.warning(
                "[UserCache] Redis error for user ID %s, falling back to database: %s",
                user_id,
                exc,
            )
            return await self._load_from_database(user_id=user_id)

        logger.debug("[UserCache] Cache miss for user ID %s, loading from database", user_id)
        return await self._load_from_database(user_id=user_id)

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by normalized email with cache lookup and database fallback.

        Args:
            email: Normalized lowercase email

        Returns:
            User object or None if not found
        """
        if not is_redis_available():
            return await self._load_from_database(email=email)

        redis = get_async_redis()
        if not redis:
            return await self._load_from_database(email=email)

        try:
            index_key = _keys.USER_BY_EMAIL.format(email=email)
            user_id_str = await redis.get(index_key)

            if user_id_str:
                try:
                    user_id = int(user_id_str)
                    return await self.get_by_id(user_id)
                except (ValueError, TypeError):
                    try:
                        await redis.delete(index_key)
                    except Exception as exc:
                        logger.debug("Corrupted user email index deletion failed: %s", exc)
                    return await self._load_from_database(email=email)
        except Exception as exc:
            logger.warning(
                "[UserCache] Redis error for email lookup, falling back to database: %s",
                exc,
            )
            return await self._load_from_database(email=email)

        return await self._load_from_database(email=email)

    async def get_by_phone(self, phone: str) -> Optional[User]:
        """
        Get user by phone number with cache lookup and database fallback.

        Args:
            phone: Phone number

        Returns:
            User object or None if not found
        """
        if not is_redis_available():
            phone_masked = phone[:3] + "***" + phone[-4:]
            logger.debug(
                "[UserCache] Redis unavailable, loading user by phone %s from database",
                phone_masked,
            )
            return await self._load_from_database(phone=phone)

        redis = get_async_redis()
        if not redis:
            return await self._load_from_database(phone=phone)

        try:
            index_key = _keys.USER_BY_PHONE.format(phone=phone)
            user_id_str = await redis.get(index_key)

            if user_id_str:
                try:
                    user_id = int(user_id_str)
                    return await self.get_by_id(user_id)
                except (ValueError, TypeError) as e:
                    phone_masked = phone[:3] + "***" + phone[-4:]
                    logger.error(
                        "[UserCache] Invalid user ID in phone index for %s: %s",
                        phone_masked,
                        e,
                    )
                    try:
                        await redis.delete(index_key)
                    except Exception as exc:
                        logger.debug("Corrupted user phone index deletion failed: %s", exc)
                    return await self._load_from_database(phone=phone)
        except Exception as e:
            phone_masked = phone[:3] + "***" + phone[-4:]
            logger.warning(
                "[UserCache] Redis error for phone %s, falling back to database: %s",
                phone_masked,
                e,
            )
            return await self._load_from_database(phone=phone)

        phone_masked = phone[:3] + "***" + phone[-4:]
        logger.debug("[UserCache] Cache miss for phone %s, loading from database", phone_masked)
        return await self._load_from_database(phone=phone)

    async def cache_user(self, user: User) -> bool:
        """
        Cache user in Redis (non-blocking).

        Writes the user hash and phone index in a single pipeline
        to avoid multiple round-trips.

        Args:
            user: User SQLAlchemy model instance

        Returns:
            True if cached successfully, False otherwise
        """
        if not is_redis_available():
            logger.debug("[UserCache] Redis unavailable, skipping cache write")
            return False

        redis_client = get_async_redis()
        if not redis_client:
            logger.debug("[UserCache] Redis client unavailable, skipping cache write")
            return False

        try:
            user_dict = self._serialize_user(user)
            user_key = _keys.USER_BY_ID.format(user_id=user.id)

            async with redis_client.pipeline(transaction=False) as pipe:
                # DELETE before HSET to clear any stale key with wrong type.
                pipe.delete(user_key)
                pipe.hset(user_key, mapping=user_dict)
                pipe.expire(user_key, USER_CACHE_TTL)
                if user.phone:
                    phone_index_key = _keys.USER_BY_PHONE.format(phone=user.phone)
                    pipe.set(phone_index_key, str(user.id), ex=USER_CACHE_TTL)
                user_email = getattr(user, "email", None)
                if user_email:
                    email_index_key = _keys.USER_BY_EMAIL.format(email=user_email)
                    pipe.set(email_index_key, str(user.id), ex=USER_CACHE_TTL)
                await pipe.execute()

            phone_prefix = user.phone[:3] if user.phone and len(user.phone) >= 3 else "***"
            phone_suffix = user.phone[-4:] if user.phone and len(user.phone) >= 4 else ""
            phone_masked = phone_prefix + "***" + phone_suffix
            logger.debug("[UserCache] Cached user ID %s (phone: %s)", user.id, phone_masked)

            return True
        except Exception as exc:
            logger.warning("[UserCache] Failed to cache user ID %s: %s", user.id, exc)
            return False

    async def bulk_cache_users(self, users: List[User]) -> int:
        """Cache many users in a single Redis pipeline (G9).

        Used by the startup cache loader to amortise the per-user round-trip
        cost: one ``MULTI`` round-trip per *batch* instead of one per user.
        Returns the number of users we attempted to write — the caller is
        expected to compare against ``len(users)`` to detect partial failure.

        Behaves like ``cache_user`` per record (delete-then-hset, plus phone
        and email indexes when present), but keeps the entire batch in a
        single non-transactional pipeline so a single bad record cannot abort
        the rest.
        """
        if not users:
            return 0
        if not is_redis_available():
            logger.debug("[UserCache] Redis unavailable, skipping bulk cache write")
            return 0
        redis_client = get_async_redis()
        if not redis_client:
            logger.debug("[UserCache] Redis client unavailable, skipping bulk cache write")
            return 0

        prepared: List[tuple] = []
        for user in users:
            try:
                prepared.append(
                    (
                        int(user.id),
                        self._serialize_user(user),
                        getattr(user, "phone", None),
                        getattr(user, "email", None),
                    )
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "[UserCache] Skipping user %s in bulk write: %s",
                    getattr(user, "id", "?"),
                    exc,
                )

        if not prepared:
            return 0

        try:
            async with redis_client.pipeline(transaction=False) as pipe:
                for user_id, user_dict, phone, email in prepared:
                    user_key = _keys.USER_BY_ID.format(user_id=user_id)
                    pipe.delete(user_key)
                    pipe.hset(user_key, mapping=user_dict)
                    pipe.expire(user_key, USER_CACHE_TTL)
                    if phone:
                        pipe.set(
                            _keys.USER_BY_PHONE.format(phone=phone),
                            str(user_id),
                            ex=USER_CACHE_TTL,
                        )
                    if email:
                        pipe.set(
                            _keys.USER_BY_EMAIL.format(email=email),
                            str(user_id),
                            ex=USER_CACHE_TTL,
                        )
                await pipe.execute()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("[UserCache] Bulk pipeline execute failed: %s", exc)
            return 0

        return len(prepared)

    async def invalidate(self, user_id: int, phone: Optional[str] = None, email: Optional[str] = None) -> bool:
        """
        Invalidate user cache entries (non-blocking).

        Deletes the user hash and phone index in a single pipeline.

        Args:
            user_id: User ID
            phone: Phone number
            email: Normalized email

        Returns:
            True if invalidated successfully, False otherwise
        """
        if not is_redis_available():
            logger.debug("[UserCache] Redis unavailable, skipping cache invalidation")
            return False

        redis_client = get_async_redis()
        if not redis_client:
            return False

        try:
            user_key = _keys.USER_BY_ID.format(user_id=user_id)
            keys_to_delete = [user_key]
            if phone:
                keys_to_delete.append(_keys.USER_BY_PHONE.format(phone=phone))
            if email:
                keys_to_delete.append(_keys.USER_BY_EMAIL.format(email=email))

            await redis_client.delete(*keys_to_delete)

            logger.info("[UserCache] Invalidated cache for user ID %s", user_id)
            return True
        except Exception as exc:
            logger.warning(
                "[UserCache] Failed to invalidate cache for user ID %s: %s",
                user_id,
                exc,
            )
            return False


def get_user_cache() -> UserCache:
    """Get or create global UserCache instance."""
    if not hasattr(get_user_cache, "cache_instance"):
        get_user_cache.cache_instance = UserCache()
        logger.info("[UserCache] Initialized")
    return get_user_cache.cache_instance


# Convenience alias
user_cache = get_user_cache()
