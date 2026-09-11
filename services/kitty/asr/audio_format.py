"""Kitty mic wire formats. Fun-ASR accepts PCM16LE; Opus only if Ogg-wrapped.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

ASR_FORMAT_PCM = "pcm"
ASR_FORMAT_OPUS = "opus"
ASR_AUDIO_FORMATS = (ASR_FORMAT_PCM, ASR_FORMAT_OPUS)


def normalize_asr_audio_format(raw: object) -> str:
    """Accept ``pcm`` / ``opus``; anything else stays PCM (browser default)."""
    if isinstance(raw, str):
        value = raw.strip().lower()
        if value in ASR_AUDIO_FORMATS:
            return value
    return ASR_FORMAT_PCM


def parse_asr_audio_format(message: dict) -> str:
    """Read ``format`` or ``audio_format`` from asr_start / asr_audio."""
    if "format" in message:
        return normalize_asr_audio_format(message.get("format"))
    return normalize_asr_audio_format(message.get("audio_format"))


def is_silent_asr_provider_error(err: str) -> bool:
    """DashScope uses this for a hold that never contained speech."""
    text = err.strip().lower()
    return "no valid audio" in text
