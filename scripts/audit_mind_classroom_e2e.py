"""
Live 思维讲堂 audit: one real mind map → script + first-slide audio.

Checks mid-job prefix persist, TTS, and LLM-slot isolation (qwen vs deepseek).

Usage (WSL, repo root, conda python313):
  PYTHONPATH=. python scripts/audit_mind_classroom_e2e.py
"""

from __future__ import annotations

import asyncio
import json
import os
import struct
import time
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import create_engine, text as sql_text

from repositories.mind_classroom_repo import MindClassroomJobRepository
from services.kitty.tts.cosyvoice_realtime import resolve_runtime_model_and_voice
from services.mind_classroom.enqueue import create_and_enqueue_job
from services.mind_classroom.job_events import (
    TERMINAL_JOB_STATUSES,
    decode_pubsub_data,
)
from services.mind_classroom.job_manifest import hash_spec_snapshot
from services.mind_classroom.job_match import (
    job_matches_live_nodes,
    job_matches_llm_model,
    spec_snapshot_node_ids,
)
from services.mind_classroom.transcript_md import render_transcript_markdown
from services.redis.redis_async_client import get_async_redis
from services.tts.facade import TtsSynthRequest, synthesize_http
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from tests.smoke.mindmap_smoke_helpers import mindmap_smoke_helpers_load_dotenv
from utils.db.session_open import system_rls_session

ROOT = Path(__file__).resolve().parents[1]
mindmap_smoke_helpers_load_dotenv(ROOT / ".env")
OUT_DIR = ROOT / "tmp" / "mind_classroom_e2e"
PREFERRED_DIAGRAM_IDS = (
    "59f5fab0-6ee0-4b75-b82a-cf5de9aea852",
    "fe00a4fd-ba17-40bf-af38-609dc39c0c87",
    "81e73295-c70b-4708-a5d5-240db65473f1",
    "6d225751-2183-41e9-b033-97fd9dae6ef0",
)
JOB_TIMEOUT_S = 420.0


def _sync_db_url() -> str:
    raw = (os.environ.get("DATABASE_URL") or "").strip()
    if not raw:
        raise RuntimeError("DATABASE_URL is not set")
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)


def _node_count(spec: dict[str, Any]) -> int:
    nodes = spec.get("nodes")
    return len(nodes) if isinstance(nodes, list) else 0


def load_real_mindmap() -> dict[str, Any]:
    """Pick a saved mind map with enough nodes for a canvas tour."""
    engine = create_engine(_sync_db_url())
    with engine.connect() as conn:
        for diagram_id in PREFERRED_DIAGRAM_IDS:
            row = (
                conn.execute(
                    sql_text(
                        "SELECT d.id, d.title, d.user_id, d.spec, u.organization_id "
                        "FROM diagrams d JOIN users u ON u.id = d.user_id "
                        "WHERE d.id = :id AND d.is_deleted = false"
                    ),
                    {"id": diagram_id},
                )
                .mappings()
                .first()
            )
            if row and _node_count(row["spec"] if isinstance(row["spec"], dict) else {}) >= 4:
                return dict(row)
        row = (
            conn.execute(
                sql_text(
                    "SELECT d.id, d.title, d.user_id, d.spec, u.organization_id "
                    "FROM diagrams d JOIN users u ON u.id = d.user_id "
                    "WHERE d.is_deleted = false AND d.diagram_type = 'mindmap' "
                    "ORDER BY d.updated_at DESC LIMIT 24"
                )
            )
            .mappings()
            .all()
        )
    for item in row:
        spec = item["spec"] if isinstance(item["spec"], dict) else {}
        if _node_count(spec) >= 4:
            return dict(item)
    raise RuntimeError("No saved mind map with at least 4 nodes")


def tour_settings(llm_model: str) -> dict[str, Any]:
    """Canvas-tour settings for one LLM slot."""
    return {
        "mode": "canvas_tour",
        "mastery": "first_look",
        "tone": "classroom",
        "tour_scope": "main_branch",
        "slide_style": "general",
        "audience_level": "general",
        "audience_title": "",
        "language": "zh",
        "llm_model": llm_model,
    }


def _step_rows(job: dict[str, Any]) -> list[dict[str, Any]]:
    """Lecture steps from a job snapshot."""
    result = job.get("result_json")
    if not isinstance(result, dict):
        return []
    steps = result.get("steps")
    if not isinstance(steps, list):
        return []
    return [step for step in steps if isinstance(step, dict)]


def _first_caption(job: dict[str, Any]) -> str:
    """Opening spoken caption, if the job already has steps."""
    for step in _step_rows(job):
        caption = str(step.get("caption") or "").strip()
        if caption:
            return caption
    return ""


def _write_wav_pcm(path: Path, pcm: bytes, sample_rate: int = 22050) -> None:
    """Write 16-bit mono PCM as a WAV file."""
    data_size = len(pcm)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        sample_rate * 2,
        2,
        16,
        b"data",
        data_size,
    )
    path.write_bytes(header + pcm)


