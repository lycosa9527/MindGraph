"""Feature flags and other application settings.

This module provides feature flags and miscellaneous configuration properties.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)


class FeaturesConfigMixin:
    """Mixin class for feature flags and other settings.

    This mixin expects the class to inherit from BaseConfig or provide
    a _get_cached_value method, and to have access to properties from
    other mixins (version, host, port, debug from BaseConfig,
    QWEN_API_URL, QWEN_MODEL_CLASSIFICATION, QWEN_MODEL_GENERATION from
    LLMConfigMixin, D3_TOPIC_FILL, D3_SIM_FILL, D3_DIFF_FILL,
    D3_BASE_WIDTH, D3_BASE_HEIGHT from VisualizationConfigMixin).
    """

    if TYPE_CHECKING:

        def _get_cached_value(self, _key: str, _default: Any = None) -> Any:
            """Type stub: method provided by BaseConfig."""
            return None

        @property
        def version(self) -> str:
            """Type stub: property provided by BaseConfig."""
            return ""

        @property
        def host(self) -> str:
            """Type stub: property provided by BaseConfig."""
            return ""

        @property
        def port(self) -> int:
            """Type stub: property provided by BaseConfig."""
            return 0

        @property
        def debug(self) -> bool:
            """Type stub: property provided by BaseConfig."""
            return False

        @property
        def QWEN_API_URL(self) -> str:
            """Type stub: property provided by LLMConfigMixin."""
            return ""

        @property
        def QWEN_MODEL_CLASSIFICATION(self) -> str:
            """Type stub: property provided by LLMConfigMixin."""
            return ""

        @property
        def QWEN_MODEL_GENERATION(self) -> str:
            """Type stub: property provided by LLMConfigMixin."""
            return ""

        @property
        def D3_TOPIC_FILL(self) -> str:
            """Type stub: property provided by VisualizationConfigMixin."""
            return ""

        @property
        def D3_SIM_FILL(self) -> str:
            """Type stub: property provided by VisualizationConfigMixin."""
            return ""

        @property
        def D3_DIFF_FILL(self) -> str:
            """Type stub: property provided by VisualizationConfigMixin."""
            return ""

        @property
        def D3_BASE_WIDTH(self) -> int:
            """Type stub: property provided by VisualizationConfigMixin."""
            return 0

        @property
        def D3_BASE_HEIGHT(self) -> int:
            """Type stub: property provided by VisualizationConfigMixin."""
            return 0

    @property
    def FEATURE_MINDMATE(self):
        """Enable MindMate AI Assistant button (experimental feature)."""
        return self._get_cached_value("FEATURE_MINDMATE", "False").lower() == "true"

    @property
    def FEATURE_KITTY_AGENT(self):
        """Enable Kitty Agent — Qwen-Omni-Realtime multimodal canvas control."""
        return self._get_cached_value("FEATURE_KITTY_AGENT", "False").lower() == "true"

    @property
    def FEATURE_KITTY_WS_ENABLED(self):
        """True when Kitty WebSocket (/ws/kitty) should be served."""
        return bool(self.FEATURE_KITTY_AGENT)

    @property
    def FEATURE_DRAG_AND_DROP(self):
        """Enable drag and drop functionality for diagram nodes."""
        return self._get_cached_value("FEATURE_DRAG_AND_DROP", "False").lower() == "true"

    @property
    def FEATURE_RAG_CHUNK_TEST(self):
        """Enable RAG Chunk Test feature (hidden by default)."""
        return self._get_cached_value("FEATURE_RAG_CHUNK_TEST", "False").lower() == "true"

    @property
    def FEATURE_KNOWLEDGE_SPACE(self):
        """Enable Personal Knowledge Space (RAG) feature.

        Disabled by default. Set FEATURE_KNOWLEDGE_SPACE=True in .env to enable.
        Requires Qdrant and Celery to be running.
        """
        return self._get_cached_value("FEATURE_KNOWLEDGE_SPACE", "False").lower() == "true"

    @property
    def FEATURE_MINDMAP_V2_CANVAS(self):
        """Expose Classic/New mind map canvas choice in Language settings.

        Disabled by default: all users stay on classic canvas; the segmented control is hidden.
        Set FEATURE_MINDMAP_V2_CANVAS=True in .env to show the opt-in and allow new canvas.
        """
        return self._get_cached_value("FEATURE_MINDMAP_V2_CANVAS", "False").lower() == "true"

    @property
    def FEATURE_DEBATEVERSE(self):
        """Enable DebateVerse (论境) debate system feature.

        Disabled by default. Set FEATURE_DEBATEVERSE=True in .env to enable.
        """
        return self._get_cached_value("FEATURE_DEBATEVERSE", "False").lower() == "true"

    @property
    def FEATURE_COURSE(self):
        """Enable Thinking Course (思维课程) feature.

        Disabled by default. Set FEATURE_COURSE=True in .env to enable.
        """
        return self._get_cached_value("FEATURE_COURSE", "False").lower() == "true"

    @property
    def FEATURE_TEMPLATE(self):
        """Enable Template Resources (模板资源) feature.

        Disabled by default. Set FEATURE_TEMPLATE=True in .env to enable.
        """
        return self._get_cached_value("FEATURE_TEMPLATE", "False").lower() == "true"

    @property
    def FEATURE_COMMUNITY(self):
        """Enable Community Sharing (社区分享) feature.

        Disabled by default. Set FEATURE_COMMUNITY=True in .env to enable.
        """
        return self._get_cached_value("FEATURE_COMMUNITY", "False").lower() == "true"

    @property
    def FEATURE_ASKONCE(self):
        """Enable AskOnce (多应) multi-LLM chat feature.

        Enabled by default. Set FEATURE_ASKONCE=False in .env to disable.
        """
        return self._get_cached_value("FEATURE_ASKONCE", "True").lower() == "true"

    @property
    def FEATURE_SCHOOL_ZONE(self):
        """Enable School Zone (学校专区) organization sharing feature.

        Disabled by default. Set FEATURE_SCHOOL_ZONE=True in .env to enable.
        """
        return self._get_cached_value("FEATURE_SCHOOL_ZONE", "False").lower() == "true"

    @property
    def FEATURE_LIBRARY(self):
        """Enable Library (图书馆) PDF viewing feature with danmaku comments.

        Disabled by default. Set FEATURE_LIBRARY=True in .env to enable.
        """
        return self._get_cached_value("FEATURE_LIBRARY", "False").lower() == "true"

    @property
    def FEATURE_OAUTH_LOGIN(self):
        """Enable WeChat / DingTalk OAuth QR login for end users.

        Disabled by default. Set FEATURE_OAUTH_LOGIN=True in .env to enable.
        """
        return self._get_cached_value("FEATURE_OAUTH_LOGIN", "False").lower() == "true"

    @property
    def WECHAT_OAUTH_APP_ID(self) -> str:
        """WeChat Open Platform 网站应用 AppID for OAuth QR login."""
        return (self._get_cached_value("WECHAT_OAUTH_APP_ID", "") or "").strip()

    @property
    def WECHAT_OAUTH_APP_SECRET(self) -> str:
        """WeChat Open Platform 网站应用 AppSecret for OAuth QR login."""
        return (self._get_cached_value("WECHAT_OAUTH_APP_SECRET", "") or "").strip()

    @property
    def FEATURE_GEWE(self):
        """Enable Gewe WeChat integration (admin only).

        Disabled by default. Set FEATURE_GEWE=True in .env to enable.
        """
        return self._get_cached_value("FEATURE_GEWE", "False").lower() == "true"

    @property
    def FEATURE_SMART_RESPONSE(self):
        """Enable Smart Response (智回) ESP32 watch teacher interface.

        Disabled by default. Set FEATURE_SMART_RESPONSE=True in .env to enable.
        """
        return self._get_cached_value("FEATURE_SMART_RESPONSE", "False").lower() == "true"

    @property
    def FEATURE_TEACHER_USAGE(self):
        """Enable Teacher Usage (教师使用度) admin analytics dashboard.

        Disabled by default. Set FEATURE_TEACHER_USAGE=True in .env to enable.
        Admin-only feature for teacher engagement classification.
        """
        return self._get_cached_value("FEATURE_TEACHER_USAGE", "False").lower() == "true"

    @property
    def FEATURE_WORKSHOP_CHAT(self):
        """Enable Workshop Chat (教研坊) school-scoped communication system.

        Disabled by default. Set FEATURE_WORKSHOP_CHAT=True in .env to enable.
        Provides channels, topics, and DMs for teacher collaboration.
        """
        return self._get_cached_value("FEATURE_WORKSHOP_CHAT", "False").lower() == "true"

    @property
    def WORKSHOP_CHAT_PREVIEW_ORG_IDS(self) -> frozenset[int]:
        """Organization IDs that may use Workshop Chat without admin/manager role.

        Comma-separated integers (e.g. ``5`` or ``5,12``). Used while the feature
        is under development so a specific school can test; admins and managers
        always have access when FEATURE_WORKSHOP_CHAT is enabled.

        Empty by default (only elevated roles).
        """
        raw = str(self._get_cached_value("WORKSHOP_CHAT_PREVIEW_ORG_IDS", "") or "")
        result: list[int] = []
        for part in raw.split(","):
            part_stripped = part.strip()
            if not part_stripped:
                continue
            try:
                result.append(int(part_stripped))
            except ValueError:
                logger.warning(
                    "Invalid org id in WORKSHOP_CHAT_PREVIEW_ORG_IDS: %s",
                    part_stripped,
                )
        return frozenset(result)

    @property
    def FEATURE_MCP_HTTP(self):
        """Expose Model Context Protocol (Streamable HTTP) at /api/mcp.

        Disabled by default. Set FEATURE_MCP_HTTP=True in .env to enable.
        Clients use the same mgat_ token and X-MG-Account headers as the REST API.
        """
        return self._get_cached_value("FEATURE_MCP_HTTP", "False").lower() == "true"

    @property
    def FEATURE_MARKETS(self):
        """Enable Market (市场) catalog, orders, and Alipay checkout.

        Disabled by default. Set FEATURE_MARKETS=True in .env to enable.
        """
        return self._get_cached_value("FEATURE_MARKETS", "False").lower() == "true"

    @property
    def FEATURE_MINDBOT(self):
        """Enable MindBot (DingTalk HTTP robot ↔ per-org Dify).

        Enabled by default. Set FEATURE_MINDBOT=False in .env to disable.
        """
        return self._get_cached_value("FEATURE_MINDBOT", "True").lower() == "true"

    @property
    def FEATURE_MINDMATE_EXPORT(self):
        """Enable the MindMate 记录导出 admin subtab (view/export Dify conversation history).

        Disabled by default. Set FEATURE_MINDMATE_EXPORT=True in .env to enable.
        Per-org rollout is additionally gated via feature_org_access.
        """
        return self._get_cached_value("FEATURE_MINDMATE_EXPORT", "False").lower() == "true"

    @property
    def FEATURE_THINKING_COINS(self):
        """Enable thinking coin (思维币) wallet for trial school teachers.

        Disabled by default. Set FEATURE_THINKING_COINS=True in .env to enable.
        """
        return self._get_cached_value("FEATURE_THINKING_COINS", "False").lower() == "true"

    @property
    def FEATURE_AUTH_PIXEL_BATTLE(self):
        """Enable retro pixel-art battle background on /auth (test / easter-egg).

        Disabled by default. Set FEATURE_AUTH_PIXEL_BATTLE=True in .env to enable.
        """
        return self._get_cached_value("FEATURE_AUTH_PIXEL_BATTLE", "False").lower() == "true"

    @property
    def MINDBOT_DIFY_HEALTH_BASE_URL(self) -> str:
        """Dify app API base (no trailing slash) for admin GET /parameters probe."""
        raw = (
            self._get_cached_value(
                "MINDBOT_DIFY_HEALTH_BASE_URL",
                "https://dify.mindspringedu.com/v1",
            )
            or ""
        ).strip()
        return raw.rstrip("/")

    @property
    def MINDBOT_DIFY_HEALTH_API_KEY(self) -> str:
        """App API key for MindBot admin Dify online probe (Bearer). Keep server-side only."""
        return (self._get_cached_value("MINDBOT_DIFY_HEALTH_API_KEY", "") or "").strip()

    @property
    def AI_ASSISTANT_NAME(self):
        """AI Assistant display name (appears in toolbar button and panel header)."""
        return self._get_cached_value("AI_ASSISTANT_NAME", "MindMate AI")

    @property
    def DEFAULT_LANGUAGE(self):
        """Default UI language (en/zh/az)."""
        lang = self._get_cached_value("DEFAULT_LANGUAGE", "zh").lower()
        if lang not in ["en", "zh", "az"]:
            logger.warning("Invalid DEFAULT_LANGUAGE '%s', using 'zh'", lang)
            return "zh"
        return lang

    @property
    def WECHAT_QR_IMAGE(self):
        """WeChat group QR code image filename (stored in static/qr/ folder)."""
        return self._get_cached_value("WECHAT_QR_IMAGE", "")

    @property
    def GRAPH_LANGUAGE(self):
        """Language for graph generation (zh/en)."""
        return self._get_cached_value("GRAPH_LANGUAGE", "zh")

    @property
    def WATERMARK_TEXT(self):
        """Watermark text displayed on generated graphs."""
        return self._get_cached_value("WATERMARK_TEXT", "MindGraph")

    def print_config_summary(self):
        """
        Print a comprehensive configuration summary.

        Displays:
        - Application version
        - FastAPI application settings
        - API configurations and availability
        - D3.js visualization settings
        - Theme and styling options
        """
        logger.info(
            "Configuration: v%s | %s:%s | lang=%s | Qwen classification=%s | Qwen generation=%s",
            self.version,
            self.host,
            self.port,
            self.GRAPH_LANGUAGE,
            self.QWEN_MODEL_CLASSIFICATION,
            self.QWEN_MODEL_GENERATION,
        )
        logger.debug("Configuration Summary:")
        logger.debug("   Version: %s", self.version)
        logger.debug("   FastAPI: %s:%s (Debug: %s)", self.host, self.port, self.debug)
        logger.debug("   Qwen: %s", self.QWEN_API_URL)
        logger.debug("     - Classification: %s", self.QWEN_MODEL_CLASSIFICATION)
        logger.debug("     - Generation: %s", self.QWEN_MODEL_GENERATION)

        logger.debug("   Language: %s", self.GRAPH_LANGUAGE)
        logger.debug(
            "   Theme: %s / %s / %s",
            self.D3_TOPIC_FILL,
            self.D3_SIM_FILL,
            self.D3_DIFF_FILL,
        )
        logger.debug("   Dimensions: %sx%spx", self.D3_BASE_WIDTH, self.D3_BASE_HEIGHT)
