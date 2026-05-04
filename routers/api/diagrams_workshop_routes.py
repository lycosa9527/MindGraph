"""Workshop-related diagram routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy import select

from config.database import AsyncSessionLocal
from models.domain.auth import User
from models.domain.diagrams import Diagram
from models.requests.requests_diagram import (
    WorkshopJoinOrganizationRequest,
    WorkshopStartRequest,
)
from services.online_collab.core.online_collab_manager import get_online_collab_manager
from utils.auth import get_current_user

from .helpers import check_endpoint_rate_limit, get_rate_limit_identifier

logger = logging.getLogger(__name__)

router = APIRouter(tags=["diagrams"])


async def _owner_has_active_workshop(diagram_id: str, user_id: int) -> bool:
    """True when this user owns the diagram and it still has a workshop code."""
    async with AsyncSessionLocal() as db:
        row = await db.execute(
            select(Diagram.workshop_code).where(
                Diagram.id == diagram_id,
                Diagram.user_id == user_id,
                ~Diagram.is_deleted,
            )
        )
        code = row.scalar_one_or_none()
        return bool(code and str(code).strip())


@router.post("/diagrams/{diagram_id}/workshop/start")
async def start_workshop(
    diagram_id: str,
    request: Request,
    body: Optional[WorkshopStartRequest] = Body(default=None),
    current_user: User = Depends(get_current_user),
):
    """
    Start presentation mode for a diagram (live collaborative editing).

    Generates a shareable code (xxx-xxx format) that others can use to join
    and edit the diagram collaboratively.

    Rate limited: 10 requests per minute per user.
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("workshop", identifier, max_requests=10, window_seconds=60)

    visibility = body.visibility if body else "organization"
    duration = body.duration if body else "today"
    target_org_id = body.org_id if body else None
    code, error_msg, expires_at, stopped_previous_sessions = (
        await get_online_collab_manager().start_online_collab(
            diagram_id, current_user.id, visibility, duration,
            target_org_id=target_org_id,
        )
    )

    if not code:
        raise HTTPException(status_code=400, detail=error_msg or "Failed to start presentation mode")

    logger.info(
        "[Diagrams] Started presentation mode %s for diagram %s (user %s)",
        code,
        diagram_id,
        current_user.id,
    )

    payload = {
        "success": True,
        "code": code,
        "message": "Presentation mode started",
        "duration": duration,
        "stopped_previous_sessions": stopped_previous_sessions,
    }
    if expires_at is not None:
        payload["expires_at"] = expires_at.isoformat() + "Z"
    return payload


@router.post("/diagrams/{diagram_id}/workshop/stop")
async def stop_workshop(
    diagram_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Stop presentation mode for a diagram.

    Only the diagram owner can stop the session. Succeeds with no workshop
    code on the row as well (idempotent after idle or zombie teardown).

    Rate limited: 10 requests per minute per user.
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("workshop", identifier, max_requests=10, window_seconds=60)

    success = await get_online_collab_manager().stop_online_collab(diagram_id, current_user.id)

    if not success:
        if await _owner_has_active_workshop(diagram_id, current_user.id):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Could not save the latest collaborative edits. "
                    "Please try again in a few seconds."
                ),
            )
        raise HTTPException(
            status_code=404,
            detail="Presentation mode not found or not authorized",
        )

    logger.info(
        "[Diagrams] Stopped presentation mode for diagram %s (user %s)",
        diagram_id,
        current_user.id,
    )

    return {
        "success": True,
        "message": "Presentation mode stopped",
    }


@router.get("/diagrams/{diagram_id}/workshop/status")
async def get_workshop_status(
    diagram_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Get presentation mode status for a diagram.

    Rate limited: 30 requests per minute per user.
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("workshop", identifier, max_requests=30, window_seconds=60)

    status, err = await get_online_collab_manager().get_online_collab_status(diagram_id, current_user.id)

    if err == "not_found" or status is None:
        raise HTTPException(status_code=404, detail="Diagram not found")
    if err == "forbidden":
        raise HTTPException(status_code=403, detail="Not allowed to view workshop status")

    return status


@router.post("/workshop/join")
async def join_workshop(
    request: Request,
    code: str = Query(..., description="Presentation code (xxx-xxx format)"),
    current_user: User = Depends(get_current_user),
):
    """
    Join presentation mode using a share code.

    Rate limited: 20 requests per minute per user.
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("workshop", identifier, max_requests=20, window_seconds=60)

    workshop_info = await get_online_collab_manager().join_online_collab(code, current_user.id)

    if not workshop_info:
        raise HTTPException(
            status_code=404,
            detail="Collaboration session ended or invalid code",
        )

    logger.info(
        "[Diagrams] User %s joined presentation mode %s (diagram %s)",
        current_user.id,
        code,
        workshop_info["diagram_id"],
    )

    return {
        "success": True,
        "workshop": workshop_info,
    }


@router.get("/workshop/organization/sessions")
async def list_organization_workshop_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    List active organization-scoped workshops for the same school (校内).
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("workshop", identifier, max_requests=30, window_seconds=60)

    sessions = await get_online_collab_manager().list_org_online_collab_sessions(current_user.id)
    return {"success": True, "sessions": sessions}


@router.post("/workshop/join-organization")
async def join_workshop_organization(
    request: Request,
    body: WorkshopJoinOrganizationRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Join a 校内 session by diagram id (no meeting code in the UI).
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("workshop", identifier, max_requests=20, window_seconds=60)

    workshop_info = await get_online_collab_manager().join_online_collab_by_diagram(body.diagram_id, current_user.id)

    if not workshop_info:
        raise HTTPException(
            status_code=404,
            detail="Collaboration session ended or unavailable organization workshop",
        )

    logger.info(
        "[Diagrams] User %s joined org workshop diagram %s",
        current_user.id,
        body.diagram_id,
    )

    return {
        "success": True,
        "workshop": workshop_info,
    }
