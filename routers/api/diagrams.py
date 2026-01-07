"""
Diagram Storage API Router
===========================

API endpoints for user diagram storage:
- POST /api/diagrams - Create new diagram
- GET /api/diagrams - List user's diagrams (paginated)
- GET /api/diagrams/{id} - Get specific diagram
- PUT /api/diagrams/{id} - Update diagram
- DELETE /api/diagrams/{id} - Soft delete diagram
- POST /api/diagrams/{id}/duplicate - Duplicate diagram

Rate limited: 100 requests per minute per user.
Max diagrams per user: 10 (configurable via DIAGRAM_MAX_PER_USER).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from models.auth import User
from models.requests import DiagramCreateRequest, DiagramUpdateRequest
from models.responses import DiagramResponse, DiagramListResponse, DiagramListItem
from utils.auth import get_current_user
from services.redis_diagram_cache import get_diagram_cache
from .helpers import get_rate_limit_identifier, check_endpoint_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["diagrams"])


@router.post('/diagrams', response_model=DiagramResponse)
async def create_diagram(
    req: DiagramCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new diagram.
    
    Rate limited: 100 requests per minute per user.
    Max diagrams per user: 10.
    """
    # Rate limiting
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit('diagrams', identifier, max_requests=100, window_seconds=60)
    
    cache = get_diagram_cache()
    
    success, diagram_id, error = await cache.save_diagram(
        user_id=current_user.id,
        diagram_id=None,  # New diagram
        title=req.title,
        diagram_type=req.diagram_type,
        spec=req.spec,
        language=req.language,
        thumbnail=req.thumbnail
    )
    
    if not success:
        if "limit reached" in (error or "").lower():
            raise HTTPException(status_code=403, detail=error)
        raise HTTPException(status_code=400, detail=error or "Failed to create diagram")
    
    # Get the created diagram
    diagram = await cache.get_diagram(current_user.id, diagram_id)
    if not diagram:
        raise HTTPException(status_code=500, detail="Diagram created but failed to retrieve")
    
    logger.info(f"[Diagrams] Created diagram {diagram_id} for user {current_user.id}")
    
    return DiagramResponse(
        id=diagram['id'],
        title=diagram['title'],
        diagram_type=diagram['diagram_type'],
        spec=diagram['spec'],
        language=diagram.get('language', 'zh'),
        thumbnail=diagram.get('thumbnail'),
        created_at=datetime.fromisoformat(diagram['created_at']) if diagram.get('created_at') else datetime.utcnow(),
        updated_at=datetime.fromisoformat(diagram['updated_at']) if diagram.get('updated_at') else datetime.utcnow()
    )


@router.get('/diagrams', response_model=DiagramListResponse)
async def list_diagrams(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=50, description="Items per page"),
    current_user: User = Depends(get_current_user)
):
    """
    List user's diagrams with pagination.
    
    Rate limited: 100 requests per minute per user.
    """
    # Rate limiting
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit('diagrams', identifier, max_requests=100, window_seconds=60)
    
    cache = get_diagram_cache()
    result = await cache.list_diagrams(current_user.id, page, page_size)
    
    # Convert to response models
    items = []
    for d in result['diagrams']:
        items.append(DiagramListItem(
            id=d['id'],
            title=d['title'],
            diagram_type=d['diagram_type'],
            thumbnail=d.get('thumbnail'),
            updated_at=datetime.fromisoformat(d['updated_at']) if d.get('updated_at') else datetime.utcnow()
        ))
    
    return DiagramListResponse(
        diagrams=items,
        total=result['total'],
        page=result['page'],
        page_size=result['page_size'],
        has_more=result['has_more'],
        max_diagrams=result['max_diagrams']
    )


