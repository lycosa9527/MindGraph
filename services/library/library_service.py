"""
Library Service for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Service layer for library document management and danmaku operations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from PIL import Image
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from models.domain.library import (
    LibraryDocument,
    LibraryDanmaku,
    LibraryDanmakuLike,
    LibraryDanmakuReply,
    LibraryBookmark,
)
from services.library.library_path_utils import normalize_library_path, resolve_library_path
from services.library.image_path_resolver import (
    resolve_page_image,
    count_pages,
    detect_image_pattern,
    list_page_images
)


logger = logging.getLogger(__name__)


class LibraryService:
    """
    Library management service.

    Handles document management and danmaku operations.
    Documents are image-based (pages exported as images).
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
        storage_dir_env = os.getenv("LIBRARY_STORAGE_DIR", "./storage/library")
        self.storage_dir = Path(storage_dir_env).resolve()
        self.covers_dir = self.storage_dir / "covers"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.covers_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size = int(os.getenv("LIBRARY_MAX_FILE_SIZE", "104857600"))  # 100MB default
        self.cover_max_width = int(os.getenv("LIBRARY_COVER_MAX_WIDTH", "400"))  # Max width for cover images
        self.cover_max_height = int(os.getenv("LIBRARY_COVER_MAX_HEIGHT", "580"))  # Max height for cover images (matches original)

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
                    "use_images": doc.use_images,
                    "pages_dir_path": doc.pages_dir_path,
                    "total_pages": doc.total_pages,
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

    # PDF upload functionality removed - no longer needed for image-based viewing
    # Documents are now registered via register_image_folders.py script
    # Users manually export PDFs to images and place folders in storage/library/

    def _process_cover_image(self, source_image_path: Path, document_id: int) -> Optional[str]:
        """
        Process and copy the first page image as a cover image.

        Args:
            source_image_path: Path to the source image file
            document_id: Document ID for naming the cover file

        Returns:
            Normalized path to the cover image, or None if processing failed
        """
        try:
            # Open and process the image
            with Image.open(source_image_path) as img:
                # Convert to RGB if necessary (handles RGBA, P mode, etc.)
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create white background for transparency
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                # Calculate new size maintaining aspect ratio
                width, height = img.size
                aspect_ratio = width / height

                if width > self.cover_max_width or height > self.cover_max_height:
                    if aspect_ratio > 1:
                        # Landscape: fit to max width
                        new_width = min(width, self.cover_max_width)
                        new_height = int(new_width / aspect_ratio)
                        if new_height > self.cover_max_height:
                            new_height = self.cover_max_height
                            new_width = int(new_height * aspect_ratio)
                    else:
                        # Portrait: fit to max height
                        new_height = min(height, self.cover_max_height)
                        new_width = int(new_height * aspect_ratio)
                        if new_width > self.cover_max_width:
                            new_width = self.cover_max_width
                            new_height = int(new_width / aspect_ratio)

                    # Resize with high-quality resampling
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Determine output format and extension
                source_ext = source_image_path.suffix.lower()
                if source_ext in ('.jpg', '.jpeg'):
                    output_ext = '.jpg'
                    output_format = 'JPEG'
                    save_kwargs = {'quality': 85, 'optimize': True}
                elif source_ext == '.png':
                    output_ext = '.png'
                    output_format = 'PNG'
                    save_kwargs = {'optimize': True}
                else:
                    # Default to JPEG for other formats
                    output_ext = '.jpg'
                    output_format = 'JPEG'
                    save_kwargs = {'quality': 85, 'optimize': True}

                # Save to covers directory
                cover_filename = f"{document_id}_cover{output_ext}"
                cover_path = self.covers_dir / cover_filename

                img.save(cover_path, output_format, **save_kwargs)

                # Store absolute path string (matching original upload_cover_image behavior)
                cover_image_path = str(cover_path.resolve())

                logger.info(
                    "[Library] Processed cover image: %s -> %s (%dx%d -> %dx%d)",
                    source_image_path.name,
                    cover_filename,
                    width,
                    height,
                    img.size[0],
                    img.size[1]
                )

                return cover_image_path

        except Exception as e:
            logger.error(
                "[Library] Failed to process cover image %s: %s",
                source_image_path,
                e,
                exc_info=True
            )
            return None

    def register_book_folder(
        self,
        folder_path: Path,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> LibraryDocument:
        """
        Register a folder containing page images as a library document.

        Args:
            folder_path: Path to folder containing page images
            title: Optional title (defaults to folder name)
            description: Optional description

        Returns:
            Created or updated LibraryDocument instance

        Raises:
            ValueError: If folder doesn't exist or contains no images
        """
        if not folder_path.exists() or not folder_path.is_dir():
            raise ValueError(f"Folder does not exist: {folder_path}")

        # Count pages and detect pattern
        page_count = count_pages(folder_path)
        if page_count == 0:
            raise ValueError(f"Folder contains no images: {folder_path}")

        pattern_info = detect_image_pattern(folder_path)
        if not pattern_info:
            raise ValueError(f"Could not detect image pattern in folder: {folder_path}")

        # Normalize path
        pages_dir_path = normalize_library_path(folder_path, self.storage_dir, Path.cwd())

        # Get first page image to use as cover
        page_images = list_page_images(folder_path)
        first_page_image_path = None
        if page_images:
            first_page_image_path = page_images[0][1]  # Get the Path from (page_num, image_path) tuple

        # Check if document already exists
        existing_doc = self.db.query(LibraryDocument).filter(
            LibraryDocument.pages_dir_path == pages_dir_path
        ).first()

        if existing_doc:
            # Update existing document
            existing_doc.use_images = True
            existing_doc.total_pages = page_count
            existing_doc.pages_dir_path = pages_dir_path
            if title:
                existing_doc.title = title
            elif not existing_doc.title or existing_doc.title == 'Untitled':
                existing_doc.title = folder_path.name
            if description is not None:
                existing_doc.description = description

            # Process cover image if first page is available and cover doesn't exist
            if first_page_image_path:
                # Check if cover already exists
                cover_exists = False
                if existing_doc.cover_image_path:
                    cover_resolved = resolve_library_path(
                        existing_doc.cover_image_path,
                        self.covers_dir,
                        Path.cwd()
                    )
                    if cover_resolved and cover_resolved.exists():
                        cover_exists = True

                # Process cover if it doesn't exist
                if not cover_exists:
                    cover_image_path = self._process_cover_image(first_page_image_path, existing_doc.id)
                    if cover_image_path:
                        existing_doc.cover_image_path = cover_image_path

            existing_doc.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing_doc)
            logger.info(
                "[Library] Updated book folder: %s (ID: %s, Pages: %s, Cover: %s)",
                folder_path.name,
                existing_doc.id,
                page_count,
                existing_doc.cover_image_path or "none"
            )
            return existing_doc

        # Create new document
        if not self.user_id:
            raise ValueError("User ID required to register book folder")

        # Create placeholder file_path (not used for image-based docs)
        placeholder_path = normalize_library_path(
            folder_path / 'placeholder.pdf',
            self.storage_dir,
            Path.cwd()
        )

        # Create document first to get ID for cover processing
        new_doc = LibraryDocument(
            title=title or folder_path.name,
            description=description,
            file_path=placeholder_path,  # Placeholder, not actually used
            file_size=0,  # Not applicable for image-based docs
            cover_image_path=None,  # Will be set after processing
            uploader_id=self.user_id,
            views_count=0,
            likes_count=0,
            comments_count=0,
            is_active=True,
            use_images=True,
            pages_dir_path=pages_dir_path,
            total_pages=page_count
        )

        self.db.add(new_doc)
        self.db.commit()
        self.db.refresh(new_doc)

        # Process cover image now that we have document ID
        cover_image_path = None
        if first_page_image_path:
            cover_image_path = self._process_cover_image(first_page_image_path, new_doc.id)
            if cover_image_path:
                new_doc.cover_image_path = cover_image_path
                self.db.commit()
                self.db.refresh(new_doc)

        logger.info(
            "[Library] Registered book folder: %s (ID: %s, Pages: %s, Cover: %s)",
            folder_path.name,
            new_doc.id,
            page_count,
            cover_image_path or "none"
        )
        return new_doc

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

    def get_page_image_path(self, document_id: int, page_number: int) -> Optional[Path]:
        """
        Get path to page image for a document.
        
        Args:
            document_id: Document ID
            page_number: Page number (1-indexed)
            
        Returns:
            Path to image file, or None if not found or document doesn't use images
        """
        document = self.get_document(document_id)
        if not document or not document.use_images or not document.pages_dir_path:
            return None
        
        # Resolve pages directory path
        pages_dir = resolve_library_path(
            document.pages_dir_path,
            self.storage_dir,
            Path.cwd()
        )
        
        if not pages_dir or not pages_dir.exists():
            return None
        
        # Resolve page image
        return resolve_page_image(pages_dir, page_number)

    def resolve_pages_directory(self, document_id: int) -> Optional[Path]:
        """
        Resolve pages directory path for a document.
        
        Args:
            document_id: Document ID
            
        Returns:
            Path to pages directory, or None if not found or document doesn't use images
        """
        document = self.get_document(document_id)
        if not document or not document.use_images or not document.pages_dir_path:
            return None
        
        return resolve_library_path(
            document.pages_dir_path,
            self.storage_dir,
            Path.cwd()
        )

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
