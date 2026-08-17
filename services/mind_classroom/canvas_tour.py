"""Generate canvas-tour lecture steps from a spec snapshot."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

from config.settings import config
from services.infrastructure.http.error_handler import LLMServiceError
from services.mind_classroom.canvas_tour_chunks import (
    family_branch_label,
    merge_usage,
    split_each_node_families,
)
from services.mind_classroom.deep_outline import build_tour_nodes
from services.mind_classroom.job_manifest import mark_job_ready, mark_job_stage
from services.mind_classroom.lease import LeaseLost, mark_terminal_from_error, require_run_lease
from services.mind_classroom.lesson_planner import planner_max_tokens, planner_model_id
from services.mind_classroom.metrics_log import log_job_completed, log_script_llm_done
from services.mind_classroom.canvas_tour_llm import stream_tour_script_text
from services.mind_classroom.progress_log import log_job_stage
from services.mind_classroom.tour_progress import patch_tour_progress
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


@dataclass(frozen=True)
class _TourChat:
    """One canvas-tour LLM call plus manifesto progress keys."""

    job_id: Optional[str]
    celery_task_id: Optional[str]
    user_id: Optional[int]
    organization_id: Optional[int]
    branch: Optional[int]
    branch_total: Optional[int]
    branch_label: str


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


def _branch_suffix(chat: _TourChat) -> str:
    if chat.branch is None or chat.branch_total is None:
        return ""
    return f" branch={chat.branch}/{chat.branch_total}"


async def _await_llm_chat(
    chat: _TourChat,
    *,
    prompt: str,
    model: str,
    system_message: str,
    max_tokens: int,
    temperature: float,
    repair: bool = False,
) -> tuple[str, Optional[dict[str, Any]]]:
    phase = "llm_repair" if repair else "llm_request"
    action = "DashScope repair sent" if repair else "DashScope request sent"
    branch_part = _branch_suffix(chat)
    if chat.job_id:
        log_job_stage(
            chat.job_id,
            f"{action} model={model}{branch_part} chars={len(prompt)}",
            status="generating",
            phase=phase,
        )
    if chat.branch is None:
        await patch_tour_progress(
            chat.job_id,
            celery_task_id=chat.celery_task_id,
            status="generating",
            stage=phase,
            phase=phase,
            branch=chat.branch,
            branch_label=chat.branch_label,
            extra={"model": model, "prompt_chars": len(prompt)},
        )
    started = time.monotonic()
    response, usage = await stream_tour_script_text(
        prompt=prompt,
        model=model,
        system_message=system_message,
        max_tokens=max_tokens,
        temperature=temperature,
        user_id=chat.user_id,
        organization_id=chat.organization_id,
        job_id=chat.job_id,
        celery_task_id=chat.celery_task_id,
        branch=chat.branch,
        branch_total=chat.branch_total,
        branch_label=chat.branch_label,
    )
    elapsed = time.monotonic() - started
    chars = len(response or "")
    if chat.job_id:
        log_job_stage(
            chat.job_id,
            f"LLM results received elapsed={elapsed:.2f}s chars={chars}{branch_part}",
            status="generating",
            phase="llm_received",
        )
    if chat.branch is None:
        await patch_tour_progress(
            chat.job_id,
            celery_task_id=chat.celery_task_id,
            status="generating",
            stage="llm_received",
            phase="llm_received",
            branch=chat.branch,
            branch_state="done",
            branch_label=chat.branch_label,
            chars=chars,
            extra={"elapsed_s": round(elapsed, 2)},
        )
    return response or "", usage


async def _chat_script(
    chat: _TourChat,
    *,
    prompt: str,
    settings: dict[str, Any],
) -> tuple[list[dict[str, Any]], Optional[dict[str, Any]]]:
    model = planner_model_id()
    max_tokens = max(planner_max_tokens(), 8000)
    system_message = build_canvas_tour_system_message(settings)
    started = time.monotonic()
    response, usage = await _await_llm_chat(
        chat,
        prompt=prompt,
        model=model,
        system_message=system_message,
        max_tokens=max_tokens,
        temperature=0.4,
    )
    try:
        parsed = parse_canvas_tour_json(response or "")
        log_script_llm_done(
            elapsed=time.monotonic() - started,
            usage=usage,
            chunk_index=chat.branch,
            chunk_total=chat.branch_total,
        )
        return parsed, usage
    except _PARSE_ERRORS:
        repair_started = time.monotonic()
        response, usage = await _await_llm_chat(
            chat,
            prompt=f"{prompt}\n\n{CANVAS_TOUR_REPAIR}",
            model=model,
            system_message=system_message,
            max_tokens=max_tokens,
            temperature=0.2,
            repair=True,
        )
        parsed = parse_canvas_tour_json(response or "")
        log_script_llm_done(
            elapsed=time.monotonic() - repair_started,
            usage=usage,
            chunk_index=chat.branch,
            chunk_total=chat.branch_total,
            repair=True,
        )
        return parsed, usage


def contiguous_raw_prefix(
    slots: list[Optional[list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    """Merge finished families in map order, stopping at the first hole."""
    merged: list[dict[str, Any]] = []
    for raw_steps in slots:
        if raw_steps is None:
            break
        merged.extend(raw_steps)
    return merged


async def persist_ready_tour_prefix(
    job_id: str,
    *,
    spec: dict[str, Any],
    slots: list[Optional[list[dict[str, Any]]]],
    celery_task_id: Optional[str],
    labels: list[str],
    completed_index: int,
) -> int:
    """Write the contiguous finished prefix so TTS can catch up mid-job."""
    prefix = contiguous_raw_prefix(slots)
    steps = normalize_steps(prefix, spec=spec, max_steps=_max_steps())
    label = labels[completed_index] if 0 <= completed_index < len(labels) else ""
    prefix_families = 0
    for raw_steps in slots:
        if raw_steps is None:
            break
        prefix_families += 1
    phase = "first_branch" if prefix_families <= 1 else "tour_prefix"
    if steps:
        log_job_stage(
            job_id,
            (f"tour prefix ready families={prefix_families} steps={len(steps)} label={label or '-'} TTS catch-up"),
            status="generating",
            phase=phase,
        )
    await patch_tour_progress(
        job_id,
        celery_task_id=celery_task_id,
        status="generating",
        stage=phase,
        phase=phase,
        branch=completed_index + 1,
        branch_state="done",
        branch_label=label,
        tts_ready=bool(steps),
        step_count=len(steps) if steps else None,
        result_json={"steps": steps, "partial": True} if steps else None,
    )
    return len(steps)


async def generate_tour_steps(
    tour_nodes: list[dict[str, Any]],
    *,
    settings: dict[str, Any],
    user_id: Optional[int],
    organization_id: Optional[int],
    job_id: Optional[str] = None,
    celery_task_id: Optional[str] = None,
    spec: Optional[dict[str, Any]] = None,
) -> tuple[list[dict[str, Any]], Optional[dict[str, Any]]]:
    """One LLM call, or one parallel call per L1 family (main_branch or each_node)."""
    families = split_each_node_families(tour_nodes)
    if len(families) <= 1:
        label = family_branch_label(families[0]) if families else ""
        if job_id:
            log_job_stage(
                job_id,
                "generating script for full tour",
                status="generating",
                phase="script",
            )
        prompt = build_canvas_tour_user_message(
            tour_nodes,
            settings=settings,
            max_steps=_max_steps(),
        )
        chat = _TourChat(
            job_id=job_id,
            celery_task_id=celery_task_id,
            user_id=user_id,
            organization_id=organization_id,
            branch=None,
            branch_total=None,
            branch_label=label,
        )
        return await _chat_script(chat, prompt=prompt, settings=settings)
    return await _generate_family_scripts_parallel(
        tour_nodes,
        families,
        settings=settings,
        user_id=user_id,
        organization_id=organization_id,
        job_id=job_id,
        celery_task_id=celery_task_id,
        spec=spec,
    )


async def _generate_family_scripts_parallel(
    tour_nodes: list[dict[str, Any]],
    families: list[list[dict[str, Any]]],
    *,
    settings: dict[str, Any],
    user_id: Optional[int],
    organization_id: Optional[int],
    job_id: Optional[str],
    celery_task_id: Optional[str],
    spec: Optional[dict[str, Any]] = None,
) -> tuple[list[dict[str, Any]], Optional[dict[str, Any]]]:
    """Fire one DashScope call per trunk family at the same time; merge in map order."""
    last_index = len(families) - 1
    jobs: list[tuple[_TourChat, str]] = []
    for index, family in enumerate(families):
        branch = index + 1
        label = family_branch_label(family)
        write_ids = [str(node.get("id") or "") for node in family if node.get("id")]
        prompt = build_canvas_tour_user_message(
            tour_nodes,
            settings=settings,
            max_steps=_max_steps(),
            write_only_ids=write_ids,
            emit_overview=index == 0,
            emit_closing=index == last_index,
        )
        jobs.append(
            (
                _TourChat(
                    job_id=job_id,
                    celery_task_id=celery_task_id,
                    user_id=user_id,
                    organization_id=organization_id,
                    branch=branch,
                    branch_total=len(families),
                    branch_label=label,
                ),
                prompt,
            )
        )
    if job_id:
        labels = ", ".join(chat.branch_label or f"#{chat.branch}" for chat, _prompt in jobs)
        log_job_stage(
            job_id,
            f"generating script for {len(jobs)} branches in parallel labels={labels}",
            status="generating",
            phase="script_parallel",
        )
    await patch_tour_progress(
        job_id,
        celery_task_id=celery_task_id,
        status="generating",
        stage="script_parallel",
        phase="script_parallel",
        seed_labels=[chat.branch_label for chat, _prompt in jobs],
    )
    pending: dict[asyncio.Task[tuple[list[dict[str, Any]], Optional[dict[str, Any]]]], int] = {}
    for index, (chat, prompt) in enumerate(jobs):
        task = asyncio.create_task(_chat_script(chat, prompt=prompt, settings=settings))
        pending[task] = index
    slots: list[Optional[list[dict[str, Any]]]] = [None] * len(jobs)
    usage: Optional[dict[str, Any]] = None
    try:
        while pending:
            finished, _ = await asyncio.wait(pending.keys(), return_when=asyncio.FIRST_COMPLETED)
            for task in finished:
                index = pending.pop(task)
                raw_steps, chunk_usage = task.result()
                slots[index] = raw_steps
                usage = merge_usage(usage, chunk_usage)
                if job_id and spec is not None:
                    await persist_ready_tour_prefix(
                        job_id,
                        spec=spec,
                        slots=slots,
                        celery_task_id=celery_task_id,
                        labels=[chat.branch_label for chat, _prompt in jobs],
                        completed_index=index,
                    )
                    continue
                await patch_tour_progress(
                    job_id,
                    celery_task_id=celery_task_id,
                    status="generating",
                    stage="llm_received",
                    phase="llm_received",
                    branch=index + 1,
                    branch_state="done",
                    branch_label=jobs[index][0].branch_label,
                )
    finally:
        await _cancel_pending_family_tasks(pending)
    merged: list[dict[str, Any]] = []
    for raw_steps in slots:
        if raw_steps:
            merged.extend(raw_steps)
    return merged, usage


async def _cancel_pending_family_tasks(
    pending: dict[asyncio.Task[tuple[list[dict[str, Any]], Optional[dict[str, Any]]]], int],
) -> None:
    """Stop sibling DashScope calls when one family fails or the wait is cancelled."""
    leftovers = list(pending)
    pending.clear()
    for task in leftovers:
        task.cancel()
    if leftovers:
        await asyncio.gather(*leftovers, return_exceptions=True)


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
        log_job_stage(job_id, "reading diagram spec", status="planning", phase="reading_spec")
        await mark_job_stage(
            job_id,
            status="planning",
            stage="reading_spec",
            progress={"phase": "reading_spec"},
            celery_task_id=celery_task_id,
            clear_error=True,
            started=True,
        )
        deep = str(settings.get("tour_scope") or "") == "each_node"
        tour_nodes = build_tour_nodes(spec, deep=deep)
        node_count = len(tour_nodes)
        log_job_stage(
            job_id,
            f"diagram spec ready nodes={node_count} deep={str(deep).lower()}",
            status="planning",
            phase="reading_spec",
        )
        if node_count > _max_steps():
            raise ValueError(f"Tour has {node_count} nodes; max is {_max_steps()}")
        await require_run_lease(job_id, celery_task_id=celery_task_id)
        await mark_job_stage(
            job_id,
            status="generating",
            stage="generating",
            progress={"phase": "transcript", "node_count": node_count},
            celery_task_id=celery_task_id,
        )
        llm_started = time.monotonic()
        raw_steps, usage = await generate_tour_steps(
            tour_nodes,
            settings=settings,
            user_id=user_id,
            organization_id=organization_id,
            job_id=job_id,
            celery_task_id=celery_task_id,
            spec=spec,
        )
        llm_elapsed = time.monotonic() - llm_started
        await track_classroom_usage(
            model_alias="qwen",
            usage=usage,
            request_type="mind_classroom_canvas_tour",
            user_id=user_id,
            organization_id=organization_id,
            job_id=job_id,
            response_time=llm_elapsed,
            success=True,
        )
        persist_started = time.monotonic()
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
        persist_elapsed = time.monotonic() - persist_started
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
        log_job_completed(
            kind="Script generation",
            elapsed=time.monotonic() - started,
            breakdown={"llm": llm_elapsed, "persist": persist_elapsed},
            target="canvas_tour",
            extra=f"steps={len(steps)} job={job_id}",
        )
        return True
    except LeaseLost as exc:
        logger.debug("[MindClassroom] Canvas tour lease lost job=%s reason=%s", job_id, exc)
        return False
    except _TOUR_ERRORS as exc:
        logger.exception("[MindClassroom] Canvas tour failed job=%s err=%s", job_id, exc)
        await mark_terminal_from_error(job_id, exc, celery_task_id=celery_task_id)
        return False
