"""Dispatch MindBot tool ingress before Dify."""

from __future__ import annotations

from typing import Any, Callable, Coroutine, Optional

from services.mindbot.tools.context import ToolIngressContext
from services.mindbot.tools.handlers.pair_code import PairCodeToolHandler
from services.mindbot.tools.registry import register_tool_handler, try_handle_tool_ingress

register_tool_handler(PairCodeToolHandler())

RecordUsageFn = Callable[..., Coroutine[Any, Any, None]]


async def try_handle_mindbot_tools(
    *,
    cfg: Any,
    body: dict[str, Any],
    inbound_msg_type: str,
    text_in: str,
    sender_staff_id: str,
    session_webhook_valid: Optional[str],
    session_webhook_pinned_ip: str,
    pipeline_ctx: str,
    record_usage: RecordUsageFn,
    hdr_for_code: Callable[..., dict[str, str]],
) -> Optional[tuple[int, dict[str, str]]]:
    """Run registered tool handlers; return None to continue to Dify."""
    ctx = ToolIngressContext(
        cfg=cfg,
        body=body,
        inbound_msg_type=inbound_msg_type,
        text_in=text_in,
        sender_staff_id=sender_staff_id,
        session_webhook_valid=session_webhook_valid,
        session_webhook_pinned_ip=session_webhook_pinned_ip,
        pipeline_ctx=pipeline_ctx,
        record_usage=record_usage,
        hdr_for_code=hdr_for_code,
    )
    return await try_handle_tool_ingress(ctx)
