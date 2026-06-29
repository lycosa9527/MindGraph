"""Document Summary (文档总结) session API for the canvas Knowledge portal.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.requests.requests_knowledge_space import DocSummarySessionStartRequest
from models.responses import PackageResponse
from services.knowledge.knowledge_package_service import KnowledgePackageService
from services.utils.error_types import DATABASE_ERRORS
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


def _package_response(package, stats: dict) -> PackageResponse:
    total = stats.get("total", 0)
    completed = stats.get("completed", 0)
    status = "empty" if total == 0 else ("completed" if completed >= total else "processing")
    return PackageResponse(
        id=package.id,
        name=package.name,
        diagram_id=package.diagram_id,
        source=package.source,
        status=status,
        document_count=total,
        completed_count=completed,
        created_at=package.created_at.isoformat(),
        updated_at=package.updated_at.isoformat(),
    )


@router.post("/doc-summary/session/start")
async def start_doc_summary_session(
    request: DocSummarySessionStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Resume or create the Document Summary package for the current canvas session."""
    service = KnowledgePackageService(db, current_user.id)
    try:
        package = await service.ensure_doc_summary_session(
            diagram_id=request.diagram_id,
            diagram_title=request.diagram_title,
            package_id=request.package_id,
            create_if_missing=request.create_if_missing,
        )
        stats_map = await service.get_package_stats([package.id])
        stats = stats_map.get(package.id, {"total": 0, "completed": 0})
        return _package_response(package, stats)
    except ValueError as exc:
        detail = str(exc)
        if detail == "No Document Summary package for this session":
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    except DATABASE_ERRORS as exc:
        logger.error("[DocSummary] session/start failed user=%s: %s", current_user.id, exc)
        raise HTTPException(status_code=500, detail="Session start failed") from exc
