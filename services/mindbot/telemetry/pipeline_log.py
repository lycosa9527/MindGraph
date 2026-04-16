"""Structured correlation strings and log adapters for MindBot pipeline logs.

Structured logging
------------------
:class:`MindBotLogAdapter` injects key observability fields as ``extra`` kwargs on
every log record so JSON log processors (Datadog, ELK, CloudWatch) can index and
alert on them without regex-parsing log lines.

Usage::

    from services.mindbot.telemetry.pipeline_log import get_pipeline_logger
    log = get_pipeline_logger(org_id=42, msg_id="abc", error_code="MINDBOT_OK")
    log.info("[MindBot] pipeline done")
    # The emitted record carries: extra.org_id=42, extra.msg_id="abc", ...

The ``pipeline_ctx`` string (for human-readable log lines) and the structured
``extra`` fields are complementary: use ``pipeline_ctx`` in the message body,
use ``extra`` for machine filtering.
"""

from __future__ import annotations

import logging
from typing import Any, MutableMapping
from urllib.parse import urlparse


class MindBotLogAdapter(logging.LoggerAdapter):
    """Logger adapter that injects MindBot structured fields into every log record.

    Fields injected into ``extra`` (available on ``LogRecord`` attributes):
    - ``mb_org_id`` – organization ID (int or "")
    - ``mb_msg_id`` – inbound message ID (str or "")
    - ``mb_error_code`` – ``MindbotErrorCode`` value or "" when not yet known
    - ``mb_robot_code`` – DingTalk robot code or ""
    - ``mb_streaming`` – True/False/None

    JSON formatters that emit all ``LogRecord.__dict__`` fields (e.g.
    python-json-logger, structlog) will automatically surface these.
    """

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> tuple[Any, MutableMapping[str, Any]]:
        extra = dict(self.extra or {})
        existing = kwargs.get("extra") or {}
        extra.update(existing)
        kwargs["extra"] = extra
        return msg, kwargs


def get_pipeline_logger(
    logger: logging.Logger,
    *,
    org_id: int | str = "",
    msg_id: str = "",
    error_code: str = "",
    robot_code: str = "",
    streaming: bool | None = None,
) -> MindBotLogAdapter:
    """Return a :class:`MindBotLogAdapter` that enriches log records with pipeline context."""
    return MindBotLogAdapter(
        logger,
        {
            "mb_org_id": org_id,
            "mb_msg_id": msg_id,
            "mb_error_code": error_code,
            "mb_robot_code": robot_code,
            "mb_streaming": streaming,
        },
    )


def clip_id(value: str | None, max_len: int = 28) -> str:
    """Truncate ids for log lines; empty string if missing."""
    if value is None:
        return ""
    s = value.strip()
    if not s:
        return ""
    if len(s) <= max_len:
        return s
    return f"{s[: max_len - 3]}..."


def format_pipeline_ctx(
    org_id: int,
    robot_code: str,
    *,
    msg_id: str = "",
    staff_id: str = "",
    nick: str = "",
    chat_type: str = "",
    conv_dingtalk: str = "",
    dify_conv: str = "",
) -> str:
    """
    Single-line correlation prefix for DingTalk ↔ Dify traffic logs.

    Field order: who (staff/nick) → where (chat_type:conv) → trace (org, robot, msg, dify).
    Does not include API keys, tokens, or message text.

    ``chat_type`` should be ``"group"`` or ``"1:1"``; when set it is prefixed to the
    conversation id as ``group:conv`` or ``1:1:conv`` for at-a-glance context.
    ``nick`` is the sender display name; appended as ``staff=id(Nick)`` when present.
    """
    parts = []
    staff = clip_id(staff_id, 20)
    if staff:
        nick_s = nick.strip()[:20] if isinstance(nick, str) else ""
        parts.append(f"staff={staff}({nick_s})" if nick_s else f"staff={staff}")
    cdt = clip_id(conv_dingtalk, 20)
    if chat_type and cdt:
        parts.append(f"{chat_type}:{cdt}")
    elif chat_type:
        parts.append(f"chat={chat_type}")
    elif cdt:
        parts.append(f"conv={cdt}")
    parts.append(f"org={org_id}")
    parts.append(f"robot={clip_id(robot_code, 12)}")
    mid = clip_id(msg_id, 16)
    if mid:
        parts.append(f"msg={mid}")
    dcv = clip_id(dify_conv, 24)
    if dcv:
        parts.append(f"dify={dcv}")
    return " ".join(parts)


def session_webhook_host(session_webhook: str) -> str:
    """Log-safe host for session webhook URL (no path/query)."""
    try:
        netloc = urlparse(session_webhook.strip()).netloc
        return netloc if netloc else "?"
    except (TypeError, ValueError):
        return "?"
