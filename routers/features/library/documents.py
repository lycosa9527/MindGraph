"""Library Document Endpoints.

API endpoints for library document management.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional
from pathlib import Path
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from services.library import LibraryService
from services.library.library_path_utils import resolve_library_path
from services.library.image_path_resolver import resolve_page_image
from services.library.exceptions import (
    DocumentNotFoundError,
    PageNotFoundError,
    PageImageNotFoundError,
    PagesDirectoryNotFoundError,
    DocumentNotImageBasedError
)
from services.redis.rate_limiting.redis_rate_limiter import RedisRateLimiter
from utils.auth import get_current_user
from utils.auth.roles import is_admin

from .helpers import serialize_document, require_admin, get_optional_user
from .models import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUpdate,
    BookRegisterRequest,
    BookRegisterBatchRequest
)


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    _current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    List all library documents.

    Returns paginated list of documents (image-based).
    Public endpoint - authentication optional.
    """
    service = LibraryService(db)
    result = service.get_documents(page=page, page_size=page_size, search=search)
    return result


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a single library document.
    Requires authentication.
    """
    service = LibraryService(db)
    document = service.get_document(document_id)

    if not document:
        error = DocumentNotFoundError(document_id)
        logger.warning(
            "[Library] Document not found",
            extra={
                "error_code": error.error_code,
                "user_id": current_user.id,
                **error.context
            }
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error.message
        )

    # Structured logging
    logger.info(
        "[Library] Document retrieved",
        extra={
            "document_id": document_id,
            "user_id": current_user.id,
            "title": document.title
        }
    )

    return serialize_document(document)


@router.get("/documents/{document_id}/pages/{page_number}")
@router.head("/documents/{document_id}/pages/{page_number}")
async def get_document_page_image(
    document_id: int,
    page_number: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Serve page image for image-based documents.

    Supports both GET (returns image) and HEAD (checks existence).
    Returns the image file for the specified page number.
    Requires authentication.
    """
    # Rate limit: 150 pages per minute per user
    rate_limiter = RedisRateLimiter()
    is_allowed, _, error_msg = rate_limiter.check_and_record(
        category='library_image_download',
        identifier=str(current_user.id),
        max_attempts=150,
        window_seconds=60
    )
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {error_msg}. Maximum 150 pages per minute."
        )

    service = LibraryService(db)

    try:
        # Try to use cached metadata first (for high concurrency)
        cached_metadata = service.get_cached_document_metadata(document_id)

        if cached_metadata:
            # Use cached metadata - no DB query needed!
            if not cached_metadata.get("use_images"):
                raise DocumentNotImageBasedError(document_id)

            # Validate page number
            total_pages = cached_metadata.get("total_pages")
            if total_pages and page_number > total_pages:
                raise PageNotFoundError(document_id, page_number, total_pages)

            # Get page image path using cached metadata
            pages_dir_path = cached_metadata.get("pages_dir_path")
            if not pages_dir_path:
                raise PagesDirectoryNotFoundError(document_id, pages_dir_path)

            pages_dir = resolve_library_path(
                pages_dir_path,
                service.storage_dir,
                Path.cwd()
            )

            if not pages_dir or not pages_dir.exists():
                raise PagesDirectoryNotFoundError(document_id, str(pages_dir) if pages_dir else None)

            image_path = resolve_page_image(pages_dir, page_number)
            document_title = cached_metadata.get("title", "Document")
        else:
            # Cache miss - query DB and cache result
            document = service.get_document(document_id, use_cache=True)

            if not document:
                raise DocumentNotFoundError(document_id)

            if not document.use_images:
                raise DocumentNotImageBasedError(document_id)

            # Validate page number against total_pages
            if document.total_pages and page_number > document.total_pages:
                raise PageNotFoundError(document_id, page_number, document.total_pages)

            # Get page image path - pass document to avoid duplicate DB query
            image_path = service.get_page_image_path_from_document(document, page_number)
            document_title = document.title

        if not image_path or not image_path.exists():
            raise PageImageNotFoundError(document_id, page_number, str(image_path) if image_path else None)

    except (DocumentNotFoundError, PageNotFoundError, PageImageNotFoundError,
            PagesDirectoryNotFoundError, DocumentNotImageBasedError) as e:
        # Log with context for debugging
        logger.warning(
            "[Library] Error serving page image: %s",
            e.message,
            extra={
                "error_code": e.error_code,
                "user_id": current_user.id,
                **e.context
            }
        )
        # Convert to HTTPException with appropriate status code
        status_map = {
            "DOCUMENT_NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "PAGE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "PAGE_IMAGE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "PAGES_DIRECTORY_NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "DOCUMENT_NOT_IMAGE_BASED": status.HTTP_400_BAD_REQUEST,
        }
        error_code = e.error_code if e.error_code else "DOCUMENT_NOT_FOUND"
        raise HTTPException(
            status_code=status_map.get(error_code, status.HTTP_404_NOT_FOUND),
            detail=e.message
        ) from e

    # Determine content type from file extension
    content_type = "image/jpeg"
    if image_path.suffix.lower() == ".png":
        content_type = "image/png"

    # Structured logging with context
    logger.info(
        "[Library] Serving page image",
        extra={
            "document_id": document_id,
            "page_number": page_number,
            "user_id": current_user.id,
            "image_filename": image_path.name,
            "file_size": image_path.stat().st_size if image_path.exists() else None
        }
    )

    return FileResponse(
        path=str(image_path),
        media_type=content_type,
        filename=f"{document_title}_page_{page_number}{image_path.suffix}",
        headers={
            'Cache-Control': 'public, max-age=3600',
        }
    )


