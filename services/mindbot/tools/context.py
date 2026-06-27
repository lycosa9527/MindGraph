"""Shared context for MindBot tool ingress handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Optional

from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.errors import MindbotErrorCode

RecordUsageFn = Callable[..., Coroutine[Any, Any, None]]
HttpResult = tuple[int, dict[str, str]]
HdrForCodeFn = Callable[[MindbotErrorCode], dict[str, str]]


@dataclass(frozen=True)
class ToolIngressContext:
    """Inputs available to every MindBot tool handler."""

    cfg: OrganizationMindbotConfig
    body: dict[str, Any]
    inbound_msg_type: str
    text_in: str
    sender_staff_id: str
    session_webhook_valid: Optional[str]
    session_webhook_pinned_ip: str
    pipeline_ctx: str
    record_usage: RecordUsageFn
    hdr_for_code: HdrForCodeFn
