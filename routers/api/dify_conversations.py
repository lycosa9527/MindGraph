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

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clients.dify import AsyncDifyClient
from config.database import get_async_db
from models.domain.auth import User
from models.domain.pinned_conversations import PinnedConversation
from services.dify.org_mindmate_client import resolve_mindmate_dify_client_short_lived
from services.dify.unified_conversations import list_unified_conversations, resolve_client_and_dify_user
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from utils.auth import get_current_user
from utils.dify_mindmate_user_id import mindmate_dify_user_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])

_DIFY_NOT_CONFIGURED = "AI service not configured"


def get_dify_user_id(user: User) -> str:
    """Generate consistent Dify user ID from MindGraph user."""
    return mindmate_dify_user_id(user)


def _organization_id_for_user(user: User) -> Optional[int]:
    """Organization id for user."""
    org_id = getattr(user, "organization_id", None)
    return int(org_id) if org_id is not None else None


async def _resolve_dify_client(user: User) -> AsyncDifyClient:
    """Resolve org Dify credentials without a request-scoped DB session."""
    return await resolve_mindmate_dify_client_short_lived(
        _organization_id_for_user(user),
        detail=_DIFY_NOT_CONFIGURED,
    )


class RenameRequest(BaseModel):
    """Request body for renaming a conversation"""

    name: Optional[str] = None
    auto_generate: bool = False


class FeedbackRequest(BaseModel):
    """Request body for message feedback (like/dislike)"""

    rating: Optional[str] = None  # "like", "dislike", or null to clear
    content: Optional[str] = None  # Optional feedback text


