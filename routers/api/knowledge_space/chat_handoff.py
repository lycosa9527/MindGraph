"""Chat handoff API for file-reader → Document Summary package ingest.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.diagrams import Diagram
from models.requests.requests_knowledge_space import ChatHandoffIngestRequest, ChatHandoffStartRequest
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.api.knowledge_space.packages import _document_to_response
from services.knowledge.chat_handoff_service import (
    claim_handoff_for_ingest,
    list_waiting_handoffs,
    load_handoff,
    mint_handoff_code,
    update_handoff_status,
)
from services.knowledge.chat_transcript_normalizer import normalize_chat_messages, normalize_raw_content
from services.knowledge.doc_summary_ingest import DocSummaryIngestService
from services.knowledge.knowledge_package_service import KnowledgePackageService
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat-handoff/start")
async def start_chat_handoff(
    request: ChatHandoffStartRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Mint a six-digit pairing code for file-reader upload."""
    identifier = get_rate_limit_identifier(current_user, http_request)
    await check_endpoint_rate_limit("chat_handoff_start", identifier, max_requests=30, window_seconds=600)

    service = KnowledgePackageService(db, current_user.id)
    package = await service.get_package(request.package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    try:
        code = await mint_handoff_code(current_user.id, request.package_id)
        return {"code": code, "expires_in_seconds": 600, "package_id": request.package_id}
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error("[ChatHandoff] mint allocation failed: %s", exc)
        raise HTTPException(status_code=503, detail="Pairing service unavailable") from exc
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[ChatHandoff] mint failed: %s", exc)
        raise HTTPException(status_code=503, detail="Pairing service unavailable") from exc


@router.get("/chat-handoff/waiting")
async def list_chat_handoff_waiting(
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """List website pairing sessions waiting for file-reader upload."""
    identifier = get_rate_limit_identifier(current_user, http_request)
    await check_endpoint_rate_limit("chat_handoff_waiting", identifier, max_requests=60, window_seconds=60)

    waiting = await list_waiting_handoffs(current_user.id)
    service = KnowledgePackageService(db, current_user.id)
    items = []
    for session in waiting:
        package = await service.get_package(session.package_id)
        name = package.name if package else None
        diagram_title: str | None = None
        if package and package.diagram_id:
            diag_result = await db.execute(
                select(Diagram.title).where(
                    Diagram.id == package.diagram_id,
                    Diagram.user_id == current_user.id,
                )
            )
            diagram_title = diag_result.scalar_one_or_none()
        items.append(
            {
                "code": session.code,
                "package_id": session.package_id,
                "package_name": name,
                "diagram_title": diagram_title,
                "status": session.status,
                "expires_in_seconds": session.expires_in_seconds,
            }
        )
    return {"sessions": items, "total": len(items)}


@router.get("/chat-handoff/status")
async def chat_handoff_status(
    http_request: Request,
    code: str = Query(..., min_length=6, max_length=6),
    current_user: User = Depends(get_current_user),
):
    """Poll pairing + document indexing status for the web panel."""
    identifier = get_rate_limit_identifier(current_user, http_request)
    await check_endpoint_rate_limit("chat_handoff_status", identifier, max_requests=120, window_seconds=60)

    record = await load_handoff(code)
    if not record or record.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Pairing code not found or expired")
    return {
        "code": code,
        "status": record.status,
        "package_id": record.package_id,
        "document_id": record.document_id,
    }


@router.post("/chat-handoff/ingest")
async def ingest_chat_handoff(
    request: ChatHandoffIngestRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Ingest chat transcript from file-reader using mgat auth + pairing code."""
    identifier = get_rate_limit_identifier(current_user, http_request)
    await check_endpoint_rate_limit("chat_handoff_ingest", identifier, max_requests=20, window_seconds=600)

    record = await claim_handoff_for_ingest(request.code, current_user.id)
    if not record:
        existing = await load_handoff(request.code)
        if not existing:
            raise HTTPException(status_code=404, detail="Pairing code not found or expired")
        if existing.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Pairing code user mismatch")
        raise HTTPException(status_code=409, detail="Pairing code already used")

    service = KnowledgePackageService(db, current_user.id)
    package = await service.get_package(record.package_id)
    if not package:
        await update_handoff_status(request.code, "failed")
        raise HTTPException(status_code=404, detail="Package not found")

    try:
        if request.messages:
            body = normalize_chat_messages(
                request.messages,
                request.chat_title,
                request.platform,
            )
            message_count = len(request.messages)
        elif request.content:
            body = normalize_raw_content(
                request.content,
                request.chat_title,
                request.platform,
            )
            message_count = None
        else:
            raise HTTPException(status_code=400, detail="content or messages required")

        extra_metadata: dict[str, object] = {
            "chat_platform": request.platform,
            "handoff_code": request.code,
        }
        if request.source_export_name:
            extra_metadata["source_export_name"] = request.source_export_name.strip()
        if message_count is not None:
            extra_metadata["message_count"] = message_count

        if package.source == "doc_summary":
            ingest = DocSummaryIngestService(db, current_user.id)
            document = await ingest.ingest_text(
                record.package_id,
                content=body,
                title=request.chat_title,
                source_kind=request.platform,
                language=request.language,
                extra_metadata=extra_metadata,
            )
        else:
            document = await service.add_text_source(
                record.package_id,
                content=body,
                title=request.chat_title,
                source_kind=request.platform,
                language=request.language,
                extra_metadata=extra_metadata,
            )
        await update_handoff_status(request.code, "done", document.id)
        logger.info(
            "[ChatHandoff] Ingested doc_id=%s package=%s user=%s",
            document.id,
            record.package_id,
            current_user.id,
        )
        return _document_to_response(document)
    except ValueError as exc:
        await update_handoff_status(request.code, "failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DATABASE_ERRORS as exc:
        await update_handoff_status(request.code, "failed")
        logger.error("[ChatHandoff] ingest failed: %s", exc)
        raise HTTPException(status_code=500, detail="Ingest failed") from exc