def _write_audio(path: Path, audio: bytes) -> Path:
    """Persist MP3/WAV bytes next to the generated script."""
    if audio[:3] == b"ID3" or audio[:4] == b"ftyp" or audio[:2] == b"\xff\xfb":
        dest = path.with_suffix(".mp3")
        dest.write_bytes(audio)
        return dest
    dest = path.with_suffix(".wav")
    _write_wav_pcm(dest, audio)
    return dest


class JobWatch:
    """Collect Redis job events until terminal or timeout."""

    def __init__(self, job_id: str, started: float) -> None:
        self.job_id = job_id
        self.started = started
        self.done = asyncio.Event()
        self.status = "queued"
        self.job: dict[str, Any] = {}
        self.first_steps_s: Optional[float] = None
        self.prefix_status: Optional[str] = None
        self.ready_s: Optional[float] = None
        self.error: Optional[str] = None

    def apply(self, job: dict[str, Any]) -> None:
        """Merge one Redis job snapshot."""
        self.job = job
        self.status = str(job.get("status") or self.status)
        elapsed = time.monotonic() - self.started
        if self.first_steps_s is None and _step_rows(job):
            self.first_steps_s = elapsed
            self.prefix_status = self.status
        if self.status in TERMINAL_JOB_STATUSES:
            if self.ready_s is None:
                self.ready_s = elapsed
            if self.status in {"failed", "cancelled"}:
                self.error = str(job.get("error_message") or self.status)
            self.done.set()


async def _listen(watch: JobWatch, subscribed: asyncio.Event) -> None:
    """Follow Redis classroom job events for one watch."""
    redis = get_async_redis()
    pubsub = redis.pubsub()
    await pubsub.psubscribe("mind_classroom:job:*")
    subscribed.set()
    try:
        async for message in pubsub.listen():
            if message is None:
                continue
            if message.get("type") not in {"message", "pmessage"}:
                continue
            raw_payload = decode_pubsub_data(message.get("data"))
            if not raw_payload:
                continue
            try:
                payload = json.loads(raw_payload)
            except json.JSONDecodeError:
                continue
            job = payload.get("job") if isinstance(payload, dict) else None
            if not isinstance(job, dict):
                continue
            if str(job.get("id") or "") != watch.job_id:
                continue
            watch.apply(job)
            if watch.done.is_set():
                return
    finally:
        await pubsub.punsubscribe("mind_classroom:job:*")
        await pubsub.aclose()


async def run_one_job(
    *,
    user_id: int,
    organization_id: Optional[int],
    diagram_id: str,
    spec: dict[str, Any],
    llm_model: str,
) -> JobWatch:
    """Enqueue one canvas-tour job and wait until it is terminal."""
    settings = tour_settings(llm_model)
    watch = JobWatch("", time.monotonic())
    subscribed = asyncio.Event()
    listener = asyncio.create_task(_listen(watch, subscribed))
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
        watch.job_id = str(created["job_id"])
        watch.status = str(created.get("status") or "queued")
        print(
            f"enqueued llm={llm_model} job={watch.job_id} status={watch.status}",
            flush=True,
        )
        if watch.status in TERMINAL_JOB_STATUSES:
            watch.apply(
                {
                    "id": watch.job_id,
                    "status": watch.status,
                    "error_message": created.get("error_message") or "enqueue",
                }
            )
        else:
            await asyncio.wait_for(watch.done.wait(), timeout=JOB_TIMEOUT_S)
    except TimeoutError:
        watch.error = watch.error or "timeout"
        watch.done.set()
    except BACKGROUND_INFRA_ERRORS as exc:
        watch.error = f"enqueue: {exc}"
        watch.done.set()
    except RuntimeError as exc:
        watch.error = f"enqueue: {exc}"
        watch.done.set()
    finally:
        listener.cancel()
        try:
            await listener
        except asyncio.CancelledError:
            pass
    return watch


async def synth_first_caption(job: dict[str, Any], slug: str) -> tuple[Optional[str], Optional[str]]:
    """Synthesize the opening caption the same way Kitty HTTP TTS does."""
    caption = _first_caption(job)
    if not caption:
        return None, "no_caption"
    try:
        model, voice = await resolve_runtime_model_and_voice()
        audio = await synthesize_http(TtsSynthRequest(text=caption, model=model, voice=voice, mode="http"))
        path = _write_audio(OUT_DIR / f"{slug}_first_slide", audio)
        return str(path), None
    except (RuntimeError, OSError, ValueError, TypeError) as exc:
        return None, str(exc)


async def latest_job_id(user_id: int, diagram_id: str, llm_model: str) -> Optional[str]:
    """Same lookup as GET /jobs/by-diagram?llm_model=."""
    async with system_rls_session() as db:
        row = await MindClassroomJobRepository(db).latest_job_for_diagram(
            user_id=user_id,
            diagram_id=diagram_id,
            mode="canvas_tour",
            llm_model=llm_model,
        )
        return row.id if row is not None else None


