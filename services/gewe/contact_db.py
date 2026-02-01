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
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

from sqlalchemy import select, delete, and_
from sqlalchemy.orm import Session

from models.domain.gewe_contact import GeweContact
from services.redis.redis_client import RedisOperations, is_redis_available

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

    def __init__(self, db: Session):
        """
        Initialize contact database service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self._redis = RedisOperations()

    def save_contact(
        self,
        app_id: str,
        wxid: str,
        nickname: Optional[str] = None,
        remark: Optional[str] = None,
        avatar: Optional[str] = None,
        alias: Optional[str] = None,
        contact_type: Optional[str] = None,
        region: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
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

            # Serialize extra_data to JSON
            extra_data_json = None
            if extra_data:
                extra_data_json = json.dumps(extra_data, ensure_ascii=False)

            # Check if contact exists
            existing = self.db.execute(
                select(GeweContact).where(
                    and_(
                        GeweContact.app_id == app_id,
                        GeweContact.wxid == wxid
                    )
                )
            ).scalar_one_or_none()

            if existing:
                # Update existing contact
                existing.nickname = nickname
                existing.remark = remark
                existing.avatar = avatar
                existing.alias = alias
                existing.contact_type = contact_type
                existing.region = region
                existing.extra_data = extra_data_json
                existing.last_updated = datetime.utcnow()
            else:
                # Create new contact
                contact = GeweContact(
                    app_id=app_id,
                    wxid=wxid,
                    nickname=nickname,
                    remark=remark,
                    avatar=avatar,
                    alias=alias,
                    contact_type=contact_type,
                    region=region,
                    extra_data=extra_data_json,
                    last_updated=datetime.utcnow()
                )
                self.db.add(contact)

            self.db.commit()

            # Invalidate Redis cache (write-through pattern)
            if is_redis_available():
                try:
                    cache_key = f"{CONTACT_KEY_PREFIX}{app_id}:{wxid}"
                    self._redis.delete(cache_key)
                except Exception as e:
                    logger.debug("Failed to invalidate contact cache %s:%s: %s", app_id, wxid, e)

            return True
        except Exception as e:
            logger.error("Failed to save contact: %s", e, exc_info=True)
            self.db.rollback()
            return False

    def save_contacts_batch(
        self,
        app_id: str,
        contacts: List[Dict[str, Any]]
    ) -> int:
        """
        Save multiple contacts in batch.

        Args:
            app_id: Gewe app ID
            contacts: List of contact dictionaries

        Returns:
            Number of contacts saved
        """
        saved_count = 0
        for contact in contacts:
            wxid = contact.get("wxid") or contact.get("Wxid") or ""
            if not wxid:
                continue

            if self.save_contact(
                app_id=app_id,
                wxid=wxid,
                nickname=contact.get("nickname") or contact.get("NickName"),
                remark=contact.get("remark") or contact.get("Remark"),
                avatar=contact.get("avatar") or contact.get("BigHeadImgUrl") or contact.get("SmallHeadImgUrl"),
                alias=contact.get("alias") or contact.get("Alias"),
                contact_type=contact.get("type"),
                region=contact.get("region"),
                extra_data=contact
            ):
                saved_count += 1

        return saved_count

    def get_contact(
        self,
        app_id: str,
        wxid: str
    ) -> Optional[Dict[str, Any]]:
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
                cached = self._redis.get(cache_key)
                if cached:
                    try:
                        result = json.loads(cached)
                        logger.debug("Cache hit for contact %s:%s", app_id, wxid)
                        return result
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning("Corrupted cache for contact %s:%s: %s", app_id, wxid, e)
                        # Invalidate corrupted cache
                        self._redis.delete(cache_key)
            except Exception as e:
                logger.debug("Redis error for contact %s:%s: %s", app_id, wxid, e)

        # Cache miss - load from database
        try:
            contact = self.db.execute(
                select(GeweContact).where(
                    and_(
                        GeweContact.app_id == app_id,
                        GeweContact.wxid == wxid
                    )
                )
            ).scalar_one_or_none()

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
                "last_updated": contact.last_updated.isoformat() if contact.last_updated else None
            }

            # Parse extra_data
            if contact.extra_data:
                try:
                    extra = json.loads(contact.extra_data)
                    result.update(extra)
                except Exception:
                    pass

            # Cache result in Redis (non-blocking)
            if is_redis_available():
                try:
                    cache_key = f"{CONTACT_KEY_PREFIX}{app_id}:{wxid}"
                    self._redis.set_with_ttl(
                        cache_key,
                        json.dumps(result, ensure_ascii=False),
                        CONTACT_CACHE_TTL
                    )
                except Exception as e:
                    logger.debug("Failed to cache contact %s:%s: %s", app_id, wxid, e)

            return result
        except Exception as e:
            logger.error("Failed to get contact: %s", e, exc_info=True)
            return None

    def get_contacts(
        self,
        app_id: str,
        contact_type: Optional[str] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None
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
            query = select(GeweContact).where(
                GeweContact.app_id == app_id
            )

            if contact_type:
                query = query.where(GeweContact.contact_type == contact_type)

            query = query.order_by(GeweContact.nickname)

            if limit:
                query = query.limit(limit)
            if offset:
                query = query.offset(offset)

            result = self.db.execute(query)
            contacts = []

            for contact in result.scalars().all():
                contact_dict = {
                    "wxid": contact.wxid,
                    "nickname": contact.nickname,
                    "remark": contact.remark,
                    "avatar": contact.avatar,
                    "alias": contact.alias,
                    "type": contact.contact_type,
                    "region": contact.region,
                    "last_updated": contact.last_updated.isoformat() if contact.last_updated else None
                }

                # Parse extra_data
                if contact.extra_data:
                    try:
                        extra = json.loads(contact.extra_data)
                        contact_dict.update(extra)
                    except Exception:
                        pass

                contacts.append(contact_dict)

            return contacts
        except Exception as e:
            logger.error("Failed to get contacts: %s", e, exc_info=True)
            return []

    def delete_contact(
        self,
        app_id: str,
        wxid: str
    ) -> bool:
        """
        Delete contact from database.

        Args:
            app_id: Gewe app ID
            wxid: Contact wxid

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            result = self.db.execute(
                delete(GeweContact).where(
                    and_(
                        GeweContact.app_id == app_id,
                        GeweContact.wxid == wxid
                    )
                )
            )
            self.db.commit()

            # Invalidate Redis cache
            if is_redis_available():
                try:
                    cache_key = f"{CONTACT_KEY_PREFIX}{app_id}:{wxid}"
                    self._redis.delete(cache_key)
                except Exception as e:
                    logger.debug("Failed to invalidate contact cache %s:%s: %s", app_id, wxid, e)

            return result.rowcount > 0
        except Exception as e:
            logger.error("Failed to delete contact: %s", e, exc_info=True)
            self.db.rollback()
            return False

    def get_contacts_count(
        self,
        app_id: str,
        contact_type: Optional[str] = None
    ) -> int:
        """
        Get count of contacts.

        Args:
            app_id: Gewe app ID
            contact_type: Filter by type

        Returns:
            Contact count
        """
        try:
            query = select(GeweContact).where(
                GeweContact.app_id == app_id
            )

            if contact_type:
                query = query.where(GeweContact.contact_type == contact_type)

            result = self.db.execute(query)
            return len(list(result.scalars().all()))
        except Exception as e:
            logger.error("Failed to get contacts count: %s", e, exc_info=True)
            return 0
