"""HTTP handlers for the 云点播 admin catalog."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.vod import generate_vod_uuid
from routers.auth.dependencies import get_async_db_with_request_rls, require_panel_capability
from services.features.vod.catalog import (
    VodCatalogError,
    delete_catalog_media,
    get_media,
    issue_play_token,
    issue_upload_signature,
    list_media,
    optional_list_org_filter,
    public_player_config,
    refresh_media_metadata,
    register_media,
    resolve_catalog_org_id,
    serialize_media,
)
from utils.auth import get_current_user
from utils.auth.admin_panel_permissions import CAP_TAB_VOD_EDIT, CAP_TAB_VOD_VIEW
from utils.auth.admin_scope import AdminScope

router = APIRouter()


class RegisterMediaBody(BaseModel):
    """Register a Tencent FileId after client upload."""

    file_id: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    organization_id: Optional[int] = None
    class_id: int = 0
    source_context: str = Field(default="", max_length=256)
    refresh: bool = True


class UploadSignBody(BaseModel):
    """Request a one-time client upload signature."""

    organization_id: Optional[int] = None
    title: str = Field(default="", max_length=200)


def _http_error(exc: VodCatalogError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=exc.code)


@router.get("/config")
async def get_vod_config(
    _scope: AdminScope = Depends(require_panel_capability(CAP_TAB_VOD_VIEW)),
) -> dict:
    """Public-safe TCPlayer config (no PlayKey or CAM secrets)."""
    return public_player_config()


@router.get("/media")
async def list_vod_media(
    q: str = Query(default=""),
    status: str = Query(default=""),
    organization_id: Optional[int] = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_VOD_VIEW)),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
) -> dict:
    """Org-scoped catalog list."""
    try:
        org_filter = optional_list_org_filter(scope, organization_id)
        rows, total = await list_media(db, org_filter, query=q, status=status, offset=offset, limit=limit)
    except VodCatalogError as exc:
        raise _http_error(exc) from exc
    return {
        "items": [serialize_media(row) for row in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/media/{media_id}")
async def get_vod_media(
    media_id: str,
    organization_id: Optional[int] = Query(default=None),
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_VOD_VIEW)),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
) -> dict:
    """One catalog row."""
    try:
        org_filter = optional_list_org_filter(scope, organization_id)
        row = await get_media(db, media_id, org_filter)
    except VodCatalogError as exc:
        raise _http_error(exc) from exc
    return serialize_media(row)


@router.post("/uploads/sign")
async def sign_vod_upload(
    body: UploadSignBody,
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_VOD_EDIT)),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Issue a one-time vod-js-sdk upload signature."""
    try:
        org_id = resolve_catalog_org_id(scope, body.organization_id)
        media_id = generate_vod_uuid()
        payload = issue_upload_signature(org_id, int(current_user.id), media_id)
    except VodCatalogError as exc:
        raise _http_error(exc) from exc
    return payload


@router.post("/media")
async def create_vod_media(
    body: RegisterMediaBody,
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_VOD_EDIT)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
) -> dict:
    """Register FileId after the browser finishes uploading to Tencent."""
    try:
        org_id = resolve_catalog_org_id(scope, body.organization_id)
        row = await register_media(
            db,
            organization_id=org_id,
            owner=current_user,
            file_id=body.file_id,
            title=body.title,
            description=body.description,
            class_id=body.class_id,
            source_context=body.source_context,
            refresh=body.refresh,
        )
    except VodCatalogError as exc:
        raise _http_error(exc) from exc
    return serialize_media(row)


@router.post("/media/{media_id}/refresh")
async def refresh_vod_media(
    media_id: str,
    organization_id: Optional[int] = Query(default=None),
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_VOD_EDIT)),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
) -> dict:
    """Pull duration/status from DescribeMediaInfos."""
    try:
        org_filter = optional_list_org_filter(scope, organization_id)
        row = await get_media(db, media_id, org_filter)
        row = await refresh_media_metadata(db, row)
    except VodCatalogError as exc:
        raise _http_error(exc) from exc
    return serialize_media(row)


@router.get("/media/{media_id}/play")
async def play_vod_media(
    media_id: str,
    organization_id: Optional[int] = Query(default=None),
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_VOD_VIEW)),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
) -> dict:
    """TCPlayer FileID payload: appId, fileId, psign, licenseUrl, expireAt."""
    try:
        org_filter = optional_list_org_filter(scope, organization_id)
        row = await get_media(db, media_id, org_filter)
        return issue_play_token(row)
    except VodCatalogError as exc:
        raise _http_error(exc) from exc


@router.delete("/media/{media_id}")
async def delete_vod_media(
    media_id: str,
    organization_id: Optional[int] = Query(default=None),
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_VOD_EDIT)),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
) -> dict:
    """Best-effort DeleteMedia, then drop the catalog row."""
    try:
        org_filter = optional_list_org_filter(scope, organization_id)
        row = await get_media(db, media_id, org_filter)
        await delete_catalog_media(db, row)
    except VodCatalogError as exc:
        raise _http_error(exc) from exc
    return {"ok": True, "id": media_id}
