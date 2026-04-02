"""
Library Danmaku Mixin for MindGraph

Mixin class for danmaku operations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import re
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.sql.functions import count as sql_count
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from models.domain.library import (
    LibraryDanmaku,
    LibraryDanmakuLike,
    LibraryDanmakuReply,
)

if TYPE_CHECKING:
    from models.domain.library import LibraryDocument

logger = logging.getLogger(__name__)


class LibraryDanmakuMixin:
    """Mixin for danmaku operations."""

    db: AsyncSession
    user_id: Optional[int]

    if TYPE_CHECKING:

        async def get_document(self, document_id: int) -> Optional["LibraryDocument"]:
            """Get a single library document - provided by LibraryDocumentMixin."""
            raise NotImplementedError

    async def get_danmaku(
        self,
        document_id: int,
        page_number: Optional[int] = None,
        selected_text: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get danmaku for a document.

        Uses Redis cache for filtered queries (by page or selected_text) to reduce DB load.

        Args:
            document_id: Document ID
            page_number: Optional page number filter
            selected_text: Optional text selection filter

        Returns:
            List of danmaku dictionaries
        """
        if page_number is not None or selected_text:
            try:
                from services.library.redis_cache import LibraryRedisCache

                redis_cache = LibraryRedisCache()
                cached_list = redis_cache.get_danmaku_list(
                    document_id=document_id,
                    page_number=page_number,
                    selected_text=selected_text,
                )
                if cached_list is not None:
                    logger.debug("[Library] Redis cache hit for danmaku doc=%s", document_id)
                    return cached_list
            except Exception as exc:
                logger.debug("[Library] Redis cache check failed: %s", exc)

        stmt = select(LibraryDanmaku).where(LibraryDanmaku.document_id == document_id, LibraryDanmaku.is_active)

        if page_number is not None:
            stmt = stmt.where(LibraryDanmaku.page_number == page_number)

        if selected_text:
            stmt = stmt.where(LibraryDanmaku.selected_text == selected_text)

        stmt = stmt.options(joinedload(LibraryDanmaku.user))
        stmt = stmt.order_by(LibraryDanmaku.created_at.asc())

        result = await self.db.execute(stmt)
        danmaku_list = result.scalars().unique().all()
        danmaku_ids = [d.id for d in danmaku_list]

        if not danmaku_ids:
            return []

        likes_result = await self.db.execute(
            select(
                LibraryDanmakuLike.danmaku_id,
                sql_count(LibraryDanmakuLike.id).label("count"),
            )
            .where(LibraryDanmakuLike.danmaku_id.in_(danmaku_ids))
            .group_by(LibraryDanmakuLike.danmaku_id)
        )
        likes_counts = dict(likes_result.all())

        user_liked_ids: set = set()
        if self.user_id:
            liked_result = await self.db.execute(
                select(LibraryDanmakuLike.danmaku_id).where(
                    LibraryDanmakuLike.danmaku_id.in_(danmaku_ids),
                    LibraryDanmakuLike.user_id == self.user_id,
                )
            )
            user_liked_ids = {row[0] for row in liked_result.all()}

        replies_result = await self.db.execute(
            select(
                LibraryDanmakuReply.danmaku_id,
                sql_count(LibraryDanmakuReply.id).label("count"),
            )
            .where(
                LibraryDanmakuReply.danmaku_id.in_(danmaku_ids),
                LibraryDanmakuReply.is_active,
            )
            .group_by(LibraryDanmakuReply.danmaku_id)
        )
        replies_counts = dict(replies_result.all())

        result_list = [
            {
                "id": d.id,
                "document_id": d.document_id,
                "user_id": d.user_id,
                "page_number": d.page_number,
                "position_x": d.position_x,
                "position_y": d.position_y,
                "selected_text": d.selected_text,
                "text_bbox": d.text_bbox,
                "content": d.content,
                "color": d.color,
                "highlight_color": d.highlight_color,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "user": {
                    "id": d.user.id if d.user else None,
                    "name": d.user.name if d.user else None,
                    "avatar": d.user.avatar if d.user else None,
                },
                "likes_count": likes_counts.get(d.id, 0),
                "is_liked": d.id in user_liked_ids,
                "replies_count": replies_counts.get(d.id, 0),
            }
            for d in danmaku_list
        ]

        if (page_number is not None or selected_text) and result_list:
            try:
                from services.library.redis_cache import LibraryRedisCache

                redis_cache = LibraryRedisCache()
                redis_cache.cache_danmaku_list(
                    document_id=document_id,
                    danmaku_list=result_list,
                    page_number=page_number,
                    selected_text=selected_text,
                )
            except Exception as exc:
                logger.debug("[Library] Redis cache write failed: %s", exc)

        return result_list

    async def get_recent_danmaku(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent danmaku across all documents.

        Args:
            limit: Maximum number of danmaku to return

        Returns:
            List of danmaku dictionaries, ordered by created_at descending
        """
        stmt = (
            select(LibraryDanmaku)
            .options(joinedload(LibraryDanmaku.user))
            .where(LibraryDanmaku.is_active)
            .order_by(LibraryDanmaku.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        danmaku_list = result.scalars().unique().all()

        if not danmaku_list:
            return []

        danmaku_ids = [d.id for d in danmaku_list]

        likes_result = await self.db.execute(
            select(
                LibraryDanmakuLike.danmaku_id,
                sql_count(LibraryDanmakuLike.id).label("count"),
            )
            .where(LibraryDanmakuLike.danmaku_id.in_(danmaku_ids))
            .group_by(LibraryDanmakuLike.danmaku_id)
        )
        likes_counts = dict(likes_result.all())

        user_liked_ids: set = set()
        if self.user_id:
            liked_result = await self.db.execute(
                select(LibraryDanmakuLike.danmaku_id).where(
                    LibraryDanmakuLike.danmaku_id.in_(danmaku_ids),
                    LibraryDanmakuLike.user_id == self.user_id,
                )
            )
            user_liked_ids = {row[0] for row in liked_result.all()}

        replies_result = await self.db.execute(
            select(
                LibraryDanmakuReply.danmaku_id,
                sql_count(LibraryDanmakuReply.id).label("count"),
            )
            .where(
                LibraryDanmakuReply.danmaku_id.in_(danmaku_ids),
                LibraryDanmakuReply.is_active,
            )
            .group_by(LibraryDanmakuReply.danmaku_id)
        )
        replies_counts = dict(replies_result.all())

        result_list = [
            {
                "id": d.id,
                "document_id": d.document_id,
                "user_id": d.user_id,
                "page_number": d.page_number,
                "position_x": d.position_x,
                "position_y": d.position_y,
                "selected_text": d.selected_text,
                "text_bbox": d.text_bbox,
                "content": d.content,
                "color": d.color,
                "highlight_color": d.highlight_color,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "user": {
                    "id": d.user.id if d.user else None,
                    "name": d.user.name if d.user else None,
                    "avatar": d.user.avatar if d.user else None,
                },
                "likes_count": likes_counts.get(d.id, 0),
                "is_liked": d.id in user_liked_ids,
                "replies_count": replies_counts.get(d.id, 0),
            }
            for d in danmaku_list
        ]

        if result_list:
            try:
                from services.library.redis_cache import LibraryRedisCache

                redis_cache = LibraryRedisCache()
                redis_cache.cache_recent_danmaku(limit, result_list)
            except Exception as exc:
                logger.debug("[Library] Redis cache write failed: %s", exc)

        return result_list

    async def create_danmaku(
        self,
        document_id: int,
        content: str,
        page_number: int,
        position_x: Optional[int] = None,
        position_y: Optional[int] = None,
        selected_text: Optional[str] = None,
        text_bbox: Optional[Dict[str, Any]] = None,
        color: Optional[str] = None,
        highlight_color: Optional[str] = None,
    ) -> LibraryDanmaku:
        """
        Create a danmaku comment.

        Args:
            document_id: Document ID
            content: Comment content
            page_number: Page number (1-indexed)
            position_x: X position (for position mode)
            position_y: Y position (for position mode)
            selected_text: Selected text (for text selection mode)
            text_bbox: Text bounding box (for text selection mode)
            color: Danmaku color
            highlight_color: Highlight color

        Returns:
            Created LibraryDanmaku instance
        """
        document = await self.get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")

        sanitized_content = self.sanitize_content(content)
        sanitized_selected_text = self.sanitize_content(selected_text) if selected_text else None

        danmaku = LibraryDanmaku(
            document_id=document_id,
            user_id=self.user_id,
            page_number=page_number,
            position_x=position_x,
            position_y=position_y,
            selected_text=sanitized_selected_text,
            text_bbox=text_bbox,
            content=sanitized_content,
            color=color,
            highlight_color=highlight_color,
        )

        self.db.add(danmaku)
        document.comments_count += 1
        try:
            await self.db.commit()
            await self.db.refresh(danmaku)
        except Exception:
            await self.db.rollback()
            raise

        logger.info(
            "[Library] Danmaku created",
            extra={
                "danmaku_id": danmaku.id,
                "document_id": document_id,
                "user_id": self.user_id,
                "page_number": page_number,
            },
        )

        try:
            from services.library.redis_cache import LibraryRedisCache

            redis_cache = LibraryRedisCache()
            redis_cache.invalidate_danmaku(document_id)
        except Exception as exc:
            logger.debug("[Library] Redis cache invalidation failed: %s", exc)

        return danmaku

    async def toggle_like(self, danmaku_id: int) -> Dict[str, Any]:
        """
        Toggle like on a danmaku.

        Args:
            danmaku_id: Danmaku ID

        Returns:
            Dict with is_liked and likes_count
        """
        result = await self.db.execute(
            select(LibraryDanmaku).where(LibraryDanmaku.id == danmaku_id, LibraryDanmaku.is_active)
        )
        danmaku = result.scalar_one_or_none()

        if not danmaku:
            raise ValueError(f"Danmaku {danmaku_id} not found")

        like_result = await self.db.execute(
            select(LibraryDanmakuLike).where(
                LibraryDanmakuLike.danmaku_id == danmaku_id,
                LibraryDanmakuLike.user_id == self.user_id,
            )
        )
        existing_like = like_result.scalar_one_or_none()

        if existing_like:
            await self.db.delete(existing_like)
            is_liked = False
        else:
            like = LibraryDanmakuLike(danmaku_id=danmaku_id, user_id=self.user_id)
            self.db.add(like)
            is_liked = True

        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        count_result = await self.db.execute(
            select(sql_count(LibraryDanmakuLike.id)).where(LibraryDanmakuLike.danmaku_id == danmaku_id)
        )
        likes_count = count_result.scalar_one()

        return {"is_liked": is_liked, "likes_count": likes_count}

    async def get_replies(self, danmaku_id: int) -> List[Dict[str, Any]]:
        """
        Get replies to a danmaku.

        Args:
            danmaku_id: Danmaku ID

        Returns:
            List of reply dictionaries
        """
        result = await self.db.execute(
            select(LibraryDanmakuReply)
            .options(joinedload(LibraryDanmakuReply.user))
            .where(
                LibraryDanmakuReply.danmaku_id == danmaku_id,
                LibraryDanmakuReply.is_active,
            )
            .order_by(LibraryDanmakuReply.created_at.asc())
        )
        replies = result.scalars().unique().all()

        return [
            {
                "id": r.id,
                "danmaku_id": r.danmaku_id,
                "user_id": r.user_id,
                "parent_reply_id": r.parent_reply_id,
                "content": r.content,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "user": {
                    "id": r.user.id if r.user else None,
                    "name": r.user.name if r.user else None,
                    "avatar": r.user.avatar if r.user else None,
                },
            }
            for r in replies
        ]

    async def create_reply(
        self, danmaku_id: int, content: str, parent_reply_id: Optional[int] = None
    ) -> LibraryDanmakuReply:
        """
        Create a reply to a danmaku.

        Args:
            danmaku_id: Danmaku ID
            content: Reply content
            parent_reply_id: Parent reply ID for nested replies

        Returns:
            Created LibraryDanmakuReply instance
        """
        result = await self.db.execute(
            select(LibraryDanmaku).where(LibraryDanmaku.id == danmaku_id, LibraryDanmaku.is_active)
        )
        danmaku = result.scalar_one_or_none()

        if not danmaku:
            raise ValueError(f"Danmaku {danmaku_id} not found")

        sanitized_content = self.sanitize_content(content)

        reply = LibraryDanmakuReply(
            danmaku_id=danmaku_id,
            user_id=self.user_id,
            parent_reply_id=parent_reply_id,
            content=sanitized_content,
        )

        self.db.add(reply)
        try:
            await self.db.commit()
            await self.db.refresh(reply)
        except Exception:
            await self.db.rollback()
            raise

        logger.info(
            "[Library] Reply created",
            extra={
                "reply_id": reply.id,
                "danmaku_id": danmaku_id,
                "user_id": self.user_id,
                "parent_reply_id": parent_reply_id,
            },
        )

        try:
            refresh_result = await self.db.execute(select(LibraryDanmaku).where(LibraryDanmaku.id == danmaku_id))
            refreshed_danmaku = refresh_result.scalar_one_or_none()
            if refreshed_danmaku:
                from services.library.redis_cache import LibraryRedisCache

                redis_cache = LibraryRedisCache()
                redis_cache.invalidate_danmaku(refreshed_danmaku.document_id)
        except Exception as exc:
            logger.debug("[Library] Redis cache invalidation failed: %s", exc)

        return reply

    async def delete_danmaku(self, danmaku_id: int, is_admin: bool = False) -> bool:
        """
        Delete danmaku.

        Only the creator or admin can delete.

        Args:
            danmaku_id: Danmaku ID
            is_admin: Whether current user is admin

        Returns:
            True if deleted, False if not found or not authorized
        """
        result = await self.db.execute(
            select(LibraryDanmaku).where(LibraryDanmaku.id == danmaku_id, LibraryDanmaku.is_active)
        )
        danmaku = result.scalar_one_or_none()

        if not danmaku:
            return False

        if danmaku.user_id != self.user_id and not is_admin:
            return False

        danmaku.is_active = False
        danmaku.updated_at = datetime.now(UTC)

        document = danmaku.document
        if document:
            document.comments_count = max(0, document.comments_count - 1)

        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        return True

    async def update_danmaku_position(
        self,
        danmaku_id: int,
        position_x: Optional[int] = None,
        position_y: Optional[int] = None,
        is_admin: bool = False,
    ) -> bool:
        """
        Update danmaku position.

        Only the creator or admin can update position.

        Args:
            danmaku_id: Danmaku ID
            position_x: New X position
            position_y: New Y position
            is_admin: Whether current user is admin

        Returns:
            True if updated, False if not found or not authorized
        """
        result = await self.db.execute(
            select(LibraryDanmaku).where(LibraryDanmaku.id == danmaku_id, LibraryDanmaku.is_active)
        )
        danmaku = result.scalar_one_or_none()

        if not danmaku:
            return False

        if danmaku.user_id != self.user_id and not is_admin:
            return False

        if position_x is not None:
            danmaku.position_x = position_x
        if position_y is not None:
            danmaku.position_y = position_y

        danmaku.updated_at = datetime.now(UTC)
        try:
            await self.db.commit()
            await self.db.refresh(danmaku)
        except Exception:
            await self.db.rollback()
            raise

        logger.info(
            "[Library] Danmaku position updated",
            extra={
                "danmaku_id": danmaku_id,
                "position_x": position_x,
                "position_y": position_y,
                "user_id": self.user_id,
            },
        )
        return True

    def sanitize_content(self, content: Optional[str]) -> Optional[str]:
        """
        Sanitize user content to prevent XSS attacks.

        Removes HTML tags and script content while preserving text.
        Args:
            content: User-provided content to sanitize
        Returns:
            Sanitized content or None if input was None
        """
        if not content:
            return None

        content = re.sub(r"<[^>]+>", "", content)
        content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub(r"javascript:", "", content, flags=re.IGNORECASE)
        content = re.sub(r"on\w+\s*=", "", content, flags=re.IGNORECASE)
        content = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", content)
        content = re.sub(r"\s+", " ", content)
        return content.strip()

    async def delete_reply(self, reply_id: int, is_admin: bool = False) -> bool:
        """
        Delete reply.

        Only the creator or admin can delete.

        Args:
            reply_id: Reply ID
            is_admin: Whether current user is admin

        Returns:
            True if deleted, False if not found or not authorized
        """
        result = await self.db.execute(
            select(LibraryDanmakuReply).where(LibraryDanmakuReply.id == reply_id, LibraryDanmakuReply.is_active)
        )
        reply = result.scalar_one_or_none()

        if not reply:
            return False

        if reply.user_id != self.user_id and not is_admin:
            return False

        reply.is_active = False
        reply.updated_at = datetime.now(UTC)
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        return True
