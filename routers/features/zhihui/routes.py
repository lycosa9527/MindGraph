"""ZhiHui admin history + signed asset delivery."""

from __future__ import annotations

import asyncio
import logging
import mimetypes
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.celery import celery_app
from config.settings import config
from models.domain.auth import User
from repositories.zhihui_repo import ZhihuiConversationRepository, ZhihuiGenerationRepository
from routers.api.helpers import (
    build_public_zhihui_asset_url,
    verify_signed_url,
)
from routers.auth.dependencies import (
    get_async_db_with_request_rls,
    get_current_user,
    get_current_user_optional,
    require_panel_capability,
    require_panel_capability_short_lived,
)
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, FILE_IO_ERRORS
from services.zhihui.lesson_deck import create_diagram_lesson_conversation
from services.zhihui.storage import (
    aiter_bytes,
    cos_zhihui_enabled,
    create_presigned_get,
    delete_key,
    is_zhihui_logical_key,
    resolve_local_safe,
)
from tasks.zhihui_lesson_tasks import run_diagram_lesson_task
from utils.auth.admin_panel_permissions import CAP_FEATURE_ZHIHUI, user_panel_capabilities
from utils.auth.admin_scope import AdminScope
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

router = APIRouter()

_STALE_ACTIVE_MINUTES = 60


async def _sweep_stale_jobs(user_id: int) -> None:
    """Best-effort stale active-job cleanup for one user; revoke Celery tasks."""
    try:
        async with system_rls_session() as db:
            repo = ZhihuiConversationRepository(db)
            marked, task_ids = await repo.mark_stale_active_jobs(
                max_age_minutes=_STALE_ACTIVE_MINUTES,
                user_id=user_id,
            )
            if marked:
                logger.info(
                    "[ZhiHui] Marked %s stale active conversation(s) user=%s",
                    marked,
                    user_id,
                )
        for task_id in task_ids:
            try:
                await asyncio.to_thread(
                    celery_app.control.revoke,
                    task_id,
                    terminate=False,
                )
            except BACKGROUND_INFRA_ERRORS as rev_exc:
                logger.warning(
                    "[ZhiHui] Stale Celery revoke failed task=%s err=%s",
                    task_id,
                    rev_exc,
                )
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[ZhiHui] Stale sweep failed user=%s: %s", user_id, exc)


async def _enqueue_lesson_task(conversation_id: str) -> Optional[str]:
    """Enqueue Celery runner; return task id or raise HTTP 503."""
    try:
        async_result = run_diagram_lesson_task.delay(conversation_id)
        task_id = getattr(async_result, "id", None)
        logger.info(
            "[ZhiHui] Enqueued lesson task conversation=%s celery=%s",
            conversation_id,
            task_id,
        )
        return task_id if isinstance(task_id, str) else None
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[ZhiHui] Failed to enqueue lesson task: %s", exc)
        try:
            async with system_rls_session() as db:
                fail_repo = ZhihuiConversationRepository(db)
                await fail_repo.update_conversation(
                    conversation_id,
                    status="failed",
                    error_message=f"Failed to enqueue job: {exc}"[:2000],
                    commit=True,
                )
        except BACKGROUND_INFRA_ERRORS:
            pass
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Background worker unavailable",
        ) from exc


def _stable_asset_url(request: Request, logical_key: str) -> str:
    """
    Same-origin asset URL without rotating ``sig``/``exp``.

    Admin studio polls every few seconds; signed query strings change each
    response and force ``<img>`` reloads (broken-icon races). Cookie/JWT auth
    on ``GET /api/zhihui/assets/...`` already authorizes the browser.
    """
    return build_public_zhihui_asset_url(request, logical_key.lstrip("/"))


