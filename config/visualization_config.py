"""D3.js visualization configuration settings.

This module provides D3.js visualization related configuration properties.
"""
import logging
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)


class VisualizationConfigMixin:
    """Mixin class for D3.js visualization configuration properties.
    
    This mixin expects the class to inherit from BaseConfig or provide
    a _get_cached_value method, and to have access to properties from
    other mixins (port from BaseConfig, QWEN_TIMEOUT/QWEN_MAX_TOKENS
    from LLMConfigMixin, WATERMARK_TEXT from FeaturesConfigMixin).
    """

    if TYPE_CHECKING:
        def _get_cached_value(self, _key: str, _default: Any = None) -> Any:
            """Type stub: method provided by BaseConfig."""
            return _default

        @property
        def port(self) -> int:
            """Type stub: property provided by BaseConfig."""
            return 0

        @property
        def QWEN_TIMEOUT(self) -> int:
            """Type stub: property provided by LLMConfigMixin."""
            return 0

        @property
        def QWEN_MAX_TOKENS(self) -> int:
            """Type stub: property provided by LLMConfigMixin."""
            return 0

        @property
        def WATERMARK_TEXT(self) -> str:
            """Type stub: property provided by FeaturesConfigMixin."""
            return ""

    @property
    def TOPIC_FONT_SIZE(self):
        """Font size for topic nodes in pixels."""
        try:
            val = int(self._get_cached_value('TOPIC_FONT_SIZE', '18'))
            if val <= 0:
                logger.warning("TOPIC_FONT_SIZE %s out of range, using 18", val)
                return 18
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid TOPIC_FONT_SIZE value, using 18")
            return 18

    @property
    def CHAR_FONT_SIZE(self):
        """Font size for characteristic nodes in pixels."""
        try:
            val = int(self._get_cached_value('CHAR_FONT_SIZE', '14'))
            if val <= 0:
                logger.warning("CHAR_FONT_SIZE %s out of range, using 14", val)
                return 14
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid CHAR_FONT_SIZE value, using 14")
            return 14

    @property
    def D3_BASE_WIDTH(self):
        """Base width for D3.js visualizations in pixels."""
        try:
            val = int(self._get_cached_value('D3_BASE_WIDTH', '700'))
            if val <= 0:
                logger.warning("D3_BASE_WIDTH %s out of range, using 700", val)
                return 700
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid D3_BASE_WIDTH value, using 700")
            return 700

    @property
    def D3_BASE_HEIGHT(self):
        """Base height for D3.js visualizations in pixels."""
        try:
            val = int(self._get_cached_value('D3_BASE_HEIGHT', '500'))
            if val <= 0:
                logger.warning("D3_BASE_HEIGHT %s out of range, using 500", val)
                return 500
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid D3_BASE_HEIGHT value, using 500")
            return 500

    @property
    def D3_PADDING(self):
        """Padding around D3.js visualizations in pixels."""
        try:
            val = int(self._get_cached_value('D3_PADDING', '40'))
            if val < 0:
                logger.warning("D3_PADDING %s out of range, using 40", val)
                return 40
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid D3_PADDING value, using 40")
            return 40

    @property
    def D3_TOPIC_FILL(self):
        """Fill color for topic nodes."""
        return self._get_cached_value('D3_TOPIC_FILL', '#e3f2fd')

    @property
    def D3_TOPIC_TEXT(self):
        """Text color for topic nodes."""
        return self._get_cached_value('D3_TOPIC_TEXT', '#000000')

    @property
    def D3_TOPIC_STROKE(self):
        """Stroke color for topic nodes."""
        return self._get_cached_value('D3_TOPIC_STROKE', '#000000')

    @property
    def D3_SIM_FILL(self):
        """Fill color for similarity nodes."""
        return self._get_cached_value('D3_SIM_FILL', '#a7c7e7')

    @property
    def D3_SIM_TEXT(self):
        """Text color for similarity nodes."""
        return self._get_cached_value('D3_SIM_TEXT', '#2c3e50')

    @property
    def D3_SIM_STROKE(self):
        """Stroke color for similarity nodes."""
        return self._get_cached_value('D3_SIM_STROKE', '#4e79a7')

    @property
    def D3_DIFF_FILL(self):
        """Fill color for difference nodes."""
        return self._get_cached_value('D3_DIFF_FILL', '#f4f6fb')

    @property
    def D3_DIFF_TEXT(self):
        """Text color for difference nodes."""
        return self._get_cached_value('D3_DIFF_TEXT', '#2c3e50')

    @property
    def D3_DIFF_STROKE(self):
        """Stroke color for difference nodes."""
        return self._get_cached_value('D3_DIFF_STROKE', '#a7c7e7')

    def get_d3_dimensions(self) -> dict:
        """
        Get D3.js visualization dimensions.

        Returns:
            dict: Dimension configuration for D3.js visualizations
        """
        return {
            'width': self.D3_BASE_WIDTH,
            'height': self.D3_BASE_HEIGHT,
            'padding': self.D3_PADDING,
            'topicFontSize': self.TOPIC_FONT_SIZE,
            'charFontSize': self.CHAR_FONT_SIZE
        }

    def get_watermark_config(self) -> dict:
        """
        Get watermark configuration.

        Returns:
            dict: Watermark configuration for D3.js visualizations
        """
        return {
            'watermarkText': self.WATERMARK_TEXT
        }

    def validate_numeric_config(self) -> bool:
        """
        Validate all numeric configuration values.

        Returns:
            bool: True if all numeric values are valid, False otherwise
        """
        try:
            if not 1 <= self.port <= 65535:
                return False

            if self.TOPIC_FONT_SIZE <= 0 or self.CHAR_FONT_SIZE <= 0:
                return False

            if (self.D3_BASE_WIDTH <= 0 or self.D3_BASE_HEIGHT <= 0 or
                self.D3_PADDING < 0):
                return False

            if (self.QWEN_TIMEOUT <= 0 or self.QWEN_MAX_TOKENS <= 0):
                return False

            return True
        except (ValueError, TypeError):
            return False
