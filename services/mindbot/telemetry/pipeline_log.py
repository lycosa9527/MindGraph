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

    Field order: who (staff) → where (conv) → trace (org, robot, msg, dify).
    Does not include API keys, tokens, or message text.
    """
    parts = []
    staff = clip_id(staff_id, 20)
    if staff:
        parts.append(f"staff={staff}")
    cdt = clip_id(conv_dingtalk, 20)
    if cdt:
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
