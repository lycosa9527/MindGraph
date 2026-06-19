"""
Redis pub/sub and serialization for MindMate export job progress + control.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from redis.exceptions import RedisError

from models.domain.mindmate_export_job import MindmateExportJob
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

CHANNEL_PREFIX = "mindmate_export:job"
HEARTBEAT_SECONDS = 25
MAX_SSE_CONNECTIONS_PER_USER = 2

TERMINAL_JOB_STATUSES = frozenset(
    {
        "completed",
        "completed_with_gaps",
        "cancelled",
        "failed",
        "failed_verification",
    }
)

_active_sse_connections: Dict[int, int] = {}


def export_job_channel(job_id: int) -> str:
    """Redis channel for one export job's progress and control events."""
    return f"{CHANNEL_PREFIX}:{int(job_id)}"


def export_job_to_dict(job: MindmateExportJob) -> dict:
    """Serialize a job row for API responses and SSE payloads."""
    return {
        "id": int(job.id),
        "status": job.status,
        "current_stage": job.current_stage,
        "progress_percent": int(job.progress_percent or 0),
        "progress_detail": job.progress_detail or {},
        "filters": job.filters or {},
        "verification_report": job.verification_report,
        "artifact_format": job.artifact_format,
        "artifact_size_bytes": job.artifact_size_bytes,
        "artifact_sha256": job.artifact_sha256,
        "error_message": job.error_message,
        "expires_at": job.expires_at.isoformat() if job.expires_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def build_progress_payload(job_dict: dict) -> str:
    """JSON payload for a progress SSE / pub/sub event."""
    return json.dumps({"type": "progress", "job": job_dict}, ensure_ascii=False)


def build_control_payload(action: str) -> str:
    """JSON payload for pause / cancel / resume control signals."""
    return json.dumps({"type": "control", "action": action}, ensure_ascii=False)


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


async def publish_export_job_progress(job_id: int, job_dict: dict) -> None:
    """Push a job snapshot to SSE subscribers and wake in-process listeners."""
    redis = get_async_redis()
    if redis is None:
        return
    channel = export_job_channel(job_id)
    payload = build_progress_payload(job_dict)
    try:
        await redis.publish(channel, payload)
    except (RedisError, TypeError, ValueError) as exc:
        logger.debug(
            "[MindMateExport] progress publish failed job=%s: %s",
            job_id,
            exc,
        )


async def publish_export_job_control(job_id: int, action: str) -> None:
    """Notify the Celery worker to pause, cancel, or resume promptly."""
    redis = get_async_redis()
    if redis is None:
        return
    channel = export_job_channel(job_id)
    payload = build_control_payload(action)
    try:
        await redis.publish(channel, payload)
    except (RedisError, TypeError, ValueError) as exc:
        logger.debug(
            "[MindMateExport] control publish failed job=%s action=%s: %s",
            job_id,
            action,
            exc,
        )


def increment_sse_connection(user_id: int) -> None:
    """Track an open SSE stream for rate limiting."""
    _active_sse_connections[user_id] = _active_sse_connections.get(user_id, 0) + 1


def decrement_sse_connection(user_id: int) -> None:
    """Release one SSE stream slot."""
    count = _active_sse_connections.get(user_id, 0)
    if count <= 1:
        _active_sse_connections.pop(user_id, None)
        return
    _active_sse_connections[user_id] = count - 1


def sse_connection_count(user_id: int) -> int:
    """Return how many SSE streams this user currently holds."""
    return _active_sse_connections.get(user_id, 0)


class ExportJobControlState:
    """In-process control flags fed by Redis pub/sub inside the Celery worker."""

    def __init__(self, job_id: int) -> None:
        self.job_id = int(job_id)
        self.pause_requested = False
        self.cancel_requested = False
        self._reader_task: Optional[asyncio.Task[None]] = None
        self._pubsub = None

    def should_stop(self) -> bool:
        """Return True when pause or cancel was signaled."""
        return self.pause_requested or self.cancel_requested

    async def start(self) -> None:
        """Subscribe to control messages for this job."""
        redis = get_async_redis()
        if redis is None:
            return
        channel = export_job_channel(self.job_id)
        pubsub = redis.pubsub()
        self._pubsub = pubsub
        await pubsub.subscribe(channel)

        async def _reader() -> None:
            try:
                async for message in pubsub.listen():
                    if message is None or message.get("type") != "message":
                        continue
                    text = decode_pubsub_data(message.get("data"))
                    if not text:
                        continue
                    try:
                        data = json.loads(text)
                    except json.JSONDecodeError:
                        continue
                    if data.get("type") != "control":
                        continue
                    action = str(data.get("action") or "")
                    if action == "pause":
                        self.pause_requested = True
                    elif action == "cancel":
                        self.cancel_requested = True
                    elif action == "resume":
                        self.pause_requested = False
                        self.cancel_requested = False
            except (RedisError, OSError, RuntimeError, ValueError) as exc:
                logger.debug(
                    "[MindMateExport] control listener stopped job=%s: %s",
                    self.job_id,
                    exc,
                )

        self._reader_task = asyncio.create_task(
            _reader(),
            name=f"mindmate-export-control-{self.job_id}",
        )

    async def stop(self) -> None:
        """Unsubscribe and cancel the background reader."""
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
        if self._pubsub is not None:
            try:
                channel = export_job_channel(self.job_id)
                await self._pubsub.unsubscribe(channel)
                await self._pubsub.aclose()
            except (RedisError, OSError, RuntimeError, AttributeError) as exc:
                logger.debug(
                    "[MindMateExport] control pubsub close job=%s: %s",
                    self.job_id,
                    exc,
                )
            self._pubsub = None