@router.get('/diagrams/{diagram_id}', response_model=DiagramResponse)
async def get_diagram(
    diagram_id: int,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific diagram by ID.
    
    Rate limited: 100 requests per minute per user.
    """
    # Rate limiting
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit('diagrams', identifier, max_requests=100, window_seconds=60)
    
    cache = get_diagram_cache()
    diagram = await cache.get_diagram(current_user.id, diagram_id)
    
    if not diagram:
        raise HTTPException(status_code=404, detail="Diagram not found")
    
    return DiagramResponse(
        id=diagram['id'],
        title=diagram['title'],
        diagram_type=diagram['diagram_type'],
        spec=diagram['spec'],
        language=diagram.get('language', 'zh'),
        thumbnail=diagram.get('thumbnail'),
        created_at=datetime.fromisoformat(diagram['created_at']) if diagram.get('created_at') else datetime.utcnow(),
        updated_at=datetime.fromisoformat(diagram['updated_at']) if diagram.get('updated_at') else datetime.utcnow()
    )


@router.put('/diagrams/{diagram_id}', response_model=DiagramResponse)
async def update_diagram(
    diagram_id: int,
    req: DiagramUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing diagram.
    
    Rate limited: 100 requests per minute per user.
    """
    # Rate limiting
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit('diagrams', identifier, max_requests=100, window_seconds=60)
    
    cache = get_diagram_cache()
    
    # Get existing diagram
    existing = await cache.get_diagram(current_user.id, diagram_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Diagram not found")
    
    # Merge updates
    title = req.title if req.title is not None else existing['title']
    spec = req.spec if req.spec is not None else existing['spec']
    thumbnail = req.thumbnail if req.thumbnail is not None else existing.get('thumbnail')
    
    success, _, error = await cache.save_diagram(
        user_id=current_user.id,
        diagram_id=diagram_id,
        title=title,
        diagram_type=existing['diagram_type'],  # Cannot change type
        spec=spec,
        language=existing.get('language', 'zh'),
        thumbnail=thumbnail
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=error or "Failed to update diagram")
    
    # Get updated diagram
    diagram = await cache.get_diagram(current_user.id, diagram_id)
    if not diagram:
        raise HTTPException(status_code=500, detail="Diagram updated but failed to retrieve")
    
    logger.info(f"[Diagrams] Updated diagram {diagram_id} for user {current_user.id}")
    
    return DiagramResponse(
        id=diagram['id'],
        title=diagram['title'],
        diagram_type=diagram['diagram_type'],
        spec=diagram['spec'],
        language=diagram.get('language', 'zh'),
        thumbnail=diagram.get('thumbnail'),
        created_at=datetime.fromisoformat(diagram['created_at']) if diagram.get('created_at') else datetime.utcnow(),
        updated_at=datetime.fromisoformat(diagram['updated_at']) if diagram.get('updated_at') else datetime.utcnow()
    )


@router.delete('/diagrams/{diagram_id}')
async def delete_diagram(
    diagram_id: int,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Soft delete a diagram.
    
    Rate limited: 100 requests per minute per user.
    """
    # Rate limiting
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit('diagrams', identifier, max_requests=100, window_seconds=60)
    
    cache = get_diagram_cache()
    success, error = await cache.delete_diagram(current_user.id, diagram_id)
    
    if not success:
        if "not found" in (error or "").lower():
            raise HTTPException(status_code=404, detail=error)
        raise HTTPException(status_code=400, detail=error or "Failed to delete diagram")
    
    logger.info(f"[Diagrams] Deleted diagram {diagram_id} for user {current_user.id}")
    
    return {"success": True, "message": "Diagram deleted"}


@router.post('/diagrams/{diagram_id}/duplicate', response_model=DiagramResponse)
async def duplicate_diagram(
    diagram_id: int,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Duplicate an existing diagram.
    
    Rate limited: 100 requests per minute per user.
    Max diagrams per user: 10.
    """
    # Rate limiting
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit('diagrams', identifier, max_requests=100, window_seconds=60)
    
    cache = get_diagram_cache()
    success, new_id, error = await cache.duplicate_diagram(current_user.id, diagram_id)
    
    if not success:
        if "limit reached" in (error or "").lower():
            raise HTTPException(status_code=403, detail=error)
        if "not found" in (error or "").lower():
            raise HTTPException(status_code=404, detail=error)
        raise HTTPException(status_code=400, detail=error or "Failed to duplicate diagram")
    
    # Get the new diagram
    diagram = await cache.get_diagram(current_user.id, new_id)
    if not diagram:
        raise HTTPException(status_code=500, detail="Diagram duplicated but failed to retrieve")
    
    logger.info(f"[Diagrams] Duplicated diagram {diagram_id} to {new_id} for user {current_user.id}")
    
    return DiagramResponse(
        id=diagram['id'],
        title=diagram['title'],
        diagram_type=diagram['diagram_type'],
        spec=diagram['spec'],
        language=diagram.get('language', 'zh'),
        thumbnail=diagram.get('thumbnail'),
        created_at=datetime.fromisoformat(diagram['created_at']) if diagram.get('created_at') else datetime.utcnow(),
        updated_at=datetime.fromisoformat(diagram['updated_at']) if diagram.get('updated_at') else datetime.utcnow()
    )
