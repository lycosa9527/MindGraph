"""
Org library share routes.

Send one diagram into other members' libraries, and take a first-opened edit lease.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from models.domain.auth import User
from services.diagram_shares.access import (
    current_grantee_ids,
    leave_share,
    library_access,
    replace_share_set,
)
from services.diagram_shares.lease import leave_lease
from services.diagram_shares.presence import iter_diagram_share_events
from services.features.org_member_roster import fetch_org_members_page
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from utils.auth import get_current_user
from utils.db.session_open import user_rls_session

from .helpers import check_endpoint_rate_limit, get_rate_limit_identifier

logger = logging.getLogger(__name__)

router = APIRouter(tags=["diagram-shares"])

_TAB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class ShareCandidateItem(BaseModel):
    """One person the owner can send a diagram to."""

    id: int
    name: str
    already_shared: bool


class ShareCandidatesResponse(BaseModel):
    """Org roster for the share dialog, plus everyone who already has the diagram."""

    items: list[ShareCandidateItem]
    granted_ids: list[int]


class ReplaceSharesRequest(BaseModel):
    """Full recipient set. Unchecked people are removed."""

    user_ids: list[int] = Field(default_factory=list, max_length=100)


class LeaveEditLeaseRequest(BaseModel):
    """Drop this page from the edit queue. The SSE stream is what joins."""

    tab_id: str
    epoch: int = Field(..., ge=1, le=9_007_199_254_740_991)


def _display_name(user: User) -> str:
    name = (getattr(user, "name", None) or "").strip()
    if name:
        return name[:80]
    return f"User {user.id}"


async def _invalidate_lists(user_ids: set[int]) -> None:
    cache = get_diagram_cache()
    for user_id in user_ids:
        await cache.invalidate_user_list(user_id)


def _require_tab_id(tab_id: str) -> str:
    cleaned = tab_id.strip()
    if not _TAB_ID_RE.fullmatch(cleaned):
        raise HTTPException(status_code=400, detail="Invalid tab id")
    return cleaned


@router.get("/diagrams/{diagram_id}/share-candidates", response_model=ShareCandidatesResponse)
async def list_share_candidates(
    diagram_id: str,
    request: Request,
    q: str = Query("", max_length=100),
    current_user: User = Depends(get_current_user),
) -> ShareCandidatesResponse:
    """Same-organization people, marked when they already have this diagram."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagram_shares", identifier, max_requests=60, window_seconds=60)
    org_id = getattr(current_user, "organization_id", None)
    if org_id is None:
        raise HTTPException(status_code=400, detail="Sharing requires an organization")
    granted = await current_grantee_ids(current_user, diagram_id)
    if granted is None:
        raise HTTPException(status_code=404, detail="Diagram not found")
    async with user_rls_session(int(current_user.id), org_id) as db:
        page = await fetch_org_members_page(db, int(org_id), q=q, limit=50, offset=0)
    items = [
        ShareCandidateItem(
            id=int(member.id),
            name=member.name,
            already_shared=int(member.id) in granted,
        )
        for member in page.items
        if int(member.id) != int(current_user.id)
    ]
    return ShareCandidatesResponse(items=items, granted_ids=sorted(granted))


@router.put("/diagrams/{diagram_id}/shares")
async def put_diagram_shares(
    diagram_id: str,
    body: ReplaceSharesRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    """Replace who has this diagram in their library."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagram_shares", identifier, max_requests=30, window_seconds=60)
    ok, error, affected = await replace_share_set(current_user, diagram_id, body.user_ids)
    if not ok:
        if error == "missing":
            raise HTTPException(status_code=404, detail="Diagram not found")
        if error == "no_org":
            raise HTTPException(status_code=400, detail="Sharing requires an organization")
        if error == "not_in_org":
            raise HTTPException(status_code=400, detail="Recipients must belong to your organization")
        raise HTTPException(status_code=400, detail="Failed to update shares")
    affected.add(int(current_user.id))
    await _invalidate_lists(affected)
    return {"success": True}


@router.delete("/diagrams/{diagram_id}/shares/me")
async def delete_my_diagram_share(
    diagram_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, bool]:
    """Remove this diagram from the caller's library only."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagram_shares", identifier, max_requests=30, window_seconds=60)
    access = await library_access(int(current_user.id), diagram_id)
    removed = await leave_share(int(current_user.id), diagram_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Diagram not found")
    ids = {int(current_user.id)}
    if access.owner_user_id is not None:
        ids.add(access.owner_user_id)
    await _invalidate_lists(ids)
    logger.info(
        "[DiagramShare] Share left diagram=%s user=%s owner=%s",
        diagram_id,
        current_user.id,
        access.owner_user_id,
    )
    return {"success": True}


@router.post("/diagrams/{diagram_id}/edit-lease")
async def post_edit_lease(
    diagram_id: str,
    body: LeaveEditLeaseRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict[str, bool]:
    """Drop this page from the edit queue. The open event stream is what joins."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagram_shares", identifier, max_requests=30, window_seconds=60)
    await leave_lease(diagram_id, int(current_user.id), _require_tab_id(body.tab_id), body.epoch)
    return {"success": True}


@router.get("/diagrams/{diagram_id}/share-events")
async def get_diagram_share_events(
    diagram_id: str,
    request: Request,
    tab_id: str = Query(..., min_length=8, max_length=64),
    epoch: int = Query(..., ge=1, le=9_007_199_254_740_991),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Hold this tab's edit slot until the browser closes the response."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagram_share_events", identifier, max_requests=60, window_seconds=60)
    return StreamingResponse(
        iter_diagram_share_events(
            diagram_id,
            int(current_user.id),
            _require_tab_id(tab_id),
            epoch,
            _display_name(current_user),
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
