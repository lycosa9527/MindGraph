"""
Message Endpoints
===================

Channel messages, topic messages, edit and delete.

Mirrors Zulip's ``zerver/views/message_send.py`` and
``zerver/views/message_edit.py`` — thin endpoint handlers that
delegate to the service layer after membership verification.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from models.domain.workshop_chat import ChatMessage, ChatTopic
from routers.features.workshop_chat.dependencies import (
    access_channel,
    require_membership_unless_announce,
    require_post_permission,
)
from routers.features.workshop_chat.schemas import (
    SendMessageRequest,
    EditMessageRequest,
)
from services.features.workshop_chat import (
    message_service, star_service, reaction_service, file_service,
)
from services.features.workshop_chat.mention_resolution import (
    MentionResolutionError,
)
from services.features.workshop_chat_ws_manager import chat_ws_manager
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Channel Messages ─────────────────────────────────────────────

@router.get("/channels/{channel_id}/messages")
async def get_channel_messages(
    channel_id: int,
    anchor: int = 0,
    num_before: int = 50,
    num_after: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get general channel messages (not tied to a topic)."""
    channel = access_channel(db, channel_id, current_user)
    require_membership_unless_announce(db, channel, current_user.id)
    return message_service.get_channel_messages(
        db, channel_id, anchor=anchor,
        num_before=num_before, num_after=num_after,
    )


@router.get("/channels/{channel_id}/messages/search")
def search_channel_messages(
    channel_id: int,
    q: str,
    topic_id: Optional[int] = None,
    limit: int = 40,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search message bodies within a channel; optional topic narrow (Zulip-style)."""
    channel = access_channel(db, channel_id, current_user)
    require_membership_unless_announce(db, channel, current_user.id)
    if topic_id is not None:
        topic = (
            db.query(ChatTopic)
            .filter(
                ChatTopic.id == topic_id,
                ChatTopic.channel_id == channel_id,
            )
            .first()
        )
        if not topic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Topic not found in this channel",
            )
    return message_service.search_messages(
        db, channel_id, q, topic_id=topic_id, limit=limit,
    )


@router.post("/channels/{channel_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_channel_message(
    channel_id: int,
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a general channel message."""
    channel = access_channel(db, channel_id, current_user)
    require_membership_unless_announce(db, channel, current_user.id)
    require_post_permission(channel, current_user)
    try:
        result = message_service.send_message(
            db, channel_id, current_user.id, body.content,
            message_type=body.message_type, parent_id=body.parent_id,
        )
    except MentionResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_mentions",
                "unknown": exc.unknown_names,
                "ambiguous": exc.ambiguous_names,
            },
        ) from exc
    await chat_ws_manager.broadcast_to_channel(channel_id, {
        "type": "channel_message", "channel_id": channel_id, "message": result,
    }, exclude_user=current_user.id)
    return result


# ── Topic Messages ────────────────────────────────────────────────

@router.get("/channels/{channel_id}/topics/{topic_id}/messages")
async def get_topic_messages(
    channel_id: int,
    topic_id: int,
    anchor: int = 0,
    num_before: int = 50,
    num_after: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get messages for a specific topic."""
    channel = access_channel(db, channel_id, current_user)
    require_membership_unless_announce(db, channel, current_user.id)
    return message_service.get_topic_messages(
        db, topic_id, channel_id,
        anchor=anchor, num_before=num_before, num_after=num_after,
    )


@router.post(
    "/channels/{channel_id}/topics/{topic_id}/messages",
    status_code=status.HTTP_201_CREATED,
)
async def send_topic_message(
    channel_id: int,
    topic_id: int,
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message to a topic."""
    channel = access_channel(db, channel_id, current_user)
    require_membership_unless_announce(db, channel, current_user.id)
    require_post_permission(channel, current_user)
    try:
        result = message_service.send_message(
            db, channel_id, current_user.id, body.content,
            topic_id=topic_id,
            message_type=body.message_type, parent_id=body.parent_id,
        )
    except MentionResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_mentions",
                "unknown": exc.unknown_names,
                "ambiguous": exc.ambiguous_names,
            },
        ) from exc
    await chat_ws_manager.broadcast_to_channel(channel_id, {
        "type": "topic_message", "channel_id": channel_id,
        "topic_id": topic_id, "message": result,
    }, exclude_user=current_user.id)
    return result


# ── Edit / Delete ─────────────────────────────────────────────────

@router.put("/messages/{message_id}")
async def edit_message(
    message_id: int,
    body: EditMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit a message (sender only)."""
    try:
        result = message_service.edit_message(
            db, message_id, current_user.id, body.content,
        )
    except MentionResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_mentions",
                "unknown": exc.unknown_names,
                "ambiguous": exc.ambiguous_names,
            },
        ) from exc
    if not result:
        raise HTTPException(status_code=404, detail="Message not found or not yours")
    return result


@router.delete("/messages/{message_id}")
def delete_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a message (sender or org/realm moderator)."""
    stub = (
        db.query(ChatMessage)
        .filter(ChatMessage.id == message_id)
        .first()
    )
    if not stub:
        raise HTTPException(status_code=404, detail="Message not found")
    access_channel(db, stub.channel_id, current_user)
    success = message_service.delete_message(db, message_id, current_user)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found or not permitted",
        )
    return {"ok": True}


# ── Star / Bookmark ───────────────────────────────────────────────

@router.post("/messages/{message_id}/star")
async def toggle_star(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Star or unstar a message."""
    return star_service.toggle_star(db, message_id, current_user.id)


@router.get("/starred")
async def get_starred_messages(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the current user's starred messages."""
    return star_service.get_starred_messages(
        db, current_user.id, limit=limit, offset=offset,
    )


# ── Batch Endpoints (for feed rendering) ─────────────────────────

@router.get("/messages/reactions/batch")
async def get_reactions_batch(
    ids: str,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Batch-fetch grouped reactions for multiple messages."""
    message_ids = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    return reaction_service.get_reactions_batch(db, message_ids)


@router.get("/messages/starred/batch")
async def get_starred_batch(
    ids: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return which of the given message IDs are starred by the user."""
    message_ids = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    return list(star_service.is_starred_batch(db, message_ids, current_user.id))


@router.get("/messages/attachments/batch")
async def get_attachments_batch(
    ids: str,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Batch-fetch attachments for multiple messages."""
    message_ids = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    return file_service.get_attachments_batch(db, message_ids)
