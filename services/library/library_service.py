"""
Library Service for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Service layer for library PDF management and danmaku operations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from models.domain.library import (
    LibraryDocument,
    LibraryDanmaku,
    LibraryDanmakuLike,
    LibraryDanmakuReply,
    LibraryBookmark,
)


logger = logging.getLogger(__name__)


class LibraryService:
    """
    Library management service.

    Handles PDF document management and danmaku operations.
    """

    def __init__(self, db: Session, user_id: Optional[int] = None):
        """
        Initialize service.

        Args:
            db: Database session
            user_id: User ID (optional, for user-scoped operations)
        """
        self.db = db
        self.user_id = user_id

        # Configuration
        self.storage_dir = Path(os.getenv("LIBRARY_STORAGE_DIR", "./storage/library"))
        self.covers_dir = self.storage_dir / "covers"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.covers_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size = int(os.getenv("LIBRARY_MAX_FILE_SIZE", "104857600"))  # 100MB default

    def get_documents(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get list of library documents.

        Args:
            page: Page number (1-indexed)
            page_size: Items per page
            search: Optional search query

        Returns:
            Dict with documents list and pagination info
        """
        query = self.db.query(LibraryDocument).filter(
            LibraryDocument.is_active
        )

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    LibraryDocument.title.ilike(search_term),
                    LibraryDocument.description.ilike(search_term)
                )
            )

        total = query.count()
        documents = query.order_by(
            LibraryDocument.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()

        return {
            "documents": [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "description": doc.description,
                    "cover_image_path": doc.cover_image_path,
                    "views_count": doc.views_count,
                    "likes_count": doc.likes_count,
                    "comments_count": doc.comments_count,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "uploader": {
                        "id": doc.uploader_id,
                        "name": doc.uploader.name if doc.uploader else None,
                    }
                }
                for doc in documents
            ],
            "total": total,
            "page": page,
            "page_size": page_size
        }

    def get_document(self, document_id: int) -> Optional[LibraryDocument]:
        """
        Get a single library document.

        Args:
            document_id: Document ID

        Returns:
            LibraryDocument instance or None
        """
        return self.db.query(LibraryDocument).filter(
            LibraryDocument.id == document_id,
            LibraryDocument.is_active
        ).first()

    def increment_views(self, document_id: int) -> None:
        """
        Increment view count for a document.

        Args:
            document_id: Document ID
        """
        document = self.get_document(document_id)
        if document:
            document.views_count += 1
            self.db.commit()

    def upload_document(
        self,
        file_name: str,
        file_path: str,
        file_size: int,
        title: str,
        description: Optional[str] = None,
        cover_image_path: Optional[str] = None
    ) -> LibraryDocument:
        """
        Upload a PDF document (for future admin panel).

        Args:
            file_name: Original filename
            file_path: Temporary file path
            file_size: File size in bytes
            title: Document title
            description: Document description
            cover_image_path: Cover image path

        Returns:
            LibraryDocument instance

        Raises:
            ValueError: If file size exceeds limit or file type invalid
        """
        if file_size > self.max_file_size:
            raise ValueError(f"File size ({file_size} bytes) exceeds maximum ({self.max_file_size} bytes)")

        if not file_name.lower().endswith('.pdf'):
            raise ValueError("Only PDF files are supported")

        # Move file to storage
        final_path = self.storage_dir / file_name
        shutil.move(file_path, final_path)

        # Create document record
        document = LibraryDocument(
            title=title,
            description=description,
            file_path=str(final_path),
            file_size=file_size,
            cover_image_path=cover_image_path,
            uploader_id=self.user_id,
            views_count=0,
            likes_count=0,
            comments_count=0
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)

        logger.info("[Library] Uploaded document %s (id: %s)", file_name, document.id)
        return document

    def update_document(
        self,
        document_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        cover_image_path: Optional[str] = None
    ) -> Optional[LibraryDocument]:
        """
        Update document metadata (for future admin panel).

        Args:
            document_id: Document ID
            title: New title
            description: New description
            cover_image_path: New cover image path

        Returns:
            Updated LibraryDocument instance or None
        """
        document = self.get_document(document_id)
        if not document:
            return None

        if title is not None:
            document.title = title
        if description is not None:
            document.description = description
        if cover_image_path is not None:
            document.cover_image_path = cover_image_path

        document.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(document)

        return document

    def delete_document(self, document_id: int) -> bool:
        """
        Soft delete a document (for future admin panel).

        Args:
            document_id: Document ID

        Returns:
            True if deleted, False if not found
        """
        document = self.get_document(document_id)
        if not document:
            return False

        document.is_active = False
        document.updated_at = datetime.utcnow()
        self.db.commit()

        logger.info("[Library] Deleted document %s", document_id)
        return True

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

    def delete_danmaku(self, danmaku_id: int) -> bool:
        """
        Delete own danmaku.

        Args:
            danmaku_id: Danmaku ID

        Returns:
            True if deleted, False if not found or not owner
        """
        danmaku = self.db.query(LibraryDanmaku).filter(
            LibraryDanmaku.id == danmaku_id,
            LibraryDanmaku.user_id == self.user_id,
            LibraryDanmaku.is_active
        ).first()

        if not danmaku:
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

    def delete_reply(self, reply_id: int) -> bool:
        """
        Delete own reply.

        Args:
            reply_id: Reply ID

        Returns:
            True if deleted, False if not found or not owner
        """
        reply = self.db.query(LibraryDanmakuReply).filter(
            LibraryDanmakuReply.id == reply_id,
            LibraryDanmakuReply.user_id == self.user_id,
            LibraryDanmakuReply.is_active
        ).first()

        if not reply:
            return False

        reply.is_active = False
        reply.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    def create_bookmark(
        self,
        document_id: int,
        page_number: int,
        note: Optional[str] = None
    ) -> LibraryBookmark:
        """
        Create a bookmark for a document page.

        Args:
            document_id: Document ID
            page_number: Page number (1-indexed)
            note: Optional note/description

        Returns:
            LibraryBookmark instance

        Raises:
            ValueError: If user_id is not set or bookmark already exists
        """
        if not self.user_id:
            raise ValueError("User ID required to create bookmark")

        # Check if bookmark already exists
        existing = self.db.query(LibraryBookmark).filter(
            LibraryBookmark.document_id == document_id,
            LibraryBookmark.user_id == self.user_id,
            LibraryBookmark.page_number == page_number
        ).first()

        if existing:
            # Update existing bookmark
            existing.note = note
            existing.updated_at = datetime.utcnow()
            self.db.commit()
            return existing

        bookmark = LibraryBookmark(
            document_id=document_id,
            user_id=self.user_id,
            page_number=page_number,
            note=note
        )
        self.db.add(bookmark)
        self.db.commit()
        self.db.refresh(bookmark)
        return bookmark

    def delete_bookmark(self, bookmark_id: int) -> bool:
        """
        Delete a bookmark.

        Args:
            bookmark_id: Bookmark ID

        Returns:
            True if deleted, False if not found
        """
        if not self.user_id:
            return False

        bookmark = self.db.query(LibraryBookmark).filter(
            LibraryBookmark.id == bookmark_id,
            LibraryBookmark.user_id == self.user_id
        ).first()

        if not bookmark:
            return False

        self.db.delete(bookmark)
        self.db.commit()
        return True

    def get_bookmark(self, document_id: int, page_number: int) -> Optional[LibraryBookmark]:
        """
        Get bookmark for a specific document page.

        Args:
            document_id: Document ID
            page_number: Page number

        Returns:
            LibraryBookmark or None
        """
        if not self.user_id:
            return None

        return self.db.query(LibraryBookmark).options(
            joinedload(LibraryBookmark.document)
        ).filter(
            LibraryBookmark.document_id == document_id,
            LibraryBookmark.user_id == self.user_id,
            LibraryBookmark.page_number == page_number
        ).first()

    def get_recent_bookmarks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent bookmarks for the current user.

        Args:
            limit: Maximum number of bookmarks to return

        Returns:
            List of bookmark dictionaries, ordered by created_at descending
        """
        if not self.user_id:
            return []

        bookmarks = self.db.query(LibraryBookmark).options(
            joinedload(LibraryBookmark.document)
        ).filter(
            LibraryBookmark.user_id == self.user_id
        ).order_by(LibraryBookmark.created_at.desc()).limit(limit).all()

        return [
            {
                "id": b.id,
                "uuid": b.uuid,
                "document_id": b.document_id,
                "user_id": b.user_id,
                "page_number": b.page_number,
                "note": b.note,
                "created_at": b.created_at.isoformat() if b.created_at else None,
                "updated_at": b.updated_at.isoformat() if b.updated_at else None,
                "document": {
                    "id": b.document.id if b.document else None,
                    "title": b.document.title if b.document else None,
                } if b.document else None
            }
            for b in bookmarks
        ]

    def get_bookmark_by_uuid(self, bookmark_uuid: str) -> Optional[LibraryBookmark]:
        """
        Get bookmark by UUID.

        Args:
            bookmark_uuid: Bookmark UUID

        Returns:
            LibraryBookmark or None
        """
        if not self.user_id:
            return None

        return self.db.query(LibraryBookmark).options(
            joinedload(LibraryBookmark.document)
        ).filter(
            LibraryBookmark.uuid == bookmark_uuid,
            LibraryBookmark.user_id == self.user_id
        ).first()