def _generation_payload(row: Any, request: Request) -> dict[str, Any]:
    """Serialize a generation row for admin history JSON."""
    return {
        "id": row.id,
        "prompt": row.prompt,
        "enhanced_prompt": row.enhanced_prompt,
        "language": row.language,
        "conversation_id": row.conversation_id,
        "dify_conversation_id": getattr(row, "dify_conversation_id", None),
        "dify_user_id": row.dify_user_id,
        "user_id": row.user_id,
        "organization_id": row.organization_id,
        "size": row.size,
        "content_type": row.content_type,
        "cos_logical_key": row.cos_logical_key,
        "slide_index": getattr(row, "slide_index", None),
        "slide_title": getattr(row, "slide_title", None),
        "focus_node_ids": getattr(row, "focus_node_ids", None),
        "image_url": _stable_asset_url(request, str(row.cos_logical_key)),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _conversation_list_item(
    row: Any,
    request: Request,
    *,
    cover_key: Optional[str],
    slide_count: int,
) -> dict[str, Any]:
    """Serialize a conversation for sidebar list."""
    cover_url = None
    if cover_key:
        cover_url = _stable_asset_url(request, cover_key)
    return {
        "id": row.id,
        "mode": row.mode,
        "title": row.title,
        "status": row.status,
        "progress": row.progress,
        "error_message": row.error_message,
        "diagram_id": row.diagram_id,
        "diagram_title": row.diagram_title,
        "language": row.language,
        "slide_count": slide_count,
        "cover_image_url": cover_url,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _require_zhihui_enabled() -> None:
    if not config.FEATURE_ZHIHUI:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ZhiHui disabled")


class DiagramLessonRequest(BaseModel):
    """Start a diagram→lesson PPT generation job."""

    diagram_id: str = Field(..., min_length=1, max_length=36)
    language: str = Field(default="zh", max_length=16)


@router.post("/diagram-lesson", status_code=status.HTTP_202_ACCEPTED)
async def start_diagram_lesson(
    body: DiagramLessonRequest,
    scope: AdminScope = Depends(require_panel_capability_short_lived(CAP_FEATURE_ZHIHUI)),
) -> dict[str, Any]:
    """Create conversation immediately and enqueue Celery lesson-deck job."""
    _require_zhihui_enabled()
    current_user = scope.actor
    user_id = int(current_user.id)
    await _sweep_stale_jobs(user_id)

    async with system_rls_session() as db:
        conv_repo = ZhihuiConversationRepository(db)
        active = await conv_repo.count_active_diagram_jobs(user_id)
        max_active = ZhihuiConversationRepository.max_active_diagram_jobs()
        if active >= max_active:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Too many active diagram lessons ({active}/{max_active}). Wait for a job to finish or delete it."
                ),
            )

    language = (body.language or "zh").strip() or "zh"
    org_id = getattr(current_user, "organization_id", None)
    try:
        conversation = await create_diagram_lesson_conversation(
            diagram_id=body.diagram_id.strip(),
            user_id=user_id,
            organization_id=int(org_id) if org_id is not None else None,
            language=language,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    logger.info(
        "[ZhiHui] Diagram lesson accepted conversation=%s diagram=%s user=%s lang=%s",
        conversation.id,
        body.diagram_id.strip(),
        user_id,
        language,
    )
    task_id = await _enqueue_lesson_task(conversation.id)
    if task_id:
        try:
            async with system_rls_session() as db:
                repo = ZhihuiConversationRepository(db)
                await repo.update_conversation(
                    conversation.id,
                    celery_task_id=str(task_id),
                    commit=True,
                )
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("[ZhiHui] Could not store celery_task_id: %s", exc)

    return {
        "conversation_id": conversation.id,
        "status": "queued",
        "celery_task_id": task_id,
    }


@router.post(
    "/conversations/{conversation_id}/resume",
    status_code=status.HTTP_202_ACCEPTED,
)
async def resume_diagram_lesson(
    conversation_id: str,
    scope: AdminScope = Depends(require_panel_capability_short_lived(CAP_FEATURE_ZHIHUI)),
) -> dict[str, Any]:
    """Re-enqueue a failed/partial diagram lesson that still has a lesson plan."""
    _require_zhihui_enabled()
    current_user = scope.actor
    user_id = int(current_user.id)
    await _sweep_stale_jobs(user_id)

    async with system_rls_session() as db:
        conv_repo = ZhihuiConversationRepository(db)
        row = await conv_repo.get_by_uuid(conversation_id)
        if row is None or row.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        if row.mode != "diagram":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only diagram conversations can be resumed",
            )
        if row.status not in ("failed", "partial"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conversation status is {row.status}, not resumable",
            )
        if not isinstance(row.lesson_plan_json, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No lesson plan to resume from",
            )
        active = await conv_repo.count_active_diagram_jobs(user_id)
        max_active = ZhihuiConversationRepository.max_active_diagram_jobs()
        if active >= max_active:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Too many active diagram lessons ({active}/{max_active}). Wait for a job to finish or delete it."
                ),
            )
        await conv_repo.update_conversation(
            conversation_id,
            status="queued",
            progress={"phase": "queued", "resumed": True},
            clear_error=True,
            commit=True,
        )

    task_id = await _enqueue_lesson_task(conversation_id)
    if task_id:
        try:
            async with system_rls_session() as db:
                repo = ZhihuiConversationRepository(db)
                await repo.update_conversation(
                    conversation_id,
                    celery_task_id=str(task_id),
                    commit=True,
                )
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("[ZhiHui] Could not store celery_task_id: %s", exc)

    return {
        "conversation_id": conversation_id,
        "status": "queued",
        "celery_task_id": task_id,
    }


