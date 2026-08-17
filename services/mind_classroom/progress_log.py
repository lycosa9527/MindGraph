"""Mind Classroom job-stage lines for workers and uvicorn poll."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any, Optional

logger = logging.getLogger("services.mind_classroom")

POLL_HEARTBEAT_SEC = 15.0
STREAM_HEARTBEAT_SEC = 15.0
STREAM_CHAR_STEP = 800
_POLL_STATE_CAP = 64


class _PollLogHolder:
    """Last poll fingerprint per job (no module-level mutation)."""

    def __init__(self) -> None:
        self.entries: dict[str, tuple[str, float]] = {}


_POLL_LOGS = _PollLogHolder()


def job_elapsed_seconds(row: Any) -> Optional[float]:
    """Seconds since started_at, else created_at."""
    stamp = getattr(row, "started_at", None) or getattr(row, "created_at", None)
    if stamp is None:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - stamp).total_seconds())


def progress_phase(progress: Optional[dict[str, Any]]) -> str:
    """``progress.phase`` when it is a non-empty string."""
    if not isinstance(progress, dict):
        return ""
    phase = progress.get("phase")
    if isinstance(phase, str) and phase.strip():
        return phase.strip()
    return ""


def progress_branch_part(progress: Optional[dict[str, Any]]) -> str:
    """``branch=1/4`` when both counts are present."""
    if not isinstance(progress, dict):
        return ""
    branch = progress.get("branch")
    total = progress.get("branch_total")
    if isinstance(branch, int) and isinstance(total, int) and total > 0:
        return f"branch={branch}/{total}"
    return ""


def poll_fingerprint(status: str, progress: Optional[dict[str, Any]]) -> str:
    """Stable key for poll-log dedupe (status + phase + branch + done + tts)."""
    phase = progress_phase(progress) or status
    branch = progress_branch_part(progress)
    done = ""
    tts = ""
    if isinstance(progress, dict):
        if isinstance(progress.get("done"), int):
            done = f"done={progress['done']}"
        if progress.get("tts_ready") is True:
            tts = "tts"
    return f"{status}|{phase}|{branch}|{done}|{tts}"


def format_llm_stream_detail(
    *,
    branch: Optional[int],
    branch_total: Optional[int],
    branch_label: str,
    chars: int,
    elapsed_s: float,
    first_token: bool = False,
    idle: bool = False,
) -> str:
    """Worker line while DashScope tokens arrive for one branch."""
    parts = ["LLM result streaming"]
    if branch is not None and branch_total is not None:
        parts.append(f"for branch {branch}/{branch_total}")
    else:
        parts.append("for full tour")
    if branch_label:
        parts.append(f"label={branch_label}")
    if first_token:
        parts.append("first_token")
    if idle:
        parts.append("waiting")
    parts.append(f"chars={chars}")
    parts.append(f"elapsed={elapsed_s:.1f}s")
    return " ".join(parts)


def should_log_llm_stream(
    *,
    chars: int,
    last_chars: int,
    last_at: float,
    now: float,
    first_token: bool,
    idle: bool = False,
    heartbeat_sec: float = STREAM_HEARTBEAT_SEC,
    char_step: int = STREAM_CHAR_STEP,
) -> bool:
    """Log first token, idle/time heartbeats, or every ``char_step`` new chars."""
    if first_token:
        return True
    if (now - last_at) >= heartbeat_sec:
        return True
    if idle:
        return False
    return (chars - last_chars) >= char_step


def format_job_stage_line(
    job_id: str,
    detail: str,
    *,
    status: Optional[str] = None,
    phase: Optional[str] = None,
) -> str:
    """Worker INFO line: reading spec, DashScope sent, LLM received."""
    parts = [f"[MindClassroom] job={job_id}"]
    if status:
        parts.append(f"status={status}")
    if phase:
        parts.append(f"phase={phase}")
    parts.append(detail)
    return " ".join(parts)


def format_poll_line(
    job_id: str,
    *,
    status: str,
    progress: Optional[dict[str, Any]] = None,
    elapsed_s: Optional[float] = None,
) -> str:
    """Uvicorn poll snapshot so GET is not a silent 200."""
    phase = progress_phase(progress) or status
    parts = [f"[MindClassroom] poll job={job_id}", f"status={status}", f"phase={phase}"]
    branch = progress_branch_part(progress)
    if branch:
        parts.append(branch)
    if isinstance(progress, dict):
        in_flight = progress.get("in_flight")
        if isinstance(in_flight, int) and in_flight > 0:
            parts.append(f"in_flight={in_flight}")
        done = progress.get("done")
        total = progress.get("branch_total")
        if isinstance(done, int) and isinstance(total, int) and total > 0:
            parts.append(f"done={done}/{total}")
        if progress.get("tts_ready") is True:
            parts.append("tts_ready")
        label = progress.get("branch_label")
        if isinstance(label, str) and label.strip():
            parts.append(f"label={label.strip()[:40]}")
        chars = progress.get("chars")
        if isinstance(chars, int):
            parts.append(f"chars={chars}")
    if elapsed_s is not None:
        parts.append(f"elapsed={elapsed_s:.0f}s")
    return " ".join(parts)


def should_log_poll(
    job_id: str,
    fingerprint: str,
    *,
    now: Optional[float] = None,
    heartbeat_sec: float = POLL_HEARTBEAT_SEC,
) -> bool:
    """True on first sight, phase change, or heartbeat while stuck."""
    current = time.monotonic() if now is None else now
    previous = _POLL_LOGS.entries.get(job_id)
    if previous is None:
        return True
    last_fingerprint, last_at = previous
    if last_fingerprint != fingerprint:
        return True
    return (current - last_at) >= heartbeat_sec


def remember_poll(job_id: str, fingerprint: str, *, now: Optional[float] = None) -> None:
    """Record the last emitted poll line. Evicts oldest entries past the cap."""
    current = time.monotonic() if now is None else now
    entries = _POLL_LOGS.entries
    entries[job_id] = (fingerprint, current)
    overflow = len(entries) - _POLL_STATE_CAP
    if overflow <= 0:
        return
    stale = list(entries.keys())[:overflow]
    for key in stale:
        if key != job_id:
            entries.pop(key, None)


def log_job_stage(job_id: str, detail: str, *, status: Optional[str] = None, phase: Optional[str] = None) -> None:
    """INFO on the worker (and API if called there)."""
    logger.info(format_job_stage_line(job_id, detail, status=status, phase=phase))


def log_job_poll(
    job_id: str,
    *,
    status: str,
    progress: Optional[dict[str, Any]] = None,
    elapsed_s: Optional[float] = None,
    now: Optional[float] = None,
) -> None:
    """INFO on GET poll when the stage moves or a heartbeat is due."""
    fingerprint = poll_fingerprint(status, progress)
    if not should_log_poll(job_id, fingerprint, now=now):
        return
    logger.info(format_poll_line(job_id, status=status, progress=progress, elapsed_s=elapsed_s))
    remember_poll(job_id, fingerprint, now=now)
