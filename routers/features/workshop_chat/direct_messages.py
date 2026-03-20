"""
Direct Message Endpoints
==========================

DM conversations, message history, and sending.

Organization isolation is enforced via ``access_dm_partner``,
analogous to Zulip's ``access_user_by_id`` check that prevents
cross-realm private messages.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from routers.features.workshop_chat.dependencies import access_dm_partner
from routers.features.workshop_chat.schemas import SendDMRequest
from services.features.workshop_chat import dm_service
from services.features.workshop_chat.mention_resolution import (
    MentionResolutionError,
)
from services.features.workshop_chat_ws_manager import chat_ws_manager
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/dm/conversations")
async def list_dm_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List DM conversations."""
    return dm_service.list_conversations(db, current_user.id)


@router.get("/dm/{partner_id}/messages/search")
async def search_dm_messages(
    partner_id: int,
    q: str,
    limit: int = 40,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search within the 1:1 DM narrow (same partner only)."""
    access_dm_partner(db, current_user, partner_id)
    return dm_service.search_messages(
        db, current_user.id, partner_id, q, limit=limit,
    )


@router.get("/dm/{partner_id}/messages")
async def get_dm_messages(
    partner_id: int,
    anchor: int = 0,
    num_before: int = 50,
    num_after: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get DM message history with a user (same org only)."""
    access_dm_partner(db, current_user, partner_id)
    dm_service.mark_read(db, current_user.id, partner_id)
    return dm_service.get_messages(
        db, current_user.id, partner_id,
        anchor=anchor, num_before=num_before, num_after=num_after,
    )


@router.post("/dm/{partner_id}/read")
async def mark_dm_read(
    partner_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all messages from this partner as read without loading history."""
    access_dm_partner(db, current_user, partner_id)
    updated = dm_service.mark_read(db, current_user.id, partner_id)
    return {"updated": updated}


@router.post("/dm/{partner_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_dm(
    partner_id: int,
    body: SendDMRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a direct message (same org only)."""
    access_dm_partner(db, current_user, partner_id)
    try:
        result = dm_service.send(
            db, current_user.id, partner_id,
            body.content, message_type=body.message_type,
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
    await chat_ws_manager.send_to_user(partner_id, {
        "type": "dm", "message": result,
    })
    return result
