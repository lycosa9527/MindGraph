"""DashScope / CosyVoice / Qwen TTS system-voice records.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

FAMILY_COSYVOICE = "cosyvoice"
FAMILY_QWEN_AUDIO = "qwen-audio"
FAMILY_QWEN_TTS = "qwen-tts"

COSY_V35_FLASH = "cosyvoice-v3.5-flash"
COSY_V35_PLUS = "cosyvoice-v3.5-plus"
COSY_V3_FLASH = "cosyvoice-v3-flash"
COSY_V3_PLUS = "cosyvoice-v3-plus"
COSY_V2 = "cosyvoice-v2"
COSY_V1 = "cosyvoice-v1"

QWEN_AUDIO_PLUS = "qwen-audio-3.0-tts-plus"
QWEN_AUDIO_FLASH = "qwen-audio-3.0-tts-flash"

QWEN3_INSTRUCT_RT = "qwen3-tts-instruct-flash-realtime"
QWEN3_FLASH_RT = "qwen3-tts-flash-realtime"
QWEN_TTS_RT = "qwen-tts-realtime"
QWEN3_INSTRUCT = "qwen3-tts-instruct-flash"
QWEN3_FLASH = "qwen3-tts-flash"
QWEN_TTS = "qwen-tts"

# v3.5 has no built-in system voices (design / clone only).
NO_SYSTEM_VOICE_MODELS: tuple[str, ...] = (COSY_V35_FLASH, COSY_V35_PLUS)

REGION_BJ = "cn-beijing"
REGION_SG = "ap-southeast-1"
BJ: tuple[str, ...] = (REGION_BJ,)
BJ_SG: tuple[str, ...] = (REGION_BJ, REGION_SG)

ZH_EN: tuple[str, ...] = ("zh", "en")
ZH_YUE_EN: tuple[str, ...] = ("zh-yue", "en")
ZH_DONGBEI_EN: tuple[str, ...] = ("zh-dongbei", "en")
ZH_SHAANXI_EN: tuple[str, ...] = ("zh-shaanxi", "en")
ZH_MIN_EN: tuple[str, ...] = ("zh-min", "en")
ANHUAN_V3_LANGS: tuple[str, ...] = (
    "zh",
    "zh-yue",
    "zh-dongbei",
    "zh-henan",
    "zh-hunan",
    "zh-shaanxi",
    "zh-shandong",
    "zh-sichuan",
    "zh-anhui",
    "en",
)


class TtsVoiceRow(TypedDict):
    """JSON-ready system-voice row for a future picker API."""

    voice_id: str
    name: str
    family: str
    models: list[str]
    scene: str
    trait: str
    languages: list[str]
    age: str
    ssml: bool
    instruct: bool
    word_timestamp: bool
    regions: list[str]


@dataclass(frozen=True, slots=True)
class TtsVoice:
    """One system voice and the models that accept it."""

    voice_id: str
    name: str
    family: str
    models: tuple[str, ...]
    scene: str
    trait: str
    languages: tuple[str, ...]
    age: str = ""
    ssml: bool = False
    instruct: bool = False
    word_timestamp: bool = False
    regions: tuple[str, ...] = BJ

    def as_dict(self) -> TtsVoiceRow:
        """JSON-ready row for a future voice picker."""
        return {
            "voice_id": self.voice_id,
            "name": self.name,
            "family": self.family,
            "models": list(self.models),
            "scene": self.scene,
            "trait": self.trait,
            "languages": list(self.languages),
            "age": self.age,
            "ssml": self.ssml,
            "instruct": self.instruct,
            "word_timestamp": self.word_timestamp,
            "regions": list(self.regions),
        }


def make_voice(
    voice_id: str,
    name: str,
    scene: str,
    trait: str,
    languages: tuple[str, ...],
    *,
    family: str,
    models: tuple[str, ...],
    age: str = "",
    ssml: bool = False,
    instruct: bool = False,
    word_timestamp: bool = False,
    regions: tuple[str, ...] = BJ,
) -> TtsVoice:
    """Build a frozen system-voice record."""
    return TtsVoice(
        voice_id=voice_id,
        name=name,
        family=family,
        models=models,
        scene=scene,
        trait=trait,
        languages=languages,
        age=age,
        ssml=ssml,
        instruct=instruct,
        word_timestamp=word_timestamp,
        regions=regions,
    )
