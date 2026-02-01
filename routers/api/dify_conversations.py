"""Dify Conversation Management API Router.

API endpoints for managing Dify conversations:
- GET /api/dify/conversations - List user's conversations
- DELETE /api/dify/conversations/{id} - Delete a conversation
- POST /api/dify/conversations/{id}/name - Rename/auto-generate title
- GET /api/dify/conversations/{id}/messages - Get conversation messages
- POST /api/dify/conversations/{id}/pin - Toggle pin status
- GET /api/dify/pinned - List pinned conversation IDs

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional
import logging
import os

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from clients.dify import AsyncDifyClient
from config.database import get_db
from models.domain.auth import User
from models.domain.pinned_conversations import PinnedConversation
from utils.auth import get_current_user


logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


def get_dify_user_id(user: User) -> str:
    """Generate consistent Dify user ID from MindGraph user"""
    return f"mg_user_{user.id}"


def get_dify_client() -> AsyncDifyClient:
    """Get configured Dify client"""
    api_key = os.getenv('DIFY_API_KEY')
    api_url = os.getenv('DIFY_API_URL', 'https://api.dify.ai/v1')
    timeout = int(os.getenv('DIFY_TIMEOUT', '30'))

    if not api_key:
        raise HTTPException(status_code=500, detail="AI service not configured")

    return AsyncDifyClient(api_key=api_key, api_url=api_url, timeout=timeout)


class RenameRequest(BaseModel):
    """Request body for renaming a conversation"""
    name: Optional[str] = None
    auto_generate: bool = False


class FeedbackRequest(BaseModel):
    """Request body for message feedback (like/dislike)"""
    rating: Optional[str] = None  # "like", "dislike", or null to clear
    content: Optional[str] = None  # Optional feedback text


@router.get('/dify/conversations')
async def list_conversations(
    last_id: Optional[str] = Query(None, description="Last conversation ID for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Number of conversations to return"),
    current_user: User = Depends(get_current_user)
):
    """
    List user's conversations from Dify.

    Returns conversations sorted by updated_at (newest first).
    Each conversation includes:
    - id: Conversation ID
    - name: Auto-generated or custom title
    - created_at: Creation timestamp
    - updated_at: Last activity timestamp
    """
    try:
        client = get_dify_client()
        dify_user_id = get_dify_user_id(current_user)

        result = await client.get_conversations(
            user_id=dify_user_id,
            last_id=last_id,
            limit=limit,
            sort_by="-updated_at"
        )

        logger.debug(
            "Fetched %d conversations for user %s",
            len(result.get('data', [])), current_user.id
        )

        return {
            "success": True,
            "data": result.get("data", []),
            "has_more": result.get("has_more", False),
            "limit": result.get("limit", limit)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch conversations: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete('/dify/conversations/{conversation_id}')
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a conversation from Dify.

    This permanently removes the conversation and all its messages.
    """
    try:
        client = get_dify_client()
        dify_user_id = get_dify_user_id(current_user)

        await client.delete_conversation(
            conversation_id=conversation_id,
            user_id=dify_user_id
        )

        logger.info(
            "Deleted conversation %s for user %s",
            conversation_id, current_user.id
        )

        return {"success": True, "message": "Conversation deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete conversation: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post('/dify/conversations/{conversation_id}/name')
async def rename_conversation(
    conversation_id: str,
    request: RenameRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Rename a conversation or auto-generate a title.

    If auto_generate is True, Dify will generate a title based on conversation content.
    Otherwise, use the provided name.
    """
    try:
        client = get_dify_client()
        dify_user_id = get_dify_user_id(current_user)

        result = await client.rename_conversation(
            conversation_id=conversation_id,
            user_id=dify_user_id,
            name=request.name,
            auto_generate=request.auto_generate
        )

        logger.info(
            "Renamed conversation %s for user %s",
            conversation_id, current_user.id
        )

        return {
            "success": True,
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to rename conversation: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get('/dify/conversations/{conversation_id}/messages')
async def get_conversation_messages(
    conversation_id: str,
    first_id: Optional[str] = Query(None, description="First message ID for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Number of messages to return"),
    current_user: User = Depends(get_current_user)
):
    """
    Get messages for a specific conversation.

    Returns messages in chronological order.
    Each message includes:
    - id: Message ID
    - role: 'user' or 'assistant'
    - content: Message text
    - created_at: Timestamp
    """
    try:
        client = get_dify_client()
        dify_user_id = get_dify_user_id(current_user)

        result = await client.get_messages(
            conversation_id=conversation_id,
            user_id=dify_user_id,
            first_id=first_id,
            limit=limit
        )

        logger.debug(
            "Fetched %d messages for conversation %s",
            len(result.get('data', [])), conversation_id
        )

        return {
            "success": True,
            "data": result.get("data", []),
            "has_more": result.get("has_more", False),
            "limit": result.get("limit", limit)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch messages: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get('/dify/user-id')
async def get_user_dify_id(
    current_user: User = Depends(get_current_user)
):
    """
    Get the Dify user ID for the current MindGraph user.

    This is useful for the frontend to know which user ID to use
    when communicating directly with Dify.
    """
    return {
        "success": True,
        "dify_user_id": get_dify_user_id(current_user),
        "mindgraph_user_id": current_user.id
    }


@router.post('/dify/messages/{message_id}/feedback')
async def submit_message_feedback(
    message_id: str,
    request: FeedbackRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Submit feedback (like/dislike) for a specific message.

    Args:
        message_id: The Dify message ID to provide feedback for
        request: FeedbackRequest with rating ("like", "dislike", or null) and optional content

    Returns:
        Success response with feedback result
    """
    try:
        client = get_dify_client()
        dify_user_id = get_dify_user_id(current_user)

        result = await client.message_feedback(
            message_id=message_id,
            user_id=dify_user_id,
            rating=request.rating,
            content=request.content
        )

        logger.info(
            "User %s submitted %s feedback for message %s",
            current_user.id, request.rating, message_id
        )

        return {
            "success": True,
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to submit message feedback: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get('/dify/pinned')
async def list_pinned_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of pinned conversation IDs for the current user.

    Returns a list of conversation IDs that the user has pinned.
    """
    try:
        pinned = db.query(PinnedConversation).filter(
            PinnedConversation.user_id == current_user.id
        ).order_by(PinnedConversation.pinned_at.desc()).all()

        return {
            "success": True,
            "data": [p.conversation_id for p in pinned]
        }

    except Exception as e:
        logger.error("Failed to fetch pinned conversations: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post('/dify/conversations/{conversation_id}/pin')
async def toggle_pin_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Toggle pin status for a conversation.

    If the conversation is already pinned, it will be unpinned.
    If not pinned, it will be pinned to the top.
    """
    try:
        # Check if already pinned
        existing = db.query(PinnedConversation).filter(
            PinnedConversation.user_id == current_user.id,
            PinnedConversation.conversation_id == conversation_id
        ).first()

        if existing:
            # Unpin
            db.delete(existing)
            db.commit()
            logger.info(
                "User %s unpinned conversation %s",
                current_user.id, conversation_id
            )
            return {
                "success": True,
                "is_pinned": False,
                "message": "Conversation unpinned"
            }
        else:
            # Pin
            pinned = PinnedConversation(
                user_id=current_user.id,
                conversation_id=conversation_id
            )
            db.add(pinned)
            db.commit()
            logger.info(
                "User %s pinned conversation %s",
                current_user.id, conversation_id
            )
            return {
                "success": True,
                "is_pinned": True,
                "message": "Conversation pinned"
            }

    except Exception as e:
        logger.error("Failed to toggle pin for conversation: %s", e)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e
