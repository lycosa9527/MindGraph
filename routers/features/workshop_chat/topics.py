"""
Topic Endpoints
=================

Topic CRUD for conversation threads within channels.

Topics are lightweight labels (Zulip-style).  Heavyweight operations
(resolve, set deadline) are now channel-level — see ``channels.py``.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from routers.features.workshop_chat.dependencies import (
    access_channel,
    require_membership,
)
from routers.features.workshop_chat.schemas import (
    CreateTopicRequest,
    UpdateTopicRequest,
    MoveTopicRequest,
    RenameTopicRequest,
    SetTopicVisibilityRequest,
)
from services.features.workshop_chat import topic_service, message_service
from services.features.workshop_chat_ws_manager import chat_ws_manager
from utils.auth import get_current_user, is_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/channels/{channel_id}/topics")
async def list_topics(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List topics (conversations) in a channel."""
    require_membership(db, channel_id, current_user.id)
    return topic_service.list_topics(db, channel_id, user_id=current_user.id)


@router.post("/channels/{channel_id}/topics", status_code=status.HTTP_201_CREATED)
async def create_topic(
    channel_id: int,
    body: CreateTopicRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a topic (any channel member)."""
    require_membership(db, channel_id, current_user.id)
    result = topic_service.create_topic(
        db, channel_id, body.title, current_user.id,
        description=body.description,
    )
    await chat_ws_manager.broadcast_to_channel(channel_id, {
        "type": "topic_updated", "channel_id": channel_id, "topic": result,
    })
    return result


@router.get("/channels/{channel_id}/topics/{topic_id}")
async def get_topic_detail(
    channel_id: int,
    topic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get topic detail with recent messages."""
    require_membership(db, channel_id, current_user.id)
    topic = topic_service.get_topic(db, topic_id)
    if not topic or topic.channel_id != channel_id:
        raise HTTPException(status_code=404, detail="Topic not found")
    topic_data = topic_service.list_topics(db, channel_id)
    match = next((t for t in topic_data if t["id"] == topic_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Topic not found")
    recent_msgs = message_service.get_topic_messages(
        db, topic_id, channel_id, num_before=30,
    )
    match["recent_messages"] = recent_msgs
    return match


@router.put("/channels/{channel_id}/topics/{topic_id}")
async def update_topic(
    channel_id: int,
    topic_id: int,
    body: UpdateTopicRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update topic (creator, manager, or channel owner)."""
    require_membership(db, channel_id, current_user.id)
    topic = topic_service.get_topic(db, topic_id)
    if not topic or topic.channel_id != channel_id:
        raise HTTPException(status_code=404, detail="Topic not found")
    if topic.created_by != current_user.id and not is_manager(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    result = topic_service.update_topic(
        db, topic_id,
        title=body.title, description=body.description,
    )
    if result:
        await chat_ws_manager.broadcast_to_channel(channel_id, {
            "type": "topic_updated", "channel_id": channel_id, "topic": result,
        })
    return result


# ── Move ─────────────────────────────────────────────────────────

@router.post("/channels/{channel_id}/topics/{topic_id}/move")
async def move_topic(
    channel_id: int,
    topic_id: int,
    body: MoveTopicRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Move a topic to another channel (manager or topic creator only)."""
    access_channel(db, channel_id, current_user)
    topic = topic_service.get_topic(db, topic_id)
    if not topic or topic.channel_id != channel_id:
        raise HTTPException(status_code=404, detail="Topic not found")
    if topic.created_by != current_user.id and not is_manager(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    access_channel(db, body.target_channel_id, current_user)
    result = topic_service.move_topic(db, topic_id, body.target_channel_id)
    if result:
        await chat_ws_manager.broadcast_to_channel(channel_id, {
            "type": "topic_moved",
            "channel_id": channel_id,
            "target_channel_id": body.target_channel_id,
            "topic_id": topic_id,
        })
    return result


# ── Rename ───────────────────────────────────────────────────────

@router.post("/channels/{channel_id}/topics/{topic_id}/rename")
async def rename_topic(
    channel_id: int,
    topic_id: int,
    body: RenameTopicRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rename a topic (creator or manager)."""
    require_membership(db, channel_id, current_user.id)
    topic = topic_service.get_topic(db, topic_id)
    if not topic or topic.channel_id != channel_id:
        raise HTTPException(status_code=404, detail="Topic not found")
    if topic.created_by != current_user.id and not is_manager(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    result = topic_service.rename_topic(db, topic_id, body.title)
    if result:
        await chat_ws_manager.broadcast_to_channel(channel_id, {
            "type": "topic_updated", "channel_id": channel_id, "topic": result,
        })
    return result


# ── Delete ───────────────────────────────────────────────────────

@router.delete("/channels/{channel_id}/topics/{topic_id}")
async def delete_topic(
    channel_id: int,
    topic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a topic (creator or manager)."""
    require_membership(db, channel_id, current_user.id)
    topic = topic_service.get_topic(db, topic_id)
    if not topic or topic.channel_id != channel_id:
        raise HTTPException(status_code=404, detail="Topic not found")
    if topic.created_by != current_user.id and not is_manager(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    topic_service.delete_topic(db, topic_id)
    await chat_ws_manager.broadcast_to_channel(channel_id, {
        "type": "topic_deleted", "channel_id": channel_id, "topic_id": topic_id,
    })
    return {"ok": True}


# ── Mark as read ─────────────────────────────────────────────────

@router.post("/channels/{channel_id}/topics/{topic_id}/read")
async def mark_topic_read(
    channel_id: int,
    topic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a topic as read for the current user."""
    require_membership(db, channel_id, current_user.id)
    return topic_service.mark_topic_read(db, topic_id, current_user.id)


# ── Visibility preference ────────────────────────────────────────

@router.post("/channels/{channel_id}/topics/{topic_id}/visibility")
async def set_topic_visibility(
    channel_id: int,
    topic_id: int,
    body: SetTopicVisibilityRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set user's visibility preference for a topic (mute/follow/inherit)."""
    require_membership(db, channel_id, current_user.id)
    topic = topic_service.get_topic(db, topic_id)
    if not topic or topic.channel_id != channel_id:
        raise HTTPException(status_code=404, detail="Topic not found")
    try:
        return topic_service.set_visibility(
            db, topic_id, current_user.id, body.visibility_policy,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        ) from exc
