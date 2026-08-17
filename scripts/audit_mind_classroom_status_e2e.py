"""
Real-map 思维讲堂 status e2e: Celery job → Postgres + Redis → Start-button chrome.

Enqueues ``mind_classroom.run_script`` against a saved mind map, then checks
reuse, SSE-drop reconcile, 429, Kitty rewrite, and button tone at each stage.

Usage (WSL, repo root, conda python313):
  PYTHONPATH=. python scripts/audit_mind_classroom_status_e2e.py
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Optional

from repositories.mind_classroom_repo import MindClassroomJobRepository
from scripts.audit_mind_classroom_e2e import load_real_mindmap, tour_settings
from services.mind_classroom.enqueue import ClassroomJobsBusy, create_and_enqueue_job
from services.mind_classroom.job_events import (
    classroom_sse_reconcile_payload,
    decode_pubsub_data,
    load_classroom_job_event,
    sse_job_status,
)
from services.mind_classroom.job_manifest import hash_spec_snapshot
from services.mind_classroom.job_match import (
    classroom_ready_job_reusable,
    spec_snapshot_node_ids,
)
from services.redis.redis_async_client import get_async_redis
from utils.db.session_open import system_rls_session

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "mind_classroom_status_e2e"
JOB_TIMEOUT_S = 420.0
_ACTIVE = frozenset({"queued", "planning", "generating"})
_TERMINAL = frozenset({"ready", "partial", "failed", "cancelled"})


def button_chrome(
    status: Optional[str],
    *,
    has_prepared: bool = False,
    starting: bool = False,
    voice_warmup: Optional[str] = None,
    remaining: Optional[int] = None,
    branch_name: Optional[str] = None,
    tts_ready: bool = False,
) -> dict[str, Any]:
    """Mirror ``mindClassroomButtonChrome`` for the cases this audit hits."""
    busy = starting or voice_warmup == "loading" or status in _ACTIVE
    if busy:
        tone = "busy"
    elif has_prepared:
        tone = "ready"
    elif status == "failed":
        tone = "failed"
    else:
        tone = "start"
    if busy and status == "planning":
        label = "planning"
    elif busy and status == "queued":
        label = "queued"
    elif busy and (status == "generating" or (remaining or 0) > 0):
        if tts_ready and (remaining or 0) > 0:
            label = "transcriptRemaining"
        elif branch_name:
            label = "transcriptBranch"
        else:
            label = "transcript"
    elif has_prepared and voice_warmup == "loading":
        label = "loadingVoice"
    elif has_prepared:
        label = "ready"
    elif status == "failed":
        label = "failed"
    else:
        label = "start"
    show_restart = has_prepared or status in {
        "queued",
        "planning",
        "generating",
        "failed",
        "ready",
        "partial",
    }
    return {
        "tone": tone,
        "label": label,
        "busy": busy,
        "locked": busy,
        "showRestart": show_restart,
    }


class RedisTap:
    """Collect pub/sub statuses for one job."""

    def __init__(self) -> None:
        self.job_id = ""
        self.statuses: list[str] = []
        self.terminal = asyncio.Event()

    def apply(self, job_id: str, status: str) -> None:
        """Record a status if it changed."""
        if self.job_id and job_id != self.job_id:
            return
        if not self.statuses or self.statuses[-1] != status:
            self.statuses.append(status)
        if status in _TERMINAL:
            self.terminal.set()


async def _listen(tap: RedisTap, subscribed: asyncio.Event) -> None:
    redis = get_async_redis()
    if redis is None:
        subscribed.set()
        return
    pubsub = redis.pubsub()
    await pubsub.psubscribe("mind_classroom:job:*")
    subscribed.set()
    try:
        async for message in pubsub.listen():
            if message is None or message.get("type") not in {"message", "pmessage"}:
                continue
            raw = decode_pubsub_data(message.get("data"))
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            job = payload.get("job") if isinstance(payload, dict) else None
            if not isinstance(job, dict):
                continue
            status = str(job.get("status") or "")
            job_id = str(job.get("id") or "")
            if status and job_id:
                tap.apply(job_id, status)
    finally:
        await pubsub.punsubscribe("mind_classroom:job:*")
        await pubsub.aclose()


async def _pg_event(job_id: str) -> Optional[dict[str, Any]]:
    return await load_classroom_job_event(job_id)


async def _pg_status(job_id: str) -> Optional[str]:
    event = await _pg_event(job_id)
    if event is None:
        return None
    return str(event.get("status") or "") or None


async def _reusable(
    user_id: int,
    spec: dict[str, Any],
    settings: dict[str, Any],
    diagram_id: str,
) -> Optional[str]:
    async with system_rls_session() as db:
        row = await MindClassroomJobRepository(db).find_reusable(
            user_id=user_id,
            settings=settings,
            diagram_id=diagram_id,
            spec_hash=hash_spec_snapshot(spec),
            live_ids=set(spec_snapshot_node_ids(spec)),
        )
        return row.id if row is not None else None


def _kitty_spec() -> dict[str, Any]:
    return {"nodes": [{"id": "e2e-new-root"}, {"id": "e2e-new-b1"}], "connections": []}


def _chrome_from_event(event: Optional[dict[str, Any]]) -> dict[str, Any]:
    if event is None:
        return button_chrome(None)
    status = str(event.get("status") or "") or None
    raw_progress = event.get("progress")
    progress: dict[str, Any] = raw_progress if isinstance(raw_progress, dict) else {}
    raw_result = event.get("result_json")
    result: dict[str, Any] = raw_result if isinstance(raw_result, dict) else {}
    raw_steps = result.get("steps")
    steps: list[Any] = raw_steps if isinstance(raw_steps, list) else []
    has_prepared = status in {"ready", "partial"} and any(
        isinstance(step, dict) and str(step.get("caption") or "").strip() for step in steps
    )
    raw_branches = progress.get("branches")
    branches: list[Any] = raw_branches if isinstance(raw_branches, list) else []
    branch_name = None
    remaining = 0
    for item in branches:
        if not isinstance(item, dict):
            continue
        if item.get("state") in {"streaming", "pending"}:
            remaining += 1
            if branch_name is None:
                label = str(item.get("label") or "").strip()
                branch_name = label or None
        elif item.get("state") != "done":
            remaining += 1
    if not remaining and isinstance(progress.get("in_flight"), int):
        remaining = max(0, int(progress["in_flight"]))
    return button_chrome(
        status,
        has_prepared=has_prepared,
        branch_name=branch_name,
        tts_ready=progress.get("tts_ready") is True,
        remaining=remaining or None,
    )


async def _wait_pg(
    job_id: str,
    wanted: frozenset[str],
    *,
    timeout: float,
    timeline: list[dict[str, Any]],
    tap: RedisTap,
) -> Optional[str]:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        event = await _pg_event(job_id)
        status = str(event.get("status") or "") if event else None
        if status and status != last:
            last = status
            timeline.append(
                {
                    "status": status,
                    "chrome": _chrome_from_event(event),
                    "redis": list(tap.statuses),
                }
            )
        if status in wanted:
            return status
        if status in _TERMINAL:
            return status
        await asyncio.sleep(1.0)
    return last


async def _run_live(
    *,
    user_id: int,
    organization_id: Optional[int],
    diagram_id: str,
    spec: dict[str, Any],
    settings: dict[str, Any],
) -> dict[str, Any]:
    tap = RedisTap()
    subscribed = asyncio.Event()
    listener = asyncio.create_task(_listen(tap, subscribed))
    checks: dict[str, bool] = {}
    timeline: list[dict[str, Any]] = []
    job_id = ""
    try:
        await subscribed.wait()
        created = await create_and_enqueue_job(
            user_id=user_id,
            spec_snapshot=spec,
            settings=settings,
            organization_id=organization_id,
            diagram_id=diagram_id,
            reuse=False,
        )
        job_id = str(created["job_id"])
        tap.job_id = job_id
        print(f"enqueued job={job_id} status={created.get('status')}", flush=True)
        checks["enqueue_not_failed"] = created.get("status") != "failed"
        checks["idle_is_blue"] = button_chrome(None)["tone"] == "start"
        checks["failed_is_red"] = button_chrome("failed")["tone"] == "failed"

        active_status = await _wait_pg(job_id, _ACTIVE, timeout=30.0, timeline=timeline, tap=tap)
        checks["left_idle"] = active_status in _ACTIVE or active_status in _TERMINAL
        if active_status in _ACTIVE:
            event = await _pg_event(job_id)
            chrome = _chrome_from_event(event)
            checks["inflight_busy"] = chrome["tone"] == "busy"
            dropped = await classroom_sse_reconcile_payload(job_id)
            checks["sse_drop_pg"] = sse_job_status(dropped) in _ACTIVE | _TERMINAL
            checks["sse_drop_matches_row"] = sse_job_status(dropped) == active_status
            reused = await _reusable(user_id, spec, settings, diagram_id)
            kitty_reused = await _reusable(user_id, _kitty_spec(), settings, diagram_id)
            checks["inflight_reuse"] = reused == job_id
            checks["inflight_reuse_after_kitty"] = kitty_reused == job_id
            reattach = await create_and_enqueue_job(
                user_id=user_id,
                spec_snapshot=spec,
                settings=settings,
                organization_id=organization_id,
                diagram_id=diagram_id,
                reuse=True,
            )
            checks["enqueue_reattach"] = reattach.get("reused") is True and reattach.get("job_id") == job_id
            busy_hit = False
            try:
                await create_and_enqueue_job(
                    user_id=user_id,
                    spec_snapshot=spec,
                    settings=settings,
                    organization_id=organization_id,
                    diagram_id=diagram_id,
                    reuse=False,
                )
            except ClassroomJobsBusy as exc:
                busy_hit = exc.job_id == job_id
            checks["second_start_429"] = busy_hit

        final = await _wait_pg(job_id, _TERMINAL, timeout=JOB_TIMEOUT_S, timeline=timeline, tap=tap)
        try:
            await asyncio.wait_for(tap.terminal.wait(), timeout=5.0)
        except TimeoutError:
            pass
        event = await _pg_event(job_id)
        chrome = _chrome_from_event(event)
        checks["ready_or_partial"] = final in {"ready", "partial"}
        checks["ready_green"] = chrome["tone"] == "ready"
        checks["ready_unusable_is_blue"] = button_chrome(final, has_prepared=False)["tone"] == "start"
        ready_same = await _reusable(user_id, spec, settings, diagram_id)
        ready_kitty = await _reusable(user_id, _kitty_spec(), settings, diagram_id)
        checks["ready_reuse_same_map"] = ready_same == job_id
        checks["ready_kitty_rewrite_is_fresh"] = ready_kitty is None
        result = event.get("result_json") if event else None
        checks["ready_script_reusable"] = classroom_ready_job_reusable(
            spec_hash=hash_spec_snapshot(spec),
            wanted_hash=hash_spec_snapshot(spec),
            spec_node_ids=spec_snapshot_node_ids(spec),
            live_ids=set(spec_snapshot_node_ids(spec)),
            result_json=result,
        )
        checks["redis_saw_ready"] = any(item in tap.statuses for item in ("ready", "partial"))
        checks["pg_redis_agree_terminal"] = bool(tap.statuses) and tap.statuses[-1] == final
        return {
            "job_id": job_id,
            "final": final,
            "checks": checks,
            "timeline": timeline,
            "redis": tap.statuses,
            "chrome": chrome,
        }
    finally:
        listener.cancel()
        try:
            await listener
        except asyncio.CancelledError:
            pass


async def main() -> int:
    """Run the live status audit and write tmp/mind_classroom_status_e2e/summary.json."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    diagram = load_real_mindmap()
    spec = diagram["spec"] if isinstance(diagram["spec"], dict) else {}
    diagram_id = str(diagram["id"])
    title = str(diagram["title"])
    user_id = int(diagram["user_id"])
    org_raw = diagram.get("organization_id")
    organization_id = int(org_raw) if org_raw is not None else None
    settings = tour_settings("qwen")
    print(
        f"map={title!r} id={diagram_id} nodes={len(spec_snapshot_node_ids(spec))} user={user_id}",
        flush=True,
    )

    async with system_rls_session() as db:
        active = await MindClassroomJobRepository(db).list_active_jobs(user_id)
    if active:
        summary = {
            "diagram_id": diagram_id,
            "title": title,
            "skipped": "user_has_active_classroom_job",
            "blocking_job_id": active[0].id,
            "blocking_status": active[0].status,
            "passed": False,
        }
        (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
        return 1

    started = time.monotonic()
    result = await _run_live(
        user_id=user_id,
        organization_id=organization_id,
        diagram_id=diagram_id,
        spec=spec,
        settings=settings,
    )
    checks = result["checks"]
    summary = {
        "diagram_id": diagram_id,
        "title": title,
        "nodes": len(spec_snapshot_node_ids(spec)),
        "job_id": result["job_id"],
        "final": result["final"],
        "elapsed_s": round(time.monotonic() - started, 2),
        "redis_statuses": result["redis"],
        "button": result["chrome"],
        "timeline": result["timeline"],
        "checks": checks,
        "passed": all(checks.values()),
    }
    dest = OUT_DIR / "summary.json"
    dest.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
