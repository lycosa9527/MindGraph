"""Document Summary session + extracted-markdown ownership APIs.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.requests.requests_knowledge_space import (
    DocSummarySessionClearRequest,
    DocSummarySessionStartRequest,
)
from models.responses import PackageResponse
from services.knowledge.chat_handoff_service import revoke_waiting_handoffs_for_package
from services.knowledge.doc_summary_ingest import DOC_SUMMARY_SOURCE, DocSummaryIngestService
from services.knowledge.doc_summary_limits import (
    DocSummaryStorageConflictError,
    storage_conflict_detail,
)
from services.knowledge.knowledge_package_service import KnowledgePackageService
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["doc-summary"])


class DocSummaryExtractedAccessResponse(BaseModel):
    """Ownership probe: is this caller allowed to use this package's COS object?"""

    allowed: bool
    package_id: int
    object_id: Optional[str] = None
    storage: Optional[str] = None
    has_content: bool = False
    reason: Optional[str] = None


class DocSummaryExtractedContentResponse(BaseModel):
    """Owner-only extracted markdown payload (never a public COS URL)."""

    package_id: int
    object_id: Optional[str] = None
    storage: Optional[str] = None
    markdown: str = Field(default="")
    source_filename: Optional[str] = None


def _package_response(package: Any, stats: dict) -> PackageResponse:
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


async def resolve_owned_extracted(
    *,
    db: AsyncSession,
    user_id: int,
    package_id: int,
) -> Dict[str, Any]:
    """Validate package ownership and return extract metadata + optional text."""
    packages = KnowledgePackageService(db, user_id)
    package = await packages.get_package(package_id)
    if package is None:
        return {
            "allowed": False,
            "reason": "package_not_found",
            "package_id": package_id,
        }
    if package.source != DOC_SUMMARY_SOURCE:
        return {
            "allowed": False,
            "reason": "not_doc_summary",
            "package_id": package_id,
        }

    ingest = DocSummaryIngestService(db, user_id)
    try:
        markdown = await ingest.fetch_package_markdown(package_id)
    except DocSummaryStorageConflictError as exc:
        return {
            "allowed": True,
            "reason": "storage_conflict_cleared",
            "package_id": package_id,
            "object_id": exc.object_id,
            "has_content": False,
            "markdown": "",
            "storage_conflict": True,
        }

    documents = await ingest.list_package_documents(package_id)
    completed = next((doc for doc in documents if doc.status == "completed"), None)
    if completed is None or not markdown:
        return {
            "allowed": True,
            "reason": "no_extracted_content",
            "package_id": package_id,
            "has_content": False,
        }

    meta = completed.doc_metadata or {}
    return {
        "allowed": True,
        "package_id": package_id,
        "object_id": meta.get("object_id"),
        "storage": meta.get("storage"),
        "has_content": True,
        "markdown": markdown,
        "source_filename": meta.get("source_filename") or completed.file_name,
    }


@router.post("/session/start")
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


@router.post("/session/clear")
async def clear_doc_summary_session(
    request: DocSummarySessionClearRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete the Document Summary package for a canvas reset (COS extract included)."""
    service = KnowledgePackageService(db, current_user.id)
    try:
        if request.package_id is not None:
            try:
                await revoke_waiting_handoffs_for_package(current_user.id, request.package_id)
            except BACKGROUND_INFRA_ERRORS as exc:
                logger.warning(
                    "[DocSummary] session/clear handoff revoke failed user=%s package=%s: %s",
                    current_user.id,
                    request.package_id,
                    exc,
                )
        deleted = await service.clear_doc_summary_session(
            diagram_id=request.diagram_id,
            package_id=request.package_id,
        )
        return {"deleted": deleted}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DATABASE_ERRORS as exc:
        logger.error("[DocSummary] session/clear failed user=%s: %s", current_user.id, exc)
        raise HTTPException(status_code=500, detail="Session clear failed") from exc


@router.get(
    "/{package_id}/access",
    response_model=DocSummaryExtractedAccessResponse,
)
async def authorize_extracted_access(
    package_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Ask: is this caller allowed to use this package's extracted COS object?"""
    try:
        resolved = await resolve_owned_extracted(
            db=db,
            user_id=current_user.id,
            package_id=package_id,
        )
    except DATABASE_ERRORS as exc:
        logger.error(
            "[DocSummary] extracted/access failed user=%s package=%s: %s",
            current_user.id,
            package_id,
            exc,
        )
        raise HTTPException(status_code=500, detail="Access check failed") from exc

    if not resolved.get("allowed") and resolved.get("reason") == "package_not_found":
        raise HTTPException(status_code=404, detail="Package not found")
    if not resolved.get("allowed") and resolved.get("reason") == "not_doc_summary":
        raise HTTPException(status_code=400, detail="Package is not a Document Summary session")

    return DocSummaryExtractedAccessResponse(
        allowed=True,
        package_id=package_id,
        object_id=resolved.get("object_id"),
        storage=resolved.get("storage"),
        has_content=bool(resolved.get("has_content")),
        reason=resolved.get("reason"),
    )


@router.get(
    "/{package_id}/md",
    response_model=DocSummaryExtractedContentResponse,
)
async def get_extracted_markdown(
    package_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Return extracted markdown only after ownership checks out (server-side COS fetch)."""
    try:
        resolved = await resolve_owned_extracted(
            db=db,
            user_id=current_user.id,
            package_id=package_id,
        )
    except DATABASE_ERRORS as exc:
        logger.error(
            "[DocSummary] extracted get failed user=%s package=%s: %s",
            current_user.id,
            package_id,
            exc,
        )
        raise HTTPException(status_code=500, detail="Fetch failed") from exc

    if not resolved.get("allowed") and resolved.get("reason") == "package_not_found":
        raise HTTPException(status_code=404, detail="Package not found")
    if not resolved.get("allowed") and resolved.get("reason") == "not_doc_summary":
        raise HTTPException(status_code=400, detail="Package is not a Document Summary session")
    if resolved.get("reason") == "storage_conflict_cleared":
        conflict_object_id = resolved.get("object_id")
        raise HTTPException(
            status_code=409,
            detail=storage_conflict_detail(
                package_id=package_id,
                object_id=str(conflict_object_id) if conflict_object_id else None,
            ),
        )
    if not resolved.get("has_content"):
        raise HTTPException(status_code=404, detail="No extracted content in package yet")

    return DocSummaryExtractedContentResponse(
        package_id=package_id,
        object_id=resolved.get("object_id"),
        storage=resolved.get("storage"),
        markdown=str(resolved.get("markdown") or ""),
        source_filename=resolved.get("source_filename"),
    )
