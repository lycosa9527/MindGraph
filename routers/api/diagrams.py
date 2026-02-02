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

from datetime import datetime
import io
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
import qrcode
from qrcode import constants as qrcode_constants
from PIL import Image

from models.domain.auth import User
from models.requests.requests_diagram import DiagramCreateRequest, DiagramUpdateRequest
from models.responses import DiagramListItem, DiagramListResponse, DiagramResponse
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from services.workshop import workshop_service
from utils.auth import get_current_user

from .helpers import check_endpoint_rate_limit, get_rate_limit_identifier

logger = logging.getLogger(__name__)

router = APIRouter(tags=["diagrams"])


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
    await check_endpoint_rate_limit(
        "diagrams", identifier, max_requests=100, window_seconds=60
    )

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
        raise HTTPException(
            status_code=500, detail="Diagram created but failed to retrieve"
        )

    logger.info(
        "[Diagrams] Created diagram %s for user %s", diagram_id, current_user.id
    )

    return DiagramResponse(
        id=diagram["id"],
        title=diagram["title"],
        diagram_type=diagram["diagram_type"],
        spec=diagram["spec"],
        language=diagram.get("language", "zh"),
        thumbnail=diagram.get("thumbnail"),
        created_at=datetime.fromisoformat(diagram["created_at"])
        if diagram.get("created_at")
        else datetime.utcnow(),
        updated_at=datetime.fromisoformat(diagram["updated_at"])
        if diagram.get("updated_at")
        else datetime.utcnow(),
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
    await check_endpoint_rate_limit(
        "diagrams", identifier, max_requests=100, window_seconds=60
    )

    cache = get_diagram_cache()
    result = await cache.list_diagrams(current_user.id, page, page_size)

    # Convert to response models
    items = []
    for d in result["diagrams"]:
        items.append(
            DiagramListItem(
                id=d["id"],
                title=d["title"],
                diagram_type=d["diagram_type"],
                thumbnail=d.get("thumbnail"),
                updated_at=datetime.fromisoformat(d["updated_at"])
                if d.get("updated_at")
                else datetime.utcnow(),
                is_pinned=d.get("is_pinned", False),
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
    """
    # Rate limiting
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "diagrams", identifier, max_requests=100, window_seconds=60
    )

    cache = get_diagram_cache()
    diagram = await cache.get_diagram(current_user.id, diagram_id)

    if not diagram:
        raise HTTPException(status_code=404, detail="Diagram not found")

    return DiagramResponse(
        id=diagram["id"],
        title=diagram["title"],
        diagram_type=diagram["diagram_type"],
        spec=diagram["spec"],
        language=diagram.get("language", "zh"),
        thumbnail=diagram.get("thumbnail"),
        created_at=datetime.fromisoformat(diagram["created_at"])
        if diagram.get("created_at")
        else datetime.utcnow(),
        updated_at=datetime.fromisoformat(diagram["updated_at"])
        if diagram.get("updated_at")
        else datetime.utcnow(),
    )


@router.put("/diagrams/{diagram_id}", response_model=DiagramResponse)
async def update_diagram(
    diagram_id: str,
    req: DiagramUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Update an existing diagram.

    Rate limited: 100 requests per minute per user.
    """
    # Rate limiting
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "diagrams", identifier, max_requests=100, window_seconds=60
    )

    cache = get_diagram_cache()

    # Get existing diagram
    existing = await cache.get_diagram(current_user.id, diagram_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Diagram not found")

    # Merge updates
    title = req.title if req.title is not None else existing["title"]
    spec = req.spec if req.spec is not None else existing["spec"]
    thumbnail = (
        req.thumbnail if req.thumbnail is not None else existing.get("thumbnail")
    )

    success, _, error = await cache.save_diagram(
        user_id=current_user.id,
        diagram_id=diagram_id,
        title=title,
        diagram_type=existing["diagram_type"],  # Cannot change type
        spec=spec,
        language=existing.get("language", "zh"),
        thumbnail=thumbnail,
    )

    if not success:
        raise HTTPException(status_code=400, detail=error or "Failed to update diagram")

    # Get updated diagram
    diagram = await cache.get_diagram(current_user.id, diagram_id)
    if not diagram:
        raise HTTPException(
            status_code=500, detail="Diagram updated but failed to retrieve"
        )

    logger.info(
        "[Diagrams] Updated diagram %s for user %s", diagram_id, current_user.id
    )

    return DiagramResponse(
        id=diagram["id"],
        title=diagram["title"],
        diagram_type=diagram["diagram_type"],
        spec=diagram["spec"],
        language=diagram.get("language", "zh"),
        thumbnail=diagram.get("thumbnail"),
        created_at=datetime.fromisoformat(diagram["created_at"])
        if diagram.get("created_at")
        else datetime.utcnow(),
        updated_at=datetime.fromisoformat(diagram["updated_at"])
        if diagram.get("updated_at")
        else datetime.utcnow(),
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
    """
    # Rate limiting
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "diagrams", identifier, max_requests=100, window_seconds=60
    )

    cache = get_diagram_cache()
    success, error = await cache.delete_diagram(current_user.id, diagram_id)

    if not success:
        if "not found" in (error or "").lower():
            raise HTTPException(status_code=404, detail=error)
        raise HTTPException(status_code=400, detail=error or "Failed to delete diagram")

    logger.info(
        "[Diagrams] Deleted diagram %s for user %s", diagram_id, current_user.id
    )

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
    await check_endpoint_rate_limit(
        "diagrams", identifier, max_requests=100, window_seconds=60
    )

    cache = get_diagram_cache()
    success, new_id, error = await cache.duplicate_diagram(current_user.id, diagram_id)

    if not success:
        if "limit reached" in (error or "").lower():
            raise HTTPException(status_code=403, detail=error)
        if "not found" in (error or "").lower():
            raise HTTPException(status_code=404, detail=error)
        raise HTTPException(
            status_code=400, detail=error or "Failed to duplicate diagram"
        )

    # Get the new diagram
    if not new_id:
        raise HTTPException(
            status_code=500, detail="Diagram duplicated but ID is missing"
        )
    diagram = await cache.get_diagram(current_user.id, new_id)
    if not diagram:
        raise HTTPException(
            status_code=500, detail="Diagram duplicated but failed to retrieve"
        )

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
        created_at=datetime.fromisoformat(diagram["created_at"])
        if diagram.get("created_at")
        else datetime.utcnow(),
        updated_at=datetime.fromisoformat(diagram["updated_at"])
        if diagram.get("updated_at")
        else datetime.utcnow(),
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
    await check_endpoint_rate_limit(
        "diagrams", identifier, max_requests=100, window_seconds=60
    )

    cache = get_diagram_cache()
    success, error = await cache.pin_diagram(current_user.id, diagram_id, pinned)

    if not success:
        if "not found" in (error or "").lower():
            raise HTTPException(status_code=404, detail=error)
        raise HTTPException(status_code=400, detail=error or "Failed to pin diagram")

    action = "Pinned" if pinned else "Unpinned"
    logger.info(
        "[Diagrams] %s diagram %s for user %s", action, diagram_id, current_user.id
    )

    return {
        "success": True,
        "message": f"Diagram {action.lower()}",
        "is_pinned": pinned,
    }


@router.post("/diagrams/{diagram_id}/workshop/start")
async def start_workshop(
    diagram_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Start a workshop session for a diagram.

    Generates a shareable code (xxx-xxx format) that others can use to join
    and edit the diagram collaboratively.

    Rate limited: 10 requests per minute per user.
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "workshop", identifier, max_requests=10, window_seconds=60
    )

    code, error_msg = await workshop_service.start_workshop(diagram_id, current_user.id)

    if not code:
        raise HTTPException(
            status_code=400, detail=error_msg or "Failed to start workshop session"
        )

    logger.info(
        "[Diagrams] Started workshop %s for diagram %s (user %s)",
        code,
        diagram_id,
        current_user.id,
    )

    return {
        "success": True,
        "code": code,
        "message": "Workshop session started",
    }


@router.post("/diagrams/{diagram_id}/workshop/stop")
async def stop_workshop(
    diagram_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Stop a workshop session for a diagram.

    Only the diagram owner can stop the workshop.

    Rate limited: 10 requests per minute per user.
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "workshop", identifier, max_requests=10, window_seconds=60
    )

    success = await workshop_service.stop_workshop(diagram_id, current_user.id)

    if not success:
        raise HTTPException(
            status_code=404, detail="Workshop session not found or not authorized"
        )

    logger.info(
        "[Diagrams] Stopped workshop for diagram %s (user %s)",
        diagram_id,
        current_user.id,
    )

    return {
        "success": True,
        "message": "Workshop session stopped",
    }


@router.get("/diagrams/{diagram_id}/workshop/status")
async def get_workshop_status(
    diagram_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Get workshop status for a diagram.

    Rate limited: 30 requests per minute per user.
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "workshop", identifier, max_requests=30, window_seconds=60
    )

    status = await workshop_service.get_workshop_status(
        diagram_id
    )

    if not status:
        raise HTTPException(status_code=404, detail="Diagram not found")

    return status


@router.post("/workshop/join")
async def join_workshop(
    code: str = Query(..., description="Workshop code (xxx-xxx format)"),
    request: Request = None,
    current_user: User = Depends(get_current_user),
):
    """
    Join a workshop session using a workshop code.

    Rate limited: 20 requests per minute per user.
    """
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "workshop", identifier, max_requests=20, window_seconds=60
    )

    workshop_info = await workshop_service.join_workshop(code, current_user.id)

    if not workshop_info:
        raise HTTPException(status_code=404, detail="Invalid workshop code")

    logger.info(
        "[Diagrams] User %s joined workshop %s (diagram %s)",
        current_user.id,
        code,
        workshop_info["diagram_id"],
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
