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

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from services.library import LibraryService
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
async def get_document_file(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Serve PDF file (public).

    Increments view count when accessed.
    """
    service = LibraryService(db)
    document = service.get_document(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Resolve file path - handle both absolute (from WSL) and relative paths
    file_path = Path(document.file_path)
    
    # If path doesn't exist, try multiple resolution strategies
    if not file_path.exists():
        filename = file_path.name
        tried_paths = [str(file_path)]
        
        # Strategy 1: Try relative to storage_dir (most common case)
        relative_path = service.storage_dir / filename
        if relative_path.exists():
            logger.info("[Library] Resolved path for document %s: %s (original: %s)", 
                        document_id, relative_path, document.file_path)
            file_path = relative_path
        else:
            tried_paths.append(str(relative_path))
            
            # Strategy 2: If stored path is relative, try storage_dir + path
            if not Path(document.file_path).is_absolute():
                try_relative = service.storage_dir / document.file_path
                if try_relative.exists():
                    logger.info("[Library] Resolved relative path for document %s: %s", 
                                document_id, try_relative)
                    file_path = try_relative
                else:
                    tried_paths.append(str(try_relative))
            
            # Strategy 3: Try resolving from current working directory
            try_cwd = Path.cwd() / document.file_path
            if try_cwd.exists():
                logger.info("[Library] Resolved CWD path for document %s: %s", 
                            document_id, try_cwd)
                file_path = try_cwd
            else:
                tried_paths.append(str(try_cwd))
            
            # If still not found, log all attempts and raise error
            if not file_path.exists():
                logger.error("[Library] PDF file not found for document %s (ID: %s)", 
                            document.title, document_id)
                logger.error("[Library] Stored file_path: %s", document.file_path)
                logger.error("[Library] Storage dir: %s (exists: %s, absolute: %s)", 
                            service.storage_dir, service.storage_dir.exists(), 
                            service.storage_dir.resolve())
                logger.error("[Library] Tried paths: %s", tried_paths)
                logger.error("[Library] Current working directory: %s", Path.cwd())
                
                # List files in storage_dir for debugging
                if service.storage_dir.exists():
                    files_in_storage = list(service.storage_dir.glob("*.pdf"))
                    logger.error("[Library] PDF files in storage_dir: %s", 
                                [f.name for f in files_in_storage])
                
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"PDF file not found. Tried: {', '.join(tried_paths)}"
                )

    service.increment_views(document_id)

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=document.title + ".pdf"
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

        document = service.upload_document(
            file_name=file.filename,
            file_path=tmp_path,
            file_size=len(content),
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
        cover_path = Path(document.cover_image_path)
        if not cover_path.exists():
            cover_path = None

    # If not found, try document_id pattern
    if not cover_path:
        for ext in ['.png', '.jpg', '.jpeg', '.webp']:
            potential_path = service.covers_dir / f"{document_id}_cover{ext}"
            if potential_path.exists():
                cover_path = potential_path
                break

    # If still not found, try pdf_name pattern (for extracted covers)
    if not cover_path:
        pdf_path = Path(document.file_path)
        pdf_name = pdf_path.stem
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
