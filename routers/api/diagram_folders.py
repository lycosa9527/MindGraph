"""Diagram archive folder API routes."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.diagram_folders import DiagramFolder, generate_folder_uuid
from models.domain.diagrams import Diagram
from models.requests.requests_diagram import (
    DiagramFolderCreateRequest,
    DiagramFolderUpdateRequest,
)
from models.responses import DiagramFolderListResponse, DiagramFolderItem, DiagramFolderResponse
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from utils.auth import get_current_user
from utils.db.session_open import user_rls_session

from .helpers import check_endpoint_rate_limit, get_rate_limit_identifier

logger = logging.getLogger(__name__)

router = APIRouter(tags=["diagram-folders"])


def _folder_item(folder: DiagramFolder, diagram_count: int) -> DiagramFolderItem:
    return DiagramFolderItem(
        id=folder.id,
        name=folder.name,
        sort_order=folder.sort_order,
        diagram_count=diagram_count,
        created_at=folder.created_at or datetime.now(UTC),
        updated_at=folder.updated_at or datetime.now(UTC),
    )


@router.get("/diagram-folders", response_model=DiagramFolderListResponse)
async def list_diagram_folders(
    request: Request,
    current_user=Depends(get_current_user),
):
    """List the current user's diagram archive folders."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagram_folders", identifier, max_requests=100, window_seconds=60)

    try:
        async with user_rls_session(current_user.id) as db:
            count_expr = func.count(Diagram.id).filter(~Diagram.is_deleted)
            result = await db.execute(
                select(DiagramFolder, count_expr)
                .outerjoin(
                    Diagram,
                    (Diagram.folder_id == DiagramFolder.id) & (~Diagram.is_deleted),
                )
                .where(DiagramFolder.user_id == current_user.id)
                .group_by(DiagramFolder.id)
                .order_by(DiagramFolder.sort_order.asc(), DiagramFolder.created_at.asc())
            )
            rows = result.all()
    except SQLAlchemyError as exc:
        logger.error("[DiagramFolders] list failed user=%s: %s", current_user.id, exc)
        raise HTTPException(status_code=500, detail="Failed to list folders") from exc

    folders = [_folder_item(folder, int(count or 0)) for folder, count in rows]
    return DiagramFolderListResponse(folders=folders)


@router.post("/diagram-folders", response_model=DiagramFolderResponse)
async def create_diagram_folder(
    req: DiagramFolderCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    """Create a new diagram archive folder."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagram_folders", identifier, max_requests=60, window_seconds=60)

    max_sort = await db.scalar(
        select(func.max(DiagramFolder.sort_order)).where(DiagramFolder.user_id == current_user.id)
    )
    now = datetime.now(UTC)
    folder = DiagramFolder(
        id=generate_folder_uuid(),
        user_id=current_user.id,
        name=req.name.strip(),
        sort_order=(max_sort or 0) + 1,
        created_at=now,
        updated_at=now,
    )
    db.add(folder)
    try:
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("[DiagramFolders] create failed user=%s: %s", current_user.id, exc)
        raise HTTPException(status_code=500, detail="Failed to create folder") from exc
    await db.refresh(folder)

    logger.info("[DiagramFolders] Created folder %s for user %s", folder.id, current_user.id)
    return DiagramFolderResponse(
        id=folder.id,
        name=folder.name,
        sort_order=folder.sort_order,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


@router.patch("/diagram-folders/{folder_id}", response_model=DiagramFolderResponse)
async def update_diagram_folder(
    folder_id: str,
    req: DiagramFolderUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    """Rename a diagram archive folder."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagram_folders", identifier, max_requests=60, window_seconds=60)

    result = await db.execute(
        select(DiagramFolder).where(
            DiagramFolder.id == folder_id,
            DiagramFolder.user_id == current_user.id,
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    folder.name = req.name.strip()
    folder.updated_at = datetime.now(UTC)
    try:
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("[DiagramFolders] update failed folder=%s: %s", folder_id, exc)
        raise HTTPException(status_code=500, detail="Failed to update folder") from exc
    await db.refresh(folder)

    return DiagramFolderResponse(
        id=folder.id,
        name=folder.name,
        sort_order=folder.sort_order,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


@router.delete("/diagram-folders/{folder_id}")
async def delete_diagram_folder(
    folder_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    """Delete a folder; diagrams inside become uncategorized (folder_id SET NULL)."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("diagram_folders", identifier, max_requests=60, window_seconds=60)

    result = await db.execute(
        select(DiagramFolder).where(
            DiagramFolder.id == folder_id,
            DiagramFolder.user_id == current_user.id,
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    try:
        await db.delete(folder)
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("[DiagramFolders] delete failed folder=%s: %s", folder_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete folder") from exc

    cache = get_diagram_cache()
    await cache.invalidate_user_list(current_user.id)

    logger.info("[DiagramFolders] Deleted folder %s for user %s", folder_id, current_user.id)
    return {"success": True, "message": "Folder deleted"}
