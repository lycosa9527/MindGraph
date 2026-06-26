"""Shared MindBot DingTalk bind ingress helpers."""

from __future__ import annotations

from typing import Any, Callable, Coroutine, Optional

from models.domain.mindbot_config import OrganizationMindbotConfig
from services.auth.dingtalk_bind_constants import PAIR_PURPOSE_BIND
from services.mindbot.bind.messages import pair_reply_text
from services.mindbot.errors import MindbotErrorCode
from services.mindbot.outbound.text import send_full_reply
from services.mindbot.tools.audit_log import log_tool_delivery_failed

RecordUsageFn = Callable[..., Coroutine[Any, Any, None]]

_INVALID_BIND_STAFF_IDS = frozenset({"", "unknown"})


def is_valid_bind_staff_id(staff_id: str) -> bool:
    """Reject placeholder staff ids from DingTalk callbacks."""
    normalized = (staff_id or "").strip().lower()
    return bool(normalized) and normalized not in _INVALID_BIND_STAFF_IDS


async def finish_pair_reply(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    session_webhook_valid: Optional[str],
    session_webhook_pinned_ip: str,
    pipeline_ctx: str,
    record_usage: RecordUsageFn,
    hdr_for_code: Callable[[MindbotErrorCode], dict[str, str]],
    outcome: MindbotErrorCode,
    purpose: str,
    tool: str = "pair_code",
) -> tuple[int, dict[str, str]]:
    """Send pair (bind/unbind) outcome reply and record MindBot usage."""
    reply = pair_reply_text(outcome, purpose)
    sent_ok, token_failed = await send_full_reply(
        cfg,
        body,
        session_webhook_valid,
        reply,
        pipeline_ctx=pipeline_ctx,
        pinned_ip=session_webhook_pinned_ip,
    )
    if not sent_ok:
        log_tool_delivery_failed(
            tool=tool,
            outcome=outcome.value,
            token_failed=token_failed,
            pipeline_ctx=pipeline_ctx,
        )
    await record_usage(
        outcome,
        reply_text=reply,
        dify_conversation_id=None,
        usage=None,
        streaming=False,
    )
    return 200, hdr_for_code(outcome)


async def finish_bind_reply(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    session_webhook_valid: Optional[str],
    session_webhook_pinned_ip: str,
    pipeline_ctx: str,
    record_usage: RecordUsageFn,
    hdr_for_code: Callable[[MindbotErrorCode], dict[str, str]],
    outcome: MindbotErrorCode,
) -> tuple[int, dict[str, str]]:
    """Send bind outcome reply and record MindBot usage."""
    return await finish_pair_reply(
        cfg,
        body,
        session_webhook_valid,
        session_webhook_pinned_ip,
        pipeline_ctx,
        record_usage,
        hdr_for_code,
        outcome,
        PAIR_PURPOSE_BIND,
    )
