"""Unified DashScope TTS entry: CosyVoice / Qwen-Audio / Qwen-TTS.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from services.tts.http_payloads import build_qwen_tts_http_body, build_speech_synthesizer_body
from services.tts.http_synth import synthesize_http_audio
from services.tts.routing import (
    MODE_HTTP,
    PROTOCOL_QWEN_HTTP,
    PROTOCOL_SPEECH_HTTP,
    TtsRoute,
    resolve_tts_route,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TtsSynthRequest:
    """One-shot synthesis request (HTTP families, or routing only)."""

    text: str
    model: str
    voice: str = ""
    mode: Optional[str] = None
    stream: bool = False
    audio_format: Optional[str] = None
    sample_rate: Optional[int] = None
    language_type: Optional[str] = None
    instructions: Optional[str] = None


def plan_tts(request: TtsSynthRequest) -> tuple[TtsRoute, str]:
    """Resolve route + voice without calling a provider."""
    route = resolve_tts_route(request.model, mode=request.mode)
    voice = (request.voice or "").strip() or route.default_voice
    return route, voice


async def synthesize_http(request: TtsSynthRequest) -> bytes:
    """Non-realtime HTTP synthesis for CosyVoice / Qwen-Audio / Qwen-TTS."""
    text = (request.text or "").strip()
    if not text:
        return b""
    route, voice = plan_tts(request)
    if route.protocol not in (PROTOCOL_SPEECH_HTTP, PROTOCOL_QWEN_HTTP):
        raise RuntimeError(f"synthesize_http requires mode={MODE_HTTP}, got protocol={route.protocol}")
    if not voice:
        raise RuntimeError(f"TTS HTTP needs a voice for model {route.model}")
    audio_format = (request.audio_format or route.audio_format).strip() or "pcm"
    sample_rate = int(request.sample_rate or route.sample_rate)
    if route.protocol == PROTOCOL_QWEN_HTTP:
        body = build_qwen_tts_http_body(
            route.model,
            text,
            voice,
            language_type=request.language_type,
            instructions=request.instructions,
        )
    else:
        body = build_speech_synthesizer_body(
            route.model,
            text,
            voice,
            audio_format=audio_format,
            sample_rate=sample_rate,
            instruction=request.instructions,
        )
    audio = await synthesize_http_audio(route.protocol, body, stream=request.stream)
    if not audio:
        logger.warning("TTS HTTP returned no audio model=%s protocol=%s", route.model, route.protocol)
    return audio
