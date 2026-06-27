"""Synchronous token_usage rows linked to thinking coin debits."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.token_usage import TokenUsage
from services.redis.redis_token_buffer import get_token_tracker
from services.redis.cache.redis_user_daily_token import record_tracked_daily_tokens


@dataclass(frozen=True)
class TokenUsageSnapshot:
    """Minimal usage payload for a sync token_usage insert."""

    user_id: int
    organization_id: Optional[int]
    api_key_id: Optional[int]
    session_id: Optional[str]
    conversation_id: Optional[str]
    model_alias: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_type: str
    diagram_type: Optional[str]
    endpoint_path: Optional[str]
    response_time: float
    success: bool


def build_token_usage_snapshot(
    usage_data: dict[str, Any],
    metadata: dict[str, Any],
    model: str,
    duration: float,
    *,
    success: bool = True,
) -> Optional[TokenUsageSnapshot]:
    """Build a snapshot when usage and user_id are present."""
    user_id = metadata.get("user_id")
    if user_id is None or not usage_data:
        return None

    input_tokens = int(usage_data.get("prompt_tokens") or usage_data.get("input_tokens") or 0)
    output_tokens = int(usage_data.get("completion_tokens") or usage_data.get("output_tokens") or 0)
    total_raw = usage_data.get("total_tokens")
    total_tokens = int(total_raw) if total_raw is not None else input_tokens + output_tokens

    return TokenUsageSnapshot(
        user_id=int(user_id),
        organization_id=metadata.get("organization_id"),
        api_key_id=metadata.get("api_key_id"),
        session_id=metadata.get("session_id"),
        conversation_id=metadata.get("conversation_id"),
        model_alias=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        request_type=str(metadata.get("request_type") or "diagram_generation"),
        diagram_type=metadata.get("diagram_type"),
        endpoint_path=metadata.get("endpoint_path"),
        response_time=duration,
        success=success,
    )


def build_mindmate_usage_snapshot(
    *,
    user_id: int,
    organization_id: Optional[int],
    conversation_id: Optional[str],
    input_tokens: int,
    output_tokens: int,
    total_tokens: Optional[int],
    response_time: float,
) -> TokenUsageSnapshot:
    """Snapshot for MindMate Dify streams (model alias dify)."""
    resolved_total = total_tokens if total_tokens is not None else input_tokens + output_tokens
    return TokenUsageSnapshot(
        user_id=user_id,
        organization_id=organization_id,
        api_key_id=None,
        session_id=f"session_{os.urandom(8).hex()}",
        conversation_id=conversation_id,
        model_alias="dify",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=resolved_total,
        request_type="mindmate",
        diagram_type=None,
        endpoint_path="/api/ai_assistant/stream",
        response_time=response_time,
        success=True,
    )


def merge_usage_dicts(parts: list[dict[str, Any]]) -> dict[str, int]:
    """Sum token fields across partial usage payloads."""
    input_total = 0
    output_total = 0
    for part in parts:
        if not part:
            continue
        input_total += int(part.get("prompt_tokens") or part.get("input_tokens") or 0)
        output_total += int(part.get("completion_tokens") or part.get("output_tokens") or 0)
    return {
        "prompt_tokens": input_total,
        "completion_tokens": output_total,
        "total_tokens": input_total + output_total,
    }


async def insert_token_usage_row(db: AsyncSession, snapshot: TokenUsageSnapshot) -> int:
    """Insert one token_usage row and return its primary key."""
    tracker = get_token_tracker()
    pricing = tracker.MODEL_PRICING.get(
        snapshot.model_alias,
        {"input": 0.4, "output": 1.2, "provider": "unknown"},
    )
    model_name = tracker.MODEL_NAME_MAP.get(snapshot.model_alias, snapshot.model_alias)
    input_cost = snapshot.input_tokens * pricing["input"] / 1_000_000
    output_cost = snapshot.output_tokens * pricing["output"] / 1_000_000

    row = TokenUsage(
        user_id=snapshot.user_id,
        organization_id=snapshot.organization_id,
        api_key_id=snapshot.api_key_id,
        session_id=snapshot.session_id,
        conversation_id=snapshot.conversation_id,
        model_provider=pricing["provider"],
        model_name=model_name,
        model_alias=snapshot.model_alias,
        input_tokens=snapshot.input_tokens,
        output_tokens=snapshot.output_tokens,
        total_tokens=snapshot.total_tokens,
        input_cost=round(input_cost, 6),
        output_cost=round(output_cost, 6),
        total_cost=round(input_cost + output_cost, 6),
        request_type=snapshot.request_type,
        diagram_type=snapshot.diagram_type,
        endpoint_path=snapshot.endpoint_path,
        success=snapshot.success,
        response_time=snapshot.response_time,
    )
    db.add(row)
    await db.flush()
    if snapshot.success:
        await record_tracked_daily_tokens(snapshot.user_id, snapshot.total_tokens)
    return int(row.id)
