"""
Library Bookmark Mixin for MindGraph

Mixin class for bookmark operations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import re
from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from models.domain.library import LibraryBookmark


logger = logging.getLogger(__name__)


class LibraryBookmarkMixin:
    """Mixin for bookmark operations."""

    # Type annotations for expected attributes provided by classes using this mixin
    db: Session
    user_id: Optional[int]

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
            sanitized_note = self._sanitize_content(note) if note else None
            existing.note = sanitized_note
            existing.updated_at = datetime.utcnow()
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            return existing

        # Sanitize user content to prevent XSS
        sanitized_note = self._sanitize_content(note) if note else None

        bookmark = LibraryBookmark(
            document_id=document_id,
            user_id=self.user_id,
            page_number=page_number,
            note=sanitized_note
        )
        self.db.add(bookmark)
        try:
            self.db.commit()
            self.db.refresh(bookmark)
        except Exception:
            self.db.rollback()
            raise
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
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
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

    def _sanitize_content(self, content: Optional[str]) -> Optional[str]:
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

        # Remove HTML tags
        content = re.sub(r'<[^>]+>', '', content)
        # Remove script tags and content
        content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)
        # Remove javascript: protocol
        content = re.sub(r'javascript:', '', content, flags=re.IGNORECASE)
        # Remove on* event handlers
        content = re.sub(r'on\w+\s*=', '', content, flags=re.IGNORECASE)
        # Remove control characters
        content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', content)
        # Normalize whitespace
        content = re.sub(r'\s+', ' ', content)
        return content.strip()
