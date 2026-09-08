"""Org-scoped VOD catalog: list, register, refresh, play, delete.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.vod import (
    VOD_STATUS_PROCESSING,
    VOD_STATUSES,
    VodMedia,
    generate_vod_uuid,
)
from services.features.vod.credentials import (
    TencentVodCredentials,
    TencentVodNotConfiguredError,
    load_tencent_vod_credentials,
)
from services.features.vod.play_sign import build_player_psign
from services.features.vod.upload_sign import (
    build_client_upload_signature,
    clamp_upload_ttl,
    new_upload_random,
)
from services.features.vod.vod_api import (
    TencentVodApiError,
    catalog_status_from_media_info,
    delete_media as delete_tencent_media,
    describe_media_infos,
    duration_ms_from_media_info,
    parse_media_info_set,
)
from services.utils.error_types import SQLAlchemyError
from utils.auth.admin_scope import AdminScope

logger = logging.getLogger(__name__)

DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 100
TITLE_MAX = 200


class VodCatalogError(Exception):
    """Catalog validation or lookup failure."""

    def __init__(self, code: str, http_status: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.http_status = http_status


def require_vod_credentials() -> TencentVodCredentials:
    """Load credentials or raise 503-style catalog error."""
    try:
        return load_tencent_vod_credentials()
    except TencentVodNotConfiguredError as exc:
        raise VodCatalogError("vod_not_configured", http_status=503) from exc


def resolve_catalog_org_id(scope: AdminScope, requested_org_id: Optional[int]) -> int:
    """School admins stay in their org; superadmins may filter or must pick an org."""
    if scope.org_ids is None:
        if requested_org_id is not None:
            return int(requested_org_id)
        if scope.effective_org_id is not None:
            return int(scope.effective_org_id)
        raise VodCatalogError("organization_required", http_status=400)
    if scope.effective_org_id is None:
        raise VodCatalogError("organization_required", http_status=403)
    if requested_org_id is not None and int(requested_org_id) != int(scope.effective_org_id):
        raise VodCatalogError("cross_org_forbidden", http_status=403)
    return int(scope.effective_org_id)


def optional_list_org_filter(scope: AdminScope, requested_org_id: Optional[int]) -> Optional[int]:
    """None means all orgs (superadmin, no filter); else a single org id."""
    if scope.org_ids is None:
        if requested_org_id is None:
            return None
        return int(requested_org_id)
    return resolve_catalog_org_id(scope, requested_org_id)


def _owner_name(row: VodMedia) -> str:
    owner = row.owner
    if owner is None:
        return ""
    return str(getattr(owner, "name", None) or "").strip()


def serialize_media(row: VodMedia) -> dict[str, Any]:
    """JSON-safe catalog row (no CDN hosts)."""
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "owner_id": row.owner_id,
        "owner_name": _owner_name(row),
        "file_id": row.file_id,
        "title": row.title,
        "description": row.description or "",
        "status": row.status,
        "duration_ms": row.duration_ms,
        "class_id": row.class_id,
        "source_context": row.source_context,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def get_media(db: AsyncSession, media_id: str, org_id: Optional[int]) -> VodMedia:
    """Load one row; 404 when missing or outside org."""
    stmt: Select[tuple[VodMedia]] = select(VodMedia).where(VodMedia.id == media_id)
    if org_id is not None:
        stmt = stmt.where(VodMedia.organization_id == org_id)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise VodCatalogError("not_found", http_status=404)
    return row


async def list_media(
    db: AsyncSession,
    org_id: Optional[int],
    query: str = "",
    status: str = "",
    offset: int = 0,
    limit: int = DEFAULT_LIST_LIMIT,
) -> tuple[list[VodMedia], int]:
    """Paginated org catalog with optional title/fileId search."""
    safe_limit = min(max(int(limit), 1), MAX_LIST_LIMIT)
    safe_offset = max(int(offset), 0)
    filters = []
    if org_id is not None:
        filters.append(VodMedia.organization_id == org_id)
    needle = query.strip()
    if needle:
        like = f"%{needle}%"
        filters.append(or_(VodMedia.title.ilike(like), VodMedia.file_id.ilike(like)))
    status_value = status.strip()
    if status_value:
        if status_value not in VOD_STATUSES:
            raise VodCatalogError("invalid_status", http_status=400)
        filters.append(VodMedia.status == status_value)
    count_stmt = select(func.count()).select_from(VodMedia)
    list_stmt = select(VodMedia).order_by(VodMedia.updated_at.desc())
    for clause in filters:
        count_stmt = count_stmt.where(clause)
        list_stmt = list_stmt.where(clause)
    total = int(await db.scalar(count_stmt) or 0)
    result = await db.execute(list_stmt.offset(safe_offset).limit(safe_limit))
    return list(result.scalars().all()), total


def _normalize_title(title: str) -> str:
    cleaned = title.strip()
    if not cleaned:
        raise VodCatalogError("title_required", http_status=400)
    return cleaned[:TITLE_MAX]


def _normalize_file_id(file_id: str) -> str:
    cleaned = file_id.strip()
    if not cleaned:
        raise VodCatalogError("file_id_required", http_status=400)
    if len(cleaned) > 64:
        raise VodCatalogError("file_id_invalid", http_status=400)
    return cleaned


async def _file_id_exists(db: AsyncSession, organization_id: int, file_id: str) -> bool:
    stmt = (
        select(func.count())
        .select_from(VodMedia)
        .where(
            VodMedia.organization_id == organization_id,
            VodMedia.file_id == file_id,
        )
    )
    return int(await db.scalar(stmt) or 0) > 0


async def register_media(
    db: AsyncSession,
    organization_id: int,
    owner: User,
    file_id: str,
    title: str,
    description: str = "",
    class_id: int = 0,
    source_context: str = "",
    refresh: bool = True,
) -> VodMedia:
    """Insert a FileId after client upload; optionally pull DescribeMediaInfos."""
    normalized_file_id = _normalize_file_id(file_id)
    if await _file_id_exists(db, organization_id, normalized_file_id):
        raise VodCatalogError("file_id_exists", http_status=409)
    row = VodMedia(
        id=generate_vod_uuid(),
        organization_id=organization_id,
        owner_id=int(owner.id),
        file_id=normalized_file_id,
        title=_normalize_title(title),
        description=description.strip()[:2000],
        status=VOD_STATUS_PROCESSING,
        class_id=int(class_id),
        source_context=source_context.strip()[:256],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(row)
    await db.flush()
    if refresh:
        await refresh_media_metadata(db, row)
    return row


async def refresh_media_metadata(db: AsyncSession, row: VodMedia) -> VodMedia:
    """Pull duration/status from DescribeMediaInfos (never store CDN URLs)."""
    credentials = require_vod_credentials()
    try:
        response = await describe_media_infos(credentials, [row.file_id])
    except TencentVodApiError as exc:
        logger.warning("DescribeMediaInfos failed for file_id=%s: %s", row.file_id, exc)
        row.status = VOD_STATUS_PROCESSING
        row.updated_at = datetime.now(UTC)
        await db.flush()
        return row
    infos = parse_media_info_set(response)
    if not infos:
        row.status = VOD_STATUS_PROCESSING
        row.updated_at = datetime.now(UTC)
        await db.flush()
        return row
    info = infos[0]
    duration_ms = duration_ms_from_media_info(info)
    if duration_ms is not None:
        row.duration_ms = duration_ms
    row.status = catalog_status_from_media_info(info)
    row.updated_at = datetime.now(UTC)
    await db.flush()
    return row


async def delete_catalog_media(db: AsyncSession, row: VodMedia) -> None:
    """Best-effort DeleteMedia, then drop the catalog row."""
    try:
        credentials = require_vod_credentials()
        await delete_tencent_media(credentials, row.file_id)
    except (TencentVodApiError, VodCatalogError) as exc:
        logger.warning("DeleteMedia skipped or failed for file_id=%s: %s", row.file_id, exc)
    await db.delete(row)
    try:
        await db.flush()
    except SQLAlchemyError as exc:
        raise VodCatalogError("delete_failed", http_status=500) from exc


def issue_upload_signature(
    organization_id: int,
    owner_id: int,
    media_id: str,
) -> dict[str, Any]:
    """One-time client upload signature for vod-js-sdk."""
    credentials = require_vod_credentials()
    now = int(time.time())
    ttl = clamp_upload_ttl(credentials.upload_ttl)
    expire_time = now + ttl
    random_value = new_upload_random()
    source_context = f"org:{organization_id}:user:{owner_id}:media:{media_id}"
    signature = build_client_upload_signature(
        secret_id=credentials.secret_id,
        secret_key=credentials.secret_key,
        current_time=now,
        expire_time=expire_time,
        random_value=random_value,
        procedure=credentials.procedure,
        vod_sub_app_id=credentials.app_id,
        one_time_valid=1,
        source_context=source_context,
    )
    return {
        "signature": signature,
        "expire_at": expire_time,
        "app_id": credentials.app_id,
        "source_context": source_context,
        "media_id": media_id,
    }


def issue_play_token(row: VodMedia) -> dict[str, Any]:
    """TCPlayer FileID payload: appId, fileId, psign, licenseUrl, expireAt."""
    credentials = require_vod_credentials()
    now = int(time.time())
    expire_at = now + max(int(credentials.psign_ttl), 60)
    psign = build_player_psign(
        app_id=credentials.app_id,
        file_id=row.file_id,
        play_key=credentials.play_key,
        current_time=now,
        expire_time=expire_at,
        adaptive_definition=credentials.adaptive_definition,
    )
    return {
        "appId": str(credentials.app_id),
        "fileId": row.file_id,
        "psign": psign,
        "licenseUrl": credentials.license_url,
        "licenseKey": credentials.license_key,
        "expireAt": expire_at,
        "id": row.id,
    }


def public_player_config() -> dict[str, Any]:
    """Safe config for TCPlayer (no secrets)."""
    try:
        credentials = load_tencent_vod_credentials()
    except TencentVodNotConfiguredError:
        return {"configured": False, "appId": "", "licenseUrl": "", "licenseKey": ""}
    return {
        "configured": True,
        "appId": str(credentials.app_id),
        "licenseUrl": credentials.license_url,
        "licenseKey": credentials.license_key,
    }
