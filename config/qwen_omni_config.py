"""Qwen Omni realtime voice configuration.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import TYPE_CHECKING, Any


class QwenOmniConfigMixin:
    """Mixin for Qwen Omni realtime voice settings.

    Expects the class to inherit from BaseConfig or provide ``_get_cached_value``.
    """

    if TYPE_CHECKING:

        def _get_cached_value(self, _key: str, _default: Any = None) -> Any:
            """Type stub: method provided by BaseConfig."""
            return _default

    @property
    def QWEN_OMNI_MODEL(self) -> str:
        """Qwen Omni model name"""
        return self._get_cached_value("QWEN_OMNI_MODEL", "qwen3-omni-flash-realtime-2025-12-01")

    @property
    def QWEN_OMNI_VOICE(self) -> str:
        """Qwen Omni voice name"""
        return self._get_cached_value("QWEN_OMNI_VOICE", "Cherry")

    @property
    def QWEN_OMNI_VAD_THRESHOLD(self) -> float:
        """Qwen Omni VAD threshold"""
        return float(self._get_cached_value("QWEN_OMNI_VAD_THRESHOLD", "0.5"))

    @property
    def QWEN_OMNI_VAD_SILENCE_MS(self) -> int:
        """Qwen Omni VAD silence duration (ms) - time to wait after user stops speaking"""
        return int(self._get_cached_value("QWEN_OMNI_VAD_SILENCE_MS", "1200"))

    @property
    def QWEN_OMNI_VAD_PREFIX_MS(self) -> int:
        """Qwen Omni VAD prefix padding (ms)"""
        return int(self._get_cached_value("QWEN_OMNI_VAD_PREFIX_MS", "300"))

    @property
    def QWEN_OMNI_SMOOTH_OUTPUT(self) -> bool:
        """Qwen Omni smooth output (flash models only)"""
        return self._get_cached_value("QWEN_OMNI_SMOOTH_OUTPUT", "true").lower() == "true"

    @property
    def QWEN_OMNI_INPUT_FORMAT(self) -> str:
        """Qwen Omni input audio format"""
        return self._get_cached_value("QWEN_OMNI_INPUT_FORMAT", "pcm16")

    @property
    def QWEN_OMNI_OUTPUT_FORMAT(self) -> str:
        """Qwen Omni output audio format"""
        return self._get_cached_value("QWEN_OMNI_OUTPUT_FORMAT", "pcm24")

    @property
    def QWEN_OMNI_TRANSCRIPTION_MODEL(self) -> str:
        """Qwen Omni transcription model"""
        return self._get_cached_value("QWEN_OMNI_TRANSCRIPTION_MODEL", "gummy-realtime-v1")
