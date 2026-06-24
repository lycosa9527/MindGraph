"""
Error alert dispatcher — webhook and DingTalk notifications with Redis dedup.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import deque
from typing import Any

import httpx
from sqlalchemy import select

from config.db_sessions import open_async_session
from models.domain.error_event import ErrorGroup
from services.monitoring.error_alert_config import (
    error_collection_enabled,
    error_retention_days,
    get_error_alert_config,
)
from services.monitoring.error_record import ErrorRecord
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

try:
    from services.redis.redis_async_client import get_async_redis
    from services.redis.redis_client import is_redis_available

    _REDIS_AVAILABLE = True
except ImportError:
    get_async_redis = None
    is_redis_available = None
    _REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

ALERT_SENT_KEY_PREFIX = "error_alert:sent:"

_recent_fingerprint_times: dict[str, deque[float]] = {}


class AlertDispatcher:
    """Evaluate alert rules after an error is recorded."""

    @staticmethod
    def _alert_hash(fingerprint: str, rule: str) -> str:
        raw = f"{fingerprint}:{rule}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    async def _was_alert_sent(alert_hash: str) -> bool:
        if not _REDIS_AVAILABLE or is_redis_available is None or not is_redis_available():
            return False
        if get_async_redis is None:
            return False
        try:
            redis_client = get_async_redis()
            if redis_client is None:
                return False
            key = f"{ALERT_SENT_KEY_PREFIX}{alert_hash}"
            return bool(await redis_client.exists(key))
        except BACKGROUND_INFRA_ERRORS as redis_error:
            logger.debug("[ErrorAlert] Redis check failed: %s", redis_error)
            return False

    @staticmethod
    async def _mark_alert_sent(alert_hash: str, cooldown_seconds: int) -> None:
        if not _REDIS_AVAILABLE or is_redis_available is None or not is_redis_available():
            return
        if get_async_redis is None:
            return
        try:
            redis_client = get_async_redis()
            if redis_client is None:
                return
            key = f"{ALERT_SENT_KEY_PREFIX}{alert_hash}"
            await redis_client.setex(key, cooldown_seconds, "1")
        except BACKGROUND_INFRA_ERRORS as redis_error:
            logger.debug("[ErrorAlert] Redis mark failed: %s", redis_error)

    @staticmethod
    def _count_recent(fingerprint: str, window_seconds: int) -> int:
        now = time.monotonic()
        bucket = _recent_fingerprint_times.setdefault(fingerprint, deque())
        while bucket and (now - bucket[0]) > window_seconds:
            bucket.popleft()
        bucket.append(now)
        return len(bucket)

    @staticmethod
    def _should_alert(record: ErrorRecord) -> tuple[bool, str]:
        if record.severity == "critical":
            return True, "critical"
        config = get_error_alert_config()
        count = AlertDispatcher._count_recent(
            record.fingerprint or "",
            config.threshold_window_seconds,
        )
        if count >= config.threshold_count:
            return True, "threshold"
        return False, ""

    @staticmethod
    async def _post_json(url: str, payload: dict[str, Any]) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

    @staticmethod
    async def _send_webhook(record: ErrorRecord, rule: str, event_id: int | None) -> None:
        config = get_error_alert_config()
        if not config.webhook_url:
            return
        payload = {
            "rule": rule,
            "event_id": event_id,
            "severity": record.severity,
            "source": record.source,
            "component": record.component,
            "exception_type": record.exception_type,
            "message": record.message,
            "fingerprint": record.fingerprint,
            "http_path": record.http_path,
            "tags": record.tags or {},
        }
        await AlertDispatcher._post_json(config.webhook_url, payload)

    @staticmethod
    async def _send_dingtalk(record: ErrorRecord, rule: str) -> None:
        config = get_error_alert_config()
        if not config.dingtalk_webhook_url:
            return
        title = f"[MindGraph] {record.severity.upper()} — {record.component}"
        text_lines = [
            f"### {title}",
            f"- **规则**: {rule}",
            f"- **来源**: {record.source}",
            f"- **类型**: {record.exception_type or '—'}",
            f"- **消息**: {record.message[:500]}",
        ]
        if record.http_path:
            text_lines.append(f"- **路径**: {record.http_path}")
        if record.fingerprint:
            text_lines.append(f"- **指纹**: `{record.fingerprint}`")
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": "\n".join(text_lines),
            },
        }
        await AlertDispatcher._post_json(config.dingtalk_webhook_url, payload)

    @staticmethod
    async def _is_group_muted(fingerprint: str) -> bool:
        if not fingerprint:
            return False
        try:
            async with open_async_session() as session:
                muted = (
                    await session.execute(select(ErrorGroup.muted).where(ErrorGroup.fingerprint == fingerprint))
                ).scalar_one_or_none()
            return bool(muted)
        except BACKGROUND_INFRA_ERRORS as db_error:
            logger.debug("[ErrorAlert] Muted check failed: %s", db_error)
            return False

    @staticmethod
    async def evaluate_after_record(record: ErrorRecord, event_id: int | None) -> None:
        """Run alert rules for a newly persisted error."""
        config = get_error_alert_config()
        if not config.enabled:
            return
        if not config.webhook_url and not config.dingtalk_webhook_url:
            return
        if await AlertDispatcher._is_group_muted(record.fingerprint or ""):
            return

        should_alert, rule = AlertDispatcher._should_alert(record)
        if not should_alert:
            return

        alert_hash = AlertDispatcher._alert_hash(record.fingerprint or record.message, rule)
        if await AlertDispatcher._was_alert_sent(alert_hash):
            return

        sent_any = False
        try:
            if config.webhook_url:
                await AlertDispatcher._send_webhook(record, rule, event_id)
                sent_any = True
        except httpx.HTTPError as webhook_error:
            logger.warning("[ErrorAlert] Webhook delivery failed: %s", webhook_error)
        except BACKGROUND_INFRA_ERRORS as webhook_error:
            logger.warning("[ErrorAlert] Webhook delivery failed: %s", webhook_error)

        try:
            if config.dingtalk_webhook_url:
                await AlertDispatcher._send_dingtalk(record, rule)
                sent_any = True
        except httpx.HTTPError as dingtalk_error:
            logger.warning("[ErrorAlert] DingTalk delivery failed: %s", dingtalk_error)
        except BACKGROUND_INFRA_ERRORS as dingtalk_error:
            logger.warning("[ErrorAlert] DingTalk delivery failed: %s", dingtalk_error)

        if sent_any:
            await AlertDispatcher._mark_alert_sent(alert_hash, config.cooldown_seconds)

    @staticmethod
    def config_summary() -> dict[str, Any]:
        """Return read-only alert and retention settings for the admin UI."""
        config = get_error_alert_config()
        return {
            "enabled": config.enabled,
            "webhook_configured": bool(config.webhook_url),
            "dingtalk_configured": bool(config.dingtalk_webhook_url),
            "threshold_count": config.threshold_count,
            "threshold_window_seconds": config.threshold_window_seconds,
            "cooldown_seconds": config.cooldown_seconds,
            "retention_days": error_retention_days(),
            "collection_enabled": error_collection_enabled(),
        }
