"""Library Router.

API endpoints for public library feature with PDF viewing and danmaku comments.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, List
from pathlib import Path
import logging
import os
import tempfile

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from services.library import LibraryService
from services.library.pdf_utils import resolve_library_path, validate_pdf_file
from services.library.pdf_optimizer import should_optimize_pdf, optimize_pdf
from utils.auth import get_current_user
from utils.auth.roles import is_admin


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/library", tags=["Library"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin access."""
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# =============================================================================
# Pydantic Models
# =============================================================================

class DocumentResponse(BaseModel):
    """Response model for a library document"""
    id: int
    title: str
    description: Optional[str]
    cover_image_path: Optional[str]
    views_count: int
    likes_count: int
    comments_count: int
    created_at: str
    uploader: dict


class DocumentListResponse(BaseModel):
    """Response model for document list"""
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int


class DocumentCreate(BaseModel):
    """Request model for creating a document (for future admin panel)"""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)


class DocumentUpdate(BaseModel):
    """Request model for updating document metadata"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)


class DanmakuCreate(BaseModel):
    """Request model for creating danmaku"""
    content: str = Field(..., min_length=1)
    page_number: int = Field(..., ge=1)
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    selected_text: Optional[str] = None
    text_bbox: Optional[dict] = None
    color: Optional[str] = None
    highlight_color: Optional[str] = None


class ReplyCreate(BaseModel):
    """Request model for creating a reply"""
    content: str = Field(..., min_length=1)
    parent_reply_id: Optional[int] = None


class DanmakuUpdate(BaseModel):
    """Request model for updating danmaku position"""
    position_x: Optional[int] = None
    position_y: Optional[int] = None


class BookmarkCreate(BaseModel):
    """Request model for creating a bookmark"""
    page_number: int = Field(..., ge=1)
    note: Optional[str] = None


# =============================================================================
# Document Endpoints
# =============================================================================

@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    List all library documents (public).

    Returns paginated list of PDFs.
    """
    service = LibraryService(db)
    result = service.get_documents(page=page, page_size=page_size, search=search)
    return result


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a single library document (public).
    """
    service = LibraryService(db)
    document = service.get_document(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    return {
        "id": document.id,
        "title": document.title,
        "description": document.description,
        "cover_image_path": document.cover_image_path,
        "views_count": document.views_count,
        "likes_count": document.likes_count,
        "comments_count": document.comments_count,
        "created_at": document.created_at.isoformat() if document.created_at else "",
        "uploader": {
            "id": document.uploader_id,
            "name": document.uploader.name if document.uploader else None,
        }
    }


@router.get("/documents/{document_id}/file")
@router.head("/documents/{document_id}/file")
async def get_document_file(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Serve PDF file (public).

    Supports both GET and HEAD methods.
    - GET: Returns the PDF file and increments view count
    - HEAD: Returns headers only (for checking file accessibility)
    
    Supports range requests for PDF.js streaming.
    """
    service = LibraryService(db)
    document = service.get_document(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Resolve file path using normalized path resolution
    file_path = resolve_library_path(
        document.file_path,
        service.storage_dir,
        Path.cwd()
    )

    if not file_path or not file_path.exists():
        logger.error("[Library] PDF file not found for document %s (ID: %s)",
                    document.title, document_id)
        logger.error("[Library] Stored file_path: %s", document.file_path)
        logger.error("[Library] Storage dir: %s", service.storage_dir)

        # List files in storage_dir for debugging
        if service.storage_dir.exists():
            files_in_storage = list(service.storage_dir.glob("*.pdf"))
            logger.error("[Library] PDF files in storage_dir: %s",
                        [f.name for f in files_in_storage])

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF file not found for document {document_id}"
        )

    # Get file size for logging and range request handling
    file_size = file_path.stat().st_size

    # Log request details for debugging
    range_header = request.headers.get('Range', 'none')
    method = request.method
    logger.debug("[Library] Serving PDF file: %s (ID: %s, Size: %s bytes, Method: %s, Range: %s)",
                document.title, document_id, file_size, method, range_header)

    # Only increment views for GET requests, not HEAD requests
    if method == "GET":
        service.increment_views(document_id)

    # Handle HEAD requests - return headers only
    if method == "HEAD":
        return Response(
            status_code=status.HTTP_200_OK,
            headers={
                'Accept-Ranges': 'bytes',
                'Content-Length': str(file_size),
                'Content-Type': 'application/pdf',
                'Cache-Control': 'public, max-age=3600',
            }
        )

    # Handle range requests manually to ensure proper support
    # FileResponse should handle this, but we'll ensure it works correctly
    # by checking Range header and responding appropriately
    if range_header and range_header != 'none':
        # Parse Range header: "bytes=start-end" or "bytes=start-"
        try:
            range_match = range_header.replace('bytes=', '').split('-')
            start = int(range_match[0]) if range_match[0] else None
            end = int(range_match[1]) if range_match[1] and range_match[1] else file_size - 1

            if start is None:
                # Suffix range: "bytes=-suffix_length"
                start = file_size - end
                end = file_size - 1

            # Validate range
            if start < 0 or end >= file_size or start > end:
                return Response(
                    status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                    headers={
                        'Content-Range': f'bytes */{file_size}',
                        'Accept-Ranges': 'bytes',
                    }
                )

            # Calculate content length for range
            content_length = end - start + 1

            # Read the requested range from file
            # Using synchronous I/O is fine here - range reads are fast
            with open(file_path, 'rb') as f:
                f.seek(start)
                content = f.read(content_length)

            logger.debug("[Library] Range request: bytes=%s-%s/%s (length=%s)",
                        start, end, file_size, content_length)

            return Response(
                content=content,
                status_code=status.HTTP_206_PARTIAL_CONTENT,
                headers={
                    'Content-Range': f'bytes {start}-{end}/{file_size}',
                    'Content-Length': str(content_length),
                    'Content-Type': 'application/pdf',
                    'Accept-Ranges': 'bytes',
                    'Cache-Control': 'public, max-age=3600',
                }
            )
        except (ValueError, IndexError) as e:
            logger.warning("[Library] Invalid Range header '%s': %s", range_header, e)
            # Fall through to full file response

    # Full file request (no Range header) - use FileResponse
    # FileResponse automatically handles range requests, but we've already
    # handled them above for better control
    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=document.title + ".pdf",
        headers={
            'Accept-Ranges': 'bytes',
            'Cache-Control': 'public, max-age=3600',
        }
    )


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Upload a PDF document (admin only, for future admin panel).
    """
    service = LibraryService(db, user_id=current_user.id)

    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name

        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are supported"
            )

        # Validate PDF file (magic bytes check)
        is_valid, error_msg = validate_pdf_file(Path(tmp_path))
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid PDF file: {error_msg}"
            )

        # Check and optimize PDF if xref is at end
        pdf_path = Path(tmp_path)
        should_opt, reason, _ = should_optimize_pdf(pdf_path)
        if should_opt:
            logger.info(
                "[Library] Optimizing uploaded PDF %s: %s",
                file.filename,
                reason
            )
            success, error, stats = optimize_pdf(pdf_path, backup=False)
            if success and stats['was_optimized']:
                logger.info(
                    "[Library] Optimized %s: %s -> %s bytes",
                    file.filename,
                    f"{stats['original_size']:,}",
                    f"{stats['new_size']:,}"
                )
            elif not success:
                logger.warning(
                    "[Library] Failed to optimize uploaded PDF %s: %s",
                    file.filename,
                    error
                )

        # Get file size after potential optimization
        file_size = pdf_path.stat().st_size

        document = service.upload_document(
            file_name=file.filename,
            file_path=tmp_path,
            file_size=file_size,
            title=title,
            description=description
        )

        return {
            "id": document.id,
            "title": document.title,
            "message": "Document uploaded successfully"
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.error("[Library] Upload failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Upload failed") from e


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

    try:
        cover_filename = f"{document_id}_cover{file_ext}"
        cover_path = service.covers_dir / cover_filename

        with open(cover_path, "wb") as f:
            content = await file.read()
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
    db: Session = Depends(get_db)
):
    """
    Serve cover image (public).
    
    Supports both naming patterns:
    - {document_id}_cover.{ext} (from API upload)
    - {pdf_name}_cover.png (from extraction script)
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

    # If still not found, try pdf_name pattern (for extracted covers)
    if not cover_path:
        pdf_path_resolved = resolve_library_path(
            document.file_path,
            service.storage_dir,
            Path.cwd()
        )
        if pdf_path_resolved:
            pdf_name = pdf_path_resolved.stem
            potential_path = service.covers_dir / f"{pdf_name}_cover.png"
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


