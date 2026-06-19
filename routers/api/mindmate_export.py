"""
MindMate 记录导出 — admin API to view/export Dify conversation history.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import io
import json
import logging
import time
import zipfile
from typing import List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import Organization, User
from models.domain.messages import Language, Messages
from routers.auth.dependencies import get_language_dependency, require_mindmate_export_access
from services.auth.security_logger import security_log
from services.dify.export.collect_service import (
    collect_conversation_summaries,
    collect_messages_for_summaries,
    fetch_conversation_bubbles,
    paginate_summaries,
)
from services.dify.export.endpoints import resolve_endpoint_for_message_fetch
from services.dify.export.export_config import LIST_PAGE_DEFAULT, LIST_PAGE_MAX
from services.dify.export.export_routing import should_use_background_job
from services.dify.export.target_resolution import (
    ExportScope,
    build_export_targets,
    count_export_users,
    export_scope_label,
    load_export_users,
    user_label,
)
from services.dify.export.transcript import ExportBundle, render_html
from services.dify.export.verify import (
    build_scope_manifest,
    embed_report_in_bundle,
    final_job_status,
    reconcile_collection,
    verify_artifact_integrity,
)
from services.dify.org_mindmate_client import resolve_org_dify_servers_strict
from utils.auth.request_helpers import get_client_ip
from utils.db.session_open import release_open_transaction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/mindmate-export", tags=["admin", "mindmate-export"])


def _parse_scope(raw: Optional[str], lang: Language) -> ExportScope:
    if raw in ("all", "whole", "users"):
        return cast(ExportScope, raw)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=Messages.error("invalid_request", lang),
    )


def _parse_user_ids(raw: Optional[str]) -> Optional[List[int]]:
    if not raw:
        return None
    ids: List[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            ids.append(int(token))
        except ValueError as exc:
            raise ValueError(f"invalid user id: {token}") from exc
    return ids or None


def _validate_epoch_range(
    start: Optional[int],
    end: Optional[int],
    lang: Language,
) -> None:
    if start is not None and start < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang),
        )
    if end is not None and end < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang),
        )
    if start is not None and end is not None and start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang),
        )


def _require_org_for_scope(scope: ExportScope, org_id: Optional[int], lang: Language) -> Optional[int]:
    if scope == "all":
        return None
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("missing_required_fields", lang, "org_id"),
        )
    return int(org_id)


async def _ensure_org_exists(db: AsyncSession, org_id: int, lang: Language) -> Organization:
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("organization_not_found", lang, org_id),
        )
    return org


async def _load_org_name(db: AsyncSession, org_id: Optional[int]) -> str:
    if org_id is None:
        return "All organizations"
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if org is None:
        return f"Org {org_id}"
    display = (getattr(org, "display_name", None) or "").strip()
    return display or (getattr(org, "name", None) or f"Org {org_id}")


def _ensure_sync_download_allowed(report, lang: Language) -> None:
    if final_job_status(report) == "failed_verification":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=Messages.error("invalid_request", lang),
        )


async def _resolve_export_context(
    db: AsyncSession,
    *,
    scope: ExportScope,
    org_id: Optional[int],
    user_ids: Optional[List[int]],
    start: Optional[int],
    end: Optional[int],
    lang: Language,
):
    resolved_org = _require_org_for_scope(scope, org_id, lang)
    _validate_epoch_range(start, end, lang)
    if scope in ("whole", "users") and resolved_org is not None:
        await _ensure_org_exists(db, resolved_org, lang)
    if scope == "users" and not user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("missing_required_fields", lang, "user_ids"),
        )
    users = await load_export_users(db, scope, resolved_org, user_ids)
    users_total = await count_export_users(db, scope, resolved_org, user_ids)
    if scope == "users" and user_ids and not users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang),
        )
    target_result = await build_export_targets(
        db,
        users,
        scope=scope,
        org_id=resolved_org,
        start=start,
        end=end,
    )
    strict_org = scope != "all"
    return resolved_org, users, users_total, target_result, strict_org


@router.get("/users")
async def list_export_users(
    request: Request,
    org_id: Optional[int] = Query(default=None),
    current_user: User = Depends(require_mindmate_export_access),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """List org members eligible for conversation export."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("missing_required_fields", lang, "org_id"),
        )
    resolved_org = int(org_id)
    await _ensure_org_exists(db, resolved_org, lang)
    rows = (
        await db.execute(
            select(User).where(User.organization_id == resolved_org).order_by(User.id.desc())
        )
    ).scalars().all()
    security_log.data_access(
        "MindMate export user list",
        user_id=int(current_user.id),
        ip=get_client_ip(request),
        org_id=resolved_org,
        users=len(rows),
    )
    return {
        "organization_id": resolved_org,
        "users": [{"id": int(user_row.id), "label": user_label(user_row)} for user_row in rows],
    }


