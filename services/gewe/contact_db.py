"""Gewe Contact Database Service.

Handles storage and retrieval of WeChat contacts in PostgreSQL with Redis caching.
Similar to xxxbot-pad's contacts_db but uses PostgreSQL + Redis for better performance.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import json
from datetime import UTC, datetime
from typing import Optional, List, Dict, Any
import logging

from sqlalchemy import select, delete, and_
from sqlalchemy.sql.functions import count as sql_count
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.gewe_contact import GeweContact
from services.redis.redis_async_ops import AsyncRedisOperations
from services.redis.redis_client import is_redis_available

logger = logging.getLogger(__name__)

# Redis key prefix and TTL
CONTACT_KEY_PREFIX = "gewe:contact:"
CONTACT_CACHE_TTL = 3600  # 1 hour


class GeweContactDB:
    """
    Contact database service for storing and querying WeChat contacts.

    Uses PostgreSQL for persistent storage.
    Similar to xxxbot-pad's contacts_db pattern.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize contact database service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    async def save_contact(
        self,
        app_id: str,
        wxid: str,
        nickname: Optional[str] = None,
        remark: Optional[str] = None,
        avatar: Optional[str] = None,
        alias: Optional[str] = None,
        contact_type: Optional[str] = None,
        region: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Save or update contact in database.

        Args:
            app_id: Gewe app ID
            wxid: Contact wxid
            nickname: Contact nickname
            remark: Contact remark
            avatar: Avatar URL
            alias: WeChat alias
            contact_type: Type (friend, group, official)
            region: Region/location
            extra_data: Additional data as dict

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Determine contact type if not provided
            if not contact_type:
                if wxid.endswith("@chatroom"):
                    contact_type = "group"
                elif wxid.startswith("gh_"):
                    contact_type = "official"
                else:
                    contact_type = "friend"

            # JSONB columns accept dicts directly — no json.dumps needed.

            result = await self.db.execute(
                select(GeweContact).where(and_(GeweContact.app_id == app_id, GeweContact.wxid == wxid))
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.nickname = nickname
                existing.remark = remark
                existing.avatar = avatar
                existing.alias = alias
                existing.contact_type = contact_type
                existing.region = region
                existing.extra_data = extra_data
                existing.last_updated = datetime.now(UTC)
            else:
                contact = GeweContact(
                    app_id=app_id,
                    wxid=wxid,
                    nickname=nickname,
                    remark=remark,
                    avatar=avatar,
                    alias=alias,
                    contact_type=contact_type,
                    region=region,
                    extra_data=extra_data,
                    last_updated=datetime.now(UTC),
                )
                self.db.add(contact)

            await self.db.commit()

            # Invalidate Redis cache (write-through pattern)
            if is_redis_available():
                try:
                    cache_key = f"{CONTACT_KEY_PREFIX}{app_id}:{wxid}"
                    await AsyncRedisOperations.delete(cache_key)
                except Exception as e:
                    logger.debug("Failed to invalidate contact cache %s:%s: %s", app_id, wxid, e)

            return True
        except Exception as e:
            logger.error("Failed to save contact: %s", e, exc_info=True)
            await self.db.rollback()
            return False

    async def save_contacts_batch(self, app_id: str, contacts: List[Dict[str, Any]]) -> int:
        """
        Save multiple contacts in a single transaction.

        Replaces N individual save_contact() calls (each with its own commit) with
        a bulk SELECT + upsert pattern and a single commit.

        Args:
            app_id: Gewe app ID
            contacts: List of contact dictionaries

        Returns:
            Number of contacts successfully staged for save
        """
        # Filter out entries without a wxid.
        valid = []
        for contact in contacts:
            wxid = contact.get("wxid") or contact.get("Wxid") or ""
            if wxid:
                valid.append((wxid, contact))

        if not valid:
            return 0

        wxids = [wxid for wxid, _ in valid]

        # Bulk-load existing contacts in one query.
        existing_result = await self.db.execute(
            select(GeweContact).where(and_(GeweContact.app_id == app_id, GeweContact.wxid.in_(wxids)))
        )
        existing_by_wxid = {c.wxid: c for c in existing_result.scalars().all()}

        saved_count = 0
        invalidate_wxids = []
        for wxid, contact in valid:
            try:
                nickname = contact.get("nickname") or contact.get("NickName")
                remark = contact.get("remark") or contact.get("Remark")
                avatar = contact.get("avatar") or contact.get("BigHeadImgUrl") or contact.get("SmallHeadImgUrl")
                alias = contact.get("alias") or contact.get("Alias")
                contact_type = contact.get("type")
                region = contact.get("region")

                if not contact_type:
                    if wxid.endswith("@chatroom"):
                        contact_type = "group"
                    elif wxid.startswith("gh_"):
                        contact_type = "official"
                    else:
                        contact_type = "friend"

                existing = existing_by_wxid.get(wxid)
                if existing:
                    existing.nickname = nickname
                    existing.remark = remark
                    existing.avatar = avatar
                    existing.alias = alias
                    existing.contact_type = contact_type
                    existing.region = region
                    existing.extra_data = contact
                    existing.last_updated = datetime.now(UTC)
                else:
                    self.db.add(
                        GeweContact(
                            app_id=app_id,
                            wxid=wxid,
                            nickname=nickname,
                            remark=remark,
                            avatar=avatar,
                            alias=alias,
                            contact_type=contact_type,
                            region=region,
                            extra_data=contact,
                            last_updated=datetime.now(UTC),
                        )
                    )

                saved_count += 1
                invalidate_wxids.append(wxid)
            except Exception as exc:
                logger.warning("Failed to stage contact %s: %s", wxid, exc)

        try:
            await self.db.commit()
        except Exception as exc:
            logger.error("Failed to commit contacts batch: %s", exc, exc_info=True)
            await self.db.rollback()
            return 0

        # Invalidate Redis cache entries after the commit.
        if is_redis_available() and invalidate_wxids:
            for wxid in invalidate_wxids:
                try:
                    cache_key = f"{CONTACT_KEY_PREFIX}{app_id}:{wxid}"
                    await AsyncRedisOperations.delete(cache_key)
                except Exception as exc:
                    logger.debug("Failed to invalidate contact cache %s:%s: %s", app_id, wxid, exc)

        logger.info("Saved %d contacts in batch for app %s", saved_count, app_id)
        return saved_count

    async def get_contact(self, app_id: str, wxid: str) -> Optional[Dict[str, Any]]:
        """
        Get contact from database with Redis cache lookup.

        Uses write-through pattern: Redis cache -> Database -> Cache result.

        Args:
            app_id: Gewe app ID
            wxid: Contact wxid

        Returns:
            Contact dictionary or None
        """
        # Try Redis cache first
        if is_redis_available():
            cache_key = f"{CONTACT_KEY_PREFIX}{app_id}:{wxid}"
            try:
                cached = await AsyncRedisOperations.get(cache_key)
                if cached:
                    try:
                        result = json.loads(cached)
                        logger.debug("Cache hit for contact %s:%s", app_id, wxid)
                        return result
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning("Corrupted cache for contact %s:%s: %s", app_id, wxid, e)
                        # Invalidate corrupted cache
                        await AsyncRedisOperations.delete(cache_key)
            except Exception as e:
                logger.debug("Redis error for contact %s:%s: %s", app_id, wxid, e)

        # Cache miss - load from database
        try:
            result = await self.db.execute(
                select(GeweContact).where(and_(GeweContact.app_id == app_id, GeweContact.wxid == wxid))
            )
            contact = result.scalar_one_or_none()

            if not contact:
                return None

            result = {
                "wxid": contact.wxid,
                "nickname": contact.nickname,
                "remark": contact.remark,
                "avatar": contact.avatar,
                "alias": contact.alias,
                "type": contact.contact_type,
                "region": contact.region,
                "last_updated": contact.last_updated.isoformat() if contact.last_updated else None,
            }

            # JSONB extra_data is already a dict; legacy Text rows are handled gracefully.
            if contact.extra_data:
                if isinstance(contact.extra_data, dict):
                    result.update(contact.extra_data)
                elif isinstance(contact.extra_data, str):
                    try:
                        result.update(json.loads(contact.extra_data))
                    except (ValueError, TypeError):
                        pass

            if is_redis_available():
                try:
                    cache_key = f"{CONTACT_KEY_PREFIX}{app_id}:{wxid}"
                    await AsyncRedisOperations.set_with_ttl(
                        cache_key,
                        json.dumps(result, ensure_ascii=False),
                        CONTACT_CACHE_TTL,
                    )
                except Exception as exc:
                    logger.debug("Failed to cache contact %s:%s: %s", app_id, wxid, exc)

            return result
        except Exception as exc:
            logger.error("Failed to get contact: %s", exc, exc_info=True)
            return None

    async def get_contacts(
        self,
        app_id: str,
        contact_type: Optional[str] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get contacts list with optional filtering and pagination.

        Args:
            app_id: Gewe app ID
            contact_type: Filter by type (friend, group, official)
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            List of contact dictionaries
        """
        try:
            query = select(GeweContact).where(GeweContact.app_id == app_id)

            if contact_type:
                query = query.where(GeweContact.contact_type == contact_type)

            query = query.order_by(GeweContact.nickname)

            if limit:
                query = query.limit(limit)
            if offset:
                query = query.offset(offset)

            db_result = await self.db.execute(query)
            contacts = []

            for contact in db_result.scalars().all():
                contact_dict = {
                    "wxid": contact.wxid,
                    "nickname": contact.nickname,
                    "remark": contact.remark,
                    "avatar": contact.avatar,
                    "alias": contact.alias,
                    "type": contact.contact_type,
                    "region": contact.region,
                    "last_updated": contact.last_updated.isoformat() if contact.last_updated else None,
                }

                if contact.extra_data:
                    if isinstance(contact.extra_data, dict):
                        contact_dict.update(contact.extra_data)
                    elif isinstance(contact.extra_data, str):
                        try:
                            contact_dict.update(json.loads(contact.extra_data))
                        except (ValueError, TypeError):
                            pass

                contacts.append(contact_dict)

            return contacts
        except Exception as e:
            logger.error("Failed to get contacts: %s", e, exc_info=True)
            return []

    async def delete_contact(self, app_id: str, wxid: str) -> bool:
        """
        Delete contact from database.

        Args:
            app_id: Gewe app ID
            wxid: Contact wxid

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            result = await self.db.execute(
                delete(GeweContact).where(and_(GeweContact.app_id == app_id, GeweContact.wxid == wxid))
            )
            await self.db.commit()

            # Invalidate Redis cache
            if is_redis_available():
                try:
                    cache_key = f"{CONTACT_KEY_PREFIX}{app_id}:{wxid}"
                    await AsyncRedisOperations.delete(cache_key)
                except Exception as e:
                    logger.debug("Failed to invalidate contact cache %s:%s: %s", app_id, wxid, e)

            return result.rowcount > 0
        except Exception as e:
            logger.error("Failed to delete contact: %s", e, exc_info=True)
            await self.db.rollback()
            return False

    async def get_contacts_count(self, app_id: str, contact_type: Optional[str] = None) -> int:
        """
        Get count of contacts.

        Args:
            app_id: Gewe app ID
            contact_type: Filter by type

        Returns:
            Contact count
        """
        try:
            query = select(sql_count()).select_from(GeweContact).where(GeweContact.app_id == app_id)

            if contact_type:
                query = query.where(GeweContact.contact_type == contact_type)

            count_result = await self.db.execute(query)
            return count_result.scalar() or 0
        except Exception as e:
            logger.error("Failed to get contacts count: %s", e, exc_info=True)
            return 0
