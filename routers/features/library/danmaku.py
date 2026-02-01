"""Library Danmaku Endpoints.

API endpoints for danmaku comments and replies.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from services.library import LibraryService
from services.redis.rate_limiting.redis_rate_limiter import RedisRateLimiter
from utils.auth import get_current_user
from utils.auth.roles import is_admin

from .models import DanmakuCreate, ReplyCreate, DanmakuUpdate


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/documents/{document_id}/danmaku")
async def get_danmaku(
    document_id: int,
    page_number: Optional[int] = Query(None, ge=1),
    selected_text: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get danmaku for a document.

    Can filter by page_number or selected_text.
    Requires authentication.
    """
    user_id = current_user.id
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recent danmaku across all documents.

    Returns the most recent danmaku comments ordered by creation time.
    Requires authentication.
    """
    user_id = current_user.id
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
    # Rate limit: 1 danmaku per minute per user (prevents spam)
    rate_limiter = RedisRateLimiter()
    is_allowed, _, error_msg = rate_limiter.check_and_record(
        category='library_danmaku_create',
        identifier=str(current_user.id),
        max_attempts=1,
        window_seconds=60
    )
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {error_msg}. Maximum 1 danmaku per minute."
        )

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

        # Structured logging
        logger.info(
            "[Library] Danmaku created",
            extra={
                "danmaku_id": danmaku.id,
                "document_id": document_id,
                "user_id": current_user.id,
                "page_number": data.page_number
            }
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
        logger.warning(
            "[Library] Danmaku creation failed: validation error",
            extra={
                "document_id": document_id,
                "user_id": current_user.id,
                "error": str(e)
            }
        )
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
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get replies to a danmaku.
    Requires authentication.
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

        # Structured logging
        logger.info(
            "[Library] Reply created",
            extra={
                "reply_id": reply.id,
                "danmaku_id": danmaku_id,
                "user_id": current_user.id,
                "parent_reply_id": data.parent_reply_id
            }
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
        logger.warning(
            "[Library] Reply creation failed",
            extra={
                "danmaku_id": danmaku_id,
                "user_id": current_user.id,
                "error": str(e)
            }
        )
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
    service = LibraryService(db, user_id=current_user.id)
    deleted = service.delete_reply(reply_id, is_admin=is_admin(current_user))

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reply not found or you don't have permission"
        )

    return {"message": "Reply deleted successfully"}
