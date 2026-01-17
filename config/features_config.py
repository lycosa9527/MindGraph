"""Feature flags and other application settings.

This module provides feature flags and miscellaneous configuration properties.
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
        def _get_cached_value(self, key: str, default: Any = None) -> Any:
            """Type stub: method provided by BaseConfig."""
            ...
        
        @property
        def version(self) -> str:
            """Type stub: property provided by BaseConfig."""
            ...
        
        @property
        def host(self) -> str:
            """Type stub: property provided by BaseConfig."""
            ...
        
        @property
        def port(self) -> int:
            """Type stub: property provided by BaseConfig."""
            ...
        
        @property
        def debug(self) -> bool:
            """Type stub: property provided by BaseConfig."""
            ...
        
        @property
        def QWEN_API_URL(self) -> str:
            """Type stub: property provided by LLMConfigMixin."""
            ...
        
        @property
        def QWEN_MODEL_CLASSIFICATION(self) -> str:
            """Type stub: property provided by LLMConfigMixin."""
            ...
        
        @property
        def QWEN_MODEL_GENERATION(self) -> str:
            """Type stub: property provided by LLMConfigMixin."""
            ...
        
        @property
        def D3_TOPIC_FILL(self) -> str:
            """Type stub: property provided by VisualizationConfigMixin."""
            ...
        
        @property
        def D3_SIM_FILL(self) -> str:
            """Type stub: property provided by VisualizationConfigMixin."""
            ...
        
        @property
        def D3_DIFF_FILL(self) -> str:
            """Type stub: property provided by VisualizationConfigMixin."""
            ...
        
        @property
        def D3_BASE_WIDTH(self) -> int:
            """Type stub: property provided by VisualizationConfigMixin."""
            ...
        
        @property
        def D3_BASE_HEIGHT(self) -> int:
            """Type stub: property provided by VisualizationConfigMixin."""
            ...

    @property
    def FEATURE_MINDMATE(self):
        """Enable MindMate AI Assistant button (experimental feature)."""
        return self._get_cached_value('FEATURE_MINDMATE', 'False').lower() == 'true'

    @property
    def FEATURE_VOICE_AGENT(self):
        """Enable Voice Agent (experimental feature)."""
        return self._get_cached_value('FEATURE_VOICE_AGENT', 'False').lower() == 'true'

    @property
    def FEATURE_DRAG_AND_DROP(self):
        """Enable drag and drop functionality for diagram nodes."""
        return self._get_cached_value('FEATURE_DRAG_AND_DROP', 'False').lower() == 'true'

    @property
    def FEATURE_TAB_MODE(self):
        """Enable Tab Mode (autocomplete suggestions and node expansion)."""
        return self._get_cached_value('FEATURE_TAB_MODE', 'False').lower() == 'true'

    @property
    def FEATURE_IME_AUTOCOMPLETE(self):
        """Enable IME-style autocomplete for node editing (experimental)."""
        return self._get_cached_value('FEATURE_IME_AUTOCOMPLETE', 'False').lower() == 'true'

    @property
    def AI_ASSISTANT_NAME(self):
        """AI Assistant display name (appears in toolbar button and panel header)."""
        return self._get_cached_value('AI_ASSISTANT_NAME', 'MindMate AI')

    @property
    def DEFAULT_LANGUAGE(self):
        """Default UI language (en/zh/az)."""
        lang = self._get_cached_value('DEFAULT_LANGUAGE', 'zh').lower()
        if lang not in ['en', 'zh', 'az']:
            logger.warning("Invalid DEFAULT_LANGUAGE '%s', using 'zh'", lang)
            return 'zh'
        return lang

    @property
    def WECHAT_QR_IMAGE(self):
        """WeChat group QR code image filename (stored in static/qr/ folder)."""
        return self._get_cached_value('WECHAT_QR_IMAGE', '')

    @property
    def GRAPH_LANGUAGE(self):
        """Language for graph generation (zh/en)."""
        return self._get_cached_value('GRAPH_LANGUAGE', 'zh')

    @property
    def WATERMARK_TEXT(self):
        """Watermark text displayed on generated graphs."""
        return self._get_cached_value('WATERMARK_TEXT', 'MindGraph')

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
        logger.info("Configuration Summary:")
        logger.info("   Version: %s", self.version)
        logger.info("   FastAPI: %s:%s (Debug: %s)", self.host, self.port, self.debug)
        logger.info("   Qwen: %s", self.QWEN_API_URL)
        logger.info("     - Classification: %s", self.QWEN_MODEL_CLASSIFICATION)
        logger.info("     - Generation: %s", self.QWEN_MODEL_GENERATION)

        logger.info("   Language: %s", self.GRAPH_LANGUAGE)
        logger.info("   Theme: %s / %s / %s", self.D3_TOPIC_FILL, self.D3_SIM_FILL, self.D3_DIFF_FILL)
        logger.info("   Dimensions: %sx%spx", self.D3_BASE_WIDTH, self.D3_BASE_HEIGHT)
