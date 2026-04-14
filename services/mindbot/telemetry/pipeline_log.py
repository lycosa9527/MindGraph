"""Structured correlation strings for MindBot pipeline logs (no secrets, no full bodies)."""

from __future__ import annotations

from urllib.parse import urlparse


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
    conv_dingtalk: str = "",
    dify_conv: str = "",
) -> str:
    """
    Single-line correlation prefix for DingTalk ↔ Dify traffic logs.

    Does not include API keys, tokens, or message text.
    """
    parts = [
        f"org_id={org_id}",
        f"robot={clip_id(robot_code, 20)}",
    ]
    mid = clip_id(msg_id, 24)
    if mid:
        parts.append(f"msg_id={mid}")
    staff = clip_id(staff_id, 20)
    if staff:
        parts.append(f"staff={staff}")
    cdt = clip_id(conv_dingtalk, 24)
    if cdt:
        parts.append(f"dt_conv={cdt}")
    dcv = clip_id(dify_conv, 32)
    if dcv:
        parts.append(f"dify_conv={dcv}")
    return " ".join(parts)


def session_webhook_host(session_webhook: str) -> str:
    """Log-safe host for session webhook URL (no path/query)."""
    try:
        netloc = urlparse(session_webhook.strip()).netloc
        return netloc if netloc else "?"
    except (TypeError, ValueError):
        return "?"
