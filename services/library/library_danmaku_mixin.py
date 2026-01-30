"""
Library Danmaku Mixin for MindGraph

Mixin class for danmaku operations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from datetime import datetime

from sqlalchemy.orm import Session

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

    # Type annotations for expected attributes provided by classes using this mixin
    db: Session
    user_id: Optional[int]

    if TYPE_CHECKING:
        def get_document(self, document_id: int) -> Optional["LibraryDocument"]:
            """Get a single library document - provided by LibraryDocumentMixin."""
            ...

    def get_danmaku(
        self,
        document_id: int,
        page_number: Optional[int] = None,
        selected_text: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get danmaku for a document.

        Args:
            document_id: Document ID
            page_number: Optional page number filter
            selected_text: Optional text selection filter

        Returns:
            List of danmaku dictionaries
        """
        query = self.db.query(LibraryDanmaku).filter(
            LibraryDanmaku.document_id == document_id,
            LibraryDanmaku.is_active
        )

        if page_number is not None:
            query = query.filter(LibraryDanmaku.page_number == page_number)

        if selected_text:
            query = query.filter(LibraryDanmaku.selected_text == selected_text)

        danmaku_list = query.order_by(LibraryDanmaku.created_at.asc()).all()

        return [
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
                "likes_count": self.db.query(LibraryDanmakuLike).filter(
                    LibraryDanmakuLike.danmaku_id == d.id
                ).count(),
                "is_liked": self.user_id and self.db.query(LibraryDanmakuLike).filter(
                    LibraryDanmakuLike.danmaku_id == d.id,
                    LibraryDanmakuLike.user_id == self.user_id
                ).first() is not None,
                "replies_count": self.db.query(LibraryDanmakuReply).filter(
                    LibraryDanmakuReply.danmaku_id == d.id,
                    LibraryDanmakuReply.is_active
                ).count()
            }
            for d in danmaku_list
        ]

    def get_recent_danmaku(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent danmaku across all documents.

        Args:
            limit: Maximum number of danmaku to return

        Returns:
            List of danmaku dictionaries, ordered by created_at descending
        """
        danmaku_list = self.db.query(LibraryDanmaku).filter(
            LibraryDanmaku.is_active
        ).order_by(LibraryDanmaku.created_at.desc()).limit(limit).all()

        return [
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
                "likes_count": self.db.query(LibraryDanmakuLike).filter(
                    LibraryDanmakuLike.danmaku_id == d.id
                ).count(),
                "is_liked": self.user_id and self.db.query(LibraryDanmakuLike).filter(
                    LibraryDanmakuLike.danmaku_id == d.id,
                    LibraryDanmakuLike.user_id == self.user_id
                ).first() is not None,
                "replies_count": self.db.query(LibraryDanmakuReply).filter(
                    LibraryDanmakuReply.danmaku_id == d.id,
                    LibraryDanmakuReply.is_active
                ).count()
            }
            for d in danmaku_list
        ]

    def create_danmaku(
        self,
        document_id: int,
        content: str,
        page_number: int,
        position_x: Optional[int] = None,
        position_y: Optional[int] = None,
        selected_text: Optional[str] = None,
        text_bbox: Optional[Dict[str, Any]] = None,
        color: Optional[str] = None,
        highlight_color: Optional[str] = None
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
        document = self.get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")

        danmaku = LibraryDanmaku(
            document_id=document_id,
            user_id=self.user_id,
            page_number=page_number,
            position_x=position_x,
            position_y=position_y,
            selected_text=selected_text,
            text_bbox=text_bbox,
            content=content,
            color=color,
            highlight_color=highlight_color
        )

        self.db.add(danmaku)
        document.comments_count += 1
        self.db.commit()
        self.db.refresh(danmaku)

        logger.info("[Library] Created danmaku %s for document %s", danmaku.id, document_id)
        return danmaku

    def toggle_like(self, danmaku_id: int) -> Dict[str, Any]:
        """
        Toggle like on a danmaku.

        Args:
            danmaku_id: Danmaku ID

        Returns:
            Dict with is_liked and likes_count
        """
        danmaku = self.db.query(LibraryDanmaku).filter(
            LibraryDanmaku.id == danmaku_id,
            LibraryDanmaku.is_active
        ).first()

        if not danmaku:
            raise ValueError(f"Danmaku {danmaku_id} not found")

        existing_like = self.db.query(LibraryDanmakuLike).filter(
            LibraryDanmakuLike.danmaku_id == danmaku_id,
            LibraryDanmakuLike.user_id == self.user_id
        ).first()

        if existing_like:
            self.db.delete(existing_like)
            is_liked = False
        else:
            like = LibraryDanmakuLike(
                danmaku_id=danmaku_id,
                user_id=self.user_id
            )
            self.db.add(like)
            is_liked = True

        self.db.commit()

        likes_count = self.db.query(LibraryDanmakuLike).filter(
            LibraryDanmakuLike.danmaku_id == danmaku_id
        ).count()

        return {
            "is_liked": is_liked,
            "likes_count": likes_count
        }

    def get_replies(self, danmaku_id: int) -> List[Dict[str, Any]]:
        """
        Get replies to a danmaku.

        Args:
            danmaku_id: Danmaku ID

        Returns:
            List of reply dictionaries
        """
        replies = self.db.query(LibraryDanmakuReply).filter(
            LibraryDanmakuReply.danmaku_id == danmaku_id,
            LibraryDanmakuReply.is_active
        ).order_by(LibraryDanmakuReply.created_at.asc()).all()

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
                }
            }
            for r in replies
        ]

    def create_reply(
        self,
        danmaku_id: int,
        content: str,
        parent_reply_id: Optional[int] = None
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
        danmaku = self.db.query(LibraryDanmaku).filter(
            LibraryDanmaku.id == danmaku_id,
            LibraryDanmaku.is_active
        ).first()

        if not danmaku:
            raise ValueError(f"Danmaku {danmaku_id} not found")

        reply = LibraryDanmakuReply(
            danmaku_id=danmaku_id,
            user_id=self.user_id,
            parent_reply_id=parent_reply_id,
            content=content
        )

        self.db.add(reply)
        self.db.commit()
        self.db.refresh(reply)

        logger.info("[Library] Created reply %s for danmaku %s", reply.id, danmaku_id)
        return reply

    def delete_danmaku(self, danmaku_id: int, is_admin: bool = False) -> bool:
        """
        Delete danmaku.

        Only the creator or admin can delete.

        Args:
            danmaku_id: Danmaku ID
            is_admin: Whether current user is admin

        Returns:
            True if deleted, False if not found or not authorized
        """
        danmaku = self.db.query(LibraryDanmaku).filter(
            LibraryDanmaku.id == danmaku_id,
            LibraryDanmaku.is_active
        ).first()

        if not danmaku:
            return False

        # Check permission: must be owner or admin
        if danmaku.user_id != self.user_id and not is_admin:
            return False

        danmaku.is_active = False
        danmaku.updated_at = datetime.utcnow()

        # Update document comments count
        document = danmaku.document
        if document:
            document.comments_count = max(0, document.comments_count - 1)

        self.db.commit()
        return True

    def update_danmaku_position(
        self,
        danmaku_id: int,
        position_x: Optional[int] = None,
        position_y: Optional[int] = None,
        is_admin: bool = False
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
        danmaku = self.db.query(LibraryDanmaku).filter(
            LibraryDanmaku.id == danmaku_id,
            LibraryDanmaku.is_active
        ).first()

        if not danmaku:
            return False

        # Check permission: must be owner or admin
        if danmaku.user_id != self.user_id and not is_admin:
            return False

        # Update position
        if position_x is not None:
            danmaku.position_x = position_x
        if position_y is not None:
            danmaku.position_y = position_y

        danmaku.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(danmaku)

        logger.info("[Library] Updated danmaku %s position to (%s, %s)", danmaku_id, position_x, position_y)
        return True

    def delete_reply(self, reply_id: int, is_admin: bool = False) -> bool:
        """
        Delete reply.

        Only the creator or admin can delete.

        Args:
            reply_id: Reply ID
            is_admin: Whether current user is admin

        Returns:
            True if deleted, False if not found or not authorized
        """
        reply = self.db.query(LibraryDanmakuReply).filter(
            LibraryDanmakuReply.id == reply_id,
            LibraryDanmakuReply.is_active
        ).first()

        if not reply:
            return False

        # Check permission: must be owner or admin
        if reply.user_id != self.user_id and not is_admin:
            return False

        reply.is_active = False
        reply.updated_at = datetime.utcnow()
        self.db.commit()
        return True
