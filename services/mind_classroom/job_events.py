"""Redis pub/sub snapshots for Mind Classroom job SSE."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from redis.exceptions import RedisError

from repositories.mind_classroom_repo import MindClassroomJobRepository
from services.mind_classroom.job_payload import job_event_dict
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import DATABASE_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

CHANNEL_PREFIX = "mind_classroom:job"
HEARTBEAT_SECONDS = 15
MAX_SSE_CONNECTIONS_PER_USER = 4
TERMINAL_JOB_STATUSES = frozenset({"ready", "partial", "failed", "cancelled"})


class _SseConnectionHolder:
    """Per-process open SSE counts (no module-level mutation at import)."""

    def __init__(self) -> None:
        self.by_user: dict[int, int] = {}


_SSE = _SseConnectionHolder()


def classroom_job_channel(job_id: str) -> str:
    """Redis channel for one classroom job."""
    return f"{CHANNEL_PREFIX}:{job_id}"


def build_progress_payload(job_dict: dict[str, Any]) -> str:
    """JSON payload for a progress SSE / pub/sub event."""
    return json.dumps({"type": "progress", "job": job_dict}, ensure_ascii=False)


def build_heartbeat_payload() -> str:
    """JSON payload for SSE keep-alive."""
    return json.dumps({"type": "heartbeat"}, ensure_ascii=False)


def decode_pubsub_data(raw: Any) -> Optional[str]:
    """Decode Redis pub/sub message data to UTF-8 text."""
    if isinstance(raw, (bytes, bytearray)):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if isinstance(raw, str):
        return raw
    return None


def sse_job_status(payload: str) -> Optional[str]:
    """Read ``job.status`` from an SSE / pub/sub JSON frame."""
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    job = parsed.get("job")
    if not isinstance(job, dict):
        return None
    status_value = job.get("status")
    return status_value if isinstance(status_value, str) else None


def sse_payload_is_terminal(payload: str) -> bool:
    """True when the frame is a finished classroom job."""
    status_value = sse_job_status(payload)
    return bool(status_value and status_value in TERMINAL_JOB_STATUSES)


async def load_classroom_job_event(job_id: str) -> Optional[dict[str, Any]]:
    """Read the Postgres manifesto as a public job dict."""
    if not job_id:
        return None
    try:
        async with system_rls_session() as db:
            row = await MindClassroomJobRepository(db).get_by_uuid(job_id)
    except DATABASE_ERRORS as exc:
        logger.debug("[MindClassroom] manifesto read failed job=%s: %s", job_id, exc)
        return None
    if row is None:
        return None
    return job_event_dict(row)


async def classroom_sse_reconcile_payload(job_id: str) -> str:
    """Idle-tick frame: Postgres snapshot, or a heartbeat if the row is gone."""
    job_dict = await load_classroom_job_event(job_id)
    if job_dict is None:
        return build_heartbeat_payload()
    return build_progress_payload(job_dict)


async def publish_classroom_job_progress(job_id: str, job_dict: dict[str, Any]) -> None:
    """Push a job snapshot to SSE subscribers."""
    redis = get_async_redis()
    if redis is None:
        return
    channel = classroom_job_channel(job_id)
    payload = build_progress_payload(job_dict)
    try:
        await redis.publish(channel, payload)
    except (RedisError, TypeError, ValueError) as exc:
        logger.debug("[MindClassroom] progress publish failed job=%s: %s", job_id, exc)


async def publish_classroom_job_snapshot(job_id: str) -> None:
    """Re-read the manifesto row and publish it on Redis."""
    job_dict = await load_classroom_job_event(job_id)
    if job_dict is None:
        return
    await publish_classroom_job_progress(job_id, job_dict)


def increment_sse_connection(user_id: int) -> None:
    """Track an open SSE stream for rate limiting."""
    _SSE.by_user[user_id] = _SSE.by_user.get(user_id, 0) + 1


def decrement_sse_connection(user_id: int) -> None:
    """Release one SSE stream slot."""
    count = _SSE.by_user.get(user_id, 0)
    if count <= 1:
        _SSE.by_user.pop(user_id, None)
        return
    _SSE.by_user[user_id] = count - 1


def sse_connection_count(user_id: int) -> int:
    """Return how many SSE streams this user currently holds."""
    return _SSE.by_user.get(user_id, 0)
