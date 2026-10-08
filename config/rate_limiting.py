"""Rate limiting configuration settings.

This module provides rate limiting configurations for Dashscope, ARK, SMS,
and load balancing.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

# 90% of the confirmed provider RPM, leaving headroom for the per-second RPS/TPS burst check.
# DashScope Beijing, 2026-10: qwen3.6-flash 30,000 RPM / 10,000,000 TPM;
# deepseek-v4.1-flash 15,000 RPM / 1,200,000 TPM.
# Volcengine console, DeepSeek-V4-Flash 正式版 (260731): 500 RPM / 1,000,000 TPM regular.
DASHSCOPE_DEEPSEEK_QPM_DEFAULT = 13500
QWEN_DASHSCOPE_QPM_DEFAULT = 27000
QWEN38_DASHSCOPE_QPM_DEFAULT = 13500
DEEPSEEK_VOLCENGINE_QPM_DEFAULT = 450
DOUBAO_VOLCENGINE_QPM_DEFAULT = 27000
KIMI_VOLCENGINE_QPM_DEFAULT = 4500


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

        Default: 13,500 (90% of DashScope Beijing deepseek-v4.1-flash, 15,000 RPM).

        This window is shared by Express and the logical deepseek DashScope leg,
        because both call ``deepseek-v4.1-flash``. Qwen uses its own limit.
        """
        try:
            return int(self._get_cached_value("DASHSCOPE_QPM_LIMIT", str(DASHSCOPE_DEEPSEEK_QPM_DEFAULT)))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHSCOPE_QPM_LIMIT, using %s", DASHSCOPE_DEEPSEEK_QPM_DEFAULT)
            return DASHSCOPE_DEEPSEEK_QPM_DEFAULT

    @property
    def QWEN_DASHSCOPE_QPM_LIMIT(self):
        """Qwen generation QPM. Default 27,000 (90% of qwen3.6-flash 30,000 RPM)."""
        try:
            return int(self._get_cached_value("QWEN_DASHSCOPE_QPM_LIMIT", str(QWEN_DASHSCOPE_QPM_DEFAULT)))
        except (ValueError, TypeError):
            logger.warning("Invalid QWEN_DASHSCOPE_QPM_LIMIT, using %s", QWEN_DASHSCOPE_QPM_DEFAULT)
            return QWEN_DASHSCOPE_QPM_DEFAULT

    @property
    def QWEN38_DASHSCOPE_QPM_LIMIT(self):
        """Node-explain QPM. qwen3.8-flash is dynamic on DashScope; keep a separate cap."""
        try:
            return int(self._get_cached_value("QWEN38_DASHSCOPE_QPM_LIMIT", str(QWEN38_DASHSCOPE_QPM_DEFAULT)))
        except (ValueError, TypeError):
            logger.warning("Invalid QWEN38_DASHSCOPE_QPM_LIMIT, using %s", QWEN38_DASHSCOPE_QPM_DEFAULT)
            return QWEN38_DASHSCOPE_QPM_DEFAULT

    @property
    def DASHSCOPE_CONCURRENT_LIMIT(self):
        """Dashscope concurrent request limit"""
        try:
            return int(self._get_cached_value("DASHSCOPE_CONCURRENT_LIMIT", "500"))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHSCOPE_CONCURRENT_LIMIT, using 500")
            return 500

    @property
    def DASHSCOPE_RATE_LIMITING_ENABLED(self):
        """Enable/disable Dashscope rate limiting"""
        val = self._get_cached_value("DASHSCOPE_RATE_LIMITING_ENABLED", "true")
        return val.lower() == "true"

    @property
    def ARK_QPM_LIMIT(self):
        """
        Volcengine ARK Queries Per Minute limit.

        Default: 4,500 (90% of official 5,000 RPM limit).
        """
        try:
            return int(self._get_cached_value("ARK_QPM_LIMIT", "4500"))
        except (ValueError, TypeError):
            logger.warning("Invalid ARK_QPM_LIMIT, using 4500")
            return 4500

    @property
    def ARK_CONCURRENT_LIMIT(self):
        """Volcengine ARK concurrent request limit"""
        try:
            return int(self._get_cached_value("ARK_CONCURRENT_LIMIT", "500"))
        except (ValueError, TypeError):
            logger.warning("Invalid ARK_CONCURRENT_LIMIT, using 500")
            return 500

    @property
    def ARK_RATE_LIMITING_ENABLED(self):
        """Enable/disable Volcengine rate limiting"""
        val = self._get_cached_value("ARK_RATE_LIMITING_ENABLED", "false")
        return val.lower() == "true"

    @property
    def LOAD_BALANCING_ENABLED(self):
        """Enable/disable load balancing (default: false)"""
        val = self._get_cached_value("LOAD_BALANCING_ENABLED", "false")
        return val.lower() == "true"

    @property
    def DEEPSEEK_VOLCENGINE_QPM_LIMIT(self):
        """
        DeepSeek Volcengine route QPM limit for load balancing.

        Default: 450 (90% of the console quota, 500 RPM / 1,000,000 TPM).

        Flex on that model is 200,000 TPM and is not the path we call.
        """
        try:
            return int(self._get_cached_value("DEEPSEEK_VOLCENGINE_QPM_LIMIT", str(DEEPSEEK_VOLCENGINE_QPM_DEFAULT)))
        except (ValueError, TypeError):
            logger.warning("Invalid DEEPSEEK_VOLCENGINE_QPM_LIMIT, using %s", DEEPSEEK_VOLCENGINE_QPM_DEFAULT)
            return DEEPSEEK_VOLCENGINE_QPM_DEFAULT

    @property
    def DEEPSEEK_VOLCENGINE_CONCURRENT_LIMIT(self):
        """DeepSeek Volcengine route concurrent limit for load balancing (default: 500)"""
        try:
            return int(self._get_cached_value("DEEPSEEK_VOLCENGINE_CONCURRENT_LIMIT", "500"))
        except (ValueError, TypeError):
            logger.warning("Invalid DEEPSEEK_VOLCENGINE_CONCURRENT_LIMIT, using 500")
            return 500

    @property
    def KIMI_VOLCENGINE_QPM_LIMIT(self):
        """
        Kimi Volcengine endpoint QPM limit.

        Default: 4,500. The Volcengine endpoint quota was not on the model-square page.

        DashScope ``Moonshot-Kimi-K2-Instruct`` in Beijing is 500 RPM / 1,000,000 TPM,
        which is why Kimi stays on the Volcengine endpoint.
        """
        try:
            return int(self._get_cached_value("KIMI_VOLCENGINE_QPM_LIMIT", str(KIMI_VOLCENGINE_QPM_DEFAULT)))
        except (ValueError, TypeError):
            logger.warning("Invalid KIMI_VOLCENGINE_QPM_LIMIT, using %s", KIMI_VOLCENGINE_QPM_DEFAULT)
            return KIMI_VOLCENGINE_QPM_DEFAULT

    @property
    def KIMI_VOLCENGINE_CONCURRENT_LIMIT(self):
        """Kimi Volcengine endpoint concurrent limit (default: 500)"""
        try:
            return int(self._get_cached_value("KIMI_VOLCENGINE_CONCURRENT_LIMIT", "500"))
        except (ValueError, TypeError):
            logger.warning("Invalid KIMI_VOLCENGINE_CONCURRENT_LIMIT, using 500")
            return 500

    @property
    def DOUBAO_VOLCENGINE_QPM_LIMIT(self):
        """
        Doubao Volcengine endpoint QPM limit.

        Default: 27,000 (90% of 30,000 RPM).

        The console row for Doubao-Seed-2.0-mini is 30,000 RPM / 5,000,000 TPM
        and that model is being retired. Live traffic uses the doubao_1.5pro_32k
        endpoint, so this cap is not raised further from that row.
        """
        try:
            return int(self._get_cached_value("DOUBAO_VOLCENGINE_QPM_LIMIT", str(DOUBAO_VOLCENGINE_QPM_DEFAULT)))
        except (ValueError, TypeError):
            logger.warning("Invalid DOUBAO_VOLCENGINE_QPM_LIMIT, using %s", DOUBAO_VOLCENGINE_QPM_DEFAULT)
            return DOUBAO_VOLCENGINE_QPM_DEFAULT

    @property
    def DOUBAO_VOLCENGINE_CONCURRENT_LIMIT(self):
        """Doubao Volcengine endpoint concurrent limit (default: 500)"""
        try:
            return int(self._get_cached_value("DOUBAO_VOLCENGINE_CONCURRENT_LIMIT", "500"))
        except (ValueError, TypeError):
            logger.warning("Invalid DOUBAO_VOLCENGINE_CONCURRENT_LIMIT, using 500")
            return 500

    @property
    def LOAD_BALANCING_RATE_LIMITING_ENABLED(self):
        """Enable/disable rate limiting for load balancing (default: true)"""
        val = self._get_cached_value("LOAD_BALANCING_RATE_LIMITING_ENABLED", "true")
        return val.lower() == "true"

    @property
    def LOAD_BALANCING_STRATEGY(self):
        """Load balancing strategy: 'weighted', 'random', or 'round_robin'"""
        return self._get_cached_value("LOAD_BALANCING_STRATEGY", "weighted")

    @property
    def LOAD_BALANCING_WEIGHTS(self):
        """
        Load balancing weights as dict.
        Format: 'dashscope:75,volcengine:25' -> {'dashscope': 75, 'volcengine': 25}

        A quarter stays on Volcengine so logical DeepSeek still moves if DashScope
        is degrading. The Volcengine leg is still capped at 450 QPM.

        Validates weights are in 0-100 range and normalizes to sum to 100.
        """
        weights_str = self._get_cached_value("LOAD_BALANCING_WEIGHTS", "dashscope:75,volcengine:25")
        weights = {}
        try:
            for pair in weights_str.split(","):
                if ":" in pair:
                    key, weight = pair.strip().split(":", 1)
                    weights[key] = int(weight)
        except (ValueError, AttributeError):
            logger.warning(
                "Invalid LOAD_BALANCING_WEIGHTS format: %s, using default 75/25",
                weights_str,
            )
            weights = {"dashscope": 75, "volcengine": 25}

        if "dashscope" not in weights:
            weights["dashscope"] = 75
        if "volcengine" not in weights:
            weights["volcengine"] = 25

        for provider in ["dashscope", "volcengine"]:
            if provider in weights:
                weights[provider] = max(0, min(100, weights[provider]))

        total = weights.get("dashscope", 0) + weights.get("volcengine", 0)
        if total > 0:
            dashscope_weight = weights.get("dashscope", 0)
            weights["dashscope"] = int(round(dashscope_weight * 100 / total))
            weights["volcengine"] = 100 - weights["dashscope"]
        else:
            logger.warning("LOAD_BALANCING_WEIGHTS sum to 0, using default 75/25")
            weights = {"dashscope": 75, "volcengine": 25}

        return weights

    @property
    def SMS_MAX_CONCURRENT_REQUESTS(self):
        """SMS maximum concurrent API requests"""
        try:
            return int(self._get_cached_value("SMS_MAX_CONCURRENT_REQUESTS", "10"))
        except (ValueError, TypeError):
            logger.warning("Invalid SMS_MAX_CONCURRENT_REQUESTS, using 10")
            return 10

    @property
    def SMS_QPM_LIMIT(self):
        """SMS Queries Per Minute limit"""
        try:
            return int(self._get_cached_value("SMS_QPM_LIMIT", "100"))
        except (ValueError, TypeError):
            logger.warning("Invalid SMS_QPM_LIMIT, using 100")
            return 100

    @property
    def SMS_RATE_LIMITING_ENABLED(self):
        """Enable/disable SMS rate limiting"""
        val = self._get_cached_value("SMS_RATE_LIMITING_ENABLED", "true")
        return val.lower() == "true"

    @property
    def EMAIL_MAX_CONCURRENT_REQUESTS(self):
        """Email (SES) maximum concurrent API requests"""
        try:
            return int(self._get_cached_value("EMAIL_MAX_CONCURRENT_REQUESTS", "50"))
        except (ValueError, TypeError):
            logger.warning("Invalid EMAIL_MAX_CONCURRENT_REQUESTS, using 50")
            return 50

    @property
    def EMAIL_QPM_LIMIT(self):
        """Email (SES) queries per minute limit"""
        try:
            return int(self._get_cached_value("EMAIL_QPM_LIMIT", "100"))
        except (ValueError, TypeError):
            logger.warning("Invalid EMAIL_QPM_LIMIT, using 100")
            return 100

    @property
    def EMAIL_RATE_LIMITING_ENABLED(self):
        """Enable/disable email (SES) rate limiting"""
        val = self._get_cached_value("EMAIL_RATE_LIMITING_ENABLED", "true")
        return val.lower() == "true"

    @property
    def EMAIL_VERIFY_MAX_ATTEMPTS_PER_COMBO(self):
        """Max POST /email/verify attempts per normalized email+purpose in the window (anti brute-force)."""
        try:
            return int(self._get_cached_value("EMAIL_VERIFY_MAX_ATTEMPTS_PER_COMBO", "25"))
        except (ValueError, TypeError):
            logger.warning("Invalid EMAIL_VERIFY_MAX_ATTEMPTS_PER_COMBO, using 25")
            return 25

    @property
    def EMAIL_VERIFY_WINDOW_MINUTES(self):
        """Sliding window for email verify rate limits (minutes)."""
        try:
            return int(self._get_cached_value("EMAIL_VERIFY_WINDOW_MINUTES", "15"))
        except (ValueError, TypeError):
            logger.warning("Invalid EMAIL_VERIFY_WINDOW_MINUTES, using 15")
            return 15

    @property
    def EMAIL_VERIFY_MAX_ATTEMPTS_PER_IP(self):
        """Max POST /email/verify attempts per client IP in the window."""
        try:
            return int(self._get_cached_value("EMAIL_VERIFY_MAX_ATTEMPTS_PER_IP", "150"))
        except (ValueError, TypeError):
            logger.warning("Invalid EMAIL_VERIFY_MAX_ATTEMPTS_PER_IP, using 150")
            return 150

    @property
    def EMAIL_SEND_WINDOW_MINUTES(self):
        """Sliding window for POST /email/send per-IP rate limit (minutes)."""
        try:
            return int(self._get_cached_value("EMAIL_SEND_WINDOW_MINUTES", "15"))
        except (ValueError, TypeError):
            logger.warning("Invalid EMAIL_SEND_WINDOW_MINUTES, using 15")
            return 15

    @property
    def EMAIL_SEND_MAX_ATTEMPTS_PER_IP(self):
        """Max POST /email/send attempts per client IP in the window (anti abuse)."""
        try:
            return int(self._get_cached_value("EMAIL_SEND_MAX_ATTEMPTS_PER_IP", "40"))
        except (ValueError, TypeError):
            logger.warning("Invalid EMAIL_SEND_MAX_ATTEMPTS_PER_IP, using 40")
            return 40

    @property
    def SMS_SEND_WINDOW_MINUTES(self):
        """Sliding window for POST /sms/send per-IP rate limit (minutes)."""
        try:
            return int(self._get_cached_value("SMS_SEND_WINDOW_MINUTES", "15"))
        except (ValueError, TypeError):
            logger.warning("Invalid SMS_SEND_WINDOW_MINUTES, using 15")
            return 15

    @property
    def SMS_SEND_MAX_ATTEMPTS_PER_IP(self):
        """Max POST /sms/send attempts per client IP in the window (anti abuse)."""
        try:
            return int(self._get_cached_value("SMS_SEND_MAX_ATTEMPTS_PER_IP", "40"))
        except (ValueError, TypeError):
            logger.warning("Invalid SMS_SEND_MAX_ATTEMPTS_PER_IP, using 40")
            return 40

    @property
    def SMS_VERIFY_MAX_ATTEMPTS_PER_COMBO(self):
        """Max POST /sms/verify attempts per phone+purpose in the window (anti brute-force)."""
        try:
            return int(self._get_cached_value("SMS_VERIFY_MAX_ATTEMPTS_PER_COMBO", "25"))
        except (ValueError, TypeError):
            logger.warning("Invalid SMS_VERIFY_MAX_ATTEMPTS_PER_COMBO, using 25")
            return 25

    @property
    def SMS_VERIFY_WINDOW_MINUTES(self):
        """Sliding window for SMS verify rate limits (minutes)."""
        try:
            return int(self._get_cached_value("SMS_VERIFY_WINDOW_MINUTES", "15"))
        except (ValueError, TypeError):
            logger.warning("Invalid SMS_VERIFY_WINDOW_MINUTES, using 15")
            return 15

    @property
    def SMS_VERIFY_MAX_ATTEMPTS_PER_IP(self):
        """Max POST /sms/verify attempts per client IP in the window."""
        try:
            return int(self._get_cached_value("SMS_VERIFY_MAX_ATTEMPTS_PER_IP", "150"))
        except (ValueError, TypeError):
            logger.warning("Invalid SMS_VERIFY_MAX_ATTEMPTS_PER_IP, using 150")
            return 150

    @property
    def DASHBOARD_MAX_CONCURRENT_SSE_CONNECTIONS(self):
        """Maximum concurrent SSE connections per IP for dashboard (default: 2)"""
        try:
            return int(self._get_cached_value("DASHBOARD_MAX_CONCURRENT_SSE_CONNECTIONS", "2"))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHBOARD_MAX_CONCURRENT_SSE_CONNECTIONS, using 2")
            return 2

    @property
    def DASHBOARD_SSE_POLL_INTERVAL_SECONDS(self):
        """SSE poll interval in seconds (default: 5)"""
        try:
            return int(self._get_cached_value("DASHBOARD_SSE_POLL_INTERVAL_SECONDS", "5"))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHBOARD_SSE_POLL_INTERVAL_SECONDS, using 5")
            return 5

    @property
    def DASHBOARD_STATS_UPDATE_INTERVAL(self):
        """Stats update interval in seconds (default: 10)"""
        try:
            return int(self._get_cached_value("DASHBOARD_STATS_UPDATE_INTERVAL", "10"))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHBOARD_STATS_UPDATE_INTERVAL, using 10")
            return 10

    @property
    def DASHBOARD_HEARTBEAT_INTERVAL(self):
        """Heartbeat interval in seconds (default: 30)"""
        try:
            return int(self._get_cached_value("DASHBOARD_HEARTBEAT_INTERVAL", "30"))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHBOARD_HEARTBEAT_INTERVAL, using 30")
            return 30

    @property
    def DASHBOARD_STATS_CACHE_TTL(self):
        """Stats cache TTL in seconds (default: 3)"""
        try:
            return int(self._get_cached_value("DASHBOARD_STATS_CACHE_TTL", "3"))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHBOARD_STATS_CACHE_TTL, using 3")
            return 3

    @property
    def DASHBOARD_MAP_DATA_CACHE_TTL(self):
        """Map data cache TTL in seconds (default: 20)"""
        try:
            return int(self._get_cached_value("DASHBOARD_MAP_DATA_CACHE_TTL", "20"))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHBOARD_MAP_DATA_CACHE_TTL, using 20")
            return 20

    @property
    def DASHBOARD_REGISTERED_USERS_CACHE_TTL(self):
        """Registered users cache TTL in seconds (default: 300)"""
        try:
            return int(self._get_cached_value("DASHBOARD_REGISTERED_USERS_CACHE_TTL", "300"))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHBOARD_REGISTERED_USERS_CACHE_TTL, using 300")
            return 300

    @property
    def DASHBOARD_TOKEN_USAGE_CACHE_TTL(self):
        """Token usage cache TTL in seconds (default: 60)"""
        try:
            return int(self._get_cached_value("DASHBOARD_TOKEN_USAGE_CACHE_TTL", "60"))
        except (ValueError, TypeError):
            logger.warning("Invalid DASHBOARD_TOKEN_USAGE_CACHE_TTL, using 60")
            return 60
