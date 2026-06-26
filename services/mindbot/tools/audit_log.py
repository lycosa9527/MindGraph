"""Structured audit logging for MindBot admin-tool ingress (pre-Dify)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_PREFIX = "[MindBotTool]"


def _staff_label(staff_id: str) -> str:
    text = (staff_id or "").strip()
    if not text:
        return "-"
    if len(text) <= 20:
        return text
    return f"{text[:20]}…"


def log_tool_intercepted(
    *,
    tool: str,
    org_id: int,
    staff_id: str,
    pipeline_ctx: str,
) -> None:
    """Log that an inbound message was claimed by an admin tool (Dify skipped)."""
    logger.info(
        "%s intercepted tool=%s org_id=%s staff=%s skip_dify=1 %s",
        _PREFIX,
        tool,
        org_id,
        _staff_label(staff_id),
        pipeline_ctx,
    )


def log_tool_attempt(
    *,
    tool: str,
    org_id: int,
    staff_id: str,
    purpose: str,
    pipeline_ctx: str,
) -> None:
    """Log the start of an admin-tool action from DingTalk."""
    logger.info(
        "%s attempt tool=%s purpose=%s org_id=%s staff=%s %s",
        _PREFIX,
        tool,
        purpose or "-",
        org_id,
        _staff_label(staff_id),
        pipeline_ctx,
    )


def log_tool_outcome(
    *,
    tool: str,
    org_id: int,
    staff_id: str,
    purpose: str,
    outcome: str,
    ok: bool,
    user_id: int | None = None,
    pipeline_ctx: str = "",
) -> None:
    """Log bind/unbind or other admin-tool completion."""
    level = logging.INFO if ok else logging.WARNING
    logger.log(
        level,
        "%s outcome tool=%s ok=%s purpose=%s outcome=%s org_id=%s user_id=%s staff=%s %s",
        _PREFIX,
        tool,
        int(ok),
        purpose or "-",
        outcome,
        org_id,
        user_id if user_id is not None else "-",
        _staff_label(staff_id),
        pipeline_ctx,
    )


def log_tool_rejected(
    *,
    tool: str,
    org_id: int,
    staff_id: str,
    reason: str,
    pipeline_ctx: str,
) -> None:
    """Log admin-tool rejection before claim (invalid staff, rate limit, etc.)."""
    logger.warning(
        "%s rejected tool=%s reason=%s org_id=%s staff=%s %s",
        _PREFIX,
        tool,
        reason,
        org_id,
        _staff_label(staff_id),
        pipeline_ctx,
    )


def log_tool_delivery_failed(
    *,
    tool: str,
    outcome: str,
    token_failed: bool,
    pipeline_ctx: str,
) -> None:
    """Log when the admin-tool reply could not be delivered to DingTalk."""
    logger.warning(
        "%s delivery_failed tool=%s outcome=%s token_failed=%s %s",
        _PREFIX,
        tool,
        outcome,
        int(token_failed),
        pipeline_ctx,
    )
