"""Course Builder access to the online video library.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.training import TrainingCourse, TrainingCourseStep
from models.domain.vod import VOD_STATUS_READY, VodFolder, VodMedia
from services.features.training.permissions import can_lead_any_training
from services.features.vod.catalog import VodCatalogError, get_media, issue_play_token
from services.features.vod.folders import serialize_folder
from utils.auth.expert_invited_org_ids import load_expert_invited_org_ids
from utils.auth.roles import is_expert, is_platform_bd, is_superadmin

LIBRARY_LIMIT = 200


class TrainingVodError(Exception):
    """Training-scoped library or playback failure."""

    def __init__(self, code: str, http_status: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.http_status = http_status


async def author_org_scope(user: object) -> Optional[set[int]]:
    """Org ids an author may browse. None means every school."""
    if is_superadmin(user) or is_platform_bd(user):
        return None
    if is_expert(user):
        invited = await load_expert_invited_org_ids(int(getattr(user, "id")))
        return set(invited)
    return set()


def _library_item(row: VodMedia) -> dict[str, Any]:
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "folder_id": row.folder_id,
        "title": row.title,
        "status": row.status,
        "duration_ms": row.duration_ms,
    }


async def list_author_library(db: AsyncSession, user: object) -> dict[str, Any]:
    """Ready videos and folders the course author may place on a step."""
    if not can_lead_any_training(user):
        raise TrainingVodError("forbidden", http_status=403)
    org_ids = await author_org_scope(user)
    if org_ids is not None and not org_ids:
        return {"folders": [], "items": []}
    folder_stmt = select(VodFolder).order_by(VodFolder.name.asc())
    media_stmt = (
        select(VodMedia).where(VodMedia.status == VOD_STATUS_READY).order_by(VodMedia.title.asc()).limit(LIBRARY_LIMIT)
    )
    if org_ids is not None:
        folder_stmt = folder_stmt.where(VodFolder.organization_id.in_(org_ids))
        media_stmt = media_stmt.where(VodMedia.organization_id.in_(org_ids))
    folders = list((await db.execute(folder_stmt)).scalars().all())
    items = list((await db.execute(media_stmt)).scalars().all())
    return {
        "folders": [serialize_folder(row) for row in folders],
        "items": [_library_item(row) for row in items],
    }


async def _attached_to_ready_course(db: AsyncSession, media_id: str) -> bool:
    """Published courses only. Draft steps stay with authors in scope."""
    found = await db.scalar(
        select(TrainingCourseStep.id)
        .join(TrainingCourse, TrainingCourse.id == TrainingCourseStep.course_id)
        .where(
            TrainingCourse.status == "ready",
            TrainingCourseStep.payload["vod_media_id"].astext == media_id,
        )
        .limit(1)
    )
    return found is not None


async def play_for_training(db: AsyncSession, user: object, media_id: str) -> dict[str, Any]:
    """Play token for an author in scope, or a video on a published course."""
    try:
        row = await get_media(db, media_id, None)
    except VodCatalogError as exc:
        raise TrainingVodError(exc.code, http_status=exc.http_status) from exc
    if can_lead_any_training(user):
        org_ids = await author_org_scope(user)
        if org_ids is None or int(row.organization_id) in org_ids:
            return issue_play_token(row)
    if await _attached_to_ready_course(db, media_id):
        if row.status != VOD_STATUS_READY:
            raise TrainingVodError("not_ready", http_status=409)
        return issue_play_token(row)
    raise TrainingVodError("forbidden", http_status=403)
