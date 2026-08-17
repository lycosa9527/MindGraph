"""Two-axis DashScope TTS switch: model (family) × mode (realtime | http).

``KITTY_TTS_MODEL`` picks the synthesizer. ``KITTY_TTS_MODE`` picks the
transport. A ``-realtime`` suffix on the model id is only a wire-name hint
and never overrides mode.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from services.tts.voices.catalog import list_system_voices, normalize_tts_model
from services.tts.voices.types import (
    FAMILY_COSYVOICE,
    FAMILY_QWEN_AUDIO,
    FAMILY_QWEN_TTS,
    NO_SYSTEM_VOICE_MODELS,
)

MODE_REALTIME = "realtime"
MODE_HTTP = "http"

PROTOCOL_INFERENCE_WS = "inference_ws"
PROTOCOL_QWEN_RT_WS = "qwen_realtime_ws"
PROTOCOL_SPEECH_HTTP = "speech_http"
PROTOCOL_QWEN_HTTP = "qwen_http"

_QWEN_TTS_DEFAULT_VOICE = "Cherry"
_COSY_V3_FLASH_VOICE = "longyumi_v3"
_COSY_V3_PLUS_VOICE = "longanyang"
_COSY_V2_VOICE = "longxiaochun_v2"
_QWEN_AUDIO_DEFAULT_VOICE = "longanhuan_v3.6"


@dataclass(frozen=True, slots=True)
class TtsRoute:
    """Resolved transport for one model + mode pair."""

    model: str
    family: str
    mode: str
    protocol: str
    default_voice: str
    sample_rate: int
    audio_format: str
    needs_designed_voice: bool
    supports_realtime: bool
    supports_http: bool


def resolve_tts_mode(explicit: Optional[str] = None) -> str:
    """``KITTY_TTS_MODE`` is ``realtime`` (default) or ``http``."""
    raw = (explicit if explicit is not None else os.getenv("KITTY_TTS_MODE", "")).strip().lower()
    if raw in (MODE_HTTP, "non-realtime", "non_realtime", "rest"):
        return MODE_HTTP
    return MODE_REALTIME


def tts_family_for_model(model: str) -> str:
    """Map a model id to CosyVoice / Qwen-Audio / Qwen-TTS."""
    key = normalize_tts_model(model)
    if key.startswith("qwen-audio"):
        return FAMILY_QWEN_AUDIO
    if key.startswith("qwen3-tts") or key.startswith("qwen-tts"):
        return FAMILY_QWEN_TTS
    return FAMILY_COSYVOICE


def is_qwen_tts_realtime_name(model: str) -> bool:
    """True when the model id is a Qwen-TTS Realtime snapshot."""
    key = normalize_tts_model(model)
    return tts_family_for_model(key) == FAMILY_QWEN_TTS and "realtime" in key


def canonical_tts_model(model: str) -> str:
    """Product model id with a trailing ``-realtime`` suffix removed."""
    return to_http_model(model)


def to_http_model(model: str) -> str:
    """Strip a ``-realtime`` suffix for the matching HTTP model."""
    key = normalize_tts_model(model)
    marker = "-realtime"
    if key.endswith(marker):
        return key[: -len(marker)]
    return key


def to_realtime_model(model: str) -> str:
    """Qwen-TTS HTTP ids gain ``-realtime``; CosyVoice / Qwen-Audio stay the same."""
    key = canonical_tts_model(model)
    if tts_family_for_model(key) != FAMILY_QWEN_TTS:
        return key
    return f"{key}-realtime"


def default_voice_for_model(model: str) -> str:
    """Catalog / system default; empty for CosyVoice v3.5 (design only)."""
    key = normalize_tts_model(model)
    if key in NO_SYSTEM_VOICE_MODELS or key.startswith("cosyvoice-v3.5"):
        return ""
    if key.startswith("cosyvoice-v3-flash"):
        return _COSY_V3_FLASH_VOICE
    if key.startswith("cosyvoice-v3"):
        return _COSY_V3_PLUS_VOICE
    if key.startswith("cosyvoice-v2"):
        return _COSY_V2_VOICE
    if key.startswith("qwen-audio"):
        return _QWEN_AUDIO_DEFAULT_VOICE
    rows = list_system_voices(model=key)
    if rows:
        return rows[0].voice_id
    return _QWEN_TTS_DEFAULT_VOICE


def resolve_tts_route(
    model: str,
    *,
    mode: Optional[str] = None,
) -> TtsRoute:
    """Resolve wire model + protocol from product model × realtime/http."""
    requested = canonical_tts_model(model) or "cosyvoice-v3.5-flash"
    chosen_mode = resolve_tts_mode(mode)
    family = tts_family_for_model(requested)
    if family == FAMILY_QWEN_TTS:
        resolved_model = to_realtime_model(requested) if chosen_mode == MODE_REALTIME else requested
        protocol = PROTOCOL_QWEN_RT_WS if chosen_mode == MODE_REALTIME else PROTOCOL_QWEN_HTTP
        sample_rate = 24000
        audio_format = "pcm" if chosen_mode == MODE_REALTIME else "wav"
    else:
        resolved_model = requested
        protocol = PROTOCOL_INFERENCE_WS if chosen_mode == MODE_REALTIME else PROTOCOL_SPEECH_HTTP
        sample_rate = 22050 if chosen_mode == MODE_REALTIME else 24000
        audio_format = "pcm"
    needs_designed = resolved_model in NO_SYSTEM_VOICE_MODELS or resolved_model.startswith("cosyvoice-v3.5")
    return TtsRoute(
        model=resolved_model,
        family=family,
        mode=chosen_mode,
        protocol=protocol,
        default_voice=default_voice_for_model(resolved_model),
        sample_rate=sample_rate,
        audio_format=audio_format,
        needs_designed_voice=needs_designed,
        supports_realtime=True,
        supports_http=True,
    )
