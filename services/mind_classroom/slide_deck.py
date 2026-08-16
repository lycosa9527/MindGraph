"""Diagram spec → lesson plan → Wan 组图 → classroom slides."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from config.settings import config
from repositories.mind_classroom_repo import MindClassroomJobRepository, MindClassroomSlideRepository
from services.infrastructure.http.error_handler import LLMServiceError
from services.mind_classroom.deck_resume import iter_batch_resume_ranges, next_slide_index
from services.mind_classroom.focus import resolve_frame_focus_node_ids
from services.mind_classroom.lease import (
    LeaseLost,
    mark_terminal_from_error,
    require_run_lease,
    set_status_with_lease,
)
from services.mind_classroom.lesson_planner import (
    normalize_lesson_plan_to_outline,
    plan_lesson_from_outline,
)
from services.mind_classroom.outline import extract_mindmap_outline, is_mindmap_type
from services.mind_classroom.slide_adapter import frames_to_steps
from services.mind_classroom.slide_persist import persist_slide, wipe_slides
from services.mind_classroom.steps import MAX_STEPS_DEFAULT
from services.mind_classroom.transcript_persist import attach_transcript_md
from services.mind_classroom.token_usage import track_classroom_usage
from services.mind_classroom.wan_prompt_shell import build_wan_batch_prompt, plan_batches_to_wan_jobs
from services.t2i.wan_image_client import DEFAULT_WAN_IMAGE_MODEL, DEFAULT_WAN_SIZE, generate_wan_image_batch
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_PIPELINE_ERRORS = BACKGROUND_INFRA_ERRORS + DATABASE_ERRORS + (LLMServiceError, ValueError)
_TERMINAL_OK = frozenset({"ready"})
_TERMINAL_STOP = frozenset({"cancelled", "failed"})


def _max_steps() -> int:
    raw = getattr(config, "MIND_CLASSROOM_MAX_STEPS", None)
    try:
        value = int(raw) if raw is not None else MAX_STEPS_DEFAULT
    except (TypeError, ValueError):
        return MAX_STEPS_DEFAULT
    return value if value > 0 else MAX_STEPS_DEFAULT


def _frame_title(frame: Any) -> str:
    if not isinstance(frame, dict):
        return ""
    return str(frame.get("title") or "").strip()


async def run_slide_deck_job(
    job_id: str,
    *,
    celery_task_id: Optional[str] = None,
) -> bool:
    """Background pipeline for one slide_deck classroom job."""
    async with system_rls_session() as db:
        job_repo = MindClassroomJobRepository(db)
        claimed = await job_repo.claim_for_run(job_id, celery_task_id=celery_task_id)
        if claimed is None:
            logger.error("[MindClassroom] Job missing id=%s", job_id)
            return False
        if claimed.status in _TERMINAL_OK:
            return True
        if claimed.status in _TERMINAL_STOP:
            return False
        spec = claimed.spec_snapshot if isinstance(claimed.spec_snapshot, dict) else {}
        settings = claimed.settings if isinstance(claimed.settings, dict) else {}
        language = str(settings.get("language") or "zh")
        user_id = claimed.user_id
        organization_id = claimed.organization_id
        existing_plan = claimed.lesson_plan_json if isinstance(claimed.lesson_plan_json, dict) else None
        slides = list(await MindClassroomSlideRepository(db).list_by_job(job_id))

    slide_index = next_slide_index(slides)
    saved = len(slides)
    plan = existing_plan
    pipeline_started = time.monotonic()

    try:
        diagram_type = str(spec.get("type") or spec.get("diagramType") or "mind_map")
        if diagram_type and not is_mindmap_type(diagram_type):
            raise ValueError("Only mind maps are supported for 幻灯片讲解")
        outline = extract_mindmap_outline(spec, diagram_type=diagram_type, fallback_title="")
        if plan is None:
            if slides:
                await wipe_slides(job_id)
                slide_index = 0
                saved = 0
            await set_status_with_lease(
                job_id,
                status="planning",
                stage="planning",
                progress={"phase": "planning", "planning_stage": "open"},
                clear_error=True,
                celery_task_id=celery_task_id,
                started=True,
            )
            started = time.monotonic()

            async def _on_planning_progress(payload: dict[str, Any]) -> None:
                await require_run_lease(job_id, celery_task_id=celery_task_id)
                progress = {"phase": "planning", **payload}
                await set_status_with_lease(
                    job_id,
                    status="planning",
                    stage="planning",
                    progress=progress,
                    celery_task_id=celery_task_id,
                )

            plan, usage = await plan_lesson_from_outline(
                outline,
                language=language,
                diagram_title=outline.topic,
                settings=settings,
                user_id=user_id,
                organization_id=organization_id,
                on_progress=_on_planning_progress,
            )
            await track_classroom_usage(
                model_alias="qwen",
                usage=usage,
                request_type="mind_classroom_lesson_plan",
                user_id=user_id,
                organization_id=organization_id,
                job_id=job_id,
                response_time=time.monotonic() - started,
                success=True,
            )
        elif saved == 0:
            plan = normalize_lesson_plan_to_outline(plan, outline)

        jobs = plan_batches_to_wan_jobs(plan)
        if not jobs:
            raise ValueError("Lesson plan produced no image batches")
        planned_frames = sum(len(job.get("frames") or []) for job in jobs)
        await set_status_with_lease(
            job_id,
            status="generating",
            stage="generating",
            progress={
                "phase": "generating",
                "batch_index": 1 if jobs else 0,
                "batch_total": len(jobs),
                "slide_count": saved,
                "planned_slides": planned_frames,
            },
            lesson_plan_json=plan,
            clear_error=True,
            celery_task_id=celery_task_id,
        )

        batch_counts = [len(job.get("frames") or []) for job in jobs]
        resume_ranges = iter_batch_resume_ranges(batch_counts, slide_index)
        for batch_index, job in enumerate(jobs):
            await require_run_lease(job_id, celery_task_id=celery_task_id)
            frames = job.get("frames") or []
            _batch_start, _batch_end, skip_in_batch, _frame_count = resume_ranges[batch_index]
            if skip_in_batch >= len(frames):
                continue
            remaining_frames = frames[skip_in_batch:]
            need_count = len(remaining_frames)
            batch_role = str(job.get("batch_role") or "")
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
                job_id,
                status="generating",
                stage="generating",
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
            wan_started = time.monotonic()
            batch = await generate_wan_image_batch(
                prompt=wan_prompt,
                model=DEFAULT_WAN_IMAGE_MODEL,
                n=need_count,
                size=DEFAULT_WAN_SIZE,
                watermark=False,
                enable_sequential=True,
                log_context=f"job={job_id} batch={batch_index + 1}/{len(jobs)}",
            )
            await track_classroom_usage(
                model_alias="wan",
                usage=batch.usage,
                request_type="mind_classroom_wan_batch",
                user_id=user_id,
                organization_id=organization_id,
                job_id=job_id,
                response_time=time.monotonic() - wan_started,
                success=True,
            )
            image_urls = list(batch.image_urls or [])
            for url_index, image_url in enumerate(image_urls):
                if url_index >= need_count:
                    break
                await require_run_lease(job_id, celery_task_id=celery_task_id)
                frame_offset = skip_in_batch + url_index
                frame = frames[frame_offset] if frame_offset < len(frames) else {}
                title = ""
                teacher_script = ""
                focus_branch = None
                focus_child = ""
                frame_role = ""
                if isinstance(frame, dict):
                    title = _frame_title(frame)
                    teacher_script = str(frame.get("teacher_script") or "").strip()
                    if not teacher_script:
                        teacher_script = str(frame.get("learning_point") or "").strip()
                    focus_branch = frame.get("focus_branch")
                    focus_child = str(frame.get("focus_child") or "").strip()
                    frame_role = str(frame.get("frame_role") or "").strip().lower()
                if focus_child and frame_role != "branch_intro":
                    focus_ids = [focus_child]
                else:
                    focus_ids = resolve_frame_focus_node_ids(
                        outline,
                        slide_index=slide_index,
                        batch_role=batch_role,
                        focus_branch=focus_branch,
                    )
                await persist_slide(
                    job_id=job_id,
                    user_id=int(user_id),
                    prompt=wan_prompt,
                    image_url=image_url,
                    size=batch.size or DEFAULT_WAN_SIZE,
                    slide_index=slide_index,
                    slide_title=title or None,
                    teacher_script=teacher_script or None,
                    focus_node_ids=focus_ids,
                )
                slide_index += 1
                saved += 1
                await set_status_with_lease(
                    job_id,
                    status="generating",
                    stage="generating",
                    progress={
                        "phase": "generating",
                        "batch_index": batch_index + 1,
                        "batch_total": len(jobs),
                        "slide_count": saved,
                        "planned_slides": planned_frames,
                    },
                    celery_task_id=celery_task_id,
                )

            if len(image_urls) < need_count:
                async with system_rls_session() as db:
                    persisted = list(await MindClassroomSlideRepository(db).list_by_job(job_id))
                steps = frames_to_steps(
                    plan,
                    outline=outline,
                    spec=spec,
                    slides=persisted,
                    max_steps=_max_steps(),
                )
                result_json = await attach_transcript_md(
                    job_id=job_id,
                    settings=settings,
                    steps=steps,
                    result_json={"steps": steps},
                )
                await set_status_with_lease(
                    job_id,
                    status="partial",
                    stage="partial",
                    progress={
                        "phase": "partial",
                        "slide_count": saved,
                        "planned_slides": planned_frames,
                        "shortfall": True,
                        "transcript_uploaded": bool(result_json.get("transcript_uploaded")),
                    },
                    result_json=result_json,
                    error_message=(f"Wan returned {len(image_urls)}/{need_count} images for batch {batch_index + 1}")[
                        :2000
                    ],
                    celery_task_id=celery_task_id,
                    finished=True,
                )
                return False

        async with system_rls_session() as db:
            persisted = list(await MindClassroomSlideRepository(db).list_by_job(job_id))
        steps = frames_to_steps(
            plan,
            outline=outline,
            spec=spec,
            slides=persisted,
            max_steps=_max_steps(),
        )
        result_json = await attach_transcript_md(
            job_id=job_id,
            settings=settings,
            steps=steps,
            result_json={"steps": steps},
        )
        await set_status_with_lease(
            job_id,
            status="ready",
            stage="ready",
            progress={
                "phase": "ready",
                "slide_count": saved,
                "planned_slides": planned_frames,
                "step_count": len(steps),
                "transcript_uploaded": bool(result_json.get("transcript_uploaded")),
            },
            result_json=result_json,
            clear_error=True,
            celery_task_id=celery_task_id,
            finished=True,
        )
        logger.info(
            "[MindClassroom] Slide deck ready job=%s slides=%s/%s elapsed=%.1fs",
            job_id,
            saved,
            planned_frames,
            time.monotonic() - pipeline_started,
        )
        return True
    except LeaseLost as exc:
        logger.info("[MindClassroom] Slide deck lease lost job=%s reason=%s", job_id, exc)
        return False
    except _PIPELINE_ERRORS as exc:
        logger.exception("[MindClassroom] Slide deck failed job=%s err=%s", job_id, exc)
        await mark_terminal_from_error(job_id, exc, celery_task_id=celery_task_id)
        return False