@router.get("/conversations")
async def list_export_conversations(
    request: Request,
    scope: Optional[str] = Query(default="whole"),
    org_id: Optional[int] = Query(default=None),
    user_ids: Optional[str] = Query(default=None),
    start: Optional[int] = Query(default=None),
    end: Optional[int] = Query(default=None),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=LIST_PAGE_DEFAULT, ge=1, le=LIST_PAGE_MAX),
    current_user: User = Depends(require_mindmate_export_access),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """List conversations for the selected export scope (paginated)."""
    export_scope = _parse_scope(scope, lang)
    try:
        parsed_ids = _parse_user_ids(user_ids)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang),
        ) from exc
    resolved_org, users, users_total, target_result, strict_org = await _resolve_export_context(
        db,
        scope=export_scope,
        org_id=org_id,
        user_ids=parsed_ids,
        start=start,
        end=end,
        lang=lang,
    )
    await release_open_transaction(db)
    use_job = should_use_background_job(export_scope, users_total)
    collected = await collect_conversation_summaries(
        db,
        target_result.targets,
        start=start,
        end=end,
        strict_org=strict_org,
    )
    page, next_cursor, has_more = paginate_summaries(
        collected.summaries,
        cursor=cursor,
        limit=limit,
    )
    warnings = list(target_result.warnings) + collected.warnings
    security_log.data_access(
        "MindMate export conversation list",
        user_id=int(current_user.id),
        ip=get_client_ip(request),
        org_id=resolved_org,
        scope=export_scope,
        users=len(users),
        targets=len(target_result.targets),
        conversations=len(collected.summaries),
    )
    return {
        "organization_id": resolved_org,
        "scope": export_scope,
        "users_total": users_total,
        "users_scanned": len(users),
        "targets_count": len(target_result.targets),
        "conversations_total": len(collected.summaries),
        "partial_failures": collected.partial_failures,
        "requires_job": use_job,
        "warnings": warnings,
        "conversations": [summary.to_dict() for summary in page],
        "next_cursor": next_cursor,
        "has_more": has_more,
        "verification_status": "gaps" if collected.partial_failures else "pass",
    }


@router.get("/conversations/{conversation_id}/messages")
async def get_export_conversation_messages(
    request: Request,
    conversation_id: str,
    server: int = Query(...),
    dify_user: str = Query(...),
    org_id: int = Query(...),
    channel: str = Query(default="web"),
    mindbot_config_id: Optional[int] = Query(default=None),
    current_user: User = Depends(require_mindmate_export_access),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Fetch a single conversation's bubbles from the endpoint it lives on."""
    resolved_org = int(org_id)
    org = await _ensure_org_exists(db, resolved_org, lang)
    if channel == "web":
        servers = await resolve_org_dify_servers_strict(resolved_org)
        valid_servers = {item.server for item in servers}
        if valid_servers and int(server) not in valid_servers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=Messages.error("invalid_request", lang),
            )
    endpoint = await resolve_endpoint_for_message_fetch(
        db,
        org,
        channel=channel,
        server=int(server),
        mindbot_config_id=mindbot_config_id,
        dify_user=dify_user,
        strict_org=True,
    )
    if endpoint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("invalid_request", lang),
        )
    await release_open_transaction(db)
    bubbles, complete, warning = await fetch_conversation_bubbles(endpoint, conversation_id, dify_user)
    security_log.data_access(
        "MindMate export conversation transcript",
        user_id=int(current_user.id),
        ip=get_client_ip(request),
        org_id=resolved_org,
        conversation_id=conversation_id[:64],
        dify_user=dify_user[:64],
        channel=channel,
    )
    return {
        "conversation_id": conversation_id,
        "server": int(server),
        "organization_id": resolved_org,
        "mindbot_config_id": mindbot_config_id,
        "messages_complete": complete,
        "warning": warning,
        "bubbles": [bubble.to_dict() for bubble in bubbles],
    }