# =============================================================================
# Danmaku Endpoints
# =============================================================================

@router.get("/documents/{document_id}/danmaku")
async def get_danmaku(
    document_id: int,
    page_number: Optional[int] = Query(None, ge=1),
    selected_text: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get danmaku for a document.

    Can filter by page_number or selected_text.
    """
    user_id = current_user.id if current_user else None
    service = LibraryService(db, user_id=user_id)

    danmaku_list = service.get_danmaku(
        document_id=document_id,
        page_number=page_number,
        selected_text=selected_text
    )

    return {"danmaku": danmaku_list}


@router.get("/danmaku/recent")
async def get_recent_danmaku(
    limit: int = Query(50, ge=1, le=100),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recent danmaku across all documents.

    Returns the most recent danmaku comments ordered by creation time.
    """
    user_id = current_user.id if current_user else None
    service = LibraryService(db, user_id=user_id)

    danmaku_list = service.get_recent_danmaku(limit=limit)

    return {"danmaku": danmaku_list}


@router.post("/documents/{document_id}/danmaku")
async def create_danmaku(
    document_id: int,
    data: DanmakuCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a danmaku comment.

    Supports both text selection mode and position mode.
    """
    service = LibraryService(db, user_id=current_user.id)

    try:
        danmaku = service.create_danmaku(
            document_id=document_id,
            content=data.content,
            page_number=data.page_number,
            position_x=data.position_x,
            position_y=data.position_y,
            selected_text=data.selected_text,
            text_bbox=data.text_bbox,
            color=data.color,
            highlight_color=data.highlight_color
        )

        return {
            "id": danmaku.id,
            "message": "Danmaku created successfully",
            "danmaku": {
                "id": danmaku.id,
                "content": danmaku.content,
                "page_number": danmaku.page_number,
                "selected_text": danmaku.selected_text,
                "text_bbox": danmaku.text_bbox,
                "created_at": danmaku.created_at.isoformat() if danmaku.created_at else None
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/danmaku/{danmaku_id}/like")
async def toggle_like(
    danmaku_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Toggle like on a danmaku.
    """
    service = LibraryService(db, user_id=current_user.id)

    try:
        result = service.toggle_like(danmaku_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/danmaku/{danmaku_id}/replies")
async def get_replies(
    danmaku_id: int,
    db: Session = Depends(get_db)
):
    """
    Get replies to a danmaku.
    """
    service = LibraryService(db)
    replies = service.get_replies(danmaku_id)

    return {"replies": replies}


@router.post("/danmaku/{danmaku_id}/replies")
async def create_reply(
    danmaku_id: int,
    data: ReplyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reply to a danmaku.
    """
    service = LibraryService(db, user_id=current_user.id)

    try:
        reply = service.create_reply(
            danmaku_id=danmaku_id,
            content=data.content,
            parent_reply_id=data.parent_reply_id
        )

        return {
            "id": reply.id,
            "message": "Reply created successfully",
            "reply": {
                "id": reply.id,
                "content": reply.content,
                "parent_reply_id": reply.parent_reply_id,
                "created_at": reply.created_at.isoformat() if reply.created_at else None
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.patch("/danmaku/{danmaku_id}")
async def update_danmaku_position(
    danmaku_id: int,
    data: DanmakuUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update danmaku position.
    
    Only the creator or admin can update position.
    """
    service = LibraryService(db, user_id=current_user.id)
    updated = service.update_danmaku_position(
        danmaku_id=danmaku_id,
        position_x=data.position_x,
        position_y=data.position_y,
        is_admin=is_admin(current_user)
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Danmaku not found or you don't have permission"
        )

    return {"message": "Danmaku position updated successfully"}


@router.delete("/danmaku/{danmaku_id}")
async def delete_danmaku(
    danmaku_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete own danmaku.
    """
    service = LibraryService(db, user_id=current_user.id)
    deleted = service.delete_danmaku(danmaku_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Danmaku not found or you don't have permission"
        )

    return {"message": "Danmaku deleted successfully"}


@router.delete("/danmaku/replies/{reply_id}")
async def delete_reply(
    reply_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete own reply.
    """
    service = LibraryService(db, user_id=current_user.id)
    deleted = service.delete_reply(reply_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reply not found or you don't have permission"
        )

    return {"message": "Reply deleted successfully"}


# =============================================================================
# Bookmark Endpoints
# =============================================================================

@router.post("/documents/{document_id}/bookmarks")
async def create_bookmark(
    document_id: int,
    data: BookmarkCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create or update a bookmark for a document page.
    """
    service = LibraryService(db, user_id=current_user.id)

    try:
        bookmark = service.create_bookmark(
            document_id=document_id,
            page_number=data.page_number,
            note=data.note
        )

        return {
            "id": bookmark.id,
            "message": "Bookmark created successfully",
            "bookmark": {
                "id": bookmark.id,
                "uuid": bookmark.uuid,
                "document_id": bookmark.document_id,
                "page_number": bookmark.page_number,
                "note": bookmark.note,
                "created_at": bookmark.created_at.isoformat() if bookmark.created_at else None
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/bookmarks/recent")
async def get_recent_bookmarks(
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recent bookmarks for the current user.

    Returns the most recent bookmarks ordered by creation time.
    """
    service = LibraryService(db, user_id=current_user.id)

    bookmarks = service.get_recent_bookmarks(limit=limit)

    return {"bookmarks": bookmarks}


@router.get("/documents/{document_id}/bookmarks/{page_number}")
async def get_bookmark(
    document_id: int,
    page_number: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get bookmark for a specific document page.

    Returns null if bookmark doesn't exist (200 OK, not 404).
    This is a valid state, not an error condition.
    """
    service = LibraryService(db, user_id=current_user.id)
    bookmark = service.get_bookmark(document_id, page_number)

    if not bookmark:
        return None

    return {
        "id": bookmark.id,
        "uuid": bookmark.uuid,
        "document_id": bookmark.document_id,
        "page_number": bookmark.page_number,
        "note": bookmark.note,
        "created_at": bookmark.created_at.isoformat() if bookmark.created_at else None,
        "updated_at": bookmark.updated_at.isoformat() if bookmark.updated_at else None,
    }


@router.get("/bookmarks/{bookmark_uuid}")
async def get_bookmark_by_uuid(
    bookmark_uuid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get bookmark by UUID.
    """
    service = LibraryService(db, user_id=current_user.id)
    bookmark = service.get_bookmark_by_uuid(bookmark_uuid)

    if not bookmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bookmark not found"
        )

    return {
        "id": bookmark.id,
        "uuid": bookmark.uuid,
        "document_id": bookmark.document_id,
        "page_number": bookmark.page_number,
        "note": bookmark.note,
        "created_at": bookmark.created_at.isoformat() if bookmark.created_at else None,
        "updated_at": bookmark.updated_at.isoformat() if bookmark.updated_at else None,
        "document": {
            "id": bookmark.document.id if bookmark.document else None,
            "title": bookmark.document.title if bookmark.document else None,
        } if bookmark.document else None
    }


@router.delete("/bookmarks/{bookmark_id}")
async def delete_bookmark(
    bookmark_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a bookmark.
    """
    service = LibraryService(db, user_id=current_user.id)
    deleted = service.delete_bookmark(bookmark_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bookmark not found or you don't have permission"
        )

    return {"message": "Bookmark deleted successfully"}
