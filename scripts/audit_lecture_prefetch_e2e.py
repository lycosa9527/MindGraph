"""
Ground-up 思维讲堂 lookahead audit.

Creates a new mind map in Postgres, runs canvas-tour script generation,
then walks Kitty's one-ahead CosyVoice cache: while branch 1 plays,
branch 2 must already be in the buffer.

Usage (WSL, repo root, conda python313):
  PYTHONPATH=. python scripts/audit_lecture_prefetch_e2e.py
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Optional

from repositories.mind_classroom_repo import MindClassroomJobRepository
from scripts.audit_lecture_prefetch_map import (
    build_prefetch_mindmap,
    persist_prefetch_mindmap,
    pick_map_owner,
)
from scripts.audit_lecture_prefetch_walk import (
    LectureCaption,
    WalkBeat,
    prefetch_walk_checks,
    spoken_lecture_steps,
    walk_lecture_lookahead,
)
from scripts.audit_mind_classroom_e2e import tour_settings
from services.kitty.tts.cosyvoice_realtime import resolve_kitty_tts_enabled
from services.llm import llm_service
from services.mind_classroom.canvas_tour import run_canvas_tour_job
from services.mind_classroom.job_manifest import hash_spec_snapshot
from services.mind_classroom.transcript_md import render_transcript_markdown
from services.redis.redis_client import init_redis_sync
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, LLM_PIPELINE_ERRORS
from tests.smoke.mindmap_smoke_helpers import mindmap_smoke_helpers_load_dotenv
from utils.db.session_open import system_rls_session

ROOT = Path(__file__).resolve().parents[1]
mindmap_smoke_helpers_load_dotenv(ROOT / ".env")
OUT_DIR = ROOT / "tmp" / "lecture_prefetch_e2e"
_AUDIT_ERRORS = BACKGROUND_INFRA_ERRORS + LLM_PIPELINE_ERRORS


def _job_steps(result_json: Any) -> list[dict[str, Any]]:
    if not isinstance(result_json, dict):
        return []
    raw = result_json.get("steps")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


async def create_tour_job(
    *,
    user_id: int,
    organization_id: Optional[int],
    diagram_id: str,
    spec: dict[str, Any],
) -> str:
    """Insert a queued canvas-tour job (no Celery — the audit runs it inline)."""
    settings = tour_settings("qwen")
    async with system_rls_session() as db:
        repo = MindClassroomJobRepository(db)
        row = await repo.create_job(
            user_id=user_id,
            spec_snapshot=spec,
            settings=settings,
            spec_hash=hash_spec_snapshot(spec),
            organization_id=organization_id,
            diagram_id=diagram_id,
            commit=True,
        )
        return row.id


async def load_ready_job(job_id: str) -> dict[str, Any]:
    """Reload the manifesto after canvas-tour generation."""
    async with system_rls_session() as db:
        row = await MindClassroomJobRepository(db).get_by_uuid(job_id)
        if row is None:
            raise RuntimeError(f"Classroom job missing id={job_id}")
        return {
            "id": row.id,
            "status": row.status,
            "error_message": row.error_message,
            "diagram_id": row.diagram_id,
            "result_json": row.result_json,
            "settings": row.settings,
        }


def _beat_payload(beat: WalkBeat) -> dict[str, Any]:
    return {
        "index": beat.index,
        "step_id": beat.step_id,
        "kind": beat.kind,
        "title": beat.title,
        "played_from": beat.played_from,
        "prefetch_step_id": beat.prefetch_step_id,
        "prefetch_ready": beat.prefetch_ready,
        "chunk_count": beat.chunk_count,
        "audio_path": beat.audio_path,
    }


def _step_payload(step: LectureCaption) -> dict[str, Any]:
    return {
        "id": step.id,
        "kind": step.kind,
        "title": step.title,
        "caption_chars": len(step.caption),
    }


def write_job_script(job: dict[str, Any], dest: Path) -> str:
    """Persist the generated lesson-plan markdown next to the audio."""
    raw_settings = job.get("settings")
    settings = raw_settings if isinstance(raw_settings, dict) else {}
    dest.write_text(
        render_transcript_markdown(
            job_id=str(job.get("id") or ""),
            settings=settings,
            steps=_job_steps(job.get("result_json")),
            diagram_id=str(job.get("diagram_id") or ""),
        ),
        encoding="utf-8",
    )
    return str(dest)


async def main() -> int:
    """Create a map, generate the tour, then prove N+1 audio is cached."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not resolve_kitty_tts_enabled():
        raise RuntimeError("KITTY_TTS_ENABLED is off")
    init_redis_sync()
    llm_service.initialize()

    spec = build_prefetch_mindmap()
    user_id, organization_id = await pick_map_owner()
    diagram_id = await persist_prefetch_mindmap(spec, user_id=user_id)
    print(
        f"map id={diagram_id} user={user_id} nodes={len(spec['nodes'])}",
        flush=True,
    )

    job_id = await create_tour_job(
        user_id=user_id,
        organization_id=organization_id,
        diagram_id=diagram_id,
        spec=spec,
    )
    print(f"job id={job_id} running canvas tour", flush=True)
    ok = await run_canvas_tour_job(job_id)
    job = await load_ready_job(job_id)
    if not ok or job["status"] not in {"ready", "partial"}:
        raise RuntimeError(
            f"Canvas tour failed status={job['status']} error={job.get('error_message')}"
        )

    spoken = spoken_lecture_steps(_job_steps(job.get("result_json")))
    script_md = write_job_script(job, OUT_DIR / "lesson_plan.md")
    print(
        f"job ready steps={len(spoken)} script={script_md}",
        flush=True,
    )
    if len(spoken) < 3:
        raise RuntimeError(f"Tour produced {len(spoken)} spoken steps; need at least 3")

    print("walking CosyVoice lookahead (overview + branch 1 + next)", flush=True)
    beats = await walk_lecture_lookahead(spoken, OUT_DIR)
    checks = prefetch_walk_checks(spoken, beats)
    checks["job_ready"] = job["status"] in {"ready", "partial"}
    checks["enough_spoken_steps"] = len(spoken) >= 3
    summary = {
        "diagram_id": diagram_id,
        "job_id": job_id,
        "status": job["status"],
        "script_md": script_md,
        "steps": [_step_payload(step) for step in spoken],
        "beats": [_beat_payload(beat) for beat in beats],
        "checks": checks,
        "passed": all(checks.values()),
    }
    dest = OUT_DIR / "summary.json"
    dest.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except _AUDIT_ERRORS as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=False), flush=True)
        raise SystemExit(1) from exc