@router.get("/download")
async def download_export(
    request: Request,
    scope: Optional[str] = Query(default="whole"),
    org_id: Optional[int] = Query(default=None),
    user_ids: Optional[str] = Query(default=None),
    start: Optional[int] = Query(default=None),
    end: Optional[int] = Query(default=None),
    export_format: str = Query(default="html", alias="format"),
    current_user: User = Depends(require_mindmate_export_access),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """Download conversation history as HTML, JSON, or ZIP (sync, small scope only)."""
    fmt = (export_format or "html").lower()
    if fmt not in {"html", "json", "zip"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang),
        )
    export_scope = _parse_scope(scope, lang)
    try:
        parsed_ids = _parse_user_ids(user_ids)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang),
        ) from exc
    resolved_org, users, users_total, target_result, strict_org = await _resolve_export_context(
        db,
        scope=export_scope,
        org_id=org_id,
        user_ids=parsed_ids,
        start=start,
        end=end,
        lang=lang,
    )
    if should_use_background_job(export_scope, users_total):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang),
        )
    org_name = await _load_org_name(db, resolved_org)
    scope_text = export_scope_label(export_scope, resolved_org, len(users))
    await release_open_transaction(db)

    manifest = build_scope_manifest(
        scope=export_scope,
        org_id=resolved_org,
        user_ids=parsed_ids,
        start=start,
        end=end,
        users_total=users_total,
        targets_total=len(target_result.targets),
        generated_at=int(time.time()),
    )
    collected = await collect_conversation_summaries(
        db,
        target_result.targets,
        start=start,
        end=end,
        strict_org=strict_org,
    )
    conversations, msg_warnings, messages_complete = await collect_messages_for_summaries(
        db,
        collected.summaries,
        strict_org=strict_org,
    )
    report = reconcile_collection(
        manifest,
        users_done=len(users),
        targets_done=len(target_result.targets),
        collect_result=collected,
        messages_complete=messages_complete,
    )
    report.actual["messages"] = sum(len(conv.bubbles) for conv in conversations)

    bundle = ExportBundle(
        organization_id=resolved_org,
        organization_name=org_name,
        scope=scope_text,
        conversations=conversations,
        warnings=list(target_result.warnings) + collected.warnings + msg_warnings,
        partial_failures=collected.partial_failures,
    )
    embed_report_in_bundle(bundle, report)

    if resolved_org is None:
        base_name = "mindmate-export-all-orgs"
    else:
        base_name = f"mindmate-export-org{resolved_org}"

    verification_status = report.status
    export_headers = {
        "X-MG-Export-Verification": verification_status,
        "X-MG-Export-Users-Total": str(users_total),
        "X-MG-Export-Users-Loaded": str(len(users)),
        "X-MG-Export-Partial-Failures": str(collected.partial_failures),
    }

    if fmt == "json":
        content = bundle.to_json().encode("utf-8")
        media_type = "application/json; charset=utf-8"
        filename = f"{base_name}.json"
    elif fmt == "html":
        content = render_html(bundle).encode("utf-8")
        media_type = "text/html; charset=utf-8"
        filename = f"{base_name}.html"
    else:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"{base_name}.json", bundle.to_json())
            archive.writestr(f"{base_name}.html", render_html(bundle))
            archive.writestr(
                "verification.json",
                json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            )
        content = buffer.getvalue()
        media_type = "application/zip"
        filename = f"{base_name}.zip"

    report = verify_artifact_integrity(
        report,
        artifact_bytes=content,
        verified_at=int(time.time()),
    )
    _ensure_sync_download_allowed(report, lang)
    export_headers["X-MG-Export-Sha256"] = report.artifact_sha256 or ""

    security_log.data_export(
        "MindMate conversation export",
        user_id=int(current_user.id),
        ip=get_client_ip(request),
        org_id=resolved_org,
        scope=scope_text,
        fmt=fmt,
        conversations=len(bundle.conversations),
        targets=len(target_result.targets),
        verification_status=verification_status,
        gaps_count=len(report.gaps),
        users_expected=users_total,
        users_actual=len(users),
        start=start,
        end=end,
    )
    logger.info(
        "[MindMateExport] sync download user=%s org=%s scope=%s fmt=%s "
        "conversations=%s verification=%s",
        current_user.id,
        resolved_org,
        export_scope,
        fmt,
        len(bundle.conversations),
        verification_status,
    )

    return Response(
        content=content,
        media_type=media_type,
        headers={
            **export_headers,
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
