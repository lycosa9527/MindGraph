"""Rate limiting configuration settings.

This module provides rate limiting configurations for Dashscope, ARK, SMS,
and load balancing.
"""
import logging
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)


class RateLimitingConfigMixin:
    """Mixin class for rate limiting configuration properties.

    This mixin expects the class to inherit from BaseConfig or provide
    a _get_cached_value method.
    """
    if TYPE_CHECKING:
        def _get_cached_value(self, _key: str, _default: Any = None) -> Any:
            """Type stub: method provided by BaseConfig."""
            return _default

    @property
    def DASHSCOPE_QPM_LIMIT(self):
        """
        Dashscope Queries Per Minute limit.

        Default: 13,500 (90% of official 15,000 RPM limit for qwen-plus/deepseek-v3.1).
        """
        try:
            return int(self._get_cached_value('DASHSCOPE_QPM_LIMIT', '13500'))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHSCOPE_QPM_LIMIT, using 13500")
            return 13500

    @property
    def DASHSCOPE_CONCURRENT_LIMIT(self):
        """Dashscope concurrent request limit"""
        try:
            return int(self._get_cached_value('DASHSCOPE_CONCURRENT_LIMIT', '500'))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHSCOPE_CONCURRENT_LIMIT, using 500")
            return 500

    @property
    def DASHSCOPE_RATE_LIMITING_ENABLED(self):
        """Enable/disable Dashscope rate limiting"""
        val = self._get_cached_value('DASHSCOPE_RATE_LIMITING_ENABLED', 'true')
        return val.lower() == 'true'

    @property
    def ARK_QPM_LIMIT(self):
        """
        Volcengine ARK Queries Per Minute limit.

        Default: 4,500 (90% of official 5,000 RPM limit).
        """
        try:
            return int(self._get_cached_value('ARK_QPM_LIMIT', '4500'))
        except (ValueError, TypeError):
            logger.warning("Invalid ARK_QPM_LIMIT, using 4500")
            return 4500

    @property
    def ARK_CONCURRENT_LIMIT(self):
        """Volcengine ARK concurrent request limit"""
        try:
            return int(self._get_cached_value('ARK_CONCURRENT_LIMIT', '500'))
        except (ValueError, TypeError):
            logger.warning("Invalid ARK_CONCURRENT_LIMIT, using 500")
            return 500

    @property
    def ARK_RATE_LIMITING_ENABLED(self):
        """Enable/disable Volcengine rate limiting"""
        val = self._get_cached_value('ARK_RATE_LIMITING_ENABLED', 'false')
        return val.lower() == 'true'

    @property
    def LOAD_BALANCING_ENABLED(self):
        """Enable/disable load balancing (default: false)"""
        val = self._get_cached_value('LOAD_BALANCING_ENABLED', 'false')
        return val.lower() == 'true'

    @property
    def DEEPSEEK_DASHSCOPE_QPM_LIMIT(self):
        """
        DeepSeek Dashscope route QPM limit for load balancing.

        DEPRECATED: DeepSeek Dashscope route now uses shared DASHSCOPE_QPM_LIMIT.
        """
        try:
            return int(self._get_cached_value('DEEPSEEK_DASHSCOPE_QPM_LIMIT', '13500'))
        except (ValueError, TypeError):
            logger.warning("Invalid DEEPSEEK_DASHSCOPE_QPM_LIMIT, using 13500")
            return 13500

    @property
    def DEEPSEEK_DASHSCOPE_CONCURRENT_LIMIT(self):
        """
        DeepSeek Dashscope route concurrent limit for load balancing.

        DEPRECATED: DeepSeek Dashscope route now uses shared DASHSCOPE_CONCURRENT_LIMIT.
        """
        try:
            return int(self._get_cached_value('DEEPSEEK_DASHSCOPE_CONCURRENT_LIMIT', '500'))
        except (ValueError, TypeError):
            logger.warning("Invalid DEEPSEEK_DASHSCOPE_CONCURRENT_LIMIT, using 500")
            return 500

    @property
    def DEEPSEEK_VOLCENGINE_QPM_LIMIT(self):
        """
        DeepSeek Volcengine route QPM limit for load balancing.

        Default: 13,500 (90% of official 15,000 RPM limit).
        """
        try:
            return int(self._get_cached_value('DEEPSEEK_VOLCENGINE_QPM_LIMIT', '13500'))
        except (ValueError, TypeError):
            logger.warning("Invalid DEEPSEEK_VOLCENGINE_QPM_LIMIT, using 13500")
            return 13500

    @property
    def DEEPSEEK_VOLCENGINE_CONCURRENT_LIMIT(self):
        """DeepSeek Volcengine route concurrent limit for load balancing (default: 500)"""
        try:
            return int(self._get_cached_value('DEEPSEEK_VOLCENGINE_CONCURRENT_LIMIT', '500'))
        except (ValueError, TypeError):
            logger.warning("Invalid DEEPSEEK_VOLCENGINE_CONCURRENT_LIMIT, using 500")
            return 500

    @property
    def KIMI_VOLCENGINE_QPM_LIMIT(self):
        """
        Kimi Volcengine endpoint QPM limit.

        Default: 4,500 (90% of official 5,000 RPM limit).
        """
        try:
            return int(self._get_cached_value('KIMI_VOLCENGINE_QPM_LIMIT', '4500'))
        except (ValueError, TypeError):
            logger.warning("Invalid KIMI_VOLCENGINE_QPM_LIMIT, using 4500")
            return 4500

    @property
    def KIMI_VOLCENGINE_CONCURRENT_LIMIT(self):
        """Kimi Volcengine endpoint concurrent limit (default: 500)"""
        try:
            return int(self._get_cached_value('KIMI_VOLCENGINE_CONCURRENT_LIMIT', '500'))
        except (ValueError, TypeError):
            logger.warning("Invalid KIMI_VOLCENGINE_CONCURRENT_LIMIT, using 500")
            return 500

    @property
    def DOUBAO_VOLCENGINE_QPM_LIMIT(self):
        """
        Doubao Volcengine endpoint QPM limit.

        Default: 27,000 (90% of official 30,000 RPM limit).
        """
        try:
            return int(self._get_cached_value('DOUBAO_VOLCENGINE_QPM_LIMIT', '27000'))
        except (ValueError, TypeError):
            logger.warning("Invalid DOUBAO_VOLCENGINE_QPM_LIMIT, using 27000")
            return 27000

    @property
    def DOUBAO_VOLCENGINE_CONCURRENT_LIMIT(self):
        """Doubao Volcengine endpoint concurrent limit (default: 500)"""
        try:
            return int(self._get_cached_value('DOUBAO_VOLCENGINE_CONCURRENT_LIMIT', '500'))
        except (ValueError, TypeError):
            logger.warning("Invalid DOUBAO_VOLCENGINE_CONCURRENT_LIMIT, using 500")
            return 500

    @property
    def LOAD_BALANCING_RATE_LIMITING_ENABLED(self):
        """Enable/disable rate limiting for load balancing (default: true)"""
        val = self._get_cached_value('LOAD_BALANCING_RATE_LIMITING_ENABLED', 'true')
        return val.lower() == 'true'

    @property
    def LOAD_BALANCING_STRATEGY(self):
        """Load balancing strategy: 'weighted', 'random', or 'round_robin'"""
        return self._get_cached_value('LOAD_BALANCING_STRATEGY', 'round_robin')

    @property
    def LOAD_BALANCING_WEIGHTS(self):
        """
        Load balancing weights as dict.
        Format: 'dashscope:50,volcengine:50' -> {'dashscope': 50, 'volcengine': 50}

        Validates weights are in 0-100 range and normalizes to sum to 100.
        """
        weights_str = self._get_cached_value('LOAD_BALANCING_WEIGHTS', 'dashscope:50,volcengine:50')
        weights = {}
        try:
            for pair in weights_str.split(','):
                if ':' in pair:
                    key, weight = pair.strip().split(':', 1)
                    weights[key] = int(weight)
        except (ValueError, AttributeError):
            logger.warning("Invalid LOAD_BALANCING_WEIGHTS format: %s, using default 50/50", weights_str)
            weights = {'dashscope': 50, 'volcengine': 50}

        if 'dashscope' not in weights:
            weights['dashscope'] = 50
        if 'volcengine' not in weights:
            weights['volcengine'] = 50

        for provider in ['dashscope', 'volcengine']:
            if provider in weights:
                weights[provider] = max(0, min(100, weights[provider]))

        total = weights.get('dashscope', 0) + weights.get('volcengine', 0)
        if total > 0:
            dashscope_weight = weights.get('dashscope', 0)
            weights['dashscope'] = int(round(dashscope_weight * 100 / total))
            weights['volcengine'] = 100 - weights['dashscope']
        else:
            logger.warning("LOAD_BALANCING_WEIGHTS sum to 0, using default 50/50")
            weights = {'dashscope': 50, 'volcengine': 50}

        return weights

    @property
    def SMS_MAX_CONCURRENT_REQUESTS(self):
        """SMS maximum concurrent API requests"""
        try:
            return int(self._get_cached_value('SMS_MAX_CONCURRENT_REQUESTS', '10'))
        except (ValueError, TypeError):
            logger.warning("Invalid SMS_MAX_CONCURRENT_REQUESTS, using 10")
            return 10

    @property
    def SMS_QPM_LIMIT(self):
        """SMS Queries Per Minute limit"""
        try:
            return int(self._get_cached_value('SMS_QPM_LIMIT', '100'))
        except (ValueError, TypeError):
            logger.warning("Invalid SMS_QPM_LIMIT, using 100")
            return 100

    @property
    def SMS_RATE_LIMITING_ENABLED(self):
        """Enable/disable SMS rate limiting"""
        val = self._get_cached_value('SMS_RATE_LIMITING_ENABLED', 'true')
        return val.lower() == 'true'

    @property
    def DASHBOARD_MAX_CONCURRENT_SSE_CONNECTIONS(self):
        """Maximum concurrent SSE connections per IP for dashboard (default: 2)"""
        try:
            return int(self._get_cached_value('DASHBOARD_MAX_CONCURRENT_SSE_CONNECTIONS', '2'))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHBOARD_MAX_CONCURRENT_SSE_CONNECTIONS, using 2")
            return 2

    @property
    def DASHBOARD_SSE_POLL_INTERVAL_SECONDS(self):
        """SSE poll interval in seconds (default: 5)"""
        try:
            return int(self._get_cached_value('DASHBOARD_SSE_POLL_INTERVAL_SECONDS', '5'))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHBOARD_SSE_POLL_INTERVAL_SECONDS, using 5")
            return 5

    @property
    def DASHBOARD_STATS_UPDATE_INTERVAL(self):
        """Stats update interval in seconds (default: 10)"""
        try:
            return int(self._get_cached_value('DASHBOARD_STATS_UPDATE_INTERVAL', '10'))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHBOARD_STATS_UPDATE_INTERVAL, using 10")
            return 10

    @property
    def DASHBOARD_HEARTBEAT_INTERVAL(self):
        """Heartbeat interval in seconds (default: 30)"""
        try:
            return int(self._get_cached_value('DASHBOARD_HEARTBEAT_INTERVAL', '30'))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHBOARD_HEARTBEAT_INTERVAL, using 30")
            return 30

    @property
    def DASHBOARD_STATS_CACHE_TTL(self):
        """Stats cache TTL in seconds (default: 3)"""
        try:
            return int(self._get_cached_value('DASHBOARD_STATS_CACHE_TTL', '3'))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHBOARD_STATS_CACHE_TTL, using 3")
            return 3

    @property
    def DASHBOARD_MAP_DATA_CACHE_TTL(self):
        """Map data cache TTL in seconds (default: 20)"""
        try:
            return int(self._get_cached_value('DASHBOARD_MAP_DATA_CACHE_TTL', '20'))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHBOARD_MAP_DATA_CACHE_TTL, using 20")
            return 20

    @property
    def DASHBOARD_REGISTERED_USERS_CACHE_TTL(self):
        """Registered users cache TTL in seconds (default: 300)"""
        try:
            return int(self._get_cached_value('DASHBOARD_REGISTERED_USERS_CACHE_TTL', '300'))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHBOARD_REGISTERED_USERS_CACHE_TTL, using 300")
            return 300

    @property
    def DASHBOARD_TOKEN_USAGE_CACHE_TTL(self):
        """Token usage cache TTL in seconds (default: 60)"""
        try:
            return int(self._get_cached_value('DASHBOARD_TOKEN_USAGE_CACHE_TTL', '60'))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHBOARD_TOKEN_USAGE_CACHE_TTL, using 60")
            return 60
