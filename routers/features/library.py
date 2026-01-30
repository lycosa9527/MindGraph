"""Library Router.

API endpoints for public library feature with image-based viewing and danmaku comments.

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

from fastapi import APIRouter, Depends, HTTPException, Query, status, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from services.library import LibraryService
from services.library.library_path_utils import resolve_library_path
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
    use_images: bool = False
    pages_dir_path: Optional[str] = None
    total_pages: Optional[int] = None
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

    Returns paginated list of documents (image-based).
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
        "use_images": document.use_images or False,
        "pages_dir_path": document.pages_dir_path,
        "total_pages": document.total_pages,
        "views_count": document.views_count,
        "likes_count": document.likes_count,
        "comments_count": document.comments_count,
        "created_at": document.created_at.isoformat() if document.created_at else "",
        "uploader": {
            "id": document.uploader_id,
            "name": document.uploader.name if document.uploader else None,
        }
    }


# PDF file serving endpoint removed - no longer needed for image-based viewing
# Documents are now served as images via /documents/{id}/pages/{page} endpoint

@router.get("/documents/{document_id}/pages/{page_number}")
async def get_document_page_image(
    document_id: int,
    page_number: int,
    db: Session = Depends(get_db)
):
    """
    Serve page image for image-based documents (public).
    
    Returns the image file for the specified page number.
    """
    service = LibraryService(db)
    document = service.get_document(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    if not document.use_images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document does not use images"
        )

    # Validate page number against total_pages
    if document.total_pages and page_number > document.total_pages:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_number} exceeds total pages ({document.total_pages})"
        )

    # Get page image path
    image_path = service.get_page_image_path(document_id, page_number)
    if not image_path or not image_path.exists():
        # Page doesn't exist - find next available page (only scan directory on 404)
        # This is the only time we scan, and we cache the result
        next_page = service.get_next_available_page(document_id, page_number)
        
        error_detail = f"Page {page_number} image not found"
        if next_page:
            error_detail += f". Next available page: {next_page}"
        
        # Include next available page info in response headers for frontend
        headers = {}
        if next_page:
            headers["X-Next-Available-Page"] = str(next_page)
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_detail,
            headers=headers
        )

    # Determine content type from file extension
    content_type = "image/jpeg"
    if image_path.suffix.lower() == ".png":
        content_type = "image/png"

    logger.info(
        "[Library] Serving page image: Document %s, Page %s, File: %s",
        document_id,
        page_number,
        image_path.name
    )

    return FileResponse(
        path=str(image_path),
        media_type=content_type,
        filename=f"{document.title}_page_{page_number}{image_path.suffix}",
        headers={
            'Cache-Control': 'public, max-age=3600',
        }
    )


# PDF upload endpoint removed - no longer needed for image-based viewing
# Documents are now registered via register_image_folders.py script
# Users manually export PDFs to images and place folders in storage/library/

class BookRegisterRequest(BaseModel):
    """Request model for registering a book folder"""
    folder_path: str = Field(
        ...,
        description="Path to folder containing page images (relative to storage/library or absolute)"
    )
    title: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="Book title (defaults to folder name)"
    )
    description: Optional[str] = Field(None, max_length=2000, description="Book description")


class BookRegisterBatchRequest(BaseModel):
    """Request model for batch registering book folders"""
    folder_paths: List[str] = Field(..., description="List of folder paths to register")


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

    # Resolve folder path
    folder_path = Path(data.folder_path)

    # If relative path, try resolving from storage/library
    if not folder_path.is_absolute():
        # Try relative to storage/library
        potential_path = service.storage_dir / folder_path
        if potential_path.exists() and potential_path.is_dir():
            folder_path = potential_path
        else:
            # Try relative to current working directory
            potential_path = Path.cwd() / folder_path
            if potential_path.exists() and potential_path.is_dir():
                folder_path = potential_path
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Folder not found: {data.folder_path}"
                )
    else:
        # Absolute path - verify it exists
        if not folder_path.exists() or not folder_path.is_dir():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Folder not found: {data.folder_path}"
            )

    try:
        document = service.register_book_folder(
            folder_path=folder_path,
            title=data.title,
            description=data.description
        )

        return {
            "id": document.id,
            "title": document.title,
            "description": document.description,
            "cover_image_path": document.cover_image_path,
            "use_images": document.use_images or False,
            "pages_dir_path": document.pages_dir_path,
            "total_pages": document.total_pages,
            "views_count": document.views_count,
            "likes_count": document.likes_count,
            "comments_count": document.comments_count,
            "created_at": document.created_at.isoformat() if document.created_at else "",
            "uploader": {
                "id": document.uploader_id,
                "name": document.uploader.name if document.uploader else None,
            }
        }

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
            # Resolve folder path
            folder_path = Path(folder_path_str)

            # If relative path, try resolving from storage/library
            if not folder_path.is_absolute():
                potential_path = service.storage_dir / folder_path
                if potential_path.exists() and potential_path.is_dir():
                    folder_path = potential_path
                else:
                    potential_path = Path.cwd() / folder_path
                    if potential_path.exists() and potential_path.is_dir():
                        folder_path = potential_path
                    else:
                        results["failed"].append({
                            "folder_path": folder_path_str,
                            "error": f"Folder not found: {folder_path_str}"
                        })
                        continue
            else:
                if not folder_path.exists() or not folder_path.is_dir():
                    results["failed"].append({
                        "folder_path": folder_path_str,
                        "error": f"Folder not found: {folder_path_str}"
                    })
                    continue

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
    
    Supports naming pattern:
    - {document_id}_cover.{ext} (from API upload or manual placement)
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
    Delete danmaku.
    
    Only the creator or admin can delete.
    """
    service = LibraryService(db, user_id=current_user.id)
    deleted = service.delete_danmaku(danmaku_id, is_admin=is_admin(current_user))

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
    Delete reply.
    
    Only the creator or admin can delete.
    """
    """
    Delete own reply.
    """
    service = LibraryService(db, user_id=current_user.id)
    deleted = service.delete_reply(reply_id, is_admin=is_admin(current_user))

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
    logger.info(
        "Creating bookmark: document_id=%s, page_number=%s, user_id=%s",
        document_id,
        data.page_number,
        current_user.id
    )
    service = LibraryService(db, user_id=current_user.id)

    try:
        bookmark = service.create_bookmark(
            document_id=document_id,
            page_number=data.page_number,
            note=data.note
        )
        logger.info(
            "Bookmark created successfully: id=%s, uuid=%s",
            bookmark.id,
            bookmark.uuid
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
        logger.error("Failed to create bookmark: %s", e)
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

    Returns 404 if bookmark doesn't exist or doesn't belong to the user.
    """
    service = LibraryService(db, user_id=current_user.id)
    bookmark = service.get_bookmark(document_id, page_number)

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
