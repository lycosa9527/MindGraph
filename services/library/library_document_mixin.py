"""
Library Document Mixin for MindGraph

Mixin class for document management operations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime

from PIL import Image
from sqlalchemy import or_
from sqlalchemy.orm import Session

from models.domain.library import LibraryDocument
from services.library.library_path_utils import normalize_library_path, resolve_library_path
from services.library.image_path_resolver import (
    count_pages,
    detect_image_pattern,
    list_page_images
)


logger = logging.getLogger(__name__)


class LibraryDocumentMixin:
    """Mixin for document management operations."""

    # Type annotations for expected attributes provided by classes using this mixin
    db: Session
    user_id: Optional[int]
    cover_max_width: int
    cover_max_height: int
    covers_dir: Path
    storage_dir: Path

    if TYPE_CHECKING:
        def invalidate_page_cache(self, document_id: int) -> None:
            """Invalidate cached available pages - provided by LibraryPageMixin."""
            ...

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
            # Invalidate cache since pages may have changed
            self.invalidate_page_cache(existing_doc.id)
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
        # Cache will be populated on first access, no need to invalidate new document

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
