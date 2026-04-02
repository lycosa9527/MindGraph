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
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from models.domain.library import LibraryBookmark


logger = logging.getLogger(__name__)


class LibraryBookmarkMixin:
    """Mixin for bookmark operations."""

    db: AsyncSession
    user_id: Optional[int]

    async def create_bookmark(self, document_id: int, page_number: int, note: Optional[str] = None) -> LibraryBookmark:
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

        result = await self.db.execute(
            select(LibraryBookmark).where(
                LibraryBookmark.document_id == document_id,
                LibraryBookmark.user_id == self.user_id,
                LibraryBookmark.page_number == page_number,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            sanitized_note = self._sanitize_content(note) if note else None
            setattr(existing, "note", sanitized_note)
            setattr(existing, "updated_at", datetime.now(UTC))
            try:
                await self.db.commit()
            except Exception:
                await self.db.rollback()
                raise
            return existing

        sanitized_note = self._sanitize_content(note) if note else None

        bookmark = LibraryBookmark(
            document_id=document_id,
            user_id=self.user_id,
            page_number=page_number,
            note=sanitized_note,
        )
        self.db.add(bookmark)
        try:
            await self.db.commit()
            await self.db.refresh(bookmark)
        except Exception:
            await self.db.rollback()
            raise
        return bookmark

    async def delete_bookmark(self, bookmark_id: int) -> bool:
        """
        Delete a bookmark.

        Args:
            bookmark_id: Bookmark ID

        Returns:
            True if deleted, False if not found
        """
        if not self.user_id:
            return False

        result = await self.db.execute(
            select(LibraryBookmark).where(
                LibraryBookmark.id == bookmark_id,
                LibraryBookmark.user_id == self.user_id,
            )
        )
        bookmark = result.scalar_one_or_none()

        if not bookmark:
            return False

        await self.db.delete(bookmark)
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        return True

    async def get_bookmark(self, document_id: int, page_number: int) -> Optional[LibraryBookmark]:
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

        result = await self.db.execute(
            select(LibraryBookmark)
            .options(joinedload(LibraryBookmark.document))
            .where(
                LibraryBookmark.document_id == document_id,
                LibraryBookmark.user_id == self.user_id,
                LibraryBookmark.page_number == page_number,
            )
        )
        return result.scalars().unique().first()

    async def get_recent_bookmarks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent bookmarks for the current user.

        Args:
            limit: Maximum number of bookmarks to return

        Returns:
            List of bookmark dictionaries, ordered by created_at descending
        """
        if not self.user_id:
            return []

        result = await self.db.execute(
            select(LibraryBookmark)
            .options(joinedload(LibraryBookmark.document))
            .where(LibraryBookmark.user_id == self.user_id)
            .order_by(LibraryBookmark.created_at.desc())
            .limit(limit)
        )
        bookmarks = result.scalars().unique().all()

        return [
            {
                "id": b.id,
                "uuid": b.uuid,
                "document_id": b.document_id,
                "user_id": b.user_id,
                "page_number": b.page_number,
                "note": b.note,
                "created_at": b.created_at.isoformat() if b.created_at is not None else None,
                "updated_at": b.updated_at.isoformat() if b.updated_at is not None else None,
                "document": {
                    "id": b.document.id if b.document else None,
                    "title": b.document.title if b.document else None,
                }
                if b.document
                else None,
            }
            for b in bookmarks
        ]

    async def get_bookmark_by_uuid(self, bookmark_uuid: str) -> Optional[LibraryBookmark]:
        """
        Get bookmark by UUID.

        Args:
            bookmark_uuid: Bookmark UUID

        Returns:
            LibraryBookmark or None
        """
        if not self.user_id:
            return None

        result = await self.db.execute(
            select(LibraryBookmark)
            .options(joinedload(LibraryBookmark.document))
            .where(
                LibraryBookmark.uuid == bookmark_uuid,
                LibraryBookmark.user_id == self.user_id,
            )
        )
        return result.scalars().unique().first()

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

        content = re.sub(r"<[^>]+>", "", content)
        content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub(r"javascript:", "", content, flags=re.IGNORECASE)
        content = re.sub(r"on\w+\s*=", "", content, flags=re.IGNORECASE)
        content = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", content)
        content = re.sub(r"\s+", " ", content)
        return content.strip()
