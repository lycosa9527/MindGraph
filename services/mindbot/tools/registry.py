"""Registry and dispatcher for MindBot tool ingress handlers."""

from __future__ import annotations

from typing import Optional, Protocol

from services.mindbot.tools.audit_log import log_tool_intercepted
from services.mindbot.tools.context import HttpResult, ToolIngressContext


class MindbotToolHandler(Protocol):
    """Pre-Dify handler that may short-circuit the MindBot pipeline."""

    priority: int

    def matches(self, ctx: ToolIngressContext) -> bool:
        """Cheap check (regex/type only) before Redis or DB work."""
        raise NotImplementedError

    async def handle(self, ctx: ToolIngressContext) -> Optional[HttpResult]:
        """Return HTTP result when handled, or None to try the next handler."""


_HANDLERS: list[MindbotToolHandler] = []


def register_tool_handler(handler: MindbotToolHandler) -> None:
    """Register a tool handler; lower ``priority`` runs first."""
    _HANDLERS.append(handler)
    _HANDLERS.sort(key=lambda item: item.priority)


async def try_handle_tool_ingress(ctx: ToolIngressContext) -> Optional[HttpResult]:
    """
    Run registered tool handlers before Dify.

    Returns pipeline HTTP result when a handler claims the message, else None.
    """
    if ctx.inbound_msg_type != "text":
        return None
    for handler in _HANDLERS:
        if not handler.matches(ctx):
            continue
        tool_name = getattr(handler, "tool_name", type(handler).__name__)
        log_tool_intercepted(
            tool=str(tool_name),
            org_id=int(ctx.cfg.organization_id),
            staff_id=ctx.sender_staff_id,
            pipeline_ctx=ctx.pipeline_ctx,
        )
        result = await handler.handle(ctx)
        if result is not None:
            return result
    return None
