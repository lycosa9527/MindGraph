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
from typing import Optional, Dict
from datetime import datetime

from services.redis.redis_client import is_redis_available, RedisOps, get_redis
from config.database import SessionLocal
from models.domain.auth import Organization

logger = logging.getLogger(__name__)

# Redis key prefixes
ORG_KEY_PREFIX = "org:"
ORG_CODE_INDEX_PREFIX = "org:code:"
ORG_INVITE_INDEX_PREFIX = "org:invite:"


class OrganizationCache:
    """
    Redis-based organization caching service.

    Provides fast organization lookups with automatic database fallback.
    Uses write-through pattern: database is source of truth, Redis is cache.
    """

    def __init__(self):
        """Initialize OrganizationCache instance."""
        pass

    def _serialize_org(self, org: Organization) -> Dict[str, str]:
        """
        Serialize Organization object to dict for Redis hash storage.

        Args:
            org: Organization SQLAlchemy model instance

        Returns:
            Dict with string values for Redis hash
        """
        return {
            'id': str(org.id),
            'code': org.code or '',
            'name': org.name or '',
            'invitation_code': org.invitation_code or '',
            'created_at': org.created_at.isoformat() if org.created_at else '',
            'expires_at': org.expires_at.isoformat() if org.expires_at else '',
            'is_active': '1' if (hasattr(org, 'is_active') and org.is_active) else '0',
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
        org.id = int(data.get('id', '0'))
        org.code = data.get('code') or None
        org.name = data.get('name') or None
        org.invitation_code = data.get('invitation_code') or None

        # Parse datetime fields
        if data.get('created_at'):
            try:
                org.created_at = datetime.fromisoformat(data['created_at'])
            except (ValueError, TypeError):
                org.created_at = datetime.utcnow()
        else:
            org.created_at = datetime.utcnow()

        if data.get('expires_at'):
            try:
                org.expires_at = datetime.fromisoformat(data['expires_at'])
            except (ValueError, TypeError):
                org.expires_at = None
        else:
            org.expires_at = None

        # Parse boolean
        if hasattr(Organization, 'is_active'):
            org.is_active = data.get('is_active', '0') == '1'

        return org

    def _load_from_database(
        self,
        org_id: Optional[int] = None,
        code: Optional[str] = None,
        invite_code: Optional[str] = None
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
        db = SessionLocal()
        try:
            if org_id:
                org = db.query(Organization).filter(Organization.id == org_id).first()
            elif code:
                org = db.query(Organization).filter(Organization.code == code).first()
            elif invite_code:
                org = db.query(Organization).filter(Organization.invitation_code == invite_code).first()
            else:
                return None

            if org:
                # Detach from session so it can be used after close
                db.expunge(org)
                # Cache it for next time (non-blocking)
                try:
                    self.cache_org(org)
                except Exception as e:
                    logger.debug("[OrgCache] Failed to cache org loaded from database: %s", e)

            return org
        except Exception as e:
            logger.error("[OrgCache] Database query failed: %s", e, exc_info=True)
            raise
        finally:
            db.close()

    def get_by_id(self, org_id: int) -> Optional[Organization]:
        """
        Get organization by ID with cache lookup and database fallback.

        Args:
            org_id: Organization ID

        Returns:
            Organization object or None if not found
        """
        # Check Redis availability
        if not is_redis_available():
            logger.debug("[OrgCache] Redis unavailable, loading org ID %s from database", org_id)
            return self._load_from_database(org_id=org_id)

        try:
            # Try cache read
            key = f"{ORG_KEY_PREFIX}{org_id}"
            cached = RedisOps.hash_get_all(key)

            if cached:
                try:
                    org = self._deserialize_org(cached)
                    logger.debug("[OrgCache] Cache hit for org ID %s", org_id)
                    return org
                except (KeyError, ValueError, TypeError) as e:
                    # Corrupted cache entry
                    logger.error("[OrgCache] Corrupted cache for org ID %s: %s", org_id, e, exc_info=True)
                    # Invalidate corrupted entry
                    try:
                        RedisOps.delete(key)
                    except Exception:
                        pass
                    # Fallback to database
                    return self._load_from_database(org_id=org_id)
        except Exception as e:
            # Transient Redis errors - fallback to database
            logger.warning("[OrgCache] Redis error for org ID %s, falling back to database: %s", org_id, e)
            return self._load_from_database(org_id=org_id)

        # Cache miss - load from database
        logger.debug("[OrgCache] Cache miss for org ID %s, loading from database", org_id)
        return self._load_from_database(org_id=org_id)

    def get_by_code(self, code: str) -> Optional[Organization]:
        """
        Get organization by code with cache lookup and database fallback.

        Args:
            code: Organization code

        Returns:
            Organization object or None if not found
        """
        # Check Redis availability
        if not is_redis_available():
            logger.debug("[OrgCache] Redis unavailable, loading org by code %s from database", code)
            return self._load_from_database(code=code)

        try:
            # Try cache index lookup
            index_key = f"{ORG_CODE_INDEX_PREFIX}{code}"
            org_id_str = RedisOps.get(index_key)

            if org_id_str:
                try:
                    org_id = int(org_id_str)
                    # Load org by ID (will use cache)
                    return self.get_by_id(org_id)
                except (ValueError, TypeError) as e:
                    logger.error("[OrgCache] Invalid org ID in code index for %s: %s", code, e)
                    # Invalidate corrupted index
                    try:
                        RedisOps.delete(index_key)
                    except Exception:
                        pass
                    # Fallback to database
                    return self._load_from_database(code=code)
        except Exception as e:
            # Transient Redis errors - fallback to database
            logger.warning("[OrgCache] Redis error for code %s, falling back to database: %s", code, e)
            return self._load_from_database(code=code)

        # Cache miss - load from database
        logger.debug("[OrgCache] Cache miss for org code %s, loading from database", code)
        return self._load_from_database(code=code)

    def get_by_invitation_code(self, invite_code: str) -> Optional[Organization]:
        """
        Get organization by invitation code with cache lookup and database fallback.

        Args:
            invite_code: Invitation code

        Returns:
            Organization object or None if not found
        """
        # Check Redis availability
        if not is_redis_available():
            masked_invite = f"{invite_code[:8]}***" if len(invite_code) >= 8 else "***"
            logger.debug("[OrgCache] Redis unavailable, loading org by invitation code %s from database", masked_invite)
            return self._load_from_database(invite_code=invite_code)

        try:
            # Try cache index lookup
            index_key = f"{ORG_INVITE_INDEX_PREFIX}{invite_code}"
            org_id_str = RedisOps.get(index_key)

            if org_id_str:
                try:
                    org_id = int(org_id_str)
                    # Load org by ID (will use cache)
                    return self.get_by_id(org_id)
                except (ValueError, TypeError) as e:
                    masked_invite = f"{invite_code[:8]}***" if len(invite_code) >= 8 else "***"
                    logger.error("[OrgCache] Invalid org ID in invite index for %s: %s", masked_invite, e)
                    # Invalidate corrupted index
                    try:
                        RedisOps.delete(index_key)
                    except Exception:
                        pass
                    # Fallback to database
                    return self._load_from_database(invite_code=invite_code)
        except Exception as e:
            # Transient Redis errors - fallback to database
            masked_invite = f"{invite_code[:8]}***" if len(invite_code) >= 8 else "***"
            logger.warning(
                "[OrgCache] Redis error for invitation code %s, "
                "falling back to database: %s",
                masked_invite,
                e
            )
            return self._load_from_database(invite_code=invite_code)

        # Cache miss - load from database
        masked_invite = f"{invite_code[:8]}***" if len(invite_code) >= 8 else "***"
        logger.debug("[OrgCache] Cache miss for invitation code %s, loading from database", masked_invite)
        return self._load_from_database(invite_code=invite_code)

    def cache_org(self, org: Organization) -> bool:
        """
        Cache organization in Redis (non-blocking).

        Args:
            org: Organization SQLAlchemy model instance

        Returns:
            True if cached successfully, False otherwise
        """
        if not is_redis_available():
            logger.debug("[OrgCache] Redis unavailable, skipping cache write")
            return False

        try:
            # Serialize org
            org_dict = self._serialize_org(org)

            # Store org hash
            org_key = f"{ORG_KEY_PREFIX}{org.id}"
            success = RedisOps.hash_set(org_key, org_dict)

            if not success:
                logger.warning("[OrgCache] Failed to cache org ID %s", org.id)
                return False

            # Store code and invitation code indexes (permanent, no TTL)
            redis = get_redis()
            if redis:
                if org.code:
                    code_index_key = f"{ORG_CODE_INDEX_PREFIX}{org.code}"
                    redis.set(code_index_key, str(org.id))  # Permanent storage, no TTL

                if org.invitation_code:
                    invite_index_key = f"{ORG_INVITE_INDEX_PREFIX}{org.invitation_code}"
                    redis.set(invite_index_key, str(org.id))  # Permanent storage, no TTL

            if org.invitation_code and len(org.invitation_code) >= 8:
                masked_invite = f"{org.invitation_code[:8]}***"
            else:
                masked_invite = "***"
            logger.debug("[OrgCache] Cached org indexes: code %s, invite %s -> ID %s", org.code, masked_invite, org.id)

            return True
        except Exception as e:
            # Log but don't raise - cache failures are non-critical
            logger.warning("[OrgCache] Failed to cache org ID %s: %s", org.id, e)
            return False

    def invalidate(self, org_id: int, code: Optional[str] = None, invite_code: Optional[str] = None) -> bool:
        """
        Invalidate organization cache entries (non-blocking).

        Args:
            org_id: Organization ID
            code: Organization code (optional, for index deletion)
            invite_code: Invitation code (optional, for index deletion)

        Returns:
            True if invalidated successfully, False otherwise
        """
        if not is_redis_available():
            logger.debug("[OrgCache] Redis unavailable, skipping cache invalidation")
            return False

        try:
            # Delete org hash
            org_key = f"{ORG_KEY_PREFIX}{org_id}"
            RedisOps.delete(org_key)

            # Delete code index
            if code:
                code_index_key = f"{ORG_CODE_INDEX_PREFIX}{code}"
                RedisOps.delete(code_index_key)

            # Delete invitation code index
            if invite_code:
                invite_index_key = f"{ORG_INVITE_INDEX_PREFIX}{invite_code}"
                RedisOps.delete(invite_index_key)

            logger.info("[OrgCache] Invalidated cache for org ID %s", org_id)
            logger.debug("[OrgCache] Deleted cache keys: org:%s, org:code:%s, org:invite:%s", org_id, code, invite_code)

            return True
        except Exception as e:
            # Log but don't raise - invalidation failures are non-critical
            logger.warning("[OrgCache] Failed to invalidate cache for org ID %s: %s", org_id, e)
            return False


def get_org_cache() -> OrganizationCache:
    """Get or create global OrganizationCache instance."""
    if not hasattr(get_org_cache, 'cache_instance'):
        get_org_cache.cache_instance = OrganizationCache()
        logger.info("[OrgCache] Initialized")
    return get_org_cache.cache_instance


# Convenience alias
org_cache = get_org_cache()

