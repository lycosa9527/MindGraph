"""Diagram Storage API Router.

API endpoints for user diagram storage:
- POST /api/diagrams - Create new diagram
- GET /api/diagrams - List user's diagrams (paginated)
- GET /api/diagrams/{id} - Get specific diagram
- PUT /api/diagrams/{id} - Update diagram
- DELETE /api/diagrams/{id} - Soft delete diagram
- POST /api/diagrams/{id}/duplicate - Duplicate diagram
- POST /api/diagrams/{id}/pin - Pin/unpin diagram to top

Rate limited: 100 requests per minute per user.
Max diagrams per user: 20 (configurable via DIAGRAM_MAX_PER_USER).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import UTC, datetime

import io
import json
import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request
from fastapi.responses import Response
import qrcode
from qrcode import constants as qrcode_constants
from PIL import Image
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import AsyncSessionLocal, get_async_db
from models.domain.auth import User
from models.domain.diagram_snapshots import DiagramSnapshot
from models.domain.diagrams import Diagram
from models.requests.requests_diagram import (
    DiagramCreateRequest,
    DiagramUpdateRequest,
    SnapshotTakeRequest,
    WorkshopJoinOrganizationRequest,
    WorkshopStartRequest,
)
from models.responses import (
    DiagramListItem,
    DiagramListResponse,
    DiagramResponse,
    SnapshotListResponse,
    SnapshotMetadata,
    SnapshotRecallResponse,
)
from services.redis.cache._redis_diagram_cache_helpers import MAX_SPEC_SIZE_KB
from services.online_collab.core.online_collab_manager import (
    get_online_collab_manager,
)
from services.online_collab.lifecycle.online_collab_expiry import is_online_collab_expired
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from utils.auth import get_current_user

from .helpers import (
    check_endpoint_rate_limit,
    get_rate_limit_identifier,
    log_diagram_edit,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["diagrams"])


async def _get_diagram_as_org_workshop_participant(
    diagram_id: str,
    requesting_org_id: Optional[int],
) -> Optional[dict]:
    """
    Return raw diagram data dict for a participant accessing via an active org
    workshop session.  Returns ``None`` if no matching active org session exists
    or the requester's org does not match the diagram owner's org.

    This supplements ``cache.get_diagram(user_id, diagram_id)`` which only
    returns diagrams owned by the requesting user.  Org participants need read
    access to diagrams they don't own so their CanvasPage can bootstrap before
    the WS snapshot arrives.
    """
    if not requesting_org_id:
        return None
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Diagram, User)
                .join(User, User.id == Diagram.user_id)
                .where(
                    Diagram.id == diagram_id,
                    ~Diagram.is_deleted,
                    Diagram.workshop_code.isnot(None),
                    or_(
                        Diagram.workshop_expires_at.is_(None),
                        Diagram.workshop_expires_at > datetime.now(UTC),
                    ),
                    or_(
                        Diagram.workshop_visibility.is_(None),
                        Diagram.workshop_visibility == "organization",
                    ),
                    User.organization_id == requesting_org_id,
                )
            )
            row = result.first()
            if row is None:
                return None
            d, _ = row
            if is_online_collab_expired(d.workshop_expires_at):
                return None
            raw_spec = getattr(d, "spec", None)
            if isinstance(raw_spec, dict):
                spec: dict = raw_spec
            elif isinstance(raw_spec, str):
                try:
                    spec = json.loads(raw_spec)
                except (ValueError, TypeError):
                    spec = {}
            else:
                spec = {}
            created_at_val = getattr(d, "created_at", None)
            updated_at_val = getattr(d, "updated_at", None)
            return {
                "id": d.id,
                "user_id": d.user_id,
                "title": d.title,
                "diagram_type": d.diagram_type,
                "spec": spec,
                "language": getattr(d, "language", "zh"),
                "thumbnail": getattr(d, "thumbnail", None),
                "created_at": created_at_val.isoformat() if created_at_val else None,
                "updated_at": updated_at_val.isoformat() if updated_at_val else None,
                "is_deleted": False,
            }
    except SQLAlchemyError as exc:
        logger.warning(
            "[Diagrams] org-participant fallback query failed diagram_id=%s: %s",
            diagram_id, exc,
        )
        return None


async def _diagram_spec_with_live_collab_overlay(
    diagram_id: str,
    spec: dict,
) -> dict:
    """When a workshop is active, prefer authoritative Redis live_spec for responses."""
    active_code = await get_online_collab_manager().get_active_online_collab_code_for_diagram(
        diagram_id,
    )
    if not active_code:
        return spec
    from services.redis.redis_async_client import get_async_redis  # pylint: disable=import-outside-toplevel
    from services.online_collab.spec.online_collab_live_spec import (  # pylint: disable=import-outside-toplevel
        read_live_spec,
        spec_for_snapshot,
    )

    redis_client = get_async_redis()
    if not redis_client:
        return spec
    try:
        live_doc = await read_live_spec(redis_client, active_code)
        if live_doc:
            return spec_for_snapshot(live_doc)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "[Diagrams] live spec overlay failed diagram_id=%s: %s",
            diagram_id,
            exc,
        )
    return spec


@router.post("/diagrams", response_model=DiagramResponse)
async def create_diagram(
    req: DiagramCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Create a new diagram.

    Rate limited: 100 requests per minute per user.
    Max diagrams per user: 20.
    """
    # Rate limiting
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagrams", identifier, max_requests=100, window_seconds=60)

    cache = get_diagram_cache()

    success, diagram_id, error = await cache.save_diagram(
        user_id=current_user.id,
        diagram_id=None,  # New diagram
        title=req.title,
        diagram_type=req.diagram_type,
        spec=req.spec,
        language=req.language,
        thumbnail=req.thumbnail,
    )

    if not success:
        if "limit reached" in (error or "").lower():
            raise HTTPException(status_code=403, detail=error)
        raise HTTPException(status_code=400, detail=error or "Failed to create diagram")

    # Get the created diagram
    if not diagram_id:
        raise HTTPException(status_code=500, detail="Diagram created but ID is missing")
    diagram = await cache.get_diagram(current_user.id, diagram_id)
    if not diagram:
        raise HTTPException(status_code=500, detail="Diagram created but failed to retrieve")

    logger.info("[Diagrams] Created diagram %s for user %s", diagram_id, current_user.id)

    return DiagramResponse(
        id=diagram["id"],
        title=diagram["title"],
        diagram_type=diagram["diagram_type"],
        spec=diagram["spec"],
        language=diagram.get("language", "zh"),
        thumbnail=diagram.get("thumbnail"),
        created_at=datetime.fromisoformat(diagram["created_at"]) if diagram.get("created_at") else datetime.now(UTC),
        updated_at=datetime.fromisoformat(diagram["updated_at"]) if diagram.get("updated_at") else datetime.now(UTC),
    )


