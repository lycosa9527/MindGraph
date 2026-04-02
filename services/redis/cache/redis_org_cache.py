"""
Redis Organization Cache Service
================================

High-performance organization caching using Redis with write-through pattern.
Database remains source of truth, Redis provides fast read cache.

Features:
- O(1) organization lookups by ID, code, or invitation code
- Automatic database fallback on cache miss
- Write-through pattern (database first, then Redis)
- Non-blocking cache operations
- Comprehensive error handling

Key Schema:
- org:{id} -> Hash with org data
- org:code:{code} -> String pointing to org ID (index)
- org:invite:{invite_code} -> String pointing to org ID (index)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from datetime import UTC, datetime
from typing import Optional, Dict

from sqlalchemy import select

from services.redis.redis_client import is_redis_available, RedisOps, get_redis
from config.database import AsyncSessionLocal
from models.domain.auth import Organization

logger = logging.getLogger(__name__)

# Redis key prefixes
ORG_KEY_PREFIX = "org:"
ORG_CODE_INDEX_PREFIX = "org:code:"
ORG_INVITE_INDEX_PREFIX = "org:invite:"

# Safety TTL: keys are refreshed on every cache_org() call; 24 h prevents
# orphaned keys from consuming memory indefinitely if invalidation misses.
ORG_CACHE_TTL = 86400  # 24 hours


class OrganizationCache:
    """
    Redis-based organization caching service.

    Provides fast organization lookups with automatic database fallback.
    Uses write-through pattern: database is source of truth, Redis is cache.
    """

    def __init__(self):
        """Initialize OrganizationCache instance."""

    def _serialize_org(self, org: Organization) -> Dict[str, str]:
        """
        Serialize Organization object to dict for Redis hash storage.

        Args:
            org: Organization SQLAlchemy model instance

        Returns:
            Dict with string values for Redis hash
        """
        created_at_val = getattr(org, "created_at", None)
        expires_at_val = getattr(org, "expires_at", None)
        is_active_val = getattr(org, "is_active", True) if hasattr(org, "is_active") else True
        return {
            "id": str(getattr(org, "id", 0)),
            "code": str(getattr(org, "code", None) or ""),
            "name": str(getattr(org, "name", None) or ""),
            "display_name": str(getattr(org, "display_name", None) or ""),
            "invitation_code": str(getattr(org, "invitation_code", None) or ""),
            "created_at": created_at_val.isoformat() if created_at_val else "",
            "expires_at": expires_at_val.isoformat() if expires_at_val else "",
            "is_active": "1" if is_active_val else "0",
        }

    def _deserialize_org(self, data: Dict[str, str]) -> Organization:
        """
        Deserialize dict from Redis hash to Organization object.

        Args:
            data: Dict from Redis hash_get_all()

        Returns:
            Organization SQLAlchemy model instance (detached from session)
        """
        org = Organization()
        setattr(org, "id", int(data.get("id", "0")))
        setattr(org, "code", data.get("code") or None)
        setattr(org, "name", data.get("name") or None)
        setattr(org, "invitation_code", data.get("invitation_code") or None)
        display_name_val = data.get("display_name") or None
        if hasattr(Organization, "display_name"):
            setattr(org, "display_name", display_name_val)

        # Parse datetime fields
        if data.get("created_at"):
            try:
                setattr(org, "created_at", datetime.fromisoformat(data["created_at"]))
            except (ValueError, TypeError):
                setattr(org, "created_at", datetime.now(UTC))
        else:
            setattr(org, "created_at", datetime.now(UTC))

        if data.get("expires_at"):
            try:
                setattr(org, "expires_at", datetime.fromisoformat(data["expires_at"]))
            except (ValueError, TypeError):
                setattr(org, "expires_at", None)
        else:
            setattr(org, "expires_at", None)

        # Parse boolean
        if hasattr(Organization, "is_active"):
            setattr(org, "is_active", data.get("is_active", "0") == "1")

        return org

    async def _load_from_database(
        self,
        org_id: Optional[int] = None,
        code: Optional[str] = None,
        invite_code: Optional[str] = None,
    ) -> Optional[Organization]:
        """
        Load organization from database.

        Args:
            org_id: Organization ID to load (if provided)
            code: Organization code to load (if provided)
            invite_code: Invitation code to load (if provided)

        Returns:
            Organization object or None if not found
        """
        try:
            async with AsyncSessionLocal() as db:
                if org_id:
                    result = await db.execute(select(Organization).where(Organization.id == org_id))
                    org = result.scalar_one_or_none()
                elif code:
                    result = await db.execute(select(Organization).where(Organization.code == code))
                    org = result.scalar_one_or_none()
                elif invite_code:
                    result = await db.execute(select(Organization).where(Organization.invitation_code == invite_code))
                    org = result.scalar_one_or_none()
                else:
                    return None

                if org:
                    try:
                        self.cache_org(org)
                    except Exception as e:
                        logger.debug("[OrgCache] Failed to cache org loaded from database: %s", e)

                return org
        except Exception as e:
            logger.error("[OrgCache] Database query failed: %s", e, exc_info=True)
            raise

    async def get_by_id(self, org_id: int) -> Optional[Organization]:
        """
        Get organization by ID with cache lookup and database fallback.

        Args:
            org_id: Organization ID

        Returns:
            Organization object or None if not found
        """
        if not is_redis_available():
            logger.debug("[OrgCache] Redis unavailable, loading org ID %s from database", org_id)
            return await self._load_from_database(org_id=org_id)

        try:
            key = f"{ORG_KEY_PREFIX}{org_id}"
            cached = RedisOps.hash_get_all(key)

            if cached:
                try:
                    org = self._deserialize_org(cached)
                    logger.debug("[OrgCache] Cache hit for org ID %s", org_id)
                    return org
                except (KeyError, ValueError, TypeError) as e:
                    logger.error(
                        "[OrgCache] Corrupted cache for org ID %s: %s",
                        org_id,
                        e,
                        exc_info=True,
                    )
                    try:
                        RedisOps.delete(key)
                    except Exception as exc:
                        logger.debug(
                            "Corrupted org cache entry deletion failed for org ID %s: %s",
                            org_id,
                            exc,
                        )
                    return await self._load_from_database(org_id=org_id)
        except Exception as e:
            logger.warning(
                "[OrgCache] Redis error for org ID %s, falling back to database: %s",
                org_id,
                e,
            )
            return await self._load_from_database(org_id=org_id)

        logger.debug("[OrgCache] Cache miss for org ID %s, loading from database", org_id)
        return await self._load_from_database(org_id=org_id)

    async def get_by_code(self, code: str) -> Optional[Organization]:
        """
        Get organization by code with cache lookup and database fallback.

        Args:
            code: Organization code

        Returns:
            Organization object or None if not found
        """
        if not is_redis_available():
            logger.debug(
                "[OrgCache] Redis unavailable, loading org by code %s from database",
                code,
            )
            return await self._load_from_database(code=code)

        try:
            index_key = f"{ORG_CODE_INDEX_PREFIX}{code}"
            org_id_str = RedisOps.get(index_key)

            if org_id_str:
                try:
                    org_id = int(org_id_str)
                    return await self.get_by_id(org_id)
                except (ValueError, TypeError) as e:
                    logger.error("[OrgCache] Invalid org ID in code index for %s: %s", code, e)
                    try:
                        RedisOps.delete(index_key)
                    except Exception as exc:
                        logger.debug(
                            "Corrupted org code index deletion failed for code %s: %s",
                            code,
                            exc,
                        )
                    return await self._load_from_database(code=code)
        except Exception as e:
            logger.warning(
                "[OrgCache] Redis error for code %s, falling back to database: %s",
                code,
                e,
            )
            return await self._load_from_database(code=code)

        logger.debug("[OrgCache] Cache miss for org code %s, loading from database", code)
        return await self._load_from_database(code=code)

    async def get_by_invitation_code(self, invite_code: str) -> Optional[Organization]:
        """
        Get organization by invitation code with cache lookup and database fallback.

        Args:
            invite_code: Invitation code

        Returns:
            Organization object or None if not found
        """
        if not is_redis_available():
            masked_invite = f"{invite_code[:8]}***" if len(invite_code) >= 8 else "***"
            logger.debug(
                "[OrgCache] Redis unavailable, loading org by invitation code %s from database",
                masked_invite,
            )
            return await self._load_from_database(invite_code=invite_code)

        try:
            index_key = f"{ORG_INVITE_INDEX_PREFIX}{invite_code}"
            org_id_str = RedisOps.get(index_key)

            if org_id_str:
                try:
                    org_id = int(org_id_str)
                    return await self.get_by_id(org_id)
                except (ValueError, TypeError) as e:
                    masked_invite = f"{invite_code[:8]}***" if len(invite_code) >= 8 else "***"
                    logger.error(
                        "[OrgCache] Invalid org ID in invite index for %s: %s",
                        masked_invite,
                        e,
                    )
                    try:
                        RedisOps.delete(index_key)
                    except Exception as exc:
                        logger.debug("Corrupted org invite index deletion failed: %s", exc)
                    return await self._load_from_database(invite_code=invite_code)
        except Exception as e:
            masked_invite = f"{invite_code[:8]}***" if len(invite_code) >= 8 else "***"
            logger.warning(
                "[OrgCache] Redis error for invitation code %s, falling back to database: %s",
                masked_invite,
                e,
            )
            return await self._load_from_database(invite_code=invite_code)

        masked_invite = f"{invite_code[:8]}***" if len(invite_code) >= 8 else "***"
        logger.debug(
            "[OrgCache] Cache miss for invitation code %s, loading from database",
            masked_invite,
        )
        return await self._load_from_database(invite_code=invite_code)

    def cache_org(self, org: Organization) -> bool:
        """
        Cache organization in Redis (non-blocking).

        Writes the org hash and all lookup indexes in a single pipeline
        to avoid multiple round-trips.

        Args:
            org: Organization SQLAlchemy model instance

        Returns:
            True if cached successfully, False otherwise
        """
        if not is_redis_available():
            logger.debug("[OrgCache] Redis unavailable, skipping cache write")
            return False

        redis_client = get_redis()
        if not redis_client:
            logger.debug("[OrgCache] Redis client unavailable, skipping cache write")
            return False

        try:
            org_dict = self._serialize_org(org)

            org_id = int(getattr(org, "id", 0))
            org_code = getattr(org, "code", None)
            org_invite = getattr(org, "invitation_code", None)

            org_key = f"{ORG_KEY_PREFIX}{org_id}"

            pipe = redis_client.pipeline()
            # DELETE before HSET to clear any stale key with wrong type.
            pipe.delete(org_key)
            pipe.hset(org_key, mapping=org_dict)
            pipe.expire(org_key, ORG_CACHE_TTL)
            if org_code:
                pipe.set(f"{ORG_CODE_INDEX_PREFIX}{org_code}", str(org_id), ex=ORG_CACHE_TTL)
            if org_invite:
                pipe.set(
                    f"{ORG_INVITE_INDEX_PREFIX}{org_invite}",
                    str(org_id),
                    ex=ORG_CACHE_TTL,
                )
            pipe.execute()

            if org_invite and len(org_invite) >= 8:
                masked_invite = f"{org_invite[:8]}***"
            else:
                masked_invite = "***"
            logger.debug(
                "[OrgCache] Cached org indexes: code %s, invite %s -> ID %s",
                org_code,
                masked_invite,
                org_id,
            )

            return True
        except Exception as exc:
            logger.warning("[OrgCache] Failed to cache org ID %s: %s", getattr(org, "id", "?"), exc)
            return False

    def invalidate(self, org_id: int, code: Optional[str] = None, invite_code: Optional[str] = None) -> bool:
        """
        Invalidate organization cache entries (non-blocking).

        Deletes org hash and all lookup indexes in a single DELETE command.

        Args:
            org_id: Organization ID (always delete main hash)
            code: Organization code for index deletion (use pre-update value)
            invite_code: Invitation code for index deletion (use pre-update value)

        Returns:
            True if invalidated successfully, False otherwise
        """
        if not is_redis_available():
            logger.debug("[OrgCache] Redis unavailable, skipping cache invalidation")
            return False

        redis_client = get_redis()
        if not redis_client:
            return False

        try:
            keys_to_delete = [f"{ORG_KEY_PREFIX}{org_id}"]
            if code:
                keys_to_delete.append(f"{ORG_CODE_INDEX_PREFIX}{code}")
            if invite_code:
                keys_to_delete.append(f"{ORG_INVITE_INDEX_PREFIX}{invite_code}")

            redis_client.delete(*keys_to_delete)
            logger.info("[OrgCache] Invalidated cache for org ID %s", org_id)
            return True
        except Exception as exc:
            logger.warning("[OrgCache] Failed to invalidate cache for org ID %s: %s", org_id, exc)
            return False

    def write_through(self, org: Organization, old_code: Optional[str], old_invite: Optional[str]) -> bool:
        """
        Write-through: invalidate old entries then cache updated org.
        Call only after successful db.commit(). Database is source of truth.

        Args:
            org: Session-attached Organization after db.refresh()
            old_code: Code before update (for index invalidation)
            old_invite: Invitation code before update (for index invalidation)

        Returns:
            True if cache updated successfully
        """
        self.invalidate(int(getattr(org, "id", 0)), old_code, old_invite)
        return self.cache_org(org)


def get_org_cache() -> OrganizationCache:
    """Get or create global OrganizationCache instance."""
    if not hasattr(get_org_cache, "cache_instance"):
        get_org_cache.cache_instance = OrganizationCache()
        logger.info("[OrgCache] Initialized")
    return get_org_cache.cache_instance


# Convenience alias
org_cache = get_org_cache()
