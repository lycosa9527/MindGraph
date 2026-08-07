"""Orchestrate diagram → lesson plan → Wan 组图 → COS → conversation slides."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Optional

from sqlalchemy import select

from models.domain.diagrams import Diagram
from models.domain.zhihui import ZhihuiConversation
from repositories.zhihui_repo import ZhihuiConversationRepository, ZhihuiGenerationRepository
from services.infrastructure.http.error_handler import LLMServiceError
from services.redis.redis_token_buffer import get_token_tracker
from services.t2i.wan_image_client import (
    DEFAULT_WAN_IMAGE_MODEL,
    DEFAULT_WAN_SIZE,
    download_image_bytes,
    generate_wan_image_batch,
)
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from services.zhihui.focus import resolve_frame_focus_node_ids
from services.zhihui.lesson_planner import plan_lesson_from_outline, planner_model_id
from services.zhihui.outline import extract_mindmap_outline, is_mindmap_type
from services.zhihui.storage import build_generation_key, delete_key, put_bytes
from services.zhihui.wan_prompt_shell import plan_batches_to_wan_jobs
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_PIPELINE_ERRORS = BACKGROUND_INFRA_ERRORS + DATABASE_ERRORS + (LLMServiceError,)
_TERMINAL_OK = frozenset({"complete"})
_TERMINAL_STOP = frozenset({"cancelled", "failed"})
# External stale sweep marks ``partial``/``failed``; user delete marks ``cancelled``.
_STOP_MID_RUN = frozenset({"cancelled", "failed", "partial"})


async def _load_diagram(diagram_id: str) -> Diagram:
    async with system_rls_session() as db:
        result = await db.execute(select(Diagram).where(Diagram.id == diagram_id, ~Diagram.is_deleted))
        diagram = result.scalar_one_or_none()
        if diagram is None:
            raise ValueError("Diagram not found")
        return diagram


async def _set_status(
    conversation_id: str,
    *,
    status: str,
    progress: Optional[dict[str, Any]] = None,
    error_message: Optional[str] = None,
    style_seed: Optional[str] = None,
    lesson_plan_json: Optional[dict[str, Any]] = None,
    clear_error: bool = False,
) -> None:
    async with system_rls_session() as db:
        repo = ZhihuiConversationRepository(db)
        await repo.update_conversation(
            conversation_id,
            status=status,
            progress=progress,
            error_message=error_message,
            style_seed=style_seed,
            lesson_plan_json=lesson_plan_json,
            clear_error=clear_error,
            commit=True,
        )


async def _conversation_status(conversation_id: str) -> Optional[str]:
    async with system_rls_session() as db:
        repo = ZhihuiConversationRepository(db)
        row = await repo.get_by_uuid(conversation_id)
        return row.status if row else None


async def _mark_terminal_from_error(conversation_id: str, exc: BaseException) -> str:
    """Set failed/partial from any pipeline exception; return final status."""
    async with system_rls_session() as db:
        gen_repo = ZhihuiGenerationRepository(db)
        existing = await gen_repo.list_by_conversation(conversation_id)
        status = "partial" if existing else "failed"
        conv_repo = ZhihuiConversationRepository(db)
        await conv_repo.update_conversation(
            conversation_id,
            status=status,
            error_message=str(exc)[:2000],
            progress={"phase": status, "slide_count": len(existing)},
            commit=True,
        )
        return status


async def _track_usage(
    *,
    model_alias: str,
    usage: Optional[dict[str, Any]],
    request_type: str,
    user_id: Optional[int],
    organization_id: Optional[int],
    conversation_id: str,
    response_time: float,
    success: bool,
) -> None:
    usage_data = usage or {}
    input_tokens = int(usage_data.get("prompt_tokens") or usage_data.get("input_tokens") or 0)
    output_tokens = int(usage_data.get("completion_tokens") or usage_data.get("output_tokens") or 0)
    total_tokens = usage_data.get("total_tokens")
    if total_tokens is None:
        total_tokens = input_tokens + output_tokens
    try:
        tracker = get_token_tracker()
        await tracker.track_usage(
            model_alias=model_alias,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=int(total_tokens),
            request_type=request_type,
            user_id=user_id,
            organization_id=organization_id,
            conversation_id=conversation_id,
            endpoint_path="/api/zhihui/diagram-lesson",
            response_time=response_time,
            success=success,
        )
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[ZhiHui] Token tracking failed: %s", exc)


async def _persist_slide(
    *,
    conversation_id: str,
    language: str,
    user_id: Optional[int],
    organization_id: Optional[int],
    prompt: str,
    image_url: str,
    size: Optional[str],
    slide_index: int,
    slide_title: Optional[str],
    focus_node_ids: Optional[list[str]],
) -> None:
    image_bytes = await download_image_bytes(image_url)
    generation_id = str(uuid.uuid4())
    logical_key = build_generation_key(generation_id=generation_id, suffix=".png")
    await put_bytes(logical_key, image_bytes, content_type="image/png")
    try:
        async with system_rls_session() as db:
            gen_repo = ZhihuiGenerationRepository(db)
            await gen_repo.create_generation(
                generation_id=generation_id,
                prompt=prompt[:4000],
                cos_logical_key=logical_key,
                language=language,
                user_id=user_id,
                organization_id=organization_id,
                conversation_id=conversation_id,
                content_type="image/png",
                size=size or DEFAULT_WAN_SIZE,
                slide_index=slide_index,
                slide_title=slide_title[:256] if slide_title else None,
                focus_node_ids=focus_node_ids,
                commit=True,
            )
    except DATABASE_ERRORS:
        await delete_key(logical_key)
        raise


async def _wipe_generations(conversation_id: str) -> None:
    async with system_rls_session() as db:
        gen_repo = ZhihuiGenerationRepository(db)
        gens = list(await gen_repo.list_by_conversation(conversation_id))
        keys = [gen.cos_logical_key for gen in gens if gen.cos_logical_key]
        for gen in gens:
            await gen_repo.delete_generation(gen.id, commit=False)
        await db.commit()
    for key in keys:
        await delete_key(key)


def next_slide_index(gens: list[Any]) -> int:
    """Resume index after the highest persisted ``slide_index``."""
    indexes = [int(gen.slide_index) for gen in gens if getattr(gen, "slide_index", None) is not None]
    if not indexes:
        return len(gens)
    return max(indexes) + 1


async def run_diagram_lesson_deck(
    conversation_id: str,
    *,
    celery_task_id: Optional[str] = None,
) -> bool:
    """
    Background pipeline for one diagram-lesson conversation.

    Idempotent resume: if ``lesson_plan_json`` exists, skip planning and continue
    from ``max(slide_index)+1``. Returns True on complete, False otherwise.
    """
    async with system_rls_session() as db:
        conv_repo = ZhihuiConversationRepository(db)
        claimed = await conv_repo.claim_for_run(
            conversation_id,
            celery_task_id=celery_task_id,
        )
        if claimed is None:
            logger.error("[ZhiHui] Conversation missing id=%s", conversation_id)
            return False
        if claimed.status in _TERMINAL_OK:
            return True
        if claimed.status in _TERMINAL_STOP:
            return False
        if not claimed.diagram_id:
            await conv_repo.update_conversation(
                conversation_id,
                status="failed",
                error_message="Missing diagram_id",
                commit=True,
            )
            return False
        diagram_id = claimed.diagram_id
        language = claimed.language or "zh"
        user_id = claimed.user_id
        organization_id = claimed.organization_id
        existing_plan = claimed.lesson_plan_json if isinstance(claimed.lesson_plan_json, dict) else None
        gen_repo = ZhihuiGenerationRepository(db)
        existing_gens = list(await gen_repo.list_by_conversation(conversation_id))

    slide_index = next_slide_index(existing_gens)
    saved = len(existing_gens)
    plan = existing_plan
    outline = None

    try:
        diagram = await _load_diagram(diagram_id)
        if not is_mindmap_type(diagram.diagram_type):
            raise ValueError("Only mind maps are supported for 图示生图")
        outline = extract_mindmap_outline(
            diagram.spec,
            diagram_type=diagram.diagram_type,
            fallback_title=diagram.title or "",
        )

        if plan is None:
            if existing_gens:
                await _wipe_generations(conversation_id)
                slide_index = 0
                saved = 0
            await _set_status(
                conversation_id,
                status="planning",
                progress={"phase": "planning"},
                clear_error=True,
            )
            started = time.monotonic()
            plan, usage = await plan_lesson_from_outline(
                outline,
                language=language,
                diagram_title=diagram.title or outline.topic,
                user_id=user_id,
                organization_id=organization_id,
            )
            await _track_usage(
                model_alias="qwen",
                usage=usage,
                request_type="zhihui_lesson_plan",
                user_id=user_id,
                organization_id=organization_id,
                conversation_id=conversation_id,
                response_time=time.monotonic() - started,
                success=True,
            )

        jobs = plan_batches_to_wan_jobs(plan)
        if not jobs:
            raise ValueError("Lesson plan produced no image batches")

        await _set_status(
            conversation_id,
            status="generating",
            progress={
                "phase": "generating",
                "batch_index": 0,
                "batch_total": len(jobs),
                "slide_count": saved,
            },
            style_seed=str(plan.get("style_seed") or ""),
            lesson_plan_json=plan,
            clear_error=True,
        )

        frames_done = slide_index
        for batch_index, job in enumerate(jobs):
            status_now = await _conversation_status(conversation_id)
            if status_now in _STOP_MID_RUN:
                logger.info(
                    "[ZhiHui] Stop mid-run conversation=%s status=%s",
                    conversation_id,
                    status_now,
                )
                return False

            frames = job.get("frames") or []
            batch_start = frames_done
            batch_end = frames_done + len(frames)
            if slide_index >= batch_end:
                frames_done = batch_end
                continue
            skip_in_batch = max(0, slide_index - batch_start)

            await _set_status(
                conversation_id,
                status="generating",
                progress={
                    "phase": "generating",
                    "batch_index": batch_index + 1,
                    "batch_total": len(jobs),
                    "slide_count": saved,
                },
            )
            wan_started = time.monotonic()
            batch = await generate_wan_image_batch(
                prompt=job["prompt"],
                model=DEFAULT_WAN_IMAGE_MODEL,
                n=int(job["n"]),
                size=DEFAULT_WAN_SIZE,
                watermark=False,
                enable_sequential=True,
            )
            await _track_usage(
                model_alias="wan",
                usage=batch.usage,
                request_type="zhihui_wan_batch",
                user_id=user_id,
                organization_id=organization_id,
                conversation_id=conversation_id,
                response_time=time.monotonic() - wan_started,
                success=True,
            )

            image_urls = list(batch.image_urls or [])
            batch_role = str(job.get("batch_role") or "")
            for url_index, image_url in enumerate(image_urls):
                if url_index < skip_in_batch:
                    continue
                frame = frames[url_index] if url_index < len(frames) else {}
                title = ""
                focus_branch = None
                focus_child = ""
                frame_role = ""
                if isinstance(frame, dict):
                    title = str(frame.get("title") or "").strip()
                    focus_branch = frame.get("focus_branch")
                    focus_child = str(frame.get("focus_child") or "").strip()
                    frame_role = str(frame.get("frame_role") or "").strip().lower()
                # Child/conflict slides store the child cue so canvas highlight tracks the PPT.
                if focus_child and frame_role != "branch_intro":
                    focus_ids = [focus_child]
                else:
                    focus_ids = resolve_frame_focus_node_ids(
                        outline,
                        slide_index=slide_index,
                        batch_role=batch_role,
                        focus_branch=focus_branch,
                    )
                await _persist_slide(
                    conversation_id=conversation_id,
                    language=language,
                    user_id=user_id,
                    organization_id=organization_id,
                    prompt=str(job.get("prompt") or ""),
                    image_url=image_url,
                    size=batch.size or DEFAULT_WAN_SIZE,
                    slide_index=slide_index,
                    slide_title=title or None,
                    focus_node_ids=focus_ids,
                )
                slide_index += 1
                saved += 1

            if len(image_urls) < len(frames):
                await _set_status(
                    conversation_id,
                    status="partial",
                    progress={
                        "phase": "partial",
                        "batch_index": batch_index + 1,
                        "batch_total": len(jobs),
                        "slide_count": saved,
                        "shortfall": True,
                    },
                    error_message=(f"Wan returned {len(image_urls)}/{len(frames)} images for batch {batch_index + 1}")[
                        :2000
                    ],
                )
                logger.warning(
                    "[ZhiHui] Incomplete Wan batch conversation=%s got=%s need=%s",
                    conversation_id,
                    len(image_urls),
                    len(frames),
                )
                return False

            frames_done = batch_end

        await _set_status(
            conversation_id,
            status="complete",
            progress={
                "phase": "complete",
                "batch_index": len(jobs),
                "batch_total": len(jobs),
                "slide_count": saved,
            },
            clear_error=True,
        )
        return True
    except _PIPELINE_ERRORS as exc:
        logger.exception("[ZhiHui] Lesson deck failed conversation=%s", conversation_id)
        await _mark_terminal_from_error(conversation_id, exc)
        return False


async def create_diagram_lesson_conversation(
    *,
    diagram_id: str,
    user_id: int,
    organization_id: Optional[int],
    language: str = "zh",
) -> ZhihuiConversation:
    """Validate diagram and create a queued conversation row."""
    diagram = await _load_diagram(diagram_id)
    if diagram.user_id != int(user_id):
        raise PermissionError("Diagram does not belong to user")
    if not is_mindmap_type(diagram.diagram_type):
        raise ValueError("Only mind maps are supported for 图示生图")
    extract_mindmap_outline(
        diagram.spec,
        diagram_type=diagram.diagram_type,
        fallback_title=diagram.title or "",
    )
    title = (diagram.title or "").strip() or "图示生图"
    async with system_rls_session() as db:
        conv_repo = ZhihuiConversationRepository(db)
        return await conv_repo.create_conversation(
            mode="diagram",
            title=title[:256],
            user_id=user_id,
            organization_id=organization_id,
            diagram_id=diagram.id,
            diagram_title=diagram.title,
            planner_model=planner_model_id(),
            image_model=DEFAULT_WAN_IMAGE_MODEL,
            status="queued",
            progress={"phase": "queued"},
            language=(language or "zh").strip() or "zh",
            commit=True,
        )
