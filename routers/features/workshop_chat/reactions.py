"""
Reaction Endpoints
====================

Add and remove emoji reactions on channel/topic messages.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.workshop_chat import ChatMessage, MessageReaction
from services.features.workshop_chat import reaction_service
from services.features.workshop_chat_ws_manager import chat_ws_manager
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


class AddReactionRequest(BaseModel):
    """Body for adding an emoji reaction."""

    emoji_name: str = Field(..., min_length=1, max_length=50)
    emoji_code: str = Field(..., min_length=1, max_length=10)


@router.post("/messages/{message_id}/reactions", status_code=status.HTTP_200_OK)
async def toggle_reaction(
    message_id: int,
    body: AddReactionRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle an emoji reaction on a message (add or remove)."""
    msg_result = await db.execute(select(ChatMessage).where(ChatMessage.id == message_id))
    msg = msg_result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    result = await reaction_service.toggle_reaction(
        db,
        message_id,
        current_user.id,
        body.emoji_name,
        body.emoji_code,
    )

    await chat_ws_manager.broadcast_to_channel(
        msg.channel_id,
        {
            "type": "reaction_update",
            "message_id": message_id,
            "emoji_name": body.emoji_name,
            "emoji_code": body.emoji_code,
            "user_id": current_user.id,
            "action": result["action"],
        },
    )

    return result


@router.delete(
    "/messages/{message_id}/reactions/{emoji_name}",
    status_code=status.HTTP_200_OK,
)
async def remove_reaction(
    message_id: int,
    emoji_name: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Explicitly remove a specific emoji reaction."""
    msg_result = await db.execute(select(ChatMessage).where(ChatMessage.id == message_id))
    msg = msg_result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    existing_result = await db.execute(
        select(MessageReaction).where(
            MessageReaction.message_id == message_id,
            MessageReaction.user_id == current_user.id,
            MessageReaction.emoji_name == emoji_name,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=404, detail="Reaction not found")

    emoji_code = existing.emoji_code

    await db.delete(existing)
    await db.commit()

    await chat_ws_manager.broadcast_to_channel(
        msg.channel_id,
        {
            "type": "reaction_update",
            "message_id": message_id,
            "emoji_name": emoji_name,
            "emoji_code": emoji_code,
            "user_id": current_user.id,
            "action": "removed",
        },
    )

    return {"action": "removed", "message_id": message_id, "emoji_name": emoji_name}


@router.get("/messages/{message_id}/reactions")
async def get_reactions(
    message_id: int,
    db: AsyncSession = Depends(get_async_db),
    _current_user: User = Depends(get_current_user),
):
    """Get grouped reactions for a message."""
    return await reaction_service.get_message_reactions(db, message_id)
