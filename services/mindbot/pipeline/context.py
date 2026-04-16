"""Shared context types for MindBot pipeline branch functions.

``DifyReplyContext`` carries the ten parameters that are identical for both
``run_streaming_dify_branch`` and ``run_blocking_send_branch``, shrinking
each function's parameter list and making test fixtures reusable.

Callable type aliases:
    RecordUsageCallable: async (outcome, *, reply_text, dify_conversation_id, usage, streaming)
    HdrCallable:         (error_code) -> dict[str, str]
    RedisBindDifyConvCallable: async (...) -> None
"""

from __future__ import annotations

import dataclasses
from typing import Any, Awaitable, Callable, Optional

from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.errors import MindbotErrorCode


RecordUsageCallable = Callable[..., Awaitable[None]]
HdrCallable = Callable[[MindbotErrorCode], dict[str, str]]
RedisBindDifyConvCallable = Callable[..., Awaitable[None]]


@dataclasses.dataclass
class DifyReplyContext:
    """Parameters shared by ``run_streaming_dify_branch`` and ``run_blocking_send_branch``.

    Encapsulating these ten fields in one object:
    - Reduces each branch function from 14–18 keyword params to 4–9.
    - Allows test fixtures to build the context once and reuse it across cases.
    - Makes the shared contract between streaming and blocking paths explicit.
    """

    cfg: OrganizationMindbotConfig
    body: dict[str, Any]
    session_webhook_valid: Optional[str]
    conversation_id_dt: str
    conv_key: str
    record_usage: RecordUsageCallable
    hdr: HdrCallable
    redis_bind_dify_conversation: RedisBindDifyConvCallable
    pipeline_ctx: str = ""
    session_webhook_pinned_ip: str = ""
