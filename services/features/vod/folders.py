"""One-level folders for the online video library.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.vod import VodFolder, VodMedia, generate_vod_uuid
from services.features.vod.catalog import VodCatalogError

FOLDER_NAME_MAX = 80


def normalize_folder_name(name: str) -> str:
    """Collapse whitespace and reject empty or oversized names."""
    cleaned = " ".join(name.strip().split())
    if not cleaned:
        raise VodCatalogError("folder_name_required", http_status=400)
    if len(cleaned) > FOLDER_NAME_MAX:
        raise VodCatalogError("folder_name_invalid", http_status=400)
    return cleaned


def serialize_folder(row: VodFolder) -> dict[str, Any]:
    """JSON-safe folder row."""
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "name": row.name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def list_folders(db: AsyncSession, organization_id: int) -> list[VodFolder]:
    """Folders in one school, by name."""
    stmt = select(VodFolder).where(VodFolder.organization_id == organization_id).order_by(VodFolder.name.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_folder(db: AsyncSession, folder_id: str, organization_id: int) -> VodFolder:
    """Load one folder inside the org."""
    stmt = select(VodFolder).where(
        VodFolder.id == folder_id,
        VodFolder.organization_id == organization_id,
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise VodCatalogError("folder_not_found", http_status=404)
    return row


async def create_folder(db: AsyncSession, organization_id: int, name: str) -> VodFolder:
    """Create a folder. Names are unique per school."""
    cleaned = normalize_folder_name(name)
    existing = await db.scalar(
        select(VodFolder.id).where(
            VodFolder.organization_id == organization_id,
            VodFolder.name == cleaned,
        )
    )
    if existing is not None:
        raise VodCatalogError("folder_exists", http_status=409)
    now = datetime.now(UTC)
    row = VodFolder(
        id=generate_vod_uuid(),
        organization_id=organization_id,
        name=cleaned,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    return row


async def rename_folder(db: AsyncSession, row: VodFolder, name: str) -> VodFolder:
    """Rename a folder. Names stay unique per school."""
    cleaned = normalize_folder_name(name)
    if cleaned == row.name:
        return row
    existing = await db.scalar(
        select(VodFolder.id).where(
            VodFolder.organization_id == row.organization_id,
            VodFolder.name == cleaned,
            VodFolder.id != row.id,
        )
    )
    if existing is not None:
        raise VodCatalogError("folder_exists", http_status=409)
    row.name = cleaned
    row.updated_at = datetime.now(UTC)
    await db.flush()
    return row


async def delete_folder(db: AsyncSession, row: VodFolder) -> None:
    """Remove a folder. Videos in it become unfiled."""
    await db.delete(row)
    await db.flush()


async def assign_media_folder(
    db: AsyncSession,
    row: VodMedia,
    folder_id: Optional[str],
) -> VodMedia:
    """Move a video into a folder, or clear the folder."""
    if folder_id is None or not str(folder_id).strip():
        row.folder_id = None
    else:
        folder = await get_folder(db, str(folder_id).strip(), int(row.organization_id))
        row.folder_id = folder.id
    row.updated_at = datetime.now(UTC)
    await db.flush()
    return row
