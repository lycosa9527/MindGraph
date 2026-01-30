"""
Library Page Mixin for MindGraph

Mixin class for page/image path operations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple, TYPE_CHECKING

from services.library.library_path_utils import resolve_library_path
from services.library.image_path_resolver import (
    resolve_page_image,
    list_page_images
)

if TYPE_CHECKING:
    from models.domain.library import LibraryDocument

logger = logging.getLogger(__name__)


class LibraryPageMixin:
    """Mixin for page/image path operations."""

    # Type annotations for expected attributes provided by classes using this mixin
    _available_pages_cache: Dict[int, Tuple[List[int], float]]
    _cache_ttl: float
    _max_cache_size: int
    storage_dir: Path

    if TYPE_CHECKING:
        def get_document(self, document_id: int) -> Optional["LibraryDocument"]:
            """Get a single library document - provided by LibraryDocumentMixin."""
            ...

    def get_available_page_numbers(self, document_id: int, use_cache: bool = True) -> List[int]:
        """
        Get list of available page numbers for a document.

        Uses in-memory cache to avoid repeated directory scans.

        Args:
            document_id: Document ID
            use_cache: Whether to use cache (default True)

        Returns:
            List of available page numbers (1-indexed), sorted ascending
        """
        # Check cache first
        if use_cache and document_id in self._available_pages_cache:
            cached_pages, cache_time = self._available_pages_cache[document_id]
            if time.time() - cache_time < self._cache_ttl:
                return cached_pages

        document = self.get_document(document_id)
        if not document or not document.use_images or not document.pages_dir_path:
            return []

        # Resolve pages directory path
        pages_dir = resolve_library_path(
            document.pages_dir_path,
            self.storage_dir,
            Path.cwd()
        )

        if not pages_dir or not pages_dir.exists():
            return []

        # List all available pages (this is the expensive operation)
        pages = list_page_images(pages_dir)
        page_numbers = [page_num for page_num, _ in pages]

        # Cache the result with size limit (LRU eviction)
        if len(self._available_pages_cache) >= self._max_cache_size:
            # Remove oldest entry (by timestamp)
            oldest_doc_id = min(
                self._available_pages_cache.keys(),
                key=lambda doc_id: self._available_pages_cache[doc_id][1]
            )
            self._available_pages_cache.pop(oldest_doc_id, None)

        self._available_pages_cache[document_id] = (page_numbers, time.time())

        return page_numbers

    def get_next_available_page(self, document_id: int, page_number: int) -> Optional[int]:
        """
        Get next available page number after the given page number.

        Optimized approach:
        1. Try sequential pages first (fast file existence checks)
        2. Fall back to directory scan if sequential fails
        3. Uses cache to avoid repeated scans

        Args:
            document_id: Document ID
            page_number: Current page number

        Returns:
            Next available page number, or None if no next page exists
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

        # Optimization: Try sequential pages first (fast for small gaps)
        # Check next 5 pages sequentially before scanning entire directory
        # Reduced from 10 to 5 since typically only 1-2 pages are missing
        for next_page in range(page_number + 1, page_number + 6):
            image_path = resolve_page_image(pages_dir, next_page)
            if image_path and image_path.exists():
                return next_page

        # Sequential check failed - use directory scan (cached)
        available_pages = self.get_available_page_numbers(document_id, use_cache=True)
        if not available_pages:
            return None

        # Find first page number greater than the requested page
        for page_num in available_pages:
            if page_num > page_number:
                return page_num

        return None

    def invalidate_page_cache(self, document_id: int) -> None:
        """
        Invalidate cached available pages for a document.

        Call this when pages are added/removed for a document.

        Args:
            document_id: Document ID
        """
        self._available_pages_cache.pop(document_id, None)

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
