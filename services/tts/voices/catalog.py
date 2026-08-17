"""Lookup helpers for DashScope system-voice catalogs.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Optional

from services.tts.voices.cosyvoice_v1 import COSYVOICE_V1_VOICES
from services.tts.voices.cosyvoice_v2 import COSYVOICE_V2_VOICES
from services.tts.voices.cosyvoice_v3 import COSYVOICE_V3_VOICES
from services.tts.voices.qwen_audio import QWEN_AUDIO_VOICES
from services.tts.voices.qwen_tts import QWEN_TTS_VOICES
from services.tts.voices.types import (
    FAMILY_COSYVOICE,
    FAMILY_QWEN_AUDIO,
    FAMILY_QWEN_TTS,
    NO_SYSTEM_VOICE_MODELS,
    TtsVoice,
)

_DATE_SUFFIX = re.compile(r"-\d{4}-\d{2}-\d{2}$")

ALL_SYSTEM_VOICES: tuple[TtsVoice, ...] = (
    COSYVOICE_V3_VOICES + COSYVOICE_V2_VOICES + COSYVOICE_V1_VOICES + QWEN_AUDIO_VOICES + QWEN_TTS_VOICES
)

TTS_FAMILIES: tuple[str, ...] = (FAMILY_COSYVOICE, FAMILY_QWEN_AUDIO, FAMILY_QWEN_TTS)


def normalize_tts_model(model: str) -> str:
    """Map snapshot ids (``-YYYY-MM-DD`` / ``-latest``) to catalog model keys."""
    raw = (model or "").strip()
    if not raw:
        return ""
    stripped = _DATE_SUFFIX.sub("", raw)
    if stripped.endswith("-latest"):
        return stripped[: -len("-latest")]
    return stripped


def _build_indexes() -> tuple[
    dict[tuple[str, str], TtsVoice],
    dict[tuple[str, str], TtsVoice],
    dict[str, tuple[TtsVoice, ...]],
]:
    exact: dict[tuple[str, str], TtsVoice] = {}
    folded: dict[tuple[str, str], TtsVoice] = {}
    by_model: dict[str, list[TtsVoice]] = {}
    for voice in ALL_SYSTEM_VOICES:
        for model in voice.models:
            exact[(model, voice.voice_id)] = voice
            folded[(model, voice.voice_id.casefold())] = voice
            by_model.setdefault(model, []).append(voice)
    frozen = {key: tuple(rows) for key, rows in by_model.items()}
    return exact, folded, frozen


_EXACT, _FOLDED, _BY_MODEL = _build_indexes()


def has_system_voices(model: str) -> bool:
    """False for CosyVoice v3.5 (design / clone only) and unknown models."""
    key = normalize_tts_model(model)
    if key in NO_SYSTEM_VOICE_MODELS:
        return False
    return key in _BY_MODEL


def list_system_voices(
    *,
    model: Optional[str] = None,
    family: Optional[str] = None,
) -> tuple[TtsVoice, ...]:
    """System voices, optionally filtered by model and/or family."""
    if model:
        key = normalize_tts_model(model)
        rows = _BY_MODEL.get(key, ())
    else:
        rows = ALL_SYSTEM_VOICES
    if family:
        wanted = family.strip()
        rows = tuple(item for item in rows if item.family == wanted)
    return rows


def get_system_voice(model: str, voice_id: str) -> Optional[TtsVoice]:
    """Return the catalog row if ``voice_id`` is a system voice for ``model``."""
    key = normalize_tts_model(model)
    raw_id = (voice_id or "").strip()
    if not key or not raw_id:
        return None
    found = _EXACT.get((key, raw_id))
    if found is not None:
        return found
    return _FOLDED.get((key, raw_id.casefold()))


def is_system_voice(model: str, voice_id: str) -> bool:
    """True when the pair is a documented system voice (not design / clone)."""
    return get_system_voice(model, voice_id) is not None


def list_tts_families() -> tuple[str, ...]:
    """Catalog families: CosyVoice, Qwen-Audio-TTS, Qwen-TTS."""
    return TTS_FAMILIES
