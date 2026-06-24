"""
MindMate export job API routes.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.messages import Language, Messages
from models.domain.mindmate_export_job import MindmateExportJob
from routers.auth.dependencies import get_language_dependency, require_mindmate_export_access
from services.auth.security_logger import security_log
from services.dify.export.export_config import BLOCK_ON_GAPS
from services.dify.export.export_routing import should_use_background_job
from services.dify.export.job_events import (
    export_job_to_dict,
    publish_export_job_control,
    publish_export_job_progress,
)
from services.dify.export.job_storage import TEMP_EXPORTS_DIR, expires_at_from_now, get_job
from services.dify.export.job_stream import mindmate_export_job_stream_response
from services.dify.export.target_resolution import count_export_users
from services.dify.export.types import ExportScope
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from tasks.mindmate_export_tasks import run_mindmate_export_job
from utils.auth.request_helpers import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/mindmate-export", tags=["admin", "mindmate-export"])


class CreateExportJobBody(BaseModel):
    """Request body to start a background export job."""

    scope: str = "whole"
    org_id: Optional[int] = None
    user_ids: List[int] = Field(default_factory=list)
    start: Optional[int] = None
    end: Optional[int] = None
    format: str = "zip"
    org_name: Optional[str] = None


def _job_to_dict(job: MindmateExportJob) -> dict:
    return export_job_to_dict(job)


@router.get("/jobs")
async def list_export_jobs(
    request: Request,
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(require_mindmate_export_access),
    db: AsyncSession = Depends(get_async_db),
):
    """Recent export jobs for the current admin."""
    rows = (
        (
            await db.execute(
                select(MindmateExportJob)
                .where(MindmateExportJob.created_by_user_id == int(current_user.id))
                .order_by(MindmateExportJob.id.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    security_log.data_access(
        "MindMate export job list",
        user_id=int(current_user.id),
        ip=get_client_ip(request),
        jobs=len(rows),
    )
    return {"jobs": [_job_to_dict(job) for job in rows]}


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_export_job(
    request: Request,
    body: CreateExportJobBody,
    current_user: User = Depends(require_mindmate_export_access),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Create and dispatch a background MindMate export job."""
    scope = body.scope if body.scope in ("all", "whole", "users") else None
    if scope is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang),
        )
    export_scope: ExportScope = scope
    org_id = body.org_id
    if export_scope != "all" and org_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("missing_required_fields", lang, "org_id"),
        )
    if export_scope == "users" and not body.user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("missing_required_fields", lang, "user_ids"),
        )
    fmt = str(body.format or "zip").lower()
    if fmt not in {"html", "json", "zip"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang),
        )

    user_count = await count_export_users(
        db,
        export_scope,
        org_id,
        body.user_ids if body.user_ids else None,
    )
    if not should_use_background_job(export_scope, user_count):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang),
        )

    job = MindmateExportJob(
        created_by_user_id=int(current_user.id),
        organization_id=org_id,
        status="pending",
        progress_percent=0,
        filters={
            "scope": export_scope,
            "org_id": org_id,
            "user_ids": body.user_ids,
            "start": body.start,
            "end": body.end,
            "format": fmt,
            "org_name": body.org_name,
        },
        expires_at=expires_at_from_now(),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    try:
        task = run_mindmate_export_job.delay(int(job.id), int(current_user.id))
    except BACKGROUND_INFRA_ERRORS as exc:
        job.status = "failed"
        job.error_message = f"Background worker unavailable: {exc}"[:2000]
        await db.commit()
        await publish_export_job_progress(int(job.id), _job_to_dict(job))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=Messages.error("invalid_request", lang),
        ) from exc
    job.celery_task_id = str(task.id)
    await db.commit()

    security_log.data_export(
        "MindMate export job created",
        user_id=int(current_user.id),
        ip=get_client_ip(request),
        org_id=org_id,
        job_id=int(job.id),
        scope=export_scope,
        fmt=fmt,
        user_count=user_count,
        celery_task_id=str(task.id),
    )
    logger.info(
        "[MindMateExportJob] job=%s created user=%s org=%s scope=%s fmt=%s users=%s",
        job.id,
        current_user.id,
        org_id,
        export_scope,
        fmt,
        user_count,
    )
    await publish_export_job_progress(int(job.id), _job_to_dict(job))
    return {"job": _job_to_dict(job)}


