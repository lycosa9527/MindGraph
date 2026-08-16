"""Generate canvas-tour lecture steps from a spec snapshot."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional

from config.settings import config
from services.infrastructure.http.error_handler import LLMServiceError
from services.llm import llm_service
from services.mind_classroom.canvas_tour_chunks import merge_usage, split_each_node_families
from services.mind_classroom.deep_outline import build_tour_nodes
from services.mind_classroom.job_manifest import mark_job_ready, mark_job_stage
from services.mind_classroom.lease import LeaseLost, mark_terminal_from_error, require_run_lease
from services.mind_classroom.lesson_planner import planner_max_tokens, planner_model_id
from services.mind_classroom.prompts.canvas_tour_prompts import (
    CANVAS_TOUR_REPAIR,
    build_canvas_tour_system_message,
    build_canvas_tour_user_message,
)
from services.mind_classroom.steps import MAX_STEPS_DEFAULT, normalize_steps
from services.mind_classroom.transcript_persist import attach_transcript_md
from services.mind_classroom.token_usage import track_classroom_usage
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from repositories.mind_classroom_repo import MindClassroomJobRepository
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_PARSE_ERRORS = (json.JSONDecodeError, ValueError, TypeError)
_TOUR_ERRORS = BACKGROUND_INFRA_ERRORS + (LLMServiceError, ValueError, TypeError)


def _max_steps() -> int:
    raw = getattr(config, "MIND_CLASSROOM_MAX_STEPS", None)
    try:
        value = int(raw) if raw is not None else MAX_STEPS_DEFAULT
    except (TypeError, ValueError):
        return MAX_STEPS_DEFAULT
    return value if value > 0 else MAX_STEPS_DEFAULT


def _strip_code_fence(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, count=1, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned, count=1)
    return cleaned.strip()


def parse_canvas_tour_json(raw: str) -> list[dict[str, Any]]:
    """Parse LLM JSON into a raw step list."""
    data = json.loads(_strip_code_fence(raw))
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        raise ValueError("Canvas tour root must be an object")
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Canvas tour missing steps")
    return [item for item in steps if isinstance(item, dict)]


async def _chat_script(
    *,
    prompt: str,
    settings: dict[str, Any],
    user_id: Optional[int],
    organization_id: Optional[int],
) -> tuple[list[dict[str, Any]], Optional[dict[str, Any]]]:
    model = planner_model_id()
    max_tokens = max(planner_max_tokens(), 8000)
    system_message = build_canvas_tour_system_message(settings)
    response, usage = await llm_service.chat_with_usage(
        prompt=prompt,
        model=model,
        system_message=system_message,
        max_tokens=max_tokens,
        temperature=0.4,
        user_id=user_id,
        organization_id=organization_id,
    )
    try:
        return parse_canvas_tour_json(response or ""), usage
    except _PARSE_ERRORS:
        response, usage = await llm_service.chat_with_usage(
            prompt=f"{prompt}\n\n{CANVAS_TOUR_REPAIR}",
            model=model,
            system_message=system_message,
            max_tokens=max_tokens,
            temperature=0.2,
            user_id=user_id,
            organization_id=organization_id,
        )
        return parse_canvas_tour_json(response or ""), usage


async def generate_tour_steps(
    tour_nodes: list[dict[str, Any]],
    *,
    settings: dict[str, Any],
    user_id: Optional[int],
    organization_id: Optional[int],
) -> tuple[list[dict[str, Any]], Optional[dict[str, Any]]]:
    """One LLM call, or one call per trunk family when each_node is long."""
    families = split_each_node_families(tour_nodes)
    deep = str(settings.get("tour_scope") or "") == "each_node"
    if not deep or len(families) <= 1:
        prompt = build_canvas_tour_user_message(
            tour_nodes,
            settings=settings,
            max_steps=_max_steps(),
        )
        return await _chat_script(
            prompt=prompt,
            settings=settings,
            user_id=user_id,
            organization_id=organization_id,
        )
    merged: list[dict[str, Any]] = []
    usage: Optional[dict[str, Any]] = None
    last_index = len(families) - 1
    for index, family in enumerate(families):
        write_ids = [str(node.get("id") or "") for node in family if node.get("id")]
        prompt = build_canvas_tour_user_message(
            tour_nodes,
            settings=settings,
            max_steps=_max_steps(),
            write_only_ids=write_ids,
            emit_overview=index == 0,
            emit_closing=index == last_index,
        )
        raw_steps, chunk_usage = await _chat_script(
            prompt=prompt,
            settings=settings,
            user_id=user_id,
            organization_id=organization_id,
        )
        merged.extend(raw_steps)
        usage = merge_usage(usage, chunk_usage)
    return merged, usage


async def run_canvas_tour_job(
    job_id: str,
    *,
    celery_task_id: Optional[str] = None,
) -> bool:
    """Plan a canvas-tour script / lesson plan and persist steps on the manifesto."""
    async with system_rls_session() as db:
        repo = MindClassroomJobRepository(db)
        claimed = await repo.claim_for_run(job_id, celery_task_id=celery_task_id)
        if claimed is None:
            logger.error("[MindClassroom] Job missing id=%s", job_id)
            return False
        if claimed.status == "ready":
            return True
        if claimed.status in {"cancelled", "failed"}:
            return False
        spec = claimed.spec_snapshot if isinstance(claimed.spec_snapshot, dict) else {}
        settings = claimed.settings if isinstance(claimed.settings, dict) else {}
        user_id = claimed.user_id
        organization_id = claimed.organization_id
        diagram_id = claimed.diagram_id

    started = time.monotonic()
    try:
        await require_run_lease(job_id, celery_task_id=celery_task_id)
        await mark_job_stage(
            job_id,
            status="planning",
            stage="planning",
            progress={"phase": "planning"},
            celery_task_id=celery_task_id,
            clear_error=True,
            started=True,
        )
        deep = str(settings.get("tour_scope") or "") == "each_node"
        tour_nodes = build_tour_nodes(spec, deep=deep)
        if len(tour_nodes) > _max_steps():
            raise ValueError(f"Tour has {len(tour_nodes)} nodes; max is {_max_steps()}")
        await require_run_lease(job_id, celery_task_id=celery_task_id)
        await mark_job_stage(
            job_id,
            status="generating",
            stage="generating",
            progress={"phase": "transcript", "node_count": len(tour_nodes)},
            celery_task_id=celery_task_id,
        )
        raw_steps, usage = await generate_tour_steps(
            tour_nodes,
            settings=settings,
            user_id=user_id,
            organization_id=organization_id,
        )
        await track_classroom_usage(
            model_alias="qwen",
            usage=usage,
            request_type="mind_classroom_canvas_tour",
            user_id=user_id,
            organization_id=organization_id,
            job_id=job_id,
            response_time=time.monotonic() - started,
            success=True,
        )
        steps = normalize_steps(raw_steps, spec=spec, max_steps=_max_steps())
        if not steps:
            raise ValueError("Canvas tour produced no valid steps")
        result_json = await attach_transcript_md(
            job_id=job_id,
            settings=settings,
            steps=steps,
            result_json={"steps": steps},
            user_id=user_id,
            diagram_id=diagram_id,
        )
        await require_run_lease(job_id, celery_task_id=celery_task_id)
        await mark_job_ready(
            job_id,
            result_json=result_json,
            progress={
                "phase": "ready",
                "step_count": len(steps),
                "transcript_uploaded": bool(result_json.get("transcript_uploaded")),
            },
            celery_task_id=celery_task_id,
        )
        logger.info(
            "[MindClassroom] Canvas tour ready job=%s steps=%s elapsed=%.1fs",
            job_id,
            len(steps),
            time.monotonic() - started,
        )
        return True
    except LeaseLost as exc:
        logger.info("[MindClassroom] Canvas tour lease lost job=%s reason=%s", job_id, exc)
        return False
    except _TOUR_ERRORS as exc:
        logger.exception("[MindClassroom] Canvas tour failed job=%s err=%s", job_id, exc)
        await mark_terminal_from_error(job_id, exc, celery_task_id=celery_task_id)
        return False