@router.post("/books/register", response_model=DocumentResponse)
async def register_book(
    data: BookRegisterRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Register a book folder as a library document (admin only).

    The folder should contain page images with naming patterns like:
    - page_001.jpg, page_002.jpg, ...
    - 001.jpg, 002.jpg, ...
    - page1.jpg, page2.jpg, ...
    - 1.jpg, 2.jpg, ...

    The folder can be:
    - A relative path from storage/library/ (e.g., "my_book")
    - An absolute path to a folder
    """
    service = LibraryService(db, user_id=current_user.id)

    # Resolve folder path - SECURITY: Only allow paths within storage/library/
    folder_path = Path(data.folder_path)

    # Reject absolute paths - security measure
    if folder_path.is_absolute():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Absolute paths are not allowed. Use relative paths from storage/library/"
        )

    # Resolve relative path from storage/library
    resolved_path = (service.storage_dir / folder_path).resolve()

    # SECURITY: Ensure resolved path is within storage_dir (prevent path traversal)
    try:
        if not resolved_path.is_relative_to(service.storage_dir.resolve()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path traversal detected. Folder must be within storage/library/"
            )
    except ValueError as exc:
        # Path is not relative to storage_dir
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path traversal detected. Folder must be within storage/library/"
        ) from exc

    # Verify folder exists
    if not resolved_path.exists() or not resolved_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Folder not found: {data.folder_path}"
        )

    folder_path = resolved_path

    try:
        document = service.register_book_folder(
            folder_path=folder_path,
            title=data.title,
            description=data.description
        )

        return serialize_document(document)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e


@router.post("/books/register-batch")
async def register_books_batch(
    data: BookRegisterBatchRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Register multiple book folders at once (admin only).

    Accepts a list of folder paths and registers each one.
    Returns a summary of successful and failed registrations.
    """
    service = LibraryService(db, user_id=current_user.id)

    results = {
        "successful": [],
        "failed": []
    }

    for folder_path_str in data.folder_paths:
        try:
            # Resolve folder path - SECURITY: Only allow paths within storage/library/
            folder_path = Path(folder_path_str)

            # Reject absolute paths - security measure
            if folder_path.is_absolute():
                results["failed"].append({
                    "folder_path": folder_path_str,
                    "error": "Absolute paths are not allowed. Use relative paths from storage/library/"
                })
                continue

            # Resolve relative path from storage/library
            resolved_path = (service.storage_dir / folder_path).resolve()

            # SECURITY: Ensure resolved path is within storage_dir (prevent path traversal)
            try:
                if not resolved_path.is_relative_to(service.storage_dir.resolve()):
                    results["failed"].append({
                        "folder_path": folder_path_str,
                        "error": "Path traversal detected. Folder must be within storage/library/"
                    })
                    continue
            except ValueError:
                results["failed"].append({
                    "folder_path": folder_path_str,
                    "error": "Path traversal detected. Folder must be within storage/library/"
                })
                continue

            # Verify folder exists
            if not resolved_path.exists() or not resolved_path.is_dir():
                results["failed"].append({
                    "folder_path": folder_path_str,
                    "error": f"Folder not found: {folder_path_str}"
                })
                continue

            folder_path = resolved_path

            document = service.register_book_folder(folder_path=folder_path)
            results["successful"].append({
                "folder_path": folder_path_str,
                "document_id": document.id,
                "title": document.title,
                "total_pages": document.total_pages
            })

        except ValueError as e:
            results["failed"].append({
                "folder_path": folder_path_str,
                "error": str(e)
            })
        except Exception as e:
            logger.error("[Library] Error registering folder %s: %s", folder_path_str, e, exc_info=True)
            results["failed"].append({
                "folder_path": folder_path_str,
                "error": f"Unexpected error: {str(e)}"
            })

    return {
        "total": len(data.folder_paths),
        "successful_count": len(results["successful"]),
        "failed_count": len(results["failed"]),
        "results": results
    }


@router.put("/documents/{document_id}")
async def update_document(
    document_id: int,
    data: DocumentUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Update document metadata (admin only, for future admin panel).
    """
    service = LibraryService(db, user_id=current_user.id)
    document = service.update_document(
        document_id=document_id,
        title=data.title,
        description=data.description
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    return {
        "id": document.id,
        "title": document.title,
        "description": document.description,
        "message": "Document updated successfully"
    }


@router.post("/documents/{document_id}/cover")
async def upload_cover_image(
    document_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Upload/update cover image (admin only, for future admin panel).
    """
    service = LibraryService(db, user_id=current_user.id)
    document = service.get_document(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    allowed_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPG, PNG, and WEBP images are supported"
        )

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Enforce file size limit
    if file_size > service.max_file_size:
        max_size_mb = service.max_file_size / 1024 / 1024
        got_size_mb = file_size / 1024 / 1024
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {max_size_mb:.1f}MB, got {got_size_mb:.1f}MB"
        )

    # Validate MIME type matches extension
    content_type = file.content_type or ""
    expected_mime_types = {
        '.jpg': ['image/jpeg'],
        '.jpeg': ['image/jpeg'],
        '.png': ['image/png'],
        '.webp': ['image/webp']
    }
    if file_ext in expected_mime_types:
        if content_type and content_type not in expected_mime_types[file_ext]:
            logger.warning(
                "[Library] MIME type mismatch: extension=%s, content_type=%s",
                file_ext, content_type
            )
            # Don't reject, but log warning - some clients send wrong MIME types

    # Validate file content (magic bytes check)
    if file_ext in {'.jpg', '.jpeg'}:
        if not content.startswith(b'\xff\xd8\xff'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JPEG file format"
            )
    elif file_ext == '.png':
        if not content.startswith(b'\x89PNG\r\n\x1a\n'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PNG file format"
            )
    elif file_ext == '.webp':
        if not content.startswith(b'RIFF') or b'WEBP' not in content[:12]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid WEBP file format"
            )

    try:
        cover_filename = f"{document_id}_cover{file_ext}"
        cover_path = service.covers_dir / cover_filename

        with open(cover_path, "wb") as f:
            f.write(content)

        document = service.update_document(
            document_id=document_id,
            cover_image_path=str(cover_path)
        )

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # Invalidate cache since cover image changed
        service.invalidate_document_cache(document_id)

        return {
            "id": document.id,
            "cover_image_path": document.cover_image_path,
            "message": "Cover image uploaded successfully"
        }

    except Exception as e:
        logger.error("[Library] Cover upload failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Cover upload failed") from e


