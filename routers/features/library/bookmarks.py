"""Library Bookmark Endpoints.

API endpoints for bookmarks.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from services.library import LibraryService
from utils.auth import get_current_user

from .models import BookmarkCreate


logger = logging.getLogger(__name__)

router = APIRouter()


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

        # Structured logging
        logger.info(
            "[Library] Bookmark created",
            extra={
                "bookmark_id": bookmark.id,
                "document_id": document_id,
                "page_number": data.page_number,
                "user_id": current_user.id
            }
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
