"""
Library Document Mixin for MindGraph

Mixin class for document management operations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any, cast, Tuple
from datetime import UTC, datetime
import time

from PIL import Image
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.library import LibraryDocument
from services.library.library_path_utils import (
    normalize_library_path,
    resolve_library_path,
)
from services.library.redis_cache import LibraryRedisCache
from services.library.image_path_resolver import (
    count_pages,
    detect_image_pattern,
    list_page_images,
)


logger = logging.getLogger(__name__)

_document_metadata_cache: Dict[int, Dict[str, Any]] = {}
_cache_lock = threading.Lock()
CACHE_TTL_SECONDS = 600
CACHE_MAX_SIZE = 1000


class LibraryDocumentMixin:
    """Mixin for document management operations."""

    db: AsyncSession
    user_id: Optional[int]
    cover_max_width: int
    cover_max_height: int
    covers_dir: Path
    storage_dir: Path

    async def get_documents(self, page: int = 1, page_size: int = 20, search: Optional[str] = None) -> Dict[str, Any]:
        """
        Get list of library documents.

        Args:
            page: Page number (1-indexed)
            page_size: Items per page
            search: Optional search query

        Returns:
            Dict with documents list and pagination info
        """
        conditions = [LibraryDocument.is_active]

        if search:
            search_term = f"%{search}%"
            conditions.append(
                or_(
                    LibraryDocument.title.ilike(search_term),
                    LibraryDocument.description.ilike(search_term),
                )
            )

        count_result = await self.db.execute(select(func.count(LibraryDocument.id)).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(LibraryDocument)
            .where(*conditions)
            .order_by(LibraryDocument.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        documents = result.scalars().all()

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
                    "created_at": doc.created_at.isoformat() if doc.created_at is not None else None,
                    "uploader": {
                        "id": doc.uploader_id,
                        "name": doc.uploader.name if doc.uploader else None,
                    },
                }
                for doc in documents
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_document(self, document_id: int, use_cache: bool = True) -> Optional[LibraryDocument]:
        """
        Get a single library document with optional caching.

        Uses multi-layer caching:
        1. Redis cache (shared across servers)
        2. In-memory cache (per-process)
        3. Database query (fallback)

        Args:
            document_id: Document ID
            use_cache: If True, use caching layers (default: True)

        Returns:
            LibraryDocument instance or None
        """
        if not use_cache:
            result = await self.db.execute(
                select(LibraryDocument).where(LibraryDocument.id == document_id, LibraryDocument.is_active)
            )
            return result.scalar_one_or_none()

        try:
            redis_cache = LibraryRedisCache()
            cached_metadata = redis_cache.get_document_metadata(document_id)

            if cached_metadata:
                logger.debug("[Library] Redis cache hit for document %s", document_id)
        except Exception as exc:
            logger.debug("[Library] Redis cache check failed: %s", exc)
            cached_metadata = None

        if not cached_metadata:
            with _cache_lock:
                cached = _document_metadata_cache.get(document_id)
                if cached:
                    cache_age = time.time() - cached["cached_at"]
                    if cache_age < CACHE_TTL_SECONDS:
                        cached_metadata = cached["data"]
                    else:
                        _document_metadata_cache.pop(document_id, None)

        result = await self.db.execute(
            select(LibraryDocument).where(LibraryDocument.id == document_id, LibraryDocument.is_active)
        )
        document = result.scalar_one_or_none()

        if document and use_cache:
            try:
                redis_cache = LibraryRedisCache()
                metadata = {
                    "id": document.id,
                    "pages_dir_path": document.pages_dir_path,
                    "total_pages": document.total_pages,
                    "use_images": document.use_images,
                    "is_active": document.is_active,
                    "title": document.title,
                }
                redis_cache.cache_document_metadata(document_id, metadata)
            except Exception as exc:
                logger.debug("[Library] Redis cache write failed: %s", exc)

            self._cache_document_metadata(document_id, document)

        return document

    def _cache_document_metadata(self, document_id: int, document: LibraryDocument) -> None:
        """
        Cache document metadata for fast image serving.

        Args:
            document_id: Document ID
            document: LibraryDocument instance
        """
        with _cache_lock:
            if len(_document_metadata_cache) >= CACHE_MAX_SIZE:
                sorted_items = sorted(
                    _document_metadata_cache.items(),
                    key=lambda x: x[1].get("cached_at", 0),
                )
                evict_count = max(1, CACHE_MAX_SIZE // 10)
                for doc_id, _ in sorted_items[:evict_count]:
                    _document_metadata_cache.pop(doc_id, None)
                logger.debug(
                    "[Library] Cache evicted %s entries (size: %s, max: %s)",
                    evict_count,
                    len(_document_metadata_cache),
                    CACHE_MAX_SIZE,
                )

            _document_metadata_cache[document_id] = {
                "data": {
                    "id": document.id,
                    "pages_dir_path": document.pages_dir_path,
                    "total_pages": document.total_pages,
                    "use_images": document.use_images,
                    "is_active": document.is_active,
                    "title": document.title,
                },
                "cached_at": time.time(),
            }

    def get_cached_document_metadata(self, document_id: int) -> Optional[Dict[str, Any]]:
        """
        Get cached document metadata without DB query.

        Checks Redis cache first (shared), then in-memory cache (per-process).

        Args:
            document_id: Document ID

        Returns:
            Cached metadata dict or None if not cached or expired
        """
        try:
            redis_cache = LibraryRedisCache()
            cached = redis_cache.get_document_metadata(document_id)
            if cached:
                logger.debug("[Library] Redis cache hit for document metadata %s", document_id)
                return cached
        except Exception as exc:
            logger.debug("[Library] Redis cache check failed: %s", exc)

        with _cache_lock:
            cached = _document_metadata_cache.get(document_id)
            if not cached:
                return None

            cache_age = time.time() - cached["cached_at"]
            if cache_age >= CACHE_TTL_SECONDS:
                _document_metadata_cache.pop(document_id, None)
                return None

            return cached["data"]

    def invalidate_document_cache(self, document_id: int) -> None:
        """
        Invalidate cached document metadata.

        Invalidates both Redis cache (shared) and in-memory cache (per-process).

        Args:
            document_id: Document ID
        """
        try:
            redis_cache = LibraryRedisCache()
            redis_cache.invalidate_document(document_id)
        except Exception as exc:
            logger.debug("[Library] Redis cache invalidation failed: %s", exc)

        with _cache_lock:
            _document_metadata_cache.pop(document_id, None)
        logger.debug("Invalidated cache for document %s", document_id)

    async def increment_views(self, document_id: int) -> None:
        """
        Increment view count for a document.

        Args:
            document_id: Document ID
        """
        try:
            document = await self.get_document(document_id)
            if document:
                document.views_count = cast(int, document.views_count) + 1
                await self.db.commit()
                logger.debug(
                    "[Library] Document view incremented",
                    extra={
                        "document_id": document_id,
                        "views_count": document.views_count,
                    },
                )
        except Exception:
            await self.db.rollback()
            raise

    def _convert_image_to_rgb(self, img: Image.Image) -> Image.Image:
        """Convert image to RGB, handling transparency."""
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            mask = img.split()[-1] if img.mode == "RGBA" else None
            background.paste(img, mask=mask)
            return background
        if img.mode != "RGB":
            return img.convert("RGB")
        return img

    def _compute_cover_resize(self, width: int, height: int) -> Tuple[int, int]:
        """Compute new dimensions for cover image maintaining aspect ratio."""
        aspect_ratio = width / height
        if width <= self.cover_max_width and height <= self.cover_max_height:
            return (width, height)
        if aspect_ratio > 1:
            new_width = min(width, self.cover_max_width)
            new_height = int(new_width / aspect_ratio)
            if new_height > self.cover_max_height:
                new_height = self.cover_max_height
                new_width = int(new_height * aspect_ratio)
        else:
            new_height = min(height, self.cover_max_height)
            new_width = int(new_height * aspect_ratio)
            if new_width > self.cover_max_width:
                new_width = self.cover_max_width
                new_height = int(new_width / aspect_ratio)
        return (new_width, new_height)

    def _get_cover_output_format(self, source_ext: str) -> Tuple[str, str, Dict[str, Any]]:
        """Get output format, extension, and save kwargs from source extension."""
        if source_ext in (".jpg", ".jpeg"):
            return (".jpg", "JPEG", {"quality": 85, "optimize": True})
        if source_ext == ".png":
            return (".png", "PNG", {"optimize": True})
        return (".jpg", "JPEG", {"quality": 85, "optimize": True})

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
            with Image.open(source_image_path) as img:
                img = self._convert_image_to_rgb(img)
                width, height = img.size
                new_width, new_height = self._compute_cover_resize(width, height)
                if (new_width, new_height) != (width, height):
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                ext, fmt, save_kwargs = self._get_cover_output_format(source_image_path.suffix.lower())
                cover_filename = f"{document_id}_cover{ext}"
                cover_path = self.covers_dir / cover_filename
                img.save(cover_path, fmt, **save_kwargs)
                result_path = str(cover_path.resolve())

                logger.info(
                    "[Library] Processed cover image: %s -> %s (%dx%d -> %dx%d)",
                    source_image_path.name,
                    cover_filename,
                    width,
                    height,
                    img.size[0],
                    img.size[1],
                )
                return result_path
        except Exception as exc:
            logger.error(
                "[Library] Failed to process cover image %s: %s",
                source_image_path,
                exc,
                exc_info=True,
            )
            return None

    def _validate_book_folder(self, folder_path: Path) -> int:
        """Validate folder exists and contains images. Returns page count."""
        if not folder_path.exists() or not folder_path.is_dir():
            raise ValueError(f"Folder does not exist: {folder_path}")
        page_count = count_pages(folder_path)
        if page_count == 0:
            raise ValueError(f"Folder contains no images: {folder_path}")
        if not detect_image_pattern(folder_path):
            raise ValueError(f"Could not detect image pattern in folder: {folder_path}")
        return page_count

    def _get_first_page_image_path(self, folder_path: Path) -> Optional[Path]:
        """Get path to first page image for cover, or None."""
        page_images = list_page_images(folder_path)
        return page_images[0][1] if page_images else None

    def _cover_image_exists(self, document: LibraryDocument) -> bool:
        """Check if document already has a valid cover image on disk."""
        cover_path = document.cover_image_path
        if not cover_path:
            return False
        resolved = resolve_library_path(cover_path, self.covers_dir, Path.cwd())
        return resolved is not None and resolved.exists()

    async def regenerate_cover(self, document_id: int) -> Optional[str]:
        """
        Regenerate cover image from the first page for an already-registered document.

        Overwrites any existing cover file.  Updates cover_image_path in the DB
        and invalidates both Redis and in-memory caches so the change is immediately
        visible to readers without a server restart.

        Args:
            document_id: Primary key of the LibraryDocument to regenerate.

        Returns:
            Absolute path string to the new cover file, or None if processing failed.

        Raises:
            ValueError: If the document or its folder cannot be found.
        """
        result = await self.db.execute(select(LibraryDocument).where(LibraryDocument.id == document_id))
        document = result.scalar_one_or_none()
        if not document:
            raise ValueError(f"Document not found: {document_id}")

        folder_path = resolve_library_path(document.pages_dir_path, self.storage_dir, Path.cwd())
        if not folder_path or not folder_path.exists():
            raise ValueError(f"Book folder not found for document {document_id}")

        first_page = self._get_first_page_image_path(folder_path)
        if not first_page:
            raise ValueError(f"No page images found in folder: {folder_path}")

        cover_path = self._process_cover_image(first_page, document_id)
        if not cover_path:
            return None

        document.cover_image_path = cover_path
        document.updated_at = datetime.now(UTC)
        try:
            await self.db.commit()
            await self.db.refresh(document)
        except Exception:
            await self.db.rollback()
            raise

        self.invalidate_document_cache(document_id)
        return cover_path

    async def _update_existing_book_document(
        self,
        existing_doc: LibraryDocument,
        folder_path: Path,
        page_count: int,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        first_page_image_path: Optional[Path] = None,
    ) -> LibraryDocument:
        """Update an existing document with new folder data."""
        existing_doc.use_images = True
        existing_doc.total_pages = page_count
        existing_doc.pages_dir_path = normalize_library_path(folder_path, self.storage_dir, Path.cwd())
        doc_title = existing_doc.title
        if title:
            existing_doc.title = title
        elif not doc_title or doc_title == "Untitled":
            existing_doc.title = folder_path.name
        if description is not None:
            existing_doc.description = description

        if first_page_image_path and not self._cover_image_exists(existing_doc):
            cover_image_path = self._process_cover_image(first_page_image_path, cast(int, existing_doc.id))
            if cover_image_path:
                existing_doc.cover_image_path = cover_image_path

        existing_doc.updated_at = datetime.now(UTC)
        try:
            await self.db.commit()
            await self.db.refresh(existing_doc)
        except Exception:
            await self.db.rollback()
            raise
        self.invalidate_document_cache(cast(int, existing_doc.id))
        logger.info(
            "[Library] Book folder updated",
            extra={
                "document_id": existing_doc.id,
                "folder_name": folder_path.name,
                "page_count": page_count,
                "has_cover": bool(existing_doc.cover_image_path),
            },
        )
        return existing_doc

    async def _create_new_book_document(
        self,
        folder_path: Path,
        page_count: int,
        pages_dir_path: str,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        first_page_image_path: Optional[Path] = None,
    ) -> LibraryDocument:
        """Create a new document from folder. Requires user_id to be set."""
        if not self.user_id:
            raise ValueError("User ID required to register book folder")
        placeholder_path = normalize_library_path(folder_path / "placeholder.pdf", self.storage_dir, Path.cwd())
        new_doc = LibraryDocument(
            title=title or folder_path.name,
            description=description,
            file_path=placeholder_path,
            file_size=0,
            cover_image_path=None,
            uploader_id=self.user_id,
            views_count=0,
            likes_count=0,
            comments_count=0,
            is_active=True,
            use_images=True,
            pages_dir_path=pages_dir_path,
            total_pages=page_count,
        )
        self.db.add(new_doc)
        try:
            await self.db.commit()
            await self.db.refresh(new_doc)
        except Exception:
            await self.db.rollback()
            raise

        cover_image_path = None
        if first_page_image_path:
            cover_image_path = self._process_cover_image(first_page_image_path, cast(int, new_doc.id))
            if cover_image_path:
                new_doc.cover_image_path = cover_image_path
                try:
                    await self.db.commit()
                    await self.db.refresh(new_doc)
                except Exception:
                    await self.db.rollback()
                    raise

        logger.info(
            "[Library] Book folder registered",
            extra={
                "document_id": new_doc.id,
                "folder_name": folder_path.name,
                "page_count": page_count,
                "has_cover": bool(cover_image_path),
                "title": new_doc.title,
            },
        )
        return new_doc

    async def register_book_folder(
        self,
        folder_path: Path,
        title: Optional[str] = None,
        description: Optional[str] = None,
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
        page_count = self._validate_book_folder(folder_path)
        pages_dir_path = normalize_library_path(folder_path, self.storage_dir, Path.cwd())
        first_page_image_path = self._get_first_page_image_path(folder_path)

        result = await self.db.execute(select(LibraryDocument).where(LibraryDocument.pages_dir_path == pages_dir_path))
        existing_doc = result.scalar_one_or_none()

        if not existing_doc:
            folder_name = folder_path.name
            fallback_result = await self.db.execute(
                select(LibraryDocument).where(
                    or_(
                        LibraryDocument.pages_dir_path.like(f"%/{folder_name}"),
                        LibraryDocument.pages_dir_path.like(f"%\\{folder_name}"),
                        LibraryDocument.pages_dir_path == folder_name,
                    )
                )
            )
            existing_doc = fallback_result.scalar_one_or_none()

        if existing_doc:
            return await self._update_existing_book_document(
                existing_doc,
                folder_path,
                page_count,
                title=title,
                description=description,
                first_page_image_path=first_page_image_path,
            )
        return await self._create_new_book_document(
            folder_path,
            page_count,
            pages_dir_path,
            title=title,
            description=description,
            first_page_image_path=first_page_image_path,
        )

    async def update_document(
        self,
        document_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        cover_image_path: Optional[str] = None,
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
        document = await self.get_document(document_id)
        if not document:
            return None

        if title is not None:
            document.title = title
        if description is not None:
            document.description = description
        if cover_image_path is not None:
            document.cover_image_path = cover_image_path

        document.updated_at = datetime.now(UTC)
        try:
            await self.db.commit()
            await self.db.refresh(document)
        except Exception:
            await self.db.rollback()
            raise

        self.invalidate_document_cache(document_id)

        return document

    async def delete_document(self, document_id: int) -> bool:
        """
        Soft delete a document (for future admin panel).

        Args:
            document_id: Document ID

        Returns:
            True if deleted, False if not found
        """
        document = await self.get_document(document_id)
        if not document:
            return False

        document.is_active = False
        document.updated_at = datetime.now(UTC)
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        self.invalidate_document_cache(document_id)

        logger.info(
            "[Library] Document deleted",
            extra={"document_id": document_id, "title": document.title},
        )
        return True
