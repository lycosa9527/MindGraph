"""Gewe Message Database Service.

Handles storage and retrieval of WeChat messages in PostgreSQL.
Similar to xxxbot-pad's MessageDB but uses PostgreSQL instead of SQLite.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from datetime import datetime, timedelta
from typing import Optional, List
import logging

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from models.domain.gewe_message import GeweMessage
from services.redis.redis_client import RedisOperations

logger = logging.getLogger(__name__)


class GeweMessageDB:
    """
    Message database service for storing and querying WeChat messages.

    Uses PostgreSQL for persistent storage and Redis for deduplication.
    Similar to xxxbot-pad's MessageDB pattern.
    """

    def __init__(self, db: Session):
        """
        Initialize message database service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self._redis = RedisOperations()

    def save_message(
        self,
        app_id: str,
        msg_id: int,
        sender_wxid: str,
        from_wxid: str,
        msg_type: int,
        content: Optional[str] = None,
        is_group: bool = False
    ) -> bool:
        """
        Save message to database.

        Args:
            app_id: Gewe app ID
            msg_id: Message unique ID
            sender_wxid: Message sender wxid
            from_wxid: Message source wxid (chat)
            msg_type: Message type code
            content: Message content
            is_group: Whether it is a group message

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Check for duplicate using Redis (similar to xxxbot-pad's deduplication)
            message_key = f"gewe_msg:{app_id}:{msg_id}"
            if self._redis.exists(message_key):
                logger.debug("Duplicate message detected: %s", message_key)
                return False

            # Save to database
            message = GeweMessage(
                app_id=app_id,
                msg_id=msg_id,
                sender_wxid=sender_wxid,
                from_wxid=from_wxid,
                msg_type=msg_type,
                content=content or '',
                is_group=is_group,
                timestamp=datetime.utcnow()
            )
            self.db.add(message)
            self.db.commit()

            # Mark as processed in Redis (24 hour TTL)
            self._redis.set_with_ttl(message_key, "1", 86400)

            return True
        except Exception as e:
            logger.error("Failed to save message: %s", e, exc_info=True)
            self.db.rollback()
            return False

    def get_messages(
        self,
        app_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        sender_wxid: Optional[str] = None,
        from_wxid: Optional[str] = None,
        msg_type: Optional[int] = None,
        is_group: Optional[bool] = None,
        limit: int = 100
    ) -> List[GeweMessage]:
        """
        Query message records.

        Args:
            app_id: Gewe app ID
            start_time: Start time filter
            end_time: End time filter
            sender_wxid: Sender wxid filter
            from_wxid: Source wxid filter
            msg_type: Message type filter
            is_group: Group message filter
            limit: Maximum number of results

        Returns:
            List of GeweMessage objects
        """
        try:
            query = select(GeweMessage).where(
                GeweMessage.app_id == app_id
            ).order_by(
                GeweMessage.timestamp.desc()
            ).limit(limit)

            if start_time:
                query = query.where(GeweMessage.timestamp >= start_time)
            if end_time:
                query = query.where(GeweMessage.timestamp <= end_time)
            if sender_wxid:
                query = query.where(GeweMessage.sender_wxid == sender_wxid)
            if from_wxid:
                query = query.where(GeweMessage.from_wxid == from_wxid)
            if msg_type is not None:
                query = query.where(GeweMessage.msg_type == msg_type)
            if is_group is not None:
                query = query.where(GeweMessage.is_group == is_group)

            result = self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error("Failed to query messages: %s", e, exc_info=True)
            return []

    def cleanup_old_messages(self, days: int = 3) -> int:
        """
        Clean up messages older than specified days.

        Similar to xxxbot-pad's cleanup_messages method.

        Args:
            days: Number of days to keep (default: 3, same as xxxbot-pad)

        Returns:
            Number of messages deleted
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            result = self.db.execute(
                delete(GeweMessage).where(
                    GeweMessage.timestamp < cutoff_time
                )
            )
            self.db.commit()
            deleted_count = result.rowcount
            logger.info("Cleaned up %d old messages (older than %d days)", deleted_count, days)
            return deleted_count
        except Exception as e:
            logger.error("Failed to cleanup old messages: %s", e, exc_info=True)
            self.db.rollback()
            return 0

    def get_message_count(
        self,
        app_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> int:
        """
        Get count of messages for an app.

        Args:
            app_id: Gewe app ID
            start_time: Start time filter
            end_time: End time filter

        Returns:
            Message count
        """
        try:
            query = select(GeweMessage).where(GeweMessage.app_id == app_id)
            if start_time:
                query = query.where(GeweMessage.timestamp >= start_time)
            if end_time:
                query = query.where(GeweMessage.timestamp <= end_time)

            result = self.db.execute(query)
            return len(list(result.scalars().all()))
        except Exception as e:
            logger.error("Failed to get message count: %s", e, exc_info=True)
            return 0