@router.get("/diagrams", response_model=DiagramListResponse)
async def list_diagrams(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=50, description="Items per page"),
    current_user: User = Depends(get_current_user),
):
    """
    List user's diagrams with pagination.

    Rate limited: 100 requests per minute per user.
    """
    # Rate limiting
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagrams", identifier, max_requests=100, window_seconds=60)

    cache = get_diagram_cache()
    result = await cache.list_diagrams(current_user.id, page, page_size)

    # Convert to response models
    items = []
    for d in result["diagrams"]:
        ws_code = d.get("workshop_code")
        ws_expires_raw = d.get("workshop_expires_at")
        ws_expires = None
        if ws_expires_raw:
            try:
                ws_expires = datetime.fromisoformat(ws_expires_raw)
            except (ValueError, TypeError):
                ws_expires = None
        workshop_active = bool(ws_code) and not (
            ws_expires and is_online_collab_expired(ws_expires)
        )
        items.append(
            DiagramListItem(
                id=d["id"],
                title=d["title"],
                diagram_type=d["diagram_type"],
                thumbnail=d.get("thumbnail"),
                updated_at=datetime.fromisoformat(d["updated_at"]) if d.get("updated_at") else datetime.now(UTC),
                is_pinned=d.get("is_pinned", False),
                workshop_active=workshop_active,
            )
        )

    return DiagramListResponse(
        diagrams=items,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        has_more=result["has_more"],
        max_diagrams=result["max_diagrams"],
    )


