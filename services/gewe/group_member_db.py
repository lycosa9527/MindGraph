"""Gewe Group Member Database Service.

Handles storage and retrieval of WeChat group members in PostgreSQL with Redis caching.
Similar to xxxbot-pad's group_members_db but uses PostgreSQL + Redis for better performance.

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

from models.domain.gewe_group_member import GeweGroupMember
from services.redis.redis_client import RedisOperations, is_redis_available

logger = logging.getLogger(__name__)

# Redis key prefix and TTL
GROUP_MEMBER_KEY_PREFIX = "gewe:group_member:"
GROUP_MEMBER_LIST_KEY_PREFIX = "gewe:group_members:"
GROUP_MEMBER_CACHE_TTL = 1800  # 30 minutes (shorter than contacts as group members change more frequently)


class GeweGroupMemberDB:
    """
    Group member database service for storing and querying WeChat group members.

    Uses PostgreSQL for persistent storage.
    Similar to xxxbot-pad's group_members_db pattern.
    """

    def __init__(self, db: Session):
        """
        Initialize group member database service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self._redis = RedisOperations()

    def save_group_members(
        self,
        app_id: str,
        group_wxid: str,
        members: List[Dict[str, Any]]
    ) -> int:
        """
        Save group members list to database.

        Args:
            app_id: Gewe app ID
            group_wxid: Group wxid
            members: List of member dictionaries

        Returns:
            Number of members saved
        """
        saved_count = 0
        for member in members:
            member_wxid = (
                member.get("wxid") or
                member.get("Wxid") or
                member.get("UserName") or
                ""
            )
            if not member_wxid:
                continue

            try:
                nickname = member.get("nickname") or member.get("NickName")
                display_name = member.get("display_name") or member.get("DisplayName")
                avatar = (
                    member.get("avatar") or
                    member.get("BigHeadImgUrl") or
                    member.get("SmallHeadImgUrl") or
                    member.get("HeadImgUrl")
                )
                inviter_wxid = member.get("InviterUserName") or member.get("inviter_wxid")

                # Extract join_time if available
                join_time = None
                if member.get("join_time"):
                    if isinstance(member["join_time"], datetime):
                        join_time = member["join_time"]
                    elif isinstance(member["join_time"], (int, float)):
                        join_time = datetime.fromtimestamp(member["join_time"])

                # Store extra data as JSON
                extra_data = {}
                for key, value in member.items():
                    if key not in [
                        "wxid", "Wxid", "UserName", "nickname", "NickName",
                        "display_name", "DisplayName", "avatar", "BigHeadImgUrl",
                        "SmallHeadImgUrl", "HeadImgUrl", "InviterUserName",
                        "inviter_wxid", "join_time"
                    ]:
                        extra_data[key] = value

                extra_data_json = json.dumps(extra_data, ensure_ascii=False) if extra_data else None

                # Check if member exists
                existing = self.db.execute(
                    select(GeweGroupMember).where(
                        and_(
                            GeweGroupMember.app_id == app_id,
                            GeweGroupMember.group_wxid == group_wxid,
                            GeweGroupMember.member_wxid == member_wxid
                        )
                    )
                ).scalar_one_or_none()

                if existing:
                    # Update existing member
                    existing.nickname = nickname
                    existing.display_name = display_name
                    existing.avatar = avatar
                    existing.inviter_wxid = inviter_wxid
                    existing.join_time = join_time
                    existing.extra_data = extra_data_json
                    existing.last_updated = datetime.utcnow()
                else:
                    # Create new member
                    group_member = GeweGroupMember(
                        app_id=app_id,
                        group_wxid=group_wxid,
                        member_wxid=member_wxid,
                        nickname=nickname,
                        display_name=display_name,
                        avatar=avatar,
                        inviter_wxid=inviter_wxid,
                        join_time=join_time,
                        extra_data=extra_data_json,
                        last_updated=datetime.utcnow()
                    )
                    self.db.add(group_member)

                saved_count += 1
            except Exception as e:
                logger.warning("Failed to save group member %s: %s", member_wxid, e)
                continue

        try:
            self.db.commit()
            logger.info("Saved %d group members for group %s", saved_count, group_wxid)

            # Invalidate Redis cache for group members list (write-through pattern)
            if is_redis_available():
                try:
                    list_cache_key = f"{GROUP_MEMBER_LIST_KEY_PREFIX}{app_id}:{group_wxid}"
                    self._redis.delete(list_cache_key)
                    # Also invalidate individual member caches
                    for member in members:
                        member_wxid = member.get("wxid") or member.get("Wxid") or member.get("UserName") or ""
                        if member_wxid:
                            member_cache_key = f"{GROUP_MEMBER_KEY_PREFIX}{app_id}:{group_wxid}:{member_wxid}"
                            self._redis.delete(member_cache_key)
                except Exception as e:
                    logger.debug("Failed to invalidate group member cache %s:%s: %s", app_id, group_wxid, e)
        except Exception as e:
            logger.error("Failed to commit group members: %s", e, exc_info=True)
            self.db.rollback()

        return saved_count

    def get_group_members(
        self,
        app_id: str,
        group_wxid: str
    ) -> List[Dict[str, Any]]:
        """
        Get group members list from database with Redis cache lookup.

        Uses write-through pattern: Redis cache -> Database -> Cache result.

        Args:
            app_id: Gewe app ID
            group_wxid: Group wxid

        Returns:
            List of member dictionaries
        """
        # Try Redis cache first
        if is_redis_available():
            cache_key = f"{GROUP_MEMBER_LIST_KEY_PREFIX}{app_id}:{group_wxid}"
            try:
                cached = self._redis.get(cache_key)
                if cached:
                    try:
                        members = json.loads(cached)
                        logger.debug("Cache hit for group members %s:%s", app_id, group_wxid)
                        return members
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning("Corrupted cache for group members %s:%s: %s", app_id, group_wxid, e)
                        # Invalidate corrupted cache
                        self._redis.delete(cache_key)
            except Exception as e:
                logger.debug("Redis error for group members %s:%s: %s", app_id, group_wxid, e)

        # Cache miss - load from database
        try:
            result = self.db.execute(
                select(GeweGroupMember).where(
                    and_(
                        GeweGroupMember.app_id == app_id,
                        GeweGroupMember.group_wxid == group_wxid
                    )
                ).order_by(GeweGroupMember.nickname)
            )

            members = []
            for member in result.scalars().all():
                member_dict = {
                    "wxid": member.member_wxid,
                    "nickname": member.nickname,
                    "display_name": member.display_name,
                    "avatar": member.avatar,
                    "inviter_wxid": member.inviter_wxid,
                    "join_time": member.join_time.isoformat() if member.join_time else None,
                    "last_updated": member.last_updated.isoformat() if member.last_updated else None
                }

                # Parse extra_data
                if member.extra_data:
                    try:
                        extra = json.loads(member.extra_data)
                        member_dict.update(extra)
                    except Exception:
                        pass

                members.append(member_dict)

            # Cache result in Redis (non-blocking)
            if is_redis_available():
                try:
                    cache_key = f"{GROUP_MEMBER_LIST_KEY_PREFIX}{app_id}:{group_wxid}"
                    self._redis.set_with_ttl(
                        cache_key,
                        json.dumps(members, ensure_ascii=False),
                        GROUP_MEMBER_CACHE_TTL
                    )
                except Exception as e:
                    logger.debug("Failed to cache group members %s:%s: %s", app_id, group_wxid, e)

            return members
        except Exception as e:
            logger.error("Failed to get group members: %s", e, exc_info=True)
            return []

    def get_group_member(
        self,
        app_id: str,
        group_wxid: str,
        member_wxid: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get single group member from database with Redis cache lookup.

        Args:
            app_id: Gewe app ID
            group_wxid: Group wxid
            member_wxid: Member wxid

        Returns:
            Member dictionary or None
        """
        # Try Redis cache first
        if is_redis_available():
            cache_key = f"{GROUP_MEMBER_KEY_PREFIX}{app_id}:{group_wxid}:{member_wxid}"
            try:
                cached = self._redis.get(cache_key)
                if cached:
                    try:
                        member_dict = json.loads(cached)
                        logger.debug("Cache hit for group member %s:%s:%s", app_id, group_wxid, member_wxid)
                        return member_dict
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning("Corrupted cache for group member %s:%s:%s: %s", app_id, group_wxid, member_wxid, e)
                        # Invalidate corrupted cache
                        self._redis.delete(cache_key)
            except Exception as e:
                logger.debug("Redis error for group member %s:%s:%s: %s", app_id, group_wxid, member_wxid, e)

        # Cache miss - load from database
        try:
            member = self.db.execute(
                select(GeweGroupMember).where(
                    and_(
                        GeweGroupMember.app_id == app_id,
                        GeweGroupMember.group_wxid == group_wxid,
                        GeweGroupMember.member_wxid == member_wxid
                    )
                )
            ).scalar_one_or_none()

            if not member:
                return None

            member_dict = {
                "wxid": member.member_wxid,
                "nickname": member.nickname,
                "display_name": member.display_name,
                "avatar": member.avatar,
                "inviter_wxid": member.inviter_wxid,
                "join_time": member.join_time.isoformat() if member.join_time else None,
                "last_updated": member.last_updated.isoformat() if member.last_updated else None
            }

            # Parse extra_data
            if member.extra_data:
                try:
                    extra = json.loads(member.extra_data)
                    member_dict.update(extra)
                except Exception:
                    pass

            # Cache result in Redis (non-blocking)
            if is_redis_available():
                try:
                    cache_key = f"{GROUP_MEMBER_KEY_PREFIX}{app_id}:{group_wxid}:{member_wxid}"
                    self._redis.set_with_ttl(
                        cache_key,
                        json.dumps(member_dict, ensure_ascii=False),
                        GROUP_MEMBER_CACHE_TTL
                    )
                except Exception as e:
                    logger.debug("Failed to cache group member %s:%s:%s: %s", app_id, group_wxid, member_wxid, e)

            return member_dict
        except Exception as e:
            logger.error("Failed to get group member: %s", e, exc_info=True)
            return None

    def delete_group_member(
        self,
        app_id: str,
        group_wxid: str,
        member_wxid: str
    ) -> bool:
        """
        Delete group member from database.

        Args:
            app_id: Gewe app ID
            group_wxid: Group wxid
            member_wxid: Member wxid

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            result = self.db.execute(
                delete(GeweGroupMember).where(
                    and_(
                        GeweGroupMember.app_id == app_id,
                        GeweGroupMember.group_wxid == group_wxid,
                        GeweGroupMember.member_wxid == member_wxid
                    )
                )
            )
            self.db.commit()

            # Invalidate Redis cache
            if is_redis_available() and result.rowcount > 0:
                try:
                    member_cache_key = f"{GROUP_MEMBER_KEY_PREFIX}{app_id}:{group_wxid}:{member_wxid}"
                    list_cache_key = f"{GROUP_MEMBER_LIST_KEY_PREFIX}{app_id}:{group_wxid}"
                    self._redis.delete(member_cache_key)
                    self._redis.delete(list_cache_key)
                except Exception as e:
                    logger.debug("Failed to invalidate group member cache %s:%s:%s: %s", app_id, group_wxid, member_wxid, e)

            return result.rowcount > 0
        except Exception as e:
            logger.error("Failed to delete group member: %s", e, exc_info=True)
            self.db.rollback()
            return False

    def delete_all_group_members(
        self,
        app_id: str,
        group_wxid: str
    ) -> int:
        """
        Delete all members of a group.

        Args:
            app_id: Gewe app ID
            group_wxid: Group wxid

        Returns:
            Number of members deleted
        """
        try:
            result = self.db.execute(
                delete(GeweGroupMember).where(
                    and_(
                        GeweGroupMember.app_id == app_id,
                        GeweGroupMember.group_wxid == group_wxid
                    )
                )
            )
            self.db.commit()

            # Invalidate Redis cache for group members list
            if is_redis_available() and result.rowcount > 0:
                try:
                    list_cache_key = f"{GROUP_MEMBER_LIST_KEY_PREFIX}{app_id}:{group_wxid}"
                    self._redis.delete(list_cache_key)
                except Exception as e:
                    logger.debug("Failed to invalidate group members list cache %s:%s: %s", app_id, group_wxid, e)

            return result.rowcount
        except Exception as e:
            logger.error("Failed to delete all group members: %s", e, exc_info=True)
            self.db.rollback()
            return 0

    def get_member_groups(
        self,
        app_id: str,
        member_wxid: str
    ) -> List[str]:
        """
        Get all groups that a member belongs to.

        Args:
            app_id: Gewe app ID
            member_wxid: Member wxid

        Returns:
            List of group wxids
        """
        try:
            result = self.db.execute(
                select(GeweGroupMember.group_wxid).where(
                    and_(
                        GeweGroupMember.app_id == app_id,
                        GeweGroupMember.member_wxid == member_wxid
                    )
                ).distinct()
            )

            return [row[0] for row in result.all()]
        except Exception as e:
            logger.error("Failed to get member groups: %s", e, exc_info=True)
            return []

    def get_group_member_count(
        self,
        app_id: str,
        group_wxid: str
    ) -> int:
        """
        Get count of members in a group.

        Args:
            app_id: Gewe app ID
            group_wxid: Group wxid

        Returns:
            Member count
        """
        try:
            result = self.db.execute(
                select(GeweGroupMember).where(
                    and_(
                        GeweGroupMember.app_id == app_id,
                        GeweGroupMember.group_wxid == group_wxid
                    )
                )
            )
            return len(list(result.scalars().all()))
        except Exception as e:
            logger.error("Failed to get group member count: %s", e, exc_info=True)
            return 0