@router.get("/conversations")
async def list_zhihui_conversations(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_FEATURE_ZHIHUI)),
) -> dict[str, Any]:
    """Paginated ZhiHui conversations for the current admin user."""
    _require_zhihui_enabled()
    user_id = int(current_user.id)
    await _sweep_stale_jobs(user_id)
    conv_repo = ZhihuiConversationRepository(db)
    gen_repo = ZhihuiGenerationRepository(db)
    rows = await conv_repo.list_recent(offset=offset, limit=limit, user_id=user_id)
    total = await conv_repo.count_conversations(user_id=user_id)
    meta = await gen_repo.cover_and_counts([row.id for row in rows])
    items: list[dict[str, Any]] = []
    for row in rows:
        cover, slide_count = meta.get(row.id, (None, 0))
        items.append(
            _conversation_list_item(
                row,
                request,
                cover_key=cover,
                slide_count=slide_count,
            )
        )
    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/conversations/{conversation_id}")
async def get_zhihui_conversation(
    conversation_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_FEATURE_ZHIHUI)),
) -> dict[str, Any]:
    """Conversation detail with ordered generations (poll target)."""
    _require_zhihui_enabled()
    conv_repo = ZhihuiConversationRepository(db)
    gen_repo = ZhihuiGenerationRepository(db)
    row = await conv_repo.get_by_uuid(conversation_id)
    if row is None or row.user_id != int(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    gens = await gen_repo.list_by_conversation(conversation_id)
    cover = gens[0].cos_logical_key if gens else None
    payload = _conversation_list_item(
        row,
        request,
        cover_key=cover,
        slide_count=len(gens),
    )
    payload.update(
        {
            "style_seed": row.style_seed,
            "planner_model": row.planner_model,
            "image_model": row.image_model,
            "lesson_plan_json": row.lesson_plan_json,
            "celery_task_id": row.celery_task_id,
            "generations": [_generation_payload(gen, request) for gen in gens],
        }
    )
    return payload


@router.delete("/conversations/{conversation_id}")
async def delete_zhihui_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_FEATURE_ZHIHUI)),
) -> dict[str, str]:
    """Cancel in-flight work, then delete conversation, children, and COS objects."""
    _require_zhihui_enabled()
    conv_repo = ZhihuiConversationRepository(db)
    gen_repo = ZhihuiGenerationRepository(db)
    row = await conv_repo.get_by_uuid(conversation_id)
    if row is None or row.user_id != int(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    task_id = row.celery_task_id
    if row.status in ("queued", "planning", "generating"):
        await conv_repo.update_conversation(
            conversation_id,
            status="cancelled",
            progress={"phase": "cancelled"},
            error_message="Cancelled by user",
            commit=True,
        )

    if task_id:
        try:
            await asyncio.to_thread(
                celery_app.control.revoke,
                task_id,
                terminate=False,
            )
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("[ZhiHui] Celery revoke failed task=%s err=%s", task_id, exc)

    gens = await gen_repo.list_by_conversation(conversation_id)
    keys = [gen.cos_logical_key for gen in gens if gen.cos_logical_key]
    deleted = await conv_repo.delete_conversation(conversation_id, commit=True)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    for key in keys:
        await delete_key(key)
    return {"id": conversation_id, "status": "deleted"}


@router.get("/history")
async def list_zhihui_history(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_FEATURE_ZHIHUI)),
) -> dict[str, Any]:
    """Legacy flat generation list — prefer ``/conversations``."""
    return await list_zhihui_conversations(
        request=request,
        offset=offset,
        limit=limit,
        current_user=current_user,
        db=db,
        _scope=_scope,
    )


