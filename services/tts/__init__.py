"""Shared TTS helpers (voice catalog, routing, HTTP / realtime families)."""

from services.tts.facade import TtsSynthRequest, plan_tts, synthesize_http
from services.tts.routing import (
    MODE_HTTP,
    MODE_REALTIME,
    PROTOCOL_INFERENCE_WS,
    PROTOCOL_QWEN_HTTP,
    PROTOCOL_QWEN_RT_WS,
    PROTOCOL_SPEECH_HTTP,
    TtsRoute,
    canonical_tts_model,
    default_voice_for_model,
    resolve_tts_mode,
    resolve_tts_route,
    tts_family_for_model,
)

__all__ = (
    "MODE_HTTP",
    "MODE_REALTIME",
    "PROTOCOL_INFERENCE_WS",
    "PROTOCOL_QWEN_HTTP",
    "PROTOCOL_QWEN_RT_WS",
    "PROTOCOL_SPEECH_HTTP",
    "TtsRoute",
    "TtsSynthRequest",
    "canonical_tts_model",
    "default_voice_for_model",
    "plan_tts",
    "resolve_tts_mode",
    "resolve_tts_route",
    "synthesize_http",
    "tts_family_for_model",
)
