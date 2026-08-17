"""DashScope system-voice library (CosyVoice, Qwen-Audio-TTS, Qwen-TTS).

Use ``list_system_voices(model=...)`` for a future user-facing picker.
CosyVoice v3.5 has no system voices — those ids are design / clone only.
"""

from services.tts.voices.catalog import (
    ALL_SYSTEM_VOICES,
    TTS_FAMILIES,
    get_system_voice,
    has_system_voices,
    is_system_voice,
    list_system_voices,
    list_tts_families,
    normalize_tts_model,
)
from services.tts.voices.types import (
    COSY_V1,
    COSY_V2,
    COSY_V3_FLASH,
    COSY_V3_PLUS,
    COSY_V35_FLASH,
    COSY_V35_PLUS,
    FAMILY_COSYVOICE,
    FAMILY_QWEN_AUDIO,
    FAMILY_QWEN_TTS,
    NO_SYSTEM_VOICE_MODELS,
    TtsVoice,
    TtsVoiceRow,
)

__all__ = (
    "ALL_SYSTEM_VOICES",
    "COSY_V1",
    "COSY_V2",
    "COSY_V3_FLASH",
    "COSY_V3_PLUS",
    "COSY_V35_FLASH",
    "COSY_V35_PLUS",
    "FAMILY_COSYVOICE",
    "FAMILY_QWEN_AUDIO",
    "FAMILY_QWEN_TTS",
    "NO_SYSTEM_VOICE_MODELS",
    "TTS_FAMILIES",
    "TtsVoice",
    "TtsVoiceRow",
    "get_system_voice",
    "has_system_voices",
    "is_system_voice",
    "list_system_voices",
    "list_tts_families",
    "normalize_tts_model",
)
