"""Sticky manifesto progress for parallel canvas-tour branch jobs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

from repositories.mind_classroom_repo import MindClassroomJobRepository
from services.mind_classroom.celery_log import classroom_status_changed, log_classroom_celery
from services.mind_classroom.job_events import publish_classroom_job_snapshot
from services.mind_classroom.job_manifest import (
    JOB_GENERATING,
    JOB_PLANNING,
    JOB_QUEUED,
    should_apply_job_stage,
)
from utils.db.session_open import system_rls_session

_ACTIVE_STATUS = frozenset({JOB_QUEUED, JOB_PLANNING, JOB_GENERATING})

_STATE_RANK = {"pending": 0, "streaming": 1, "done": 2}
_PROTECTED = frozenset(
    {
        "branch",
        "branch_label",
        "branch_labels",
        "branch_total",
        "branches",
        "done",
        "in_flight",
        "tts_ready",
    }
)


def seed_branch_slots(labels: list[str]) -> list[dict[str, Any]]:
    """One pending slot per trunk family, 1-based index."""
    slots: list[dict[str, Any]] = []
    for offset, label in enumerate(labels):
        text = label.strip() if isinstance(label, str) else ""
        slots.append({"index": offset + 1, "label": text, "state": "pending", "chars": 0})
    return slots


def merge_tour_progress(
    current: Optional[dict[str, Any]],
    *,
    phase: str,
    branch: Optional[int] = None,
    branch_state: Optional[str] = None,
    branch_label: str = "",
    chars: Optional[int] = None,
    tts_ready: Optional[bool] = None,
    step_count: Optional[int] = None,
    seed_labels: Optional[list[str]] = None,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Merge one branch event into the job progress blob without dropping siblings."""
    merged: dict[str, Any] = dict(current) if isinstance(current, dict) else {}
    slots = _slots_from_progress(merged)
    if seed_labels:
        slots = seed_branch_slots(seed_labels)
    if branch is not None:
        slots = _upsert_slot(
            slots,
            index=branch,
            label=branch_label,
            state=branch_state,
            chars=chars,
        )
    display = _display_slot(slots)
    merged["phase"] = phase
    if slots:
        merged["branches"] = slots
        merged["branch_labels"] = [str(slot.get("label") or "") for slot in slots]
        merged["branch_total"] = len(slots)
        merged["done"] = sum(1 for slot in slots if slot.get("state") == "done")
        merged["in_flight"] = sum(1 for slot in slots if slot.get("state") != "done")
        if display is not None:
            merged["branch"] = display["index"]
            if display.get("label"):
                merged["branch_label"] = display["label"]
            display_chars = display.get("chars")
            if isinstance(display_chars, int):
                merged["chars"] = display_chars
    elif branch_label:
        merged["branch_label"] = branch_label
    if merged.get("tts_ready") is True or tts_ready is True:
        merged["tts_ready"] = True
    elif tts_ready is False and merged.get("tts_ready") is not True:
        merged["tts_ready"] = False
    if isinstance(step_count, int):
        merged["step_count"] = step_count
    if extra:
        for key, value in extra.items():
            if key not in _PROTECTED:
                merged[key] = value
    return merged


def _slots_from_progress(progress: dict[str, Any]) -> list[dict[str, Any]]:
    raw = progress.get("branches")
    if not isinstance(raw, list):
        return []
    slots: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        if not isinstance(index, int) or isinstance(index, bool) or index < 1:
            continue
        state = item.get("state")
        if state not in _STATE_RANK:
            state = "pending"
        chars = item.get("chars")
        slots.append(
            {
                "index": index,
                "label": str(item.get("label") or "").strip(),
                "state": state,
                "chars": chars if isinstance(chars, int) and not isinstance(chars, bool) else 0,
            }
        )
    slots.sort(key=lambda slot: int(slot["index"]))
    return slots


def _upsert_slot(
    slots: list[dict[str, Any]],
    *,
    index: int,
    label: str,
    state: Optional[str],
    chars: Optional[int],
) -> list[dict[str, Any]]:
    found: Optional[dict[str, Any]] = None
    for slot in slots:
        if slot["index"] == index:
            found = slot
            break
    if found is None:
        found = {"index": index, "label": "", "state": "pending", "chars": 0}
        slots.append(found)
        slots.sort(key=lambda slot: int(slot["index"]))
    if label:
        found["label"] = label
    if state in _STATE_RANK:
        current_state = str(found.get("state") or "pending")
        if _STATE_RANK[state] >= _STATE_RANK.get(current_state, 0):
            found["state"] = state
    if isinstance(chars, int) and not isinstance(chars, bool):
        previous = found.get("chars")
        prior = previous if isinstance(previous, int) and not isinstance(previous, bool) else 0
        found["chars"] = max(prior, chars)
    return slots


def _display_slot(slots: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Lowest-index streaming family, else first still pending, else first slot."""
    for wanted in ("streaming", "pending"):
        for slot in slots:
            if slot.get("state") == wanted:
                return slot
    return slots[0] if slots else None


def _attempt_entry(status: str, stage: str) -> dict[str, Any]:
    return {
        "status": status,
        "stage": stage,
        "at": datetime.now(UTC).isoformat(),
    }


async def patch_tour_progress(
    job_id: Optional[str],
    *,
    celery_task_id: Optional[str],
    status: str,
    stage: str,
    phase: str,
    branch: Optional[int] = None,
    branch_state: Optional[str] = None,
    branch_label: str = "",
    chars: Optional[int] = None,
    tts_ready: Optional[bool] = None,
    step_count: Optional[int] = None,
    seed_labels: Optional[list[str]] = None,
    extra: Optional[dict[str, Any]] = None,
    result_json: Optional[dict[str, Any]] = None,
    record_attempt: bool = False,
) -> dict[str, Any]:
    """Read-merge-write job progress under one row lock in one session."""
    if not job_id:
        return {}
    previous_status: Optional[str] = None
    previous_stage: Optional[str] = None
    owned: Optional[str] = None
    merged: dict[str, Any] = {}
    wrote = False
    async with system_rls_session() as db:
        repo = MindClassroomJobRepository(db)
        row = await repo.lock_by_uuid(job_id)
        if row is None:
            return {}
        previous_status = row.status
        previous_stage = row.current_stage
        owned = row.celery_task_id if isinstance(row.celery_task_id, str) else None
        current = dict(row.progress) if isinstance(row.progress, dict) else {}
        if not should_apply_job_stage(previous_status, status):
            return current
        merged = merge_tour_progress(
            current,
            phase=phase,
            branch=branch,
            branch_state=branch_state,
            branch_label=branch_label,
            chars=chars,
            tts_ready=tts_ready,
            step_count=step_count,
            seed_labels=seed_labels,
            extra=extra,
        )
        await repo.update_job(
            job_id,
            status=status,
            current_stage=stage,
            progress=merged,
            result_json=result_json,
            celery_task_id=celery_task_id,
            increment_attempt=record_attempt and status in _ACTIVE_STATUS,
            attempt_entry=_attempt_entry(status, stage) if record_attempt else None,
            commit=True,
        )
        wrote = True
    if wrote and classroom_status_changed(previous_status, previous_stage, status, stage):
        detail = f"phase={phase}" if phase and phase not in {status, stage} else None
        log_classroom_celery(
            "status",
            job_id=job_id,
            celery_task_id=celery_task_id or owned,
            status=status,
            stage=stage,
            detail=detail,
        )
    if wrote:
        await publish_classroom_job_snapshot(job_id)
    return merged
