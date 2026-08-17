"""Request / response helpers for DashScope non-realtime TTS HTTP APIs.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any, Optional

from services.utils.error_types import JSON_PARSE_ERRORS


def build_speech_synthesizer_body(
    model: str,
    text: str,
    voice: str,
    *,
    audio_format: str = "pcm",
    sample_rate: int = 24000,
    volume: Optional[int] = None,
    rate: Optional[float] = None,
    pitch: Optional[float] = None,
    instruction: Optional[str] = None,
    language_hints: Optional[list[str]] = None,
    enable_ssml: Optional[bool] = None,
) -> dict[str, Any]:
    """Body for ``POST …/audio/tts/SpeechSynthesizer``."""
    payload: dict[str, Any] = {
        "text": text,
        "voice": voice,
        "format": audio_format,
        "sample_rate": sample_rate,
    }
    if volume is not None:
        payload["volume"] = volume
    if rate is not None:
        payload["rate"] = rate
    if pitch is not None:
        payload["pitch"] = pitch
    if instruction:
        payload["instruction"] = instruction
    if language_hints:
        payload["language_hints"] = language_hints
    if enable_ssml is not None:
        payload["enable_ssml"] = enable_ssml
    return {"model": model, "input": payload}


def build_qwen_tts_http_body(
    model: str,
    text: str,
    voice: str,
    *,
    language_type: Optional[str] = None,
    instructions: Optional[str] = None,
    optimize_instructions: Optional[bool] = None,
) -> dict[str, Any]:
    """Body for ``POST …/aigc/multimodal-generation/generation`` (Qwen-TTS)."""
    payload: dict[str, Any] = {"text": text, "voice": voice}
    if language_type:
        payload["language_type"] = language_type
    if instructions:
        payload["instructions"] = instructions
    if optimize_instructions is not None:
        payload["optimize_instructions"] = optimize_instructions
    return {"model": model, "input": payload}


def speech_synthesizer_headers(*, stream: bool) -> dict[str, str]:
    """Optional SSE header for streaming SpeechSynthesizer / Qwen-TTS HTTP."""
    if not stream:
        return {}
    return {"X-DashScope-SSE": "enable"}


def _audio_object(payload: dict[str, Any]) -> dict[str, Any]:
    output = payload.get("output")
    if not isinstance(output, dict):
        return {}
    audio = output.get("audio")
    return audio if isinstance(audio, dict) else {}


def extract_audio_url(payload: dict[str, Any]) -> str:
    """OSS URL from a completed non-stream (or final stream) chunk."""
    return str(_audio_object(payload).get("url") or "").strip()


def extract_audio_b64(payload: dict[str, Any]) -> str:
    """Base64 audio from a stream chunk (or non-stream ``data``)."""
    return str(_audio_object(payload).get("data") or "").strip()


def decode_audio_b64(raw: str) -> bytes:
    """Decode one Base64 audio field; empty input yields empty bytes."""
    cleaned = (raw or "").strip()
    if not cleaned:
        return b""
    try:
        return base64.b64decode(cleaned)
    except (binascii.Error, ValueError):
        return b""


def parse_sse_json_line(line: str) -> Optional[dict[str, Any]]:
    """Parse one ``data: {…}`` SSE line; ignore keep-alives and ``[DONE]``."""
    stripped = (line or "").strip()
    if not stripped.startswith("data:"):
        return None
    raw = stripped[5:].strip()
    if not raw or raw == "[DONE]":
        return None
    try:
        payload = json.loads(raw)
    except JSON_PARSE_ERRORS:
        return None
    return payload if isinstance(payload, dict) else None


def finish_reason_is_stop(payload: dict[str, Any]) -> bool:
    """True when the HTTP synthesizer reports a completed utterance."""
    output = payload.get("output")
    if not isinstance(output, dict):
        return False
    return str(output.get("finish_reason") or "").strip().lower() == "stop"
