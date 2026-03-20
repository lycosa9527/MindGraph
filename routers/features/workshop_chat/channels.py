"""
Channel Endpoints
===================

Channel CRUD, join/leave, member listing, and organization member listing.

Mirrors Zulip's ``zerver/views/streams.py`` — thin view functions that
delegate to the service layer after access checks.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from routers.auth.dependencies import require_manager
from routers.features.workshop_chat.conditional_list_response import (
    workshop_list_json_response,
)
from routers.features.workshop_chat.dependencies import (
    access_channel,
    get_effective_org_id,
    require_channel_manager,
)
from routers.features.workshop_chat.schemas import (
    CreateChannelRequest,
    OrgMembersPage,
    OrgMemberRow,
    UpdateChannelRequest,
    UpdateMemberPrefsRequest,
    UpdateChannelPermissionsRequest,
)
from services.features.workshop_chat import channel_service
from services.features.workshop_chat.default_channels import (
    seed_announce_channel,
    seed_default_channels,
)
from services.features.workshop_chat.workshop_list_etag import channels_list_etag
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

_ORG_MEMBER_Q_MAX_LEN = 100
_ORG_MEMBER_LIMIT_DEFAULT = 200
_ORG_MEMBER_LIMIT_MAX = 200


def _escape_ilike_literal(text: str) -> str:
    """Escape ``%``, ``_``, ``\\`` for use in ILIKE with PostgreSQL ESCAPE '\\'."""
    return (
        text.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


# ── Organization members ─────────────────────────────────────────

@router.get("/org-members", response_model=OrgMembersPage)
async def list_org_members(
    org_id: Optional[int] = None,
    q: Optional[str] = None,
    limit: int = _ORG_MEMBER_LIMIT_DEFAULT,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List members in the user's organization (including the current user).

    Used for the contacts roster, presence, and starting DMs with colleagues.
    Admins may pass ``org_id`` to list members of another organization.

    Pagination: ``limit`` (default 200, max 200), ``offset``. Optional ``q``
    filters display names with case-insensitive substring match (ILIKE).
    """
    effective_org_id = get_effective_org_id(current_user, org_id)
    lim = min(max(limit, 1), _ORG_MEMBER_LIMIT_MAX)
    off = max(offset, 0)

    raw_q = (q or "").strip()
    if raw_q and len(raw_q) > _ORG_MEMBER_Q_MAX_LEN:
        raw_q = raw_q[:_ORG_MEMBER_Q_MAX_LEN]

    filters = [User.organization_id == effective_org_id]
    if raw_q:
        pattern = f"%{_escape_ilike_literal(raw_q)}%"
        filters.append(User.name.ilike(pattern, escape="\\"))

    total = db.query(User).filter(*filters).count()
    users = (
        db.query(User)
        .filter(*filters)
        .order_by(User.name)
        .offset(off)
        .limit(lim)
        .all()
    )
    items = [
        OrgMemberRow(
            id=u.id,
            name=u.name or f"User {u.id}",
            avatar=u.avatar,
        )
        for u in users
    ]
    return OrgMembersPage(
        items=items,
        total=int(total),
        limit=lim,
        offset=off,
    )


# ── Initialization ────────────────────────────────────────────────
# This static path must be defined before any /channels/{channel_id} route
# so that POST /channels/initialize is matched correctly (not as channel_id="initialize").

@router.get(
    "/channels/initialize",
    status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
    responses={405: {"description": "Use POST to initialize default channels"}},
)
async def initialize_default_channels_get():
    """Initialize endpoint only accepts POST; GET returns 405."""
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Method Not Allowed. Use POST to initialize default channels.",
        headers={"Allow": "POST"},
    )


