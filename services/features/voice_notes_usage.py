"""Voice Notes usage: daily-cap / thinking-coin preflight + Fun-ASR token settle.

Fun-ASR is billed by audio duration upstream. We map PCM seconds to a token
proxy so sessions count toward ``USER_DAILY_TOKEN_CAP`` and appear in
``token_usage`` like other paid AI features.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from models.domain.auth import User
from models.domain.messages import Language
from services.auth.thinking_coin.token_usage_link import build_token_usage_snapshot
from services.auth.thinking_coin.usage_wire import (
    assert_llm_usage_budget,
    thinking_coin_post_llm_success_mutation,
    thinking_coins_apply_to_user,
)
from services.infrastructure.http.error_handler import (
    ThinkingCoinInsufficientError,
    UserDailyTokenCapExceededError,
)
from services.monitoring.module_activity import schedule_module_activity
from services.redis.redis_token_buffer import get_token_tracker
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.auth.connection_types import HttpOrWebSocket

logger = logging.getLogger(__name__)

VOICE_NOTES_REQUEST_TYPE = "voice_notes_asr"
VOICE_NOTES_MODEL_ALIAS = "fun-asr-realtime"
VOICE_NOTES_ENDPOINT_PATH = "/api/ws/voice-notes"

# 16 kHz mono PCM16
_PCM_BYTES_PER_SECOND = 16_000 * 2
# Proxy units for daily-cap / admin cost (≈1 hour session → ~360k tokens).
_TOKENS_PER_AUDIO_SECOND = 100


def estimate_voice_notes_asr_tokens(
    pcm_bytes: int,
    transcript_chars: int = 0,
) -> tuple[int, int, int]:
    """Return ``(input_tokens, output_tokens, total_tokens)`` from audio + text."""
    safe_pcm = max(0, int(pcm_bytes))
    seconds = safe_pcm / float(_PCM_BYTES_PER_SECOND) if safe_pcm else 0.0
    input_tokens = int(round(seconds * _TOKENS_PER_AUDIO_SECOND))
    output_tokens = max(0, int(transcript_chars))
    total = input_tokens + output_tokens
    return input_tokens, output_tokens, total


def voice_notes_budget_error_payload(exc: Exception) -> tuple[str, str]:
    """Map budget exceptions to browser error ``(code, message)``."""
    if isinstance(exc, ThinkingCoinInsufficientError):
        return "thinking_coin", str(exc.user_message or exc)
    if isinstance(exc, UserDailyTokenCapExceededError):
        return "daily_token_cap", str(exc.user_message or exc)
    return "budget", str(exc)


async def assert_voice_notes_usage_budget(
    user: User,
    *,
    lang: Language = "en",
) -> None:
    """Preflight thinking-coin balance or daily token cap before Fun-ASR start."""
    await assert_llm_usage_budget(
        int(user.id),
        getattr(user, "organization_id", None),
        VOICE_NOTES_REQUEST_TYPE,
        estimated_tokens=0,
        lang=lang,
    )


def schedule_voice_notes_session_activity(
    user: User,
    request: HttpOrWebSocket,
    *,
    total_tokens: Optional[int] = None,
    success: bool = True,
) -> None:
    """Fire-and-forget Redis + usage timeline activity for a voice-notes ASR session."""
    schedule_module_activity(
        user=user,
        module="voice_notes",
        redis_activity_type="voice_notes",
        request=request,
        details={"endpoint": "voice_notes_asr"},
        detail="endpoint=voice_notes_asr",
        usage_source="mindgraph",
        usage_action="voice_session",
        title="voice_notes",
        prompt_preview="voice_notes_asr",
        total_tokens=total_tokens,
        success=success,
    )


async def settle_voice_notes_usage(
    *,
    user: User,
    pcm_bytes: int,
    transcript_chars: int,
    started_at: float,
    success: bool = True,
) -> int:
    """Record Fun-ASR proxy tokens + thinking-coin debit when applicable.

    Returns total tokens recorded (0 when nothing to settle).
    """
    input_tokens, output_tokens, total_tokens = estimate_voice_notes_asr_tokens(
        pcm_bytes,
        transcript_chars,
    )
    if total_tokens <= 0 and not success:
        return 0

    user_id = int(user.id)
    organization_id = getattr(user, "organization_id", None)
    org_id_int = int(organization_id) if organization_id is not None else None
    response_time = max(0.0, time.monotonic() - started_at)

    try:
        tracker = get_token_tracker()
        await tracker.track_usage(
            model_alias=VOICE_NOTES_MODEL_ALIAS,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            request_type=VOICE_NOTES_REQUEST_TYPE,
            user_id=user_id,
            organization_id=org_id_int,
            endpoint_path=VOICE_NOTES_ENDPOINT_PATH,
            response_time=response_time,
            success=success,
        )
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[VoiceNotesASR] token track failed: %s", exc)
        return total_tokens

    if total_tokens <= 0 or not success:
        return total_tokens

    try:
        if await thinking_coins_apply_to_user(user_id, organization_id):
            snapshot = build_token_usage_snapshot(
                {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": total_tokens,
                },
                {
                    "user_id": user_id,
                    "organization_id": org_id_int,
                    "request_type": VOICE_NOTES_REQUEST_TYPE,
                    "endpoint_path": VOICE_NOTES_ENDPOINT_PATH,
                },
                VOICE_NOTES_MODEL_ALIAS,
                response_time,
                success=True,
            )
            if snapshot is not None:
                await thinking_coin_post_llm_success_mutation(
                    user_id,
                    organization_id,
                    VOICE_NOTES_REQUEST_TYPE,
                    snapshot,
                )
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[VoiceNotesASR] thinking-coin settle failed: %s", exc)

    return total_tokens


def usage_settle_kwargs_from_counts(
    pcm_bytes: int,
    final_texts: list[str],
) -> dict[str, Any]:
    """Helper for tests / callers assembling settle inputs."""
    transcript = "\n".join(part for part in final_texts if part.strip())
    return {
        "pcm_bytes": int(pcm_bytes),
        "transcript_chars": len(transcript),
    }