@router.get("/jobs/{job_id}")
async def get_export_job(
    job_id: int,
    current_user: User = Depends(require_mindmate_export_access),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Return one export job for the current admin."""
    job = await get_job(db, job_id)
    if job is None or int(job.created_by_user_id) != int(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("invalid_request", lang),
        )
    return {"job": _job_to_dict(job)}


@router.get("/jobs/{job_id}/stream")
async def stream_export_job(
    job_id: int,
    current_user: User = Depends(require_mindmate_export_access),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Stream export job progress via Server-Sent Events."""
    return await mindmate_export_job_stream_response(db, job_id, current_user, lang)


@router.get("/jobs/{job_id}/verification")
async def get_export_job_verification(
    job_id: int,
    current_user: User = Depends(require_mindmate_export_access),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Return verification report for one export job."""
    job = await get_job(db, job_id)
    if job is None or int(job.created_by_user_id) != int(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("invalid_request", lang),
        )
    return {
        "job_id": int(job.id),
        "verification_expected": job.verification_expected,
        "verification_report": job.verification_report,
    }


@router.post("/jobs/{job_id}/pause")
async def pause_export_job(
    request: Request,
    job_id: int,
    current_user: User = Depends(require_mindmate_export_access),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Pause a running export job at the next batch boundary."""
    job = await get_job(db, job_id)
    if job is None or int(job.created_by_user_id) != int(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("invalid_request", lang),
        )
    if job.status not in ("running", "pending"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang),
        )
    job.status = "paused"
    job.paused_at = datetime.now(UTC)
    await db.commit()
    job_dict = _job_to_dict(job)
    await publish_export_job_control(job_id, "pause")
    await publish_export_job_progress(job_id, job_dict)
    security_log.data_access(
        "MindMate export job paused",
        user_id=int(current_user.id),
        ip=get_client_ip(request),
        job_id=int(job.id),
    )
    logger.info("[MindMateExportJob] job=%s paused by user=%s", job_id, current_user.id)
    return {"job": job_dict}


@router.post("/jobs/{job_id}/resume")
async def resume_export_job(
    request: Request,
    job_id: int,
    current_user: User = Depends(require_mindmate_export_access),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Resume a paused export job from its checkpoint."""
    job = await get_job(db, job_id)
    if job is None or int(job.created_by_user_id) != int(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("invalid_request", lang),
        )
    if job.status != "paused":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang),
        )
    job.status = "running"
    job.paused_at = None
    await db.commit()
    try:
        task = run_mindmate_export_job.delay(int(job.id), int(current_user.id))
    except BACKGROUND_INFRA_ERRORS as exc:
        job.status = "paused"
        job.error_message = f"Background worker unavailable: {exc}"[:2000]
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=Messages.error("invalid_request", lang),
        ) from exc
    job.celery_task_id = str(task.id)
    job.error_message = None
    await db.commit()
    job_dict = _job_to_dict(job)
    await publish_export_job_control(job_id, "resume")
    await publish_export_job_progress(job_id, job_dict)
    security_log.data_access(
        "MindMate export job resumed",
        user_id=int(current_user.id),
        ip=get_client_ip(request),
        job_id=int(job.id),
        celery_task_id=str(task.id),
    )
    logger.info("[MindMateExportJob] job=%s resumed by user=%s", job_id, current_user.id)
    return {"job": job_dict}


@router.post("/jobs/{job_id}/cancel")
async def cancel_export_job(
    request: Request,
    job_id: int,
    current_user: User = Depends(require_mindmate_export_access),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Cancel a pending, running, or paused export job."""
    job = await get_job(db, job_id)
    if job is None or int(job.created_by_user_id) != int(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("invalid_request", lang),
        )
    if job.status in ("completed", "completed_with_gaps", "cancelled", "failed", "failed_verification"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang),
        )
    job.cancel_requested_at = datetime.now(UTC)
    job.status = "cancelled"
    await db.commit()
    job_dict = _job_to_dict(job)
    await publish_export_job_control(job_id, "cancel")
    await publish_export_job_progress(job_id, job_dict)
    security_log.data_access(
        "MindMate export job cancelled",
        user_id=int(current_user.id),
        ip=get_client_ip(request),
        job_id=int(job.id),
    )
    logger.info("[MindMateExportJob] job=%s cancelled by user=%s", job_id, current_user.id)
    return {"job": job_dict}


@router.get("/jobs/{job_id}/download")
async def download_export_job(
    request: Request,
    job_id: int,
    current_user: User = Depends(require_mindmate_export_access),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Download the artifact for a completed export job."""
    job = await get_job(db, job_id)
    if job is None or int(job.created_by_user_id) != int(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("invalid_request", lang),
        )
    if job.status not in ("completed", "completed_with_gaps"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang),
        )
    if BLOCK_ON_GAPS and job.status == "completed_with_gaps":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=Messages.error("invalid_request", lang),
        )
    if not job.artifact_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("invalid_request", lang),
        )
    path = Path(job.artifact_path)
    if not path.is_file():
        path = TEMP_EXPORTS_DIR / str(job_id) / Path(job.artifact_path).name
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("invalid_request", lang),
        )
    media = "application/zip" if job.artifact_format == "zip" else "application/json"
    if job.artifact_format == "html":
        media = "text/html"
    verification_status = (job.verification_report or {}).get("status")
    security_log.data_export(
        "MindMate export job download",
        user_id=int(current_user.id),
        ip=get_client_ip(request),
        job_id=int(job.id),
        org_id=job.organization_id,
        fmt=job.artifact_format,
        verification_status=verification_status,
        artifact_bytes=job.artifact_size_bytes,
    )
    logger.info(
        "[MindMateExportJob] job=%s downloaded user=%s fmt=%s verification=%s",
        job.id,
        current_user.id,
        job.artifact_format,
        verification_status,
    )
    return FileResponse(
        path,
        media_type=media,
        filename=path.name,
        headers={
            "X-MG-Export-Verification": str((job.verification_report or {}).get("status", "")),
        },
    )