@router.post("/channels/initialize", status_code=status.HTTP_200_OK)
async def initialize_default_channels(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Seed the global announce channel and org-level default channels.

    Any authenticated user with an organization can trigger this.
    Both seed functions are idempotent.
    """
    try:
        seed_announce_channel(db, current_user.id)
        if not current_user.organization_id:
            return {"ok": True, "created": 0, "channels": []}
        created = seed_default_channels(
            db, current_user.organization_id, current_user.id,
        )
        if not created:
            return {"ok": True, "created": 0, "channels": []}
        return {"ok": True, "created": len(created), "channels": created}
    except Exception as exc:
        logger.exception(
            "[WorkshopChat] initialize_default_channels failed: %s",
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


# ── Channel CRUD ─────────────────────────────────────────────────

@router.get("/channels")
async def list_channels(
    request: Request,
    org_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List channels in the user's organization.

    Admins may pass ``org_id`` to view channels of another organization.
    """
    effective_org_id = get_effective_org_id(current_user, org_id)
    etag = channels_list_etag(
        db, effective_org_id, current_user.id, current_user,
    )
    return workshop_list_json_response(
        request,
        etag,
        lambda: channel_service.list_channels(
            db, effective_org_id, current_user.id,
            current_user=current_user,
        ),
    )


@router.post("/channels", status_code=status.HTTP_201_CREATED)
async def create_channel(
    body: CreateChannelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """Create a channel — group or lesson-study (manager only).

    Pass ``parent_id`` to create a lesson-study under a group.
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to an organization",
        )
    return channel_service.create_channel(
        db,
        name=body.name,
        organization_id=current_user.organization_id,
        created_by=current_user.id,
        description=body.description,
        avatar=body.avatar,
        parent_id=body.parent_id,
        color=body.color,
        channel_status=body.status,
        deadline=body.deadline,
        diagram_id=body.diagram_id,
    )


@router.put("/channels/{channel_id}")
async def update_channel(
    channel_id: int,
    body: UpdateChannelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a channel (manager or owner only, same org)."""
    channel = access_channel(db, channel_id, current_user)
    require_channel_manager(current_user, channel)
    payload = body.model_dump(exclude_unset=True)
    clear_deadline = (
        "deadline" in payload and payload["deadline"] is None
    )
    deadline_val = None if clear_deadline else body.deadline
    return channel_service.update_channel(
        db, channel_id,
        name=body.name, description=body.description, avatar=body.avatar,
        color=body.color, channel_status=body.status,
        deadline=deadline_val, clear_deadline=clear_deadline,
        diagram_id=body.diagram_id,
        is_resolved=body.is_resolved,
    )


@router.post("/channels/{channel_id}/read")
async def mark_channel_read(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Advance the current user's read waterline to the latest channel message."""
    access_channel(db, channel_id, current_user)
    return channel_service.mark_channel_read(
        db, channel_id, current_user.id,
    )


@router.delete("/channels/{channel_id}")
async def archive_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """Archive a channel (manager only, same org)."""
    access_channel(db, channel_id, current_user)
    channel_service.archive_channel(db, channel_id)
    return {"ok": True}


# ── Membership ───────────────────────────────────────────────────

@router.post("/channels/{channel_id}/join")
async def join_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Join a channel (must be in same org)."""
    access_channel(db, channel_id, current_user)
    channel_service.join_channel(db, channel_id, current_user.id)
    return {"ok": True}


@router.post("/channels/{channel_id}/leave")
async def leave_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Leave a channel."""
    channel_service.leave_channel(db, channel_id, current_user.id)
    return {"ok": True}


@router.get("/channels/{channel_id}/members")
async def get_channel_members(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List members of a channel (must belong to same org)."""
    access_channel(db, channel_id, current_user)
    return channel_service.get_channel_members(db, channel_id)


# ── Subscription preferences ─────────────────────────────────────

@router.post("/channels/{channel_id}/mute")
async def toggle_mute(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle mute state for the current user's channel subscription."""
    access_channel(db, channel_id, current_user)
    try:
        return channel_service.toggle_mute(db, channel_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        ) from exc


@router.post("/channels/{channel_id}/pin")
async def toggle_pin(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle pin-to-top state for the current user's channel subscription."""
    access_channel(db, channel_id, current_user)
    try:
        return channel_service.toggle_pin(db, channel_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        ) from exc


@router.patch("/channels/{channel_id}/preferences")
async def update_preferences(
    channel_id: int,
    body: UpdateMemberPrefsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the current user's per-channel preferences (color, notifications)."""
    access_channel(db, channel_id, current_user)
    try:
        return channel_service.update_member_prefs(
            db, channel_id, current_user.id,
            color=body.color,
            desktop_notifications=body.desktop_notifications,
            email_notifications=body.email_notifications,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        ) from exc


# ── Channel-level permissions ─────────────────────────────────────

@router.patch("/channels/{channel_id}/permissions")
async def update_permissions(
    channel_id: int,
    body: UpdateChannelPermissionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update channel-level settings (type, posting policy, default flag).

    Requires manager or channel creator permissions.
    """
    channel = access_channel(db, channel_id, current_user)
    require_channel_manager(current_user, channel)
    result = channel_service.update_channel_permissions(
        db, channel_id,
        channel_type=body.channel_type,
        posting_policy=body.posting_policy,
        is_default=body.is_default,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )
    return result
