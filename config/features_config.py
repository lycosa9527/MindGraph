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
    a _get_cached_value method.
    """

    if TYPE_CHECKING:

        def _get_cached_value(self, _key: str, _default: Any = None) -> Any:
            """Type stub: method provided by BaseConfig."""
            return None

    @property
    def FEATURE_MINDMATE(self):
        """Enable MindMate AI Assistant button (experimental feature)."""
        return self._get_cached_value("FEATURE_MINDMATE", "False").lower() == "true"

    @property
    def FEATURE_KITTY_AGENT(self):
        """Enable Kitty Agent — text-first canvas control (Fun-ASR + CosyVoice)."""
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
    def FEATURE_SHOWCASE(self):
        """Enable Showcase (案例广场) moderated public case gallery.

        Enabled by default. Set FEATURE_SHOWCASE=False in .env to disable.
        """
        return self._get_cached_value("FEATURE_SHOWCASE", "True").lower() == "true"

    @property
    def FEATURE_ASKONCE(self):
        """Enable AskOnce (多应) multi-LLM chat feature.

        Enabled by default. Set FEATURE_ASKONCE=False in .env to disable.
        """
        return self._get_cached_value("FEATURE_ASKONCE", "True").lower() == "true"

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
    def FEATURE_MINDMATE_COLLAB(self):
        """Enable MindMate shared AI chatroom (online collab for MindMate).

        Disabled by default. Set FEATURE_MINDMATE_COLLAB=True in .env to enable.
        Requires online_collab school tier for end users when enabled.
        """
        return self._get_cached_value("FEATURE_MINDMATE_COLLAB", "False").lower() == "true"

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
        """Enable thinking coin (思维币) wallet for trial-tier org members.

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
    def FEATURE_TEST_SERVER_BANNER(self):
        """Enable SwissWarningModal + diagonal watermark on the test deployment.

        Disabled by default. Set FEATURE_TEST_SERVER_BANNER=True on the test server
        so visitors see SwissWarningModal (once/day + on login + always on /auth) and a persistent
        watermark, with a jump link to production (mg.mindspringedu.com).

        Frontend: frontend/src/components/common/SwissWarningModal.vue
        """
        return self._get_cached_value("FEATURE_TEST_SERVER_BANNER", "False").lower() == "true"

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
