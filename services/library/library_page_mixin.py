"""
Library Page Mixin for MindGraph

Mixin class for page/image path operations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from services.library.library_path_utils import resolve_library_path
from services.library.image_path_resolver import resolve_page_image

if TYPE_CHECKING:
    from models.domain.library import LibraryDocument

logger = logging.getLogger(__name__)


class LibraryPageMixin:
    """Mixin for page/image path operations."""

    # Type annotations for expected attributes provided by classes using this mixin
    storage_dir: Path

    def get_document(self, document_id: int, use_cache: bool = True) -> Optional["LibraryDocument"]:
        """
        Get a single library document - provided by LibraryDocumentMixin.
        
        This is a stub that will be overridden by LibraryDocumentMixin when classes are composed.
        
        Args:
            document_id: Document ID
            use_cache: If True, use cache (ignored in stub, used by actual implementation)
        
        Raises:
            NotImplementedError: This method must be provided by LibraryDocumentMixin
        """
        raise NotImplementedError(
            "get_document must be provided by LibraryDocumentMixin. "
            f"Attempted to get document_id={document_id} with use_cache={use_cache}"
        )

    def get_page_image_path(self, document_id: int, page_number: int) -> Optional[Path]:
        """
        Get path to page image for a document.

        Args:
            document_id: Document ID
            page_number: Page number (1-indexed)

        Returns:
            Path to image file, or None if not found or document doesn't use images
        """
        try:
            document = self.get_document(document_id, use_cache=True)
        except NotImplementedError:
            return None
        if document is None:
            return None
        return self.get_page_image_path_from_document(document, page_number)

    def get_page_image_path_from_document(
        self,
        document: Optional["LibraryDocument"],
        page_number: int
    ) -> Optional[Path]:
        """
        Get path to page image from document object (avoids duplicate DB query).

        Args:
            document: LibraryDocument instance (can be None)
            page_number: Page number (1-indexed)

        Returns:
            Path to image file, or None if not found or document doesn't use images
        """
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
        try:
            document = self.get_document(document_id, use_cache=True)
        except NotImplementedError:
            return None
        if document is None or not document.use_images or not document.pages_dir_path:
            return None

        return resolve_library_path(
            document.pages_dir_path,
            self.storage_dir,
            Path.cwd()
        )
