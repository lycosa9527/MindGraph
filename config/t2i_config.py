"""Text-to-image / ZhiHui configuration settings.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import TYPE_CHECKING, Any


class T2IConfigMixin:
    """Mixin for ZhiHui / Qwen Image / Wan diagram-lesson config properties.

    Expects the class to inherit from BaseConfig or provide ``_get_cached_value``.
    """

    if TYPE_CHECKING:

        def _get_cached_value(self, _key: str, _default: Any = None) -> Any:
            """Type stub: method provided by BaseConfig."""
            return _default

    @property
    def ZHIHUI_LESSON_PLANNER_MODEL(self) -> str:
        """LLM model for 图示生图 lesson planning (structural content)."""
        return self._get_cached_value("ZHIHUI_LESSON_PLANNER_MODEL", "qwen3.7-plus")

    @property
    def ZHIHUI_LESSON_PLANNER_MAX_TOKENS(self) -> int:
        """Max completion tokens per planner phase (open / one branch / close)."""
        return int(self._get_cached_value("ZHIHUI_LESSON_PLANNER_MAX_TOKENS", "2500"))

    @property
    def IMAGE_MODEL(self) -> str:
        """DashScope Qwen Image 3.0 model for ZhiHui /generate-text-to-image."""
        return self._get_cached_value("IMAGE_MODEL", "qwen-image-3.0")

    @property
    def IMAGE_DEFAULT_SIZE(self) -> str:
        """Default image resolution (width*height); empty = model auto."""
        return self._get_cached_value("IMAGE_DEFAULT_SIZE", "")

    @property
    def IMAGE_PROMPT_EXTEND(self) -> bool:
        """DashScope API-level prompt_extend when K12 enhance is off."""
        return self._get_cached_value("IMAGE_PROMPT_EXTEND", "true").lower() == "true"

    @property
    def IMAGE_WATERMARK(self) -> bool:
        """Default watermark flag for DashScope image generation."""
        return self._get_cached_value("IMAGE_WATERMARK", "false").lower() == "true"

    @property
    def T2I_ENABLE_PROMPT_ENHANCEMENT(self) -> bool:
        """Run K12 LLM prompt enhancement before multimodal image generation."""
        return self._get_cached_value("T2I_ENABLE_PROMPT_ENHANCEMENT", "true").lower() == "true"

    @property
    def T2I_IMAGE_DOWNLOAD_TIMEOUT(self) -> int:
        """Seconds to download DashScope temporary image URLs."""
        return int(self._get_cached_value("T2I_IMAGE_DOWNLOAD_TIMEOUT", "30"))

    @property
    def T2I_ASSET_URL_TTL_SECONDS(self) -> int:
        """Signed /api/zhihui/assets URL lifetime for Dify markdown (default 30d)."""
        return int(self._get_cached_value("T2I_ASSET_URL_TTL_SECONDS", "2592000"))