@router.delete("/history/{generation_id}")
async def delete_zhihui_history(
    generation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
    _scope: AdminScope = Depends(require_panel_capability(CAP_FEATURE_ZHIHUI)),
) -> dict[str, str]:
    """Delete a generation row and its COS/local object (legacy)."""
    _require_zhihui_enabled()
    repo = ZhihuiGenerationRepository(db)
    row = await repo.get_by_uuid(generation_id)
    if row is None:
        return await delete_zhihui_conversation(
            conversation_id=generation_id,
            current_user=current_user,
            db=db,
            _scope=_scope,
        )
    if row.user_id != int(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    logical_key = row.cos_logical_key
    deleted = await repo.delete_generation(generation_id, commit=True)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await delete_key(logical_key)
    return {"id": generation_id, "status": "deleted"}


@router.get("/assets/{asset_path:path}")
async def download_zhihui_asset(
    asset_path: str,
    sig: Optional[str] = None,
    exp: Optional[int] = None,
    proxy: bool = Query(False),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Serve ZhiHui images.

    Access: valid signed query (Dify markdown) or authenticated admin JWT.
    COS default: 302 to short-TTL presigned GET; ``proxy=1`` streams bytes.
    """
    normalized = asset_path.lstrip("/").replace("\\", "/")
    if "?" in normalized:
        normalized = normalized.split("?", 1)[0]
    if not is_zhihui_logical_key(normalized):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    signed_ok = bool(sig and exp and verify_signed_url(normalized, sig, exp))
    admin_ok = current_user is not None and CAP_FEATURE_ZHIHUI in user_panel_capabilities(current_user)
    if not signed_ok and not admin_ok:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired image URL")

    filename = Path(normalized).name
    media_type, _ = mimetypes.guess_type(filename)
    if not media_type:
        media_type = "image/jpeg"
    disposition = f'inline; filename="{filename}"'

    if proxy or not cos_zhihui_enabled():
        if not cos_zhihui_enabled():
            try:
                path = resolve_local_safe(normalized)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
            if not path.is_file():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
            return FileResponse(
                path=str(path),
                media_type=media_type,
                filename=filename,
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Content-Disposition": disposition,
                    "X-Content-Type-Options": "nosniff",
                },
            )

        async def _stream():
            async for chunk in aiter_bytes(normalized):
                yield chunk

        return StreamingResponse(
            _stream(),
            media_type=media_type,
            headers={
                "Cache-Control": "public, max-age=86400",
                "Content-Disposition": disposition,
                "X-Content-Type-Options": "nosniff",
            },
        )

    url = create_presigned_get(normalized, filename=filename)
    if url:
        return RedirectResponse(
            url=url,
            status_code=status.HTTP_302_FOUND,
            headers={
                # Do not cache the redirect: COS presign TTL is short; stable
                # same-origin ``image_url`` already stops ``<img>`` poll thrash.
                "Cache-Control": "private, no-store",
            },
        )

    # Fallback stream if presign failed
    try:
        body = b""
        async for chunk in aiter_bytes(normalized):
            body += chunk
        if not body:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        return Response(
            content=body,
            media_type=media_type,
            headers={
                "Cache-Control": "public, max-age=86400",
                "Content-Disposition": disposition,
                "X-Content-Type-Options": "nosniff",
            },
        )
    except FILE_IO_ERRORS as exc:
        logger.warning("[ZhiHui] Asset read failed key=%s err=%s", normalized, exc)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