async def reusable_job_id(
    user_id: int,
    spec: dict[str, Any],
    settings: dict[str, Any],
    diagram_id: Optional[str],
) -> Optional[str]:
    """Reuse must stay on the same spec hash, map, and full settings blob."""
    async with system_rls_session() as db:
        row = await MindClassroomJobRepository(db).find_reusable(
            user_id=user_id,
            spec_hash=hash_spec_snapshot(spec),
            settings=settings,
            diagram_id=diagram_id,
        )
        return row.id if row is not None else None


def write_script(watch: JobWatch, settings: dict[str, Any], slug: str) -> str:
    """Write the generated lesson-plan markdown next to the audio."""
    dest = OUT_DIR / f"{slug}.md"
    dest.write_text(
        render_transcript_markdown(
            job_id=watch.job_id,
            settings=settings,
            steps=_step_rows(watch.job),
            diagram_id=str(watch.job.get("diagram_id") or ""),
        ),
        encoding="utf-8",
    )
    return str(dest)


async def main() -> int:
    """Run the live audit and write tmp/mind_classroom_e2e/summary.json."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    diagram = load_real_mindmap()
    spec = diagram["spec"] if isinstance(diagram["spec"], dict) else {}
    diagram_id = str(diagram["id"])
    title = str(diagram["title"])
    user_id = int(diagram["user_id"])
    org_raw = diagram.get("organization_id")
    organization_id = int(org_raw) if org_raw is not None else None
    live_ids = set(spec_snapshot_node_ids(spec))
    print(
        f"map={title!r} id={diagram_id} nodes={len(live_ids)} user={user_id}",
        flush=True,
    )

    qwen = await run_one_job(
        user_id=user_id,
        organization_id=organization_id,
        diagram_id=diagram_id,
        spec=spec,
        llm_model="qwen",
    )
    tts_path, tts_error = await synth_first_caption(qwen.job, "qwen")
    qwen_md = write_script(qwen, tour_settings("qwen"), "qwen")

    deepseek = await run_one_job(
        user_id=user_id,
        organization_id=organization_id,
        diagram_id=diagram_id,
        spec=spec,
        llm_model="deepseek",
    )
    deepseek_md = write_script(deepseek, tour_settings("deepseek"), "deepseek")

    qwen_lookup = await latest_job_id(user_id, diagram_id, "qwen")
    deepseek_lookup = await latest_job_id(user_id, diagram_id, "deepseek")
    reused_qwen = await reusable_job_id(user_id, spec, tour_settings("qwen"), diagram_id)
    reused_cross = await reusable_job_id(user_id, spec, tour_settings("doubao"), diagram_id)

    qwen_ids = spec_snapshot_node_ids(spec)
    checks = {
        "qwen_ready": qwen.status == "ready" and not qwen.error,
        "qwen_prefix_while_generating": qwen.prefix_status == "generating",
        "qwen_has_steps": len(_step_rows(qwen.job)) > 0,
        "qwen_spec_nodes_overlap": job_matches_live_nodes(qwen_ids, live_ids),
        "qwen_tts": tts_path is not None,
        "deepseek_ready": deepseek.status == "ready" and not deepseek.error,
        "by_diagram_qwen": qwen_lookup == qwen.job_id,
        "by_diagram_deepseek": deepseek_lookup == deepseek.job_id,
        "reuse_same_llm": reused_qwen == qwen.job_id,
        "reuse_does_not_cross_llm": reused_cross is None,
        "llm_match_helper": job_matches_llm_model(tour_settings("qwen"), "qwen")
        and not job_matches_llm_model(tour_settings("qwen"), "deepseek"),
    }
    summary = {
        "diagram_id": diagram_id,
        "title": title,
        "nodes": len(live_ids),
        "qwen": {
            "job_id": qwen.job_id,
            "status": qwen.status,
            "first_script_s": round(qwen.first_steps_s or 0.0, 2),
            "ready_s": round(qwen.ready_s or 0.0, 2),
            "steps": len(_step_rows(qwen.job)),
            "prefix_status": qwen.prefix_status,
            "script_md": qwen_md,
            "first_slide_audio": tts_path,
            "error": qwen.error or tts_error,
        },
        "deepseek": {
            "job_id": deepseek.job_id,
            "status": deepseek.status,
            "first_script_s": round(deepseek.first_steps_s or 0.0, 2),
            "ready_s": round(deepseek.ready_s or 0.0, 2),
            "steps": len(_step_rows(deepseek.job)),
            "script_md": deepseek_md,
            "error": deepseek.error,
        },
        "checks": checks,
        "passed": all(checks.values()),
    }
    dest = OUT_DIR / "summary.json"
    dest.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
