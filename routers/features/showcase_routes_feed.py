"""Showcase routes: meta, listing, favorites, and post detail."""

from __future__ import annotations


from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.showcase import ShowcasePost
from routers.features.showcase_constants import (
    CASE_TYPES,
    DIAGRAM_TYPE_LABELS,
)
from routers.features.showcase_helpers import (
    post_id_from_showcase_filename,
    resolve_showcase_disk_path,
)
from routers.features.showcase_permissions import can_view_non_approved_post
from routers.features.showcase_routes_posts import list_posts
from services.showcase.field_options import load_meta_payload
from utils.auth import get_current_user

router = APIRouter()


@router.get("/assets/{asset_path:path}")
async def download_showcase_asset(
    asset_path: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Serve Showcase files with auth; non-approved posts are author/staff only."""
    normalized = asset_path.lstrip("/").replace("\\", "/")
    if not normalized.startswith("case_square/"):
        normalized = f"case_square/{normalized}"
    disk_path = resolve_showcase_disk_path(normalized)
    post_id = post_id_from_showcase_filename(disk_path.name)
    if not post_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    post = (await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if post.status != "approved" and not await can_view_non_approved_post(post, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return FileResponse(path=str(disk_path), filename=disk_path.name)


@router.get("/meta")
async def get_meta(
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Filter enums for the Showcase UI."""
    meta = await load_meta_payload(db)
    return {
        **meta,
        "diagram_types": sorted(DIAGRAM_TYPE_LABELS - {"mindmap"}),
        "case_types": sorted(CASE_TYPES),
    }


@router.get("/favorites")
async def list_favorite_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """List approved posts favorited by the current user."""
    return await list_posts(
        case_type=None,
        expert_recommended=False,
        subject=None,
        grade=None,
        diagram_type=None,
        publish_source=None,
        sort="newest",
        search=None,
        status_filter=None,
        mine=False,
        favorited=True,
        page=page,
        page_size=page_size,
        current_user=current_user,
        db=db,
    )
