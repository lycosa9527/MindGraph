"""
Library-specific exceptions for better error handling.

Provides specific exception types for different error scenarios
in the library feature, enabling better error messages and logging.
"""

from typing import Optional


class LibraryError(Exception):
    """Base exception for library-related errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, context: Optional[dict] = None):
        """
        Initialize library error.
        
        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            context: Additional context (document_id, page_number, etc.)
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}


class DocumentNotFoundError(LibraryError):
    """Raised when a document is not found."""
    
    def __init__(self, document_id: int, message: Optional[str] = None):
        super().__init__(
            message or f"Document {document_id} not found",
            error_code="DOCUMENT_NOT_FOUND",
            context={"document_id": document_id}
        )
        self.document_id = document_id


class PageNotFoundError(LibraryError):
    """Raised when a page is not found."""
    
    def __init__(self, document_id: int, page_number: int, total_pages: Optional[int] = None, message: Optional[str] = None):
        if total_pages and page_number > total_pages:
            msg = message or f"Page {page_number} exceeds total pages ({total_pages})"
        else:
            msg = message or f"Page {page_number} not found for document {document_id}"
        
        super().__init__(
            msg,
            error_code="PAGE_NOT_FOUND",
            context={
                "document_id": document_id,
                "page_number": page_number,
                "total_pages": total_pages
            }
        )
        self.document_id = document_id
        self.page_number = page_number
        self.total_pages = total_pages


class PageImageNotFoundError(LibraryError):
    """Raised when a page image file is not found."""
    
    def __init__(self, document_id: int, page_number: int, image_path: Optional[str] = None, message: Optional[str] = None):
        super().__init__(
            message or f"Page {page_number} image not found for document {document_id}",
            error_code="PAGE_IMAGE_NOT_FOUND",
            context={
                "document_id": document_id,
                "page_number": page_number,
                "image_path": image_path
            }
        )
        self.document_id = document_id
        self.page_number = page_number
        self.image_path = image_path


class PagesDirectoryNotFoundError(LibraryError):
    """Raised when pages directory is not found."""
    
    def __init__(self, document_id: int, pages_dir_path: Optional[str] = None, message: Optional[str] = None):
        super().__init__(
            message or f"Pages directory not found for document {document_id}",
            error_code="PAGES_DIRECTORY_NOT_FOUND",
            context={
                "document_id": document_id,
                "pages_dir_path": pages_dir_path
            }
        )
        self.document_id = document_id
        self.pages_dir_path = pages_dir_path


class DocumentNotImageBasedError(LibraryError):
    """Raised when document doesn't use images."""
    
    def __init__(self, document_id: int, message: Optional[str] = None):
        super().__init__(
            message or f"Document {document_id} does not use images",
            error_code="DOCUMENT_NOT_IMAGE_BASED",
            context={"document_id": document_id}
        )
        self.document_id = document_id


class DanmakuNotFoundError(LibraryError):
    """Raised when a danmaku is not found."""
    
    def __init__(self, danmaku_id: int, message: Optional[str] = None):
        super().__init__(
            message or f"Danmaku {danmaku_id} not found",
            error_code="DANMAKU_NOT_FOUND",
            context={"danmaku_id": danmaku_id}
        )
        self.danmaku_id = danmaku_id


class BookmarkNotFoundError(LibraryError):
    """Raised when a bookmark is not found."""
    
    def __init__(self, bookmark_id: Optional[int] = None, document_id: Optional[int] = None, page_number: Optional[int] = None, message: Optional[str] = None):
        if bookmark_id:
            msg = message or f"Bookmark {bookmark_id} not found"
            context = {"bookmark_id": bookmark_id}
        else:
            msg = message or f"Bookmark not found for document {document_id}, page {page_number}"
            context = {"document_id": document_id, "page_number": page_number}
        
        super().__init__(
            msg,
            error_code="BOOKMARK_NOT_FOUND",
            context=context
        )
        self.bookmark_id = bookmark_id
        self.document_id = document_id
        self.page_number = page_number


class PermissionDeniedError(LibraryError):
    """Raised when user doesn't have permission for an operation."""
    
    def __init__(self, operation: str, resource_id: Optional[int] = None, message: Optional[str] = None):
        super().__init__(
            message or f"Permission denied for operation: {operation}",
            error_code="PERMISSION_DENIED",
            context={
                "operation": operation,
                "resource_id": resource_id
            }
        )
        self.operation = operation
        self.resource_id = resource_id
