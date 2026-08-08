"""Orchestrate diagram → lesson plan → Wan 组图 → COS → conversation slides."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

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
from services.zhihui.lesson_lease import (
    LeaseLost,
    mark_terminal_from_error,
    require_run_lease,
    set_status_with_lease,
)
from services.zhihui.lesson_planner import (
    normalize_lesson_plan_to_outline,
    plan_lesson_from_outline,
    planner_model_id,
)
from services.zhihui.outline import MindMapOutline, extract_mindmap_outline, is_mindmap_type
from services.zhihui.storage import build_generation_key, delete_key, put_bytes
from services.zhihui.storage.backend import STORAGE_LOCAL, storage_backend
from services.zhihui.wan_prompt_shell import build_wan_batch_prompt, plan_batches_to_wan_jobs
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_PIPELINE_ERRORS = BACKGROUND_INFRA_ERRORS + DATABASE_ERRORS + (LLMServiceError,)
_TERMINAL_OK = frozenset({"complete"})
_TERMINAL_STOP = frozenset({"cancelled", "failed"})


async def _load_diagram(diagram_id: str) -> Diagram:
    async with system_rls_session() as db:
        result = await db.execute(select(Diagram).where(Diagram.id == diagram_id, ~Diagram.is_deleted))
        diagram = result.scalar_one_or_none()
        if diagram is None:
            raise ValueError("Diagram not found")
        return diagram


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


def _frame_title(frame: Any) -> str:
    if not isinstance(frame, dict):
        return ""
    return str(frame.get("title") or "").strip()


def _outline_branch_label(outline: Optional[MindMapOutline], hint: Any) -> str:
    """Human label like ``3/8「产品与货品策略」`` for logs."""
    if outline is None or not outline.branches:
        raw = str(hint or "").strip()
        return raw or "-"
    normalized = str(hint or "").strip().lower()
    if not normalized:
        return "-"
    total = len(outline.branches)
    for index, branch in enumerate(outline.branches, start=1):
        branch_id = (branch.id or "").strip()
        text = (branch.text or "").strip()
        if branch_id and branch_id.lower() == normalized:
            return f"{index}/{total}「{text or branch_id}」"
        if text and text.lower() == normalized:
            return f"{index}/{total}「{text}」"
    for index, branch in enumerate(outline.branches, start=1):
        text = (branch.text or "").strip()
        if not text:
            continue
        text_lower = text.lower()
        if normalized in text_lower or text_lower in normalized:
            return f"{index}/{total}「{text}」"
    return str(hint).strip() or "-"


def _batch_branch_labels(job: dict[str, Any], outline: Optional[MindMapOutline]) -> str:
    frames = job.get("frames") or []
    labels: list[str] = []
    seen: set[str] = set()
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        hint = str(frame.get("focus_branch") or "").strip()
        if not hint:
            continue
        label = _outline_branch_label(outline, hint)
        if label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return ",".join(labels) if labels else "-"


def _format_outline_branches(outline: MindMapOutline) -> str:
    parts: list[str] = []
    for index, branch in enumerate(outline.branches, start=1):
        branch_id = (branch.id or "").strip() or "-"
        text = (branch.text or "").strip() or "-"
        parts.append(f"{index}:{branch_id}/{text}")
    return " | ".join(parts)


def _summarize_jobs(
    jobs: list[dict[str, Any]],
    outline: Optional[MindMapOutline] = None,
) -> list[str]:
    """One short line per Wan batch for INFO logs."""
    lines: list[str] = []
    frames_done = 0
    for index, job in enumerate(jobs, start=1):
        frames = job.get("frames") or []
        batch_start = frames_done
        batch_end = frames_done + len(frames)
        titles = [_frame_title(frame) or f"frame-{offset + 1}" for offset, frame in enumerate(frames)]
        title_preview = " | ".join(titles[:6])
        if len(titles) > 6:
            title_preview = f"{title_preview} | …(+{len(titles) - 6})"
        branch_labels = _batch_branch_labels(job, outline)
        lines.append(
            f"batch={index}/{len(jobs)} role={job.get('batch_role') or '-'} "
            f"branch={branch_labels} slides={batch_start}-{max(batch_start, batch_end - 1)} "
            f"n={job.get('n')} frames={len(frames)} titles=[{title_preview}]"
        )
        frames_done = batch_end
    return lines


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
    teacher_script: Optional[str],
    focus_node_ids: Optional[list[str]],
) -> dict[str, Any]:
    """Download, store, and persist one slide; return debug metadata."""
    image_bytes = await download_image_bytes(image_url)
    generation_id = str(uuid.uuid4())
    logical_key = build_generation_key(generation_id=generation_id, suffix=".png")
    await put_bytes(logical_key, image_bytes, content_type="image/png")
    script = (teacher_script or "").strip() or None
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
                teacher_script=script[:4000] if script else None,
                focus_node_ids=focus_node_ids,
                commit=True,
            )
    except IntegrityError as exc:
        await delete_key(logical_key)
        raise LeaseLost(f"duplicate slide_index={slide_index}") from exc
    except DATABASE_ERRORS:
        await delete_key(logical_key)
        raise
    return {
        "generation_id": generation_id,
        "logical_key": logical_key,
        "bytes": len(image_bytes),
        "size": size or DEFAULT_WAN_SIZE,
        "source_host": image_url.split("?", 1)[0][:120],
    }


async def _wipe_generations(conversation_id: str) -> None:
    async with system_rls_session() as db:
        gen_repo = ZhihuiGenerationRepository(db)
        gens = list(await gen_repo.list_by_conversation(conversation_id))
        keys = [gen.cos_logical_key for gen in gens if gen.cos_logical_key]
        for gen in gens:
            await gen_repo.delete_generation(gen.id, commit=False)
        await db.commit()
    logger.info(
        "[ZhiHui] Wipe generations conversation=%s count=%s",
        conversation_id,
        len(keys),
    )
    for key in keys:
        await delete_key(key)


def next_slide_index(gens: list[Any]) -> int:
    """
    Resume cursor: first missing ``slide_index`` in ``0..max``, else ``max+1``.

    Backfills holes (e.g. indexes ``{0,1,3}`` → ``2``) so resume does not skip gaps.
    """
    indexes = sorted({int(gen.slide_index) for gen in gens if getattr(gen, "slide_index", None) is not None})
    if not indexes:
        return len(gens)
    expected = 0
    for index in indexes:
        if index < 0:
            continue
        if index > expected:
            return expected
        if index == expected:
            expected += 1
    return expected


def iter_batch_resume_ranges(
    batch_frame_counts: list[int],
    resume_slide: int,
) -> list[tuple[int, int, int, int]]:
    """
    Absolute slide ranges and skip offsets for each Wan batch.

    Returns list of ``(batch_start, batch_end, skip_in_batch, frames_in_batch)``.
    ``frames_done`` always starts at 0 so resume indexes align with the plan.
    """
    ranges: list[tuple[int, int, int, int]] = []
    frames_done = 0
    resume = max(0, int(resume_slide))
    for count in batch_frame_counts:
        frame_count = max(0, int(count))
        batch_start = frames_done
        batch_end = frames_done + frame_count
        if resume >= batch_end:
            skip_in_batch = frame_count
        else:
            skip_in_batch = max(0, resume - batch_start)
        ranges.append((batch_start, batch_end, skip_in_batch, frame_count))
        frames_done = batch_end
    return ranges


async def run_diagram_lesson_deck(
    conversation_id: str,
    *,
    celery_task_id: Optional[str] = None,
) -> bool:
    """
    Background pipeline for one diagram-lesson conversation.

    Idempotent resume: if ``lesson_plan_json`` exists, skip planning and continue
    from the first missing ``slide_index`` (or ``max+1``). Returns True on complete.
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
    pipeline_started = time.monotonic()

    logger.info(
        "[ZhiHui] Deck start conversation=%s diagram=%s celery=%s resume_slide=%s saved=%s has_plan=%s lang=%s user=%s",
        conversation_id,
        diagram_id,
        celery_task_id,
        slide_index,
        saved,
        plan is not None,
        language,
        user_id,
    )
    if storage_backend() == STORAGE_LOCAL:
        logger.warning(
            "[ZhiHui] Local disk storage active conversation=%s — "
            "enable COS_ZHIHUI for multi-host API/worker deployments",
            conversation_id,
        )

    try:
        diagram = await _load_diagram(diagram_id)
        if not is_mindmap_type(diagram.diagram_type):
            raise ValueError("Only mind maps are supported for 图示生图")
        outline = extract_mindmap_outline(
            diagram.spec,
            diagram_type=diagram.diagram_type,
            fallback_title=diagram.title or "",
        )
        logger.info(
            "[ZhiHui] Outline conversation=%s topic=%r branches=%s diagram_type=%s title=%r order=[%s]",
            conversation_id,
            outline.topic,
            len(outline.branches),
            diagram.diagram_type,
            diagram.title or "",
            _format_outline_branches(outline),
        )

        if plan is None:
            if existing_gens:
                await _wipe_generations(conversation_id)
                slide_index = 0
                saved = 0
            await set_status_with_lease(
                conversation_id,
                status="planning",
                progress={"phase": "planning", "planning_stage": "open", "branch_index": 0},
                clear_error=True,
                celery_task_id=celery_task_id,
            )
            logger.info("[ZhiHui] Planning start conversation=%s model=%s", conversation_id, planner_model_id())
            started = time.monotonic()

            async def _on_planning_progress(payload: dict[str, Any]) -> None:
                await require_run_lease(conversation_id, celery_task_id=celery_task_id)
                progress = {"phase": "planning", **payload}
                await set_status_with_lease(
                    conversation_id,
                    status="planning",
                    progress=progress,
                    celery_task_id=celery_task_id,
                )
                logger.info(
                    "[ZhiHui] Planning progress conversation=%s stage=%s branch=%s/%s",
                    conversation_id,
                    progress.get("planning_stage"),
                    progress.get("branch_index"),
                    progress.get("branch_total"),
                )

            plan, usage = await plan_lesson_from_outline(
                outline,
                language=language,
                diagram_title=diagram.title or outline.topic,
                user_id=user_id,
                organization_id=organization_id,
                on_progress=_on_planning_progress,
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
            usage_data = usage or {}
            logger.info(
                "[ZhiHui] Planning done conversation=%s elapsed=%.1fs tokens_in=%s tokens_out=%s style_seed=%r",
                conversation_id,
                time.monotonic() - started,
                usage_data.get("prompt_tokens") or usage_data.get("input_tokens"),
                usage_data.get("completion_tokens") or usage_data.get("output_tokens"),
                str(plan.get("style_seed") or "")[:80],
            )
        else:
            # Never permute a persisted plan after slides exist — slide_index
            # must stay aligned with the frozen frame order.
            if saved == 0:
                plan = normalize_lesson_plan_to_outline(plan, outline)
            logger.info(
                "[ZhiHui] Reusing lesson plan conversation=%s style_seed=%r saved=%s reorder=%s",
                conversation_id,
                str(plan.get("style_seed") or "")[:80],
                saved,
                saved == 0,
            )

        jobs = plan_batches_to_wan_jobs(plan)
        if not jobs:
            raise ValueError("Lesson plan produced no image batches")

        planned_frames = sum(len(job.get("frames") or []) for job in jobs)
        logger.info(
            "[ZhiHui] Wan jobs ready conversation=%s batches=%s planned_slides=%s resume_slide=%s model=%s size=%s",
            conversation_id,
            len(jobs),
            planned_frames,
            slide_index,
            DEFAULT_WAN_IMAGE_MODEL,
            DEFAULT_WAN_SIZE,
        )
        for line in _summarize_jobs(jobs, outline):
            logger.info("[ZhiHui] Plan %s conversation=%s", line, conversation_id)

        await set_status_with_lease(
            conversation_id,
            status="generating",
            progress={
                "phase": "generating",
                "batch_index": 1 if jobs else 0,
                "batch_total": len(jobs),
                "slide_count": saved,
                "planned_slides": planned_frames,
            },
            style_seed=str(plan.get("style_seed") or ""),
            lesson_plan_json=plan,
            clear_error=True,
            celery_task_id=celery_task_id,
        )

        batch_counts = [len(job.get("frames") or []) for job in jobs]
        resume_ranges = iter_batch_resume_ranges(batch_counts, slide_index)
        for batch_index, job in enumerate(jobs):
            await require_run_lease(conversation_id, celery_task_id=celery_task_id)

            frames = job.get("frames") or []
            batch_start, batch_end, skip_in_batch, _frame_count = resume_ranges[batch_index]
            if skip_in_batch >= len(frames):
                logger.info(
                    "[ZhiHui] Skip batch conversation=%s batch=%s/%s "
                    "branch=%s slides=%s-%s (already past resume_slide=%s)",
                    conversation_id,
                    batch_index + 1,
                    len(jobs),
                    _batch_branch_labels(job, outline),
                    batch_start,
                    batch_end - 1,
                    slide_index,
                )
                continue

            remaining_frames = frames[skip_in_batch:]
            need_count = len(remaining_frames)
            batch_role = str(job.get("batch_role") or "")
            frame_titles = [
                _frame_title(frame) or f"#{skip_in_batch + offset}" for offset, frame in enumerate(remaining_frames)
            ]
            branch_labels = _batch_branch_labels(job, outline)
            wan_prompt = (
                str(job.get("prompt") or "")
                if skip_in_batch == 0
                else build_wan_batch_prompt(
                    style_seed=str(job.get("style_seed") or ""),
                    frames=remaining_frames,
                    batch_role=batch_role,
                )
            )

            await set_status_with_lease(
                conversation_id,
                status="generating",
                progress={
                    "phase": "generating",
                    "batch_index": batch_index + 1,
                    "batch_total": len(jobs),
                    "slide_count": saved,
                    "planned_slides": planned_frames,
                    "batch_role": batch_role,
                },
                celery_task_id=celery_task_id,
            )
            logger.info(
                "[ZhiHui] Wan batch start conversation=%s batch=%s/%s role=%s "
                "branch=%s n=%s skip=%s resume_slide=%s slide_range=%s-%s titles=%s",
                conversation_id,
                batch_index + 1,
                len(jobs),
                batch_role or "-",
                branch_labels,
                need_count,
                skip_in_batch,
                slide_index,
                batch_start + skip_in_batch,
                batch_end - 1,
                frame_titles,
            )
            wan_started = time.monotonic()
            wan_log_context = f"conversation={conversation_id} batch={batch_index + 1}/{len(jobs)}"
            batch = await generate_wan_image_batch(
                prompt=wan_prompt,
                model=DEFAULT_WAN_IMAGE_MODEL,
                n=need_count,
                size=DEFAULT_WAN_SIZE,
                watermark=False,
                enable_sequential=True,
                log_context=wan_log_context,
            )
            wan_elapsed = time.monotonic() - wan_started
            await _track_usage(
                model_alias="wan",
                usage=batch.usage,
                request_type="zhihui_wan_batch",
                user_id=user_id,
                organization_id=organization_id,
                conversation_id=conversation_id,
                response_time=wan_elapsed,
                success=True,
            )

            image_urls = list(batch.image_urls or [])
            logger.info(
                "[ZhiHui] Wan batch result conversation=%s batch=%s/%s "
                "task_id=%s urls=%s need=%s elapsed=%.1fs size=%s",
                conversation_id,
                batch_index + 1,
                len(jobs),
                batch.task_id,
                len(image_urls),
                need_count,
                wan_elapsed,
                batch.size or DEFAULT_WAN_SIZE,
            )
            for url_index, image_url in enumerate(image_urls):
                if url_index >= need_count:
                    break
                await require_run_lease(conversation_id, celery_task_id=celery_task_id)
                frame_offset = skip_in_batch + url_index
                frame = frames[frame_offset] if frame_offset < len(frames) else {}
                title = ""
                teacher_script = ""
                focus_branch = None
                focus_child = ""
                frame_role = ""
                if isinstance(frame, dict):
                    title = str(frame.get("title") or "").strip()
                    teacher_script = str(frame.get("teacher_script") or "").strip()
                    if not teacher_script:
                        teacher_script = str(frame.get("learning_point") or "").strip()
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
                meta = await _persist_slide(
                    conversation_id=conversation_id,
                    language=language,
                    user_id=user_id,
                    organization_id=organization_id,
                    prompt=wan_prompt,
                    image_url=image_url,
                    size=batch.size or DEFAULT_WAN_SIZE,
                    slide_index=slide_index,
                    slide_title=title or None,
                    teacher_script=teacher_script or None,
                    focus_node_ids=focus_ids,
                )
                logger.info(
                    "[ZhiHui] Slide saved conversation=%s slide=%s/%s title=%r "
                    "role=%s batch=%s/%s batch_role=%s branch=%s focus=%s gen=%s key=%s "
                    "bytes=%s img_size=%s",
                    conversation_id,
                    slide_index + 1,
                    planned_frames,
                    title,
                    frame_role or "-",
                    batch_index + 1,
                    len(jobs),
                    batch_role or "-",
                    _outline_branch_label(outline, focus_branch),
                    focus_ids,
                    meta["generation_id"],
                    meta["logical_key"],
                    meta["bytes"],
                    meta["size"],
                )
                slide_index += 1
                saved += 1
                await set_status_with_lease(
                    conversation_id,
                    status="generating",
                    progress={
                        "phase": "generating",
                        "batch_index": batch_index + 1,
                        "batch_total": len(jobs),
                        "slide_count": saved,
                        "planned_slides": planned_frames,
                        "batch_role": batch_role,
                    },
                    celery_task_id=celery_task_id,
                )

            if len(image_urls) < need_count:
                await set_status_with_lease(
                    conversation_id,
                    status="partial",
                    progress={
                        "phase": "partial",
                        "batch_index": batch_index + 1,
                        "batch_total": len(jobs),
                        "slide_count": saved,
                        "planned_slides": planned_frames,
                        "shortfall": True,
                    },
                    error_message=(f"Wan returned {len(image_urls)}/{need_count} images for batch {batch_index + 1}")[
                        :2000
                    ],
                    celery_task_id=celery_task_id,
                )
                logger.warning(
                    "[ZhiHui] Incomplete Wan batch conversation=%s batch=%s/%s "
                    "got=%s need=%s skip=%s saved=%s missing_titles=%s",
                    conversation_id,
                    batch_index + 1,
                    len(jobs),
                    len(image_urls),
                    need_count,
                    skip_in_batch,
                    saved,
                    frame_titles[len(image_urls) :],
                )
                return False

            logger.info(
                "[ZhiHui] Wan batch complete conversation=%s batch=%s/%s branch=%s saved_total=%s next_slide=%s",
                conversation_id,
                batch_index + 1,
                len(jobs),
                branch_labels,
                saved,
                slide_index,
            )
        await set_status_with_lease(
            conversation_id,
            status="complete",
            progress={
                "phase": "complete",
                "batch_index": len(jobs),
                "batch_total": len(jobs),
                "slide_count": saved,
                "planned_slides": planned_frames,
            },
            clear_error=True,
            celery_task_id=celery_task_id,
        )
        logger.info(
            "[ZhiHui] Deck complete conversation=%s slides=%s/%s batches=%s elapsed=%.1fs diagram=%s",
            conversation_id,
            saved,
            planned_frames,
            len(jobs),
            time.monotonic() - pipeline_started,
            diagram_id,
        )
        return True
    except LeaseLost as exc:
        logger.info(
            "[ZhiHui] Deck lease lost conversation=%s celery=%s saved=%s slide_index=%s reason=%s",
            conversation_id,
            celery_task_id,
            saved,
            slide_index,
            exc,
        )
        return False
    except _PIPELINE_ERRORS as exc:
        logger.exception(
            "[ZhiHui] Lesson deck failed conversation=%s saved=%s slide_index=%s err=%s",
            conversation_id,
            saved,
            slide_index,
            exc,
        )
        await mark_terminal_from_error(
            conversation_id,
            exc,
            celery_task_id=celery_task_id,
        )
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