@router.get("/dify/conversations")
async def list_conversations(
    last_id: Optional[str] = Query(None, description="Last conversation ID for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Number of conversations to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List user's conversations from Dify.

    Returns conversations sorted by updated_at (newest first), merged across
    web MindMate and bound DingTalk MindBot identities when applicable.
    Each conversation includes:
    - id: Conversation ID
    - name: Auto-generated or custom title
    - created_at: Creation timestamp
    - updated_at: Last activity timestamp
    - channel: ``web`` or ``mindbot``
    - dify_user: Dify API user key (pass to message/delete/rename endpoints)
    """
    try:
        rows, has_more = await list_unified_conversations(
            db,
            current_user,
            limit=limit,
            last_id=last_id,
        )

        data = [
            {
                "id": row.id,
                "name": row.name,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "channel": row.channel,
                "dify_user": row.dify_user,
            }
            for row in rows
        ]

        logger.debug(
            "Fetched %d unified conversations for user %s",
            len(data),
            current_user.id,
        )

        return {
            "success": True,
            "data": data,
            "has_more": has_more,
            "limit": limit,
        }

    except BACKGROUND_INFRA_ERRORS as e:
        logger.error("Failed to fetch conversations: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/dify/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    dify_user: Optional[str] = Query(None, description="Dify user key from conversation list"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete a conversation from Dify.

    This permanently removes the conversation and all its messages.
    """
    try:
        client, dify_user_id = await resolve_client_and_dify_user(
            db,
            current_user,
            conversation_id,
            dify_user_hint=dify_user,
        )

        await client.delete_conversation(conversation_id=conversation_id, user_id=dify_user_id)

        logger.info("Deleted conversation %s for user %s", conversation_id, current_user.id)

        return {"success": True, "message": "Conversation deleted"}

    except BACKGROUND_INFRA_ERRORS as e:
        logger.error("Failed to delete conversation: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/dify/conversations/{conversation_id}/name")
async def rename_conversation(
    conversation_id: str,
    request: RenameRequest,
    dify_user: Optional[str] = Query(None, description="Dify user key from conversation list"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Rename a conversation or auto-generate a title.

    If auto_generate is True, Dify will generate a title based on conversation content.
    Otherwise, use the provided name.
    """
    try:
        client, dify_user_id = await resolve_client_and_dify_user(
            db,
            current_user,
            conversation_id,
            dify_user_hint=dify_user,
        )

        result = await client.rename_conversation(
            conversation_id=conversation_id,
            user_id=dify_user_id,
            name=request.name,
            auto_generate=request.auto_generate,
        )

        logger.info("Renamed conversation %s for user %s", conversation_id, current_user.id)

        return {"success": True, "data": result}

    except BACKGROUND_INFRA_ERRORS as e:
        logger.error("Failed to rename conversation: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/dify/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    first_id: Optional[str] = Query(None, description="First message ID for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Number of messages to return"),
    dify_user: Optional[str] = Query(None, description="Dify user key from conversation list"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
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
        client, dify_user_id = await resolve_client_and_dify_user(
            db,
            current_user,
            conversation_id,
            dify_user_hint=dify_user,
        )

        result = await client.get_messages(
            conversation_id=conversation_id,
            user_id=dify_user_id,
            first_id=first_id,
            limit=limit,
        )

        logger.debug(
            "Fetched %d messages for conversation %s",
            len(result.get("data", [])),
            conversation_id,
        )

        return {
            "success": True,
            "data": result.get("data", []),
            "has_more": result.get("has_more", False),
            "limit": result.get("limit", limit),
        }

    except BACKGROUND_INFRA_ERRORS as e:
        logger.error("Failed to fetch messages: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/dify/user-id")
async def get_user_dify_id(current_user: User = Depends(get_current_user)):
    """
    Get the Dify user ID for the current MindGraph user.

    This is useful for the frontend to know which user ID to use
    when communicating directly with Dify.
    """
    return {
        "success": True,
        "dify_user_id": get_dify_user_id(current_user),
        "mindgraph_user_id": current_user.id,
    }


@router.post("/dify/messages/{message_id}/feedback")
async def submit_message_feedback(
    message_id: str,
    request: FeedbackRequest,
    current_user: User = Depends(get_current_user),
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
        client = await _resolve_dify_client(current_user)
        dify_user_id = get_dify_user_id(current_user)

        result = await client.message_feedback(
            message_id=message_id,
            user_id=dify_user_id,
            rating=request.rating,
            content=request.content,
        )

        logger.info(
            "User %s submitted %s feedback for message %s",
            current_user.id,
            request.rating,
            message_id,
        )

        return {"success": True, "data": result}

    except DATABASE_ERRORS as e:
        logger.error("Failed to submit message feedback: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/dify/pinned")
async def list_pinned_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get list of pinned conversation IDs for the current user.

    Returns a list of conversation IDs that the user has pinned.
    """
    try:
        result = await db.execute(
            select(PinnedConversation)
            .where(PinnedConversation.user_id == current_user.id)
            .order_by(PinnedConversation.pinned_at.desc())
        )
        pinned = result.scalars().all()

        return {"success": True, "data": [p.conversation_id for p in pinned]}

    except DATABASE_ERRORS as e:
        logger.error("Failed to fetch pinned conversations: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/dify/conversations/{conversation_id}/pin")
async def toggle_pin_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Toggle pin status for a conversation.

    If the conversation is already pinned, it will be unpinned.
    If not pinned, it will be pinned to the top.
    """
    try:
        result = await db.execute(
            select(PinnedConversation).where(
                PinnedConversation.user_id == current_user.id,
                PinnedConversation.conversation_id == conversation_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            await db.delete(existing)
            await db.commit()
            logger.info("User %s unpinned conversation %s", current_user.id, conversation_id)
            return {
                "success": True,
                "is_pinned": False,
                "message": "Conversation unpinned",
            }

        pinned = PinnedConversation(user_id=current_user.id, conversation_id=conversation_id)
        db.add(pinned)
        await db.commit()
        logger.info("User %s pinned conversation %s", current_user.id, conversation_id)
        return {
            "success": True,
            "is_pinned": True,
            "message": "Conversation pinned",
        }

    except DATABASE_ERRORS as e:
        logger.error("Failed to toggle pin for conversation: %s", e)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e