@router.get("/diagrams/{diagram_id}", response_model=DiagramResponse)
async def get_diagram(
    diagram_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific diagram by ID.

    Rate limited: 100 requests per minute per user.
    During an active collab session the live Redis spec is returned so the
    caller always sees the current collaborative state.
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagrams", identifier, max_requests=100, window_seconds=60)

    cache = get_diagram_cache()
    diagram = await cache.get_diagram(current_user.id, diagram_id)

    if not diagram:
        # Ownership check failed.  Allow read access when the diagram is locked
        # inside an active org workshop and the requester belongs to the same org
        # as the diagram owner.  This covers participants who navigate to the
        # canvas URL directly (e.g. after a page reload) before the WebSocket
        # snapshot arrives.
        diagram = await _get_diagram_as_org_workshop_participant(
            diagram_id,
            getattr(current_user, "organization_id", None),
        )

    if not diagram:
        raise HTTPException(status_code=404, detail="Diagram not found")

    spec = diagram["spec"]
    spec = await _diagram_spec_with_live_collab_overlay(diagram_id, spec)

    return DiagramResponse(
        id=diagram["id"],
        title=diagram["title"],
        diagram_type=diagram["diagram_type"],
        spec=spec,
        language=diagram.get("language", "zh"),
        thumbnail=diagram.get("thumbnail"),
        created_at=datetime.fromisoformat(diagram["created_at"]) if diagram.get("created_at") else datetime.now(UTC),
        updated_at=datetime.fromisoformat(diagram["updated_at"]) if diagram.get("updated_at") else datetime.now(UTC),
    )


@router.put("/diagrams/{diagram_id}", response_model=DiagramResponse)
async def update_diagram(
    diagram_id: str,
    req: DiagramUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update an existing diagram.

    Rate limited: 100 requests per minute per user.
    Spec updates are blocked while a live collab session is active to prevent
    silent overwrites of collaborative changes in Redis.
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagrams", identifier, max_requests=100, window_seconds=60)

    active_code = await get_online_collab_manager().get_active_online_collab_code_for_diagram(diagram_id)
    if req.spec is not None:
        if active_code:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Diagram is in a live collaboration session — "
                    "changes must be made through the collaboration interface."
                ),
            )

    cache = get_diagram_cache()

    existing = await cache.get_diagram(current_user.id, diagram_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Diagram not found")

    title = req.title if req.title is not None else existing["title"]
    thumbnail = req.thumbnail if req.thumbnail is not None else existing.get("thumbnail")

    if active_code and req.spec is None:
        success, error = await cache.update_diagram_meta_only(
            user_id=current_user.id,
            diagram_id=diagram_id,
            title=title,
            thumbnail=thumbnail,
        )
        if not success:
            raise HTTPException(status_code=400, detail=error or "Failed to update diagram")
    else:
        spec = req.spec if req.spec is not None else existing["spec"]
        success, _, error = await cache.save_diagram(
            user_id=current_user.id,
            diagram_id=diagram_id,
            title=title,
            diagram_type=existing["diagram_type"],
            spec=spec,
            language=existing.get("language", "zh"),
            thumbnail=thumbnail,
        )

        if not success:
            raise HTTPException(status_code=400, detail=error or "Failed to update diagram")

    diagram = await cache.get_diagram(current_user.id, diagram_id)
    if not diagram:
        raise HTTPException(status_code=500, detail="Diagram updated but failed to retrieve")

    logger.info("[Diagrams] Updated diagram %s for user %s", diagram_id, current_user.id)

    edit_count = getattr(req, "edit_count", None)
    await log_diagram_edit(current_user, db, count=edit_count if edit_count else 1)

    overlay_spec = await _diagram_spec_with_live_collab_overlay(
        diagram_id, diagram["spec"],
    )

    return DiagramResponse(
        id=diagram["id"],
        title=diagram["title"],
        diagram_type=diagram["diagram_type"],
        spec=overlay_spec,
        language=diagram.get("language", "zh"),
        thumbnail=diagram.get("thumbnail"),
        created_at=datetime.fromisoformat(diagram["created_at"]) if diagram.get("created_at") else datetime.now(UTC),
        updated_at=datetime.fromisoformat(diagram["updated_at"]) if diagram.get("updated_at") else datetime.now(UTC),
    )


@router.delete("/diagrams/{diagram_id}")
async def delete_diagram(
    diagram_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Soft delete a diagram.

    Rate limited: 100 requests per minute per user.
    Deletion is blocked while a live collab session is active; the caller must
    stop the workshop first to avoid orphaning Redis state and confusing peers.
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagrams", identifier, max_requests=100, window_seconds=60)

    active_code = await get_online_collab_manager().get_active_online_collab_code_for_diagram(diagram_id)
    if active_code:
        raise HTTPException(
            status_code=409,
            detail=(
                "Diagram is in a live collaboration session — "
                "stop the workshop before deleting."
            ),
        )

    cache = get_diagram_cache()
    success, error = await cache.delete_diagram(current_user.id, diagram_id)

    if not success:
        if "not found" in (error or "").lower():
            raise HTTPException(status_code=404, detail=error)
        raise HTTPException(status_code=400, detail=error or "Failed to delete diagram")

    logger.info("[Diagrams] Deleted diagram %s for user %s", diagram_id, current_user.id)

    return {"success": True, "message": "Diagram deleted"}


@router.post("/diagrams/{diagram_id}/duplicate", response_model=DiagramResponse)
async def duplicate_diagram(
    diagram_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Duplicate an existing diagram.

    Rate limited: 100 requests per minute per user.
    Max diagrams per user: 20.
    """
    # Rate limiting
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagrams", identifier, max_requests=100, window_seconds=60)

    cache = get_diagram_cache()
    success, new_id, error = await cache.duplicate_diagram(current_user.id, diagram_id)

    if not success:
        if "limit reached" in (error or "").lower():
            raise HTTPException(status_code=403, detail=error)
        if "not found" in (error or "").lower():
            raise HTTPException(status_code=404, detail=error)
        raise HTTPException(status_code=400, detail=error or "Failed to duplicate diagram")

    # Get the new diagram
    if not new_id:
        raise HTTPException(status_code=500, detail="Diagram duplicated but ID is missing")
    diagram = await cache.get_diagram(current_user.id, new_id)
    if not diagram:
        raise HTTPException(status_code=500, detail="Diagram duplicated but failed to retrieve")

    logger.info(
        "[Diagrams] Duplicated diagram %s to %s for user %s",
        diagram_id,
        new_id,
        current_user.id,
    )

    return DiagramResponse(
        id=diagram["id"],
        title=diagram["title"],
        diagram_type=diagram["diagram_type"],
        spec=diagram["spec"],
        language=diagram.get("language", "zh"),
        thumbnail=diagram.get("thumbnail"),
        created_at=datetime.fromisoformat(diagram["created_at"]) if diagram.get("created_at") else datetime.now(UTC),
        updated_at=datetime.fromisoformat(diagram["updated_at"]) if diagram.get("updated_at") else datetime.now(UTC),
    )


@router.post("/diagrams/{diagram_id}/pin")
async def pin_diagram(
    diagram_id: str,
    request: Request,
    pinned: bool = Query(True, description="True to pin, False to unpin"),
    current_user: User = Depends(get_current_user),
):
    """
    Pin or unpin a diagram to appear at the top of the list.

    Rate limited: 100 requests per minute per user.
    """
    # Rate limiting
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagrams", identifier, max_requests=100, window_seconds=60)

    cache = get_diagram_cache()
    success, error = await cache.pin_diagram(current_user.id, diagram_id, pinned)

    if not success:
        if "not found" in (error or "").lower():
            raise HTTPException(status_code=404, detail=error)
        raise HTTPException(status_code=400, detail=error or "Failed to pin diagram")

    action = "Pinned" if pinned else "Unpinned"
    logger.info("[Diagrams] %s diagram %s for user %s", action, diagram_id, current_user.id)

    return {
        "success": True,
        "message": f"Diagram {action.lower()}",
        "is_pinned": pinned,
    }


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
        raise HTTPException(status_code=404, detail="Presentation mode not found or not authorized")

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


@router.get("/qrcode")
async def generate_qrcode(
    data: str = Query(..., description="Data to encode in QR code"),
    size: int = Query(150, ge=50, le=500, description="QR code size in pixels"),
):
    """
    Generate a QR code image from text data.

    Returns PNG image of the QR code.
    No authentication required - QR codes are public data.
    """
    try:
        # Create QR code instance
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode_constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        # Create image
        qr_img = qr.make_image(fill_color="black", back_color="white")

        # Convert to bytes first, then reload as PIL Image for proper type handling
        temp_bytes = io.BytesIO()
        qr_img.save(temp_bytes, "PNG")
        temp_bytes.seek(0)
        img = Image.open(temp_bytes)

        # Resize to requested size
        if size != 150:  # Default size is 150x150
            img = img.resize((size, size), resample=Image.Resampling.LANCZOS)

        # Convert to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, "PNG")
        img_bytes.seek(0)

        return Response(
            content=img_bytes.getvalue(),
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
            },
        )
    except Exception as e:
        logger.error("[Diagrams] Error generating QR code: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate QR code") from e


# ============================================================================
# DIAGRAM SNAPSHOT ENDPOINTS
# ============================================================================

_SNAPSHOT_MAX = 10


async def _diagram_visible_in_cache(user_id: int, diagram_id: str) -> bool:
    """Return True if GET /diagrams/{id} would succeed (Redis diagram cache)."""
    cache = get_diagram_cache()
    cached = await cache.get_diagram(user_id, diagram_id)
    return cached is not None


@router.post("/diagrams/{diagram_id}/snapshots", response_model=SnapshotMetadata)
async def take_snapshot(
    diagram_id: str,
    req: SnapshotTakeRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """
    Take a snapshot of the current diagram spec.

    Stores an immutable copy of the diagram content (without LLM results).
    Max 10 snapshots per diagram; the oldest is removed and the remaining
    versions are renumbered when the limit is reached.
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagram_snapshots", identifier, max_requests=60, window_seconds=60)

    if not await _diagram_visible_in_cache(current_user.id, diagram_id):
        raise HTTPException(status_code=404, detail="Diagram not found")

    result = await db.execute(
        select(Diagram).where(Diagram.id == diagram_id, Diagram.user_id == current_user.id, ~Diagram.is_deleted)
    )
    diagram = result.scalar_one_or_none()
    if not diagram:
        raise HTTPException(
            status_code=409,
            detail=("Snapshot storage needs the diagram saved to the database. Save the diagram, then try again."),
        )

    spec = {k: v for k, v in req.spec.items() if k != "llm_results"}

    spec_size_kb = len(json.dumps(spec).encode()) / 1024
    if spec_size_kb > MAX_SPEC_SIZE_KB:
        raise HTTPException(
            status_code=413,
            detail=(f"Snapshot spec too large ({spec_size_kb:.1f} KB > {MAX_SPEC_SIZE_KB} KB)"),
        )

    existing_result = await db.execute(
        select(DiagramSnapshot)
        .where(DiagramSnapshot.diagram_id == diagram_id, DiagramSnapshot.user_id == current_user.id)
        .order_by(DiagramSnapshot.version_number.asc())
    )
    existing = existing_result.scalars().all()

    if len(existing) >= _SNAPSHOT_MAX:
        oldest = existing[0]
        await db.delete(oldest)
        await db.flush()
        for snap in existing[1:]:
            snap.version_number -= 1
        await db.flush()
        new_version = _SNAPSHOT_MAX
    else:
        new_version = len(existing) + 1

    snapshot = DiagramSnapshot(
        diagram_id=diagram_id,
        user_id=current_user.id,
        version_number=new_version,
        spec=spec,
    )
    db.add(snapshot)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        logger.warning(
            "[Snapshots] Concurrent snapshot conflict for diagram %s user %s",
            diagram_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=409,
            detail="Another snapshot was taken at the same time. Please try again.",
        ) from None
    await db.refresh(snapshot)

    logger.info(
        "[Snapshots] User %s took snapshot v%d for diagram %s",
        current_user.id,
        new_version,
        diagram_id,
    )
    return SnapshotMetadata(
        id=snapshot.id,
        version_number=snapshot.version_number,
        created_at=snapshot.created_at,
    )


@router.get("/diagrams/{diagram_id}/snapshots", response_model=SnapshotListResponse)
async def list_snapshots(
    diagram_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all snapshots for a diagram (metadata only, no spec).

    Returns snapshots ordered by version_number ascending (oldest first).
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagram_snapshots", identifier, max_requests=60, window_seconds=60)

    if not await _diagram_visible_in_cache(current_user.id, diagram_id):
        raise HTTPException(status_code=404, detail="Diagram not found")

    result = await db.execute(
        select(DiagramSnapshot)
        .where(DiagramSnapshot.diagram_id == diagram_id, DiagramSnapshot.user_id == current_user.id)
        .order_by(DiagramSnapshot.version_number.asc())
    )
    rows = result.scalars().all()
    return SnapshotListResponse(
        snapshots=[
            SnapshotMetadata(
                id=r.id,
                version_number=r.version_number,
                created_at=r.created_at,
            )
            for r in rows
        ]
    )


@router.delete(
    "/diagrams/{diagram_id}/snapshots/{version_number}",
    response_model=SnapshotListResponse,
)
async def delete_snapshot(
    diagram_id: str,
    request: Request,
    version_number: int = Path(..., ge=1, le=10),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a specific snapshot and renumber remaining versions gap-free.

    Returns the updated snapshot list so the frontend can refresh badges
    without an extra round-trip.
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagram_snapshots", identifier, max_requests=60, window_seconds=60)

    if not await _diagram_visible_in_cache(current_user.id, diagram_id):
        raise HTTPException(status_code=404, detail="Diagram not found")

    snap_result = await db.execute(
        select(DiagramSnapshot).where(
            DiagramSnapshot.diagram_id == diagram_id,
            DiagramSnapshot.version_number == version_number,
            DiagramSnapshot.user_id == current_user.id,
        )
    )
    snapshot = snap_result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    await db.delete(snapshot)
    await db.flush()

    remaining_result = await db.execute(
        select(DiagramSnapshot)
        .where(DiagramSnapshot.diagram_id == diagram_id, DiagramSnapshot.user_id == current_user.id)
        .order_by(DiagramSnapshot.version_number.asc())
    )
    remaining = remaining_result.scalars().all()
    for idx, snap in enumerate(remaining, start=1):
        if snap.version_number != idx:
            snap.version_number = idx
    await db.commit()

    logger.info(
        "[Snapshots] User %s deleted snapshot v%d for diagram %s (%d remaining)",
        current_user.id,
        version_number,
        diagram_id,
        len(remaining),
    )
    return SnapshotListResponse(
        snapshots=[
            SnapshotMetadata(
                id=s.id,
                version_number=s.version_number,
                created_at=s.created_at,
            )
            for s in remaining
        ]
    )


@router.post(
    "/diagrams/{diagram_id}/snapshots/{version_number}/recall",
    response_model=SnapshotRecallResponse,
)
async def recall_snapshot(
    diagram_id: str,
    request: Request,
    version_number: int = Path(..., ge=1, le=10),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the full spec for a specific snapshot version.

    The caller is responsible for loading the returned spec into the canvas.
    This endpoint does not modify the diagram or its snapshots.
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagram_snapshots", identifier, max_requests=60, window_seconds=60)

    if not await _diagram_visible_in_cache(current_user.id, diagram_id):
        raise HTTPException(status_code=404, detail="Diagram not found")

    snap_result = await db.execute(
        select(DiagramSnapshot).where(
            DiagramSnapshot.diagram_id == diagram_id,
            DiagramSnapshot.version_number == version_number,
            DiagramSnapshot.user_id == current_user.id,
        )
    )
    snapshot = snap_result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    logger.info(
        "[Snapshots] User %s recalled snapshot v%d for diagram %s",
        current_user.id,
        version_number,
        diagram_id,
    )
    return SnapshotRecallResponse(
        version_number=snapshot.version_number,
        spec=snapshot.spec,
    )
