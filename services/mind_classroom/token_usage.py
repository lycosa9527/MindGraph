"""Token usage tracking for Mind Classroom LLM / Wan calls."""

from __future__ import annotations

import logging
from typing import Any, Optional

from services.redis.redis_token_buffer import get_token_tracker
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)


async def track_classroom_usage(
    *,
    model_alias: str,
    usage: Optional[dict[str, Any]],
    request_type: str,
    user_id: Optional[int],
    organization_id: Optional[int],
    job_id: str,
    response_time: float,
    success: bool,
) -> None:
    """Best-effort token tracker write."""
    usage_data = usage or {}
    input_tokens = int(usage_data.get("prompt_tokens") or usage_data.get("input_tokens") or 0)
    output_tokens = int(usage_data.get("completion_tokens") or usage_data.get("output_tokens") or 0)
    total_tokens = usage_data.get("total_tokens")
    if total_tokens is None:
        total_tokens = input_tokens + output_tokens
    try:
        tracker = get_token_tracker()
        await tracker.track_usage(
            model_alias=model_alias,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=int(total_tokens),
            request_type=request_type,
            user_id=user_id,
            organization_id=organization_id,
            conversation_id=job_id,
            endpoint_path="/api/mind-classroom/jobs",
            response_time=response_time,
            success=success,
        )
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[MindClassroom] Token tracking failed: %s", exc)