@router.get("/documents/{document_id}/cover")
async def get_cover_image(
    document_id: int,
    _current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Serve cover image.

    Supports naming pattern:
    - {document_id}_cover.{ext} (from API upload or manual placement)
    Public endpoint - authentication optional.
    """
    service = LibraryService(db)
    document = service.get_document(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Try cover_image_path from database first
    cover_path = None
    if document.cover_image_path:
        cover_path_resolved = resolve_library_path(
            document.cover_image_path,
            service.covers_dir,
            Path.cwd()
        )
        if cover_path_resolved and cover_path_resolved.exists():
            cover_path = cover_path_resolved

    # If not found, try document_id pattern
    if not cover_path:
        for ext in ['.png', '.jpg', '.jpeg', '.webp']:
            potential_path = service.covers_dir / f"{document_id}_cover{ext}"
            if potential_path.exists():
                cover_path = potential_path
                break

    # If still not found, try document title pattern (for manually added covers)
    if not cover_path:
        # Use document title as fallback pattern
        doc_title_safe = "".join(c for c in document.title if c.isalnum() or c in (' ', '-', '_')).strip()
        if doc_title_safe:
            potential_path = service.covers_dir / f"{doc_title_safe}_cover.png"
            if potential_path.exists():
                cover_path = potential_path

    if not cover_path or not cover_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cover image not found"
        )

    # Determine media type from file extension
    media_type = "image/jpeg"
    if cover_path.suffix.lower() == ".png":
        media_type = "image/png"
    elif cover_path.suffix.lower() == ".webp":
        media_type = "image/webp"
    elif cover_path.suffix.lower() in [".jpg", ".jpeg"]:
        media_type = "image/jpeg"

    return FileResponse(
        path=str(cover_path),
        media_type=media_type
    )


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Delete a document (admin only, for future admin panel).
    """
    service = LibraryService(db, user_id=current_user.id)
    deleted = service.delete_document(document_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    return {"message": "Document deleted successfully"}
