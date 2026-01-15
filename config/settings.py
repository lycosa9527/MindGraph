"""
MindGraph Configuration Module
==============================

This module provides centralized configuration management for the MindGraph application.
It handles environment variable loading, validation, and provides a clean interface
for accessing configuration values throughout the application.

Features:
- Dynamic environment variable loading with .env support
- Property-based configuration access for real-time updates
- Comprehensive validation for required and optional settings
- Default values for all configuration options
- Support for Qwen LLM configuration
- D3.js visualization customization options

Environment Variables:
- QWEN_API_KEY: Required for core functionality
- See env.example for complete configuration options

Usage:
    from settings import config
    api_key = config.QWEN_API_KEY
    is_valid = config.validate_qwen_config()

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from dotenv import load_dotenv
import os
from typing import Optional
import logging
from utils.env_utils import ensure_utf8_env_file

logger = logging.getLogger(__name__)

# Ensure .env file is UTF-8 encoded before loading
ensure_utf8_env_file()
load_dotenv()  # Load environment variables from .env file

class Config:
    """
    Centralized configuration management for MindGraph application.
    Now with caching and validation to prevent race conditions and ensure consistent values.
    """
    def __init__(self):
        self._cache = {}
        self._cache_timestamp = 0
        self._cache_duration = 30  # Cache for 30 seconds
        self._version = None  # Cached version from VERSION file
    
    @property
    def VERSION(self) -> str:
        """
        Application version - read from VERSION file (single source of truth).
        Cached after first read for performance.
        """
        if self._version is None:
            try:
                from pathlib import Path
                version_file = Path(__file__).parent.parent / 'VERSION'
                self._version = version_file.read_text().strip()
            except Exception as e:
                logger.warning(f"Failed to read VERSION file: {e}")
                self._version = "0.0.0"  # Fallback
        return self._version
    def _get_cached_value(self, key: str, default=None):
        import time
        current_time = time.time()
        if current_time - self._cache_timestamp > self._cache_duration:
            self._cache.clear()
            self._cache_timestamp = current_time
        if key not in self._cache:
            self._cache[key] = os.environ.get(key, default)
        return self._cache[key]
    @property
    def QWEN_API_KEY(self):
        api_key = self._get_cached_value('QWEN_API_KEY')
        if not api_key or not isinstance(api_key, str):
            logger.warning("Invalid or missing QWEN_API_KEY")
            return None
        return api_key.strip()
    @property
    def QWEN_API_URL(self):
        return self._get_cached_value('QWEN_API_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions')
    @property
    def QWEN_MODEL(self):
        """Legacy property - now defaults to classification model for backward compatibility"""
        return self.QWEN_MODEL_CLASSIFICATION
    
    @property
    def QWEN_MODEL_CLASSIFICATION(self):
        """Model for classification tasks"""
        return self._get_cached_value('QWEN_MODEL_CLASSIFICATION', 'qwen-plus-latest')
    
    @property
    def QWEN_MODEL_GENERATION(self):
        """Model for generation tasks (higher quality)"""
        return self._get_cached_value('QWEN_MODEL_GENERATION', 'qwen-plus-latest')
    
    # ============================================================================
    # DASHSCOPE MULTI-LLM SUPPORT
    # ============================================================================
    
    @property
    def DASHSCOPE_API_URL(self):
        """Dashscope API URL for all supported models"""
        return self._get_cached_value('DASHSCOPE_API_URL', 'https://dashscope.aliyuncs.com/api/v1/')
    
    @property
    def DEEPSEEK_MODEL(self):
        """DeepSeek model name - v3.1 is faster than R1 (no reasoning overhead)"""
        return self._get_cached_value('DEEPSEEK_MODEL', 'deepseek-v3.1')
    
    @property
    def KIMI_MODEL(self):
        """Kimi model name (Moonshot AI)"""
        return self._get_cached_value('KIMI_MODEL', 'Moonshot-Kimi-K2-Instruct')
    
    # ============================================================================
    # TENCENT HUNYUAN SUPPORT
    # ============================================================================
    
    @property
    def HUNYUAN_API_KEY(self):
        """Tencent Hunyuan API Secret Key"""
        return self._get_cached_value('HUNYUAN_API_KEY', '')
    
    @property
    def HUNYUAN_SECRET_ID(self):
        """Tencent Hunyuan API Secret ID"""
        return self._get_cached_value('HUNYUAN_SECRET_ID', '')
    
    @property
    def HUNYUAN_API_URL(self):
        """Tencent Hunyuan API URL"""
        return self._get_cached_value('HUNYUAN_API_URL', 'https://hunyuan.tencentcloudapi.com')
    
    @property
    def HUNYUAN_MODEL(self):
        """Hunyuan model name"""
        return self._get_cached_value('HUNYUAN_MODEL', 'hunyuan-turbo')
    
    # ============================================================================
    # VOLCENGINE DOUBAO SUPPORT
    # ============================================================================
    
    @property
    def ARK_API_KEY(self):
        """Volcengine ARK API Key"""
        return self._get_cached_value('ARK_API_KEY', '')
    
    @property
    def ARK_BASE_URL(self):
        """Volcengine ARK API Base URL"""
        return self._get_cached_value('ARK_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')
    
    @property
    def ARK_QWEN_ENDPOINT(self):
        """Volcengine ARK Qwen endpoint ID (higher RPM than direct model name)"""
        return self._get_cached_value('ARK_QWEN_ENDPOINT', 'ep-20250101000000-dummy')
    
    @property
    def ARK_DEEPSEEK_ENDPOINT(self):
        """Volcengine ARK DeepSeek endpoint ID (higher RPM than direct model name)"""
        return self._get_cached_value('ARK_DEEPSEEK_ENDPOINT', 'ep-20250101000000-dummy')
    
    @property
    def ARK_KIMI_ENDPOINT(self):
        """Volcengine ARK Kimi endpoint ID (higher RPM than direct model name)"""
        return self._get_cached_value('ARK_KIMI_ENDPOINT', 'ep-20250101000000-dummy')
    
    @property
    def ARK_DOUBAO_ENDPOINT(self):
        """Volcengine ARK Doubao endpoint ID (higher RPM than direct model name)"""
        return self._get_cached_value('ARK_DOUBAO_ENDPOINT', 'ep-20250101000000-dummy')
    
    @property
    def DOUBAO_MODEL(self):
        """Doubao model name"""
        return self._get_cached_value('DOUBAO_MODEL', 'doubao-1-5-pro-32k-250115')
    
    @property
    def QWEN_TEMPERATURE(self):
        try:
            temp = float(self._get_cached_value('QWEN_TEMPERATURE', '0.7'))
            if not 0.0 <= temp <= 1.0:
                logger.warning(f"Temperature {temp} out of range [0.0, 1.0], using 0.7")
                return 0.7
            return temp
        except (ValueError, TypeError):
            logger.warning("Invalid temperature value, using 0.7")
            return 0.7
    
    @property
    def LLM_TEMPERATURE(self):
        """Unified temperature for all diagram generation agents (structured output)."""
        try:
            temp = float(self._get_cached_value('LLM_TEMPERATURE', '0.5'))
            if not 0.0 <= temp <= 2.0:
                logger.warning(f"Temperature {temp} out of range [0.0, 2.0], using 0.5")
                return 0.5
            return temp
        except (ValueError, TypeError):
            logger.warning("Invalid LLM_TEMPERATURE value, using 0.5")
            return 0.5
    @property
    def QWEN_MAX_TOKENS(self):
        """Unified max tokens setting for all LLM calls."""
        return 3000
    @property
    def QWEN_TIMEOUT(self):
        try:
            val = int(self._get_cached_value('QWEN_TIMEOUT', '40'))
            if val < 5 or val > 120:
                logger.warning(f"QWEN_TIMEOUT {val} out of range, using 40")
                return 40
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid QWEN_TIMEOUT value, using 40")
            return 40






    # ============================================================================
    # DASHSCOPE RATE LIMITING (For multi-LLM parallel calls)
    # ============================================================================

    @property
    def DASHSCOPE_QPM_LIMIT(self):
        """
        Dashscope Queries Per Minute limit.
        
        Default: 13,500 (90% of official 15,000 RPM limit for qwen-plus/deepseek-v3.1).
        Official limits:
        - qwen-plus: 15,000 RPM
        - qwen-plus-latest: 15,000 RPM
        - deepseek-v3.1/v3.2/r1: 15,000 RPM
        - Moonshot-Kimi-K2-Instruct: 60 RPM (very low, use separate limit)
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

    # ============================================================================
    # VOLCENGINE ARK RATE LIMITING
    # ============================================================================

    @property
    def ARK_QPM_LIMIT(self):
        """
        Volcengine ARK Queries Per Minute limit.
        
        Default: 4,500 (90% of official 5,000 RPM limit).
        Official limits:
        - ark-kimi: 5,000 RPM, 500,000 TPM
        - ark-doubao: ~30,000 RPM (very high)
        - ark-deepseek (v3.2): 15,000 RPM, 1,500,000 TPM
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

    # ============================================================================
    # LOAD BALANCING CONFIGURATION
    # ============================================================================

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
        This property is kept for backward compatibility but is not used.
        The shared Dashscope rate limiter handles both Qwen and DeepSeek Dashscope routes together.
        
        Default: 13,500 (90% of official 15,000 RPM limit).
        Official limits:
        - deepseek-v3.1: 15,000 RPM, 1,200,000 TPM
        - deepseek-v3.2: 15,000 RPM, 1,500,000 TPM
        - deepseek-r1: 15,000 RPM, 1,200,000 TPM
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
        This property is kept for backward compatibility but is not used.
        The shared Dashscope rate limiter handles both Qwen and DeepSeek Dashscope routes together.
        
        Default: 500
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
        Official limit for ark-deepseek (v3.2 endpoint): 15,000 RPM, 1,500,000 TPM.
        Note: Volcengine endpoint has same limits as Dashscope route for DeepSeek v3.2.
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
        Official limit for ark-kimi endpoint: 5,000 RPM, 500,000 TPM.
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
        Official limit for ark-doubao endpoint: 30,000 RPM, 5,000,000 TPM.
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
            logger.warning(f"Invalid LOAD_BALANCING_WEIGHTS format: {weights_str}, using default 50/50")
            weights = {'dashscope': 50, 'volcengine': 50}
        
        # Ensure both providers are present
        if 'dashscope' not in weights:
            weights['dashscope'] = 50
        if 'volcengine' not in weights:
            weights['volcengine'] = 50
        
        # Validate weights are in valid range (0-100)
        for provider in ['dashscope', 'volcengine']:
            if provider in weights:
                weights[provider] = max(0, min(100, weights[provider]))
        
        # Normalize weights to sum to 100 for proper probability distribution
        total = weights.get('dashscope', 0) + weights.get('volcengine', 0)
        if total > 0:
            # Preserve integer values while normalizing
            dashscope_weight = weights.get('dashscope', 0)
            weights['dashscope'] = int(round(dashscope_weight * 100 / total))
            weights['volcengine'] = 100 - weights['dashscope']  # Ensure they sum to exactly 100
        else:
            # If both are 0, default to 50/50
            logger.warning("LOAD_BALANCING_WEIGHTS sum to 0, using default 50/50")
            weights = {'dashscope': 50, 'volcengine': 50}
        
        return weights

    # ============================================================================
    # SMS RATE LIMITING (For Tencent Cloud SMS API)
    # ============================================================================

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

    # ============================================================================
    # PUBLIC DASHBOARD CONFIGURATION
    # ============================================================================

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
        """Map data cache TTL in seconds (default: 20) - reasonable TTL for map updates"""
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

    @property
    def HOST(self):
        """FastAPI application host address."""
        return self._get_cached_value('HOST', '0.0.0.0')
    
    @property
    def PORT(self):
        """FastAPI application port number."""
        try:
            val = int(self._get_cached_value('PORT', '9527'))
            if not (1 <= val <= 65535):
                logger.warning(f"PORT {val} out of range, using 9527")
                return 9527
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid PORT value, using 9527")
            return 9527
    
    @property
    def SERVER_URL(self):
        """Get the server URL for static file loading."""
        host = self.HOST
        port = self.PORT
        
        # For external access, we need the actual server IP, not localhost
        # Check if we have an explicit external host configured
        try:
            # Check if EXTERNAL_HOST is set in environment
            external_host = os.environ.get('EXTERNAL_HOST')
            if external_host:
                host = external_host
                # Only log from main worker
                if os.getenv('UVICORN_WORKER_ID') is None or os.getenv('UVICORN_WORKER_ID') == '0':
                    logger.info(f"Using EXTERNAL_HOST from environment: {external_host}")
            else:
                # Fallback to LAN IP if EXTERNAL_HOST not set
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                lan_ip = s.getsockname()[0]
                s.close()
                host = lan_ip
                logger.warning(f"EXTERNAL_HOST not set, using LAN IP: {lan_ip}")
        except Exception as e:
            # If we can't determine IP, we need to fail explicitly
            # This prevents external clients from getting localhost URLs
            logger.error(f"Failed to determine server IP address for external access: {e}")
            logger.error("Please set EXTERNAL_HOST environment variable with your server's public IP")
            raise RuntimeError(
                "Cannot determine server IP address for external access. "
                "Please set EXTERNAL_HOST environment variable with your server's public IP address."
            )
        
        return f"http://{host}:{port}"
    
    @property
    def DEBUG(self):
        """FastAPI debug mode setting."""
        return self._get_cached_value('DEBUG', 'False').lower() == 'true'
    
    @property
    def LOG_LEVEL(self):
        """Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)."""
        level = self._get_cached_value('LOG_LEVEL', 'INFO').upper()
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if level not in valid_levels:
            logger.warning(f"Invalid LOG_LEVEL '{level}', using INFO")
            return 'INFO'
        return level
    
    @property
    def VERBOSE_LOGGING(self):
        """Enable verbose logging for debugging (logs all user interactions)."""
        return self._get_cached_value('VERBOSE_LOGGING', 'False').lower() == 'true'
    
    # ============================================================================
    # FEATURE FLAGS (Development/Testing)
    # ============================================================================
    
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
    
    # ============================================================================
    # AI ASSISTANT BRANDING
    # ============================================================================
    
    @property
    def AI_ASSISTANT_NAME(self):
        """AI Assistant display name (appears in toolbar button and panel header)."""
        return self._get_cached_value('AI_ASSISTANT_NAME', 'MindMate AI')
    
    # ============================================================================
    # GRAPH LANGUAGE AND CONTENT SETTINGS
    # ============================================================================
    
    @property
    def DEFAULT_LANGUAGE(self):
        """Default UI language (en/zh/az)."""
        lang = self._get_cached_value('DEFAULT_LANGUAGE', 'zh').lower()
        if lang not in ['en', 'zh', 'az']:
            logger.warning(f"Invalid DEFAULT_LANGUAGE '{lang}', using 'zh'")
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
    
    # ============================================================================
    # D3.js VISUALIZATION CONFIGURATION
    # ============================================================================
    
    # Font size settings
    @property
    def TOPIC_FONT_SIZE(self):
        """Font size for topic nodes in pixels."""
        try:
            val = int(self._get_cached_value('TOPIC_FONT_SIZE', '18'))
            if val <= 0:
                logger.warning(f"TOPIC_FONT_SIZE {val} out of range, using 18")
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
                logger.warning(f"CHAR_FONT_SIZE {val} out of range, using 14")
                return 14
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid CHAR_FONT_SIZE value, using 14")
            return 14
    
    # D3.js rendering dimensions
    @property
    def D3_BASE_WIDTH(self):
        """Base width for D3.js visualizations in pixels."""
        try:
            val = int(self._get_cached_value('D3_BASE_WIDTH', '700'))
            if val <= 0:
                logger.warning(f"D3_BASE_WIDTH {val} out of range, using 700")
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
                logger.warning(f"D3_BASE_HEIGHT {val} out of range, using 500")
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
                logger.warning(f"D3_PADDING {val} out of range, using 40")
                return 40
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid D3_PADDING value, using 40")
            return 40
    
    # ============================================================================
    # D3.js THEME COLOR CONFIGURATION
    # ============================================================================
    
    # Topic node colors
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
    
    # Similarity node colors
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
    
    # Difference node colors
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
    
    # ============================================================================
    # CONFIGURATION VALIDATION METHODS
    # ============================================================================
    
    def validate_qwen_config(self) -> bool:
        """
        Validate Qwen API configuration.
        
        Returns:
            bool: True if Qwen configuration is valid, False otherwise
        """
        if not self.QWEN_API_KEY:
            return False
        
        # Validate API URL format
        if not self.QWEN_API_URL.startswith(('http://', 'https://')):
            return False
        
        # Validate numeric values
        try:
            if not (0 <= self.QWEN_TEMPERATURE <= 1):
                return False
            if self.QWEN_MAX_TOKENS <= 0:
                return False
            if self.QWEN_TIMEOUT <= 0:
                return False
        except (ValueError, TypeError):
            return False
        
        return True
    

    
    def validate_numeric_config(self) -> bool:
        """
        Validate all numeric configuration values.
        
        Returns:
            bool: True if all numeric values are valid, False otherwise
        """
        try:
            # Validate port number
            if not (1 <= self.PORT <= 65535):
                return False
            
            # Validate font sizes
            if self.TOPIC_FONT_SIZE <= 0 or self.CHAR_FONT_SIZE <= 0:
                return False
            
            # Validate D3.js dimensions
            if (self.D3_BASE_WIDTH <= 0 or self.D3_BASE_HEIGHT <= 0 or 
                self.D3_PADDING < 0):
                return False
            
            # Validate timeouts and token limits
            if (self.QWEN_TIMEOUT <= 0 or self.QWEN_MAX_TOKENS <= 0):
                return False
            
            return True
        except (ValueError, TypeError):
            return False
    
    # ============================================================================
    # CONFIGURATION SUMMARY AND DISPLAY
    # ============================================================================
    
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
        logger.info(f"   Version: {self.VERSION}")
        logger.info(f"   FastAPI: {self.HOST}:{self.PORT} (Debug: {self.DEBUG})")
        logger.info(f"   Qwen: {self.QWEN_API_URL}")
        logger.info(f"     - Classification: {self.QWEN_MODEL_CLASSIFICATION}")
        logger.info(f"     - Generation: {self.QWEN_MODEL_GENERATION}")
        

        
        logger.info(f"   Language: {self.GRAPH_LANGUAGE}")
        logger.info(f"   Theme: {self.D3_TOPIC_FILL} / {self.D3_SIM_FILL} / {self.D3_DIFF_FILL}")
        logger.info(f"   Dimensions: {self.D3_BASE_WIDTH}x{self.D3_BASE_HEIGHT}px")
    
    # ============================================================================
    # API REQUEST FORMATTING METHODS
    # ============================================================================
    
    def get_qwen_headers(self) -> dict:
        """
        Get headers for Qwen API requests.
        
        Returns:
            dict: Headers dictionary for Qwen API requests
        """
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.QWEN_API_KEY}'
        }
    
    def get_qwen_data(self, prompt: str, model: str = None) -> dict:
        """
        Get request data for Qwen API calls.
        
        Args:
            prompt (str): The prompt to send to Qwen
            model (str): Model to use (None for default classification model)
            
        Returns:
            dict: Request data dictionary for Qwen API
            
        Note:
            Qwen3 models require enable_thinking: False when not using streaming
            to avoid API errors. This is automatically included in the payload.
        """
        if model is None:
            model = self.QWEN_MODEL_CLASSIFICATION
        
        return {
            'model': model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': self.QWEN_TEMPERATURE,
            'max_tokens': self.QWEN_MAX_TOKENS,
            # Qwen3 models require enable_thinking: False when not using streaming
            'extra_body': {'enable_thinking': False}
        }
    
    def get_qwen_classification_data(self, prompt: str) -> dict:
        """Get request data for Qwen classification tasks"""
        return self.get_qwen_data(prompt, self.QWEN_MODEL_CLASSIFICATION)
    
    def get_qwen_generation_data(self, prompt: str) -> dict:
        """Get request data for Qwen generation tasks (high quality)"""
        return self.get_qwen_data(prompt, self.QWEN_MODEL_GENERATION)
    
    def get_llm_data(self, prompt: str, model: str) -> dict:
        """
        Get request data for any LLM model via Dashscope.
        
        Args:
            prompt (str): The prompt to send
            model (str): Model identifier ('qwen', 'deepseek', 'kimi', 'chatglm')
            
        Returns:
            dict: Request data dictionary for Dashscope API
            
        Note:
            Always includes enable_thinking: False for lightweight application
        """
        # Map model identifiers to actual model names
        model_map = {
            'qwen': self.QWEN_MODEL_GENERATION,
            'deepseek': self.DEEPSEEK_MODEL,
            'kimi': self.KIMI_MODEL,
            'hunyuan': self.HUNYUAN_MODEL
        }
        
        model_name = model_map.get(model, self.QWEN_MODEL_GENERATION)
        
        return {
            'model': model_name,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': self.QWEN_TEMPERATURE,
            'max_tokens': self.QWEN_MAX_TOKENS,
            # Always disable thinking for lightweight application
            'extra_body': {'enable_thinking': False}
        }
    
    def prepare_llm_messages(self, system_prompt: str, user_prompt: str, 
                            model: str = 'qwen') -> list:
        """
        Centralized message preparation for all LLM clients.
        
        This allows future modifications like:
        - Adding common system instructions
        - Formatting adjustments
        - Model-specific message tweaks
        
        Args:
            system_prompt: The system/instruction prompt
            user_prompt: The user's input prompt
            model: Model identifier ('qwen', 'deepseek', 'kimi', 'hunyuan')
            
        Returns:
            list: Formatted messages array ready for chat_completion()
            
        Example:
            >>> messages = config.prepare_llm_messages(
            ...     "You are a helpful assistant",
            ...     "Hello!",
            ...     model='hunyuan'
            ... )
            >>> # Returns: [{'role': 'system', 'content': '...'}, ...]
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Future: Add model-specific tweaks here
        # if model == 'hunyuan':
        #     messages[0]['content'] += "\n请用简洁的中文回答。"
        
        return messages
    
    # ============================================================================
    # D3.js THEME AND DIMENSION HELPERS
    # ============================================================================
    
    # Removed get_d3_theme() - themes are now handled by style-manager.js
    
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
    
    # ============================================================================
    # QWEN OMNI REALTIME (VOICE AGENT)
    # ============================================================================
    
    @property
    def QWEN_OMNI_MODEL(self) -> str:
        """Qwen Omni model name"""
        return self._get_cached_value('QWEN_OMNI_MODEL', 'qwen3-omni-flash-realtime-2025-12-01')
    
    @property
    def QWEN_OMNI_VOICE(self) -> str:
        """Qwen Omni voice name"""
        return self._get_cached_value('QWEN_OMNI_VOICE', 'Cherry')
    
    # ============================================================================
    # KNOWLEDGE SPACE CONFIGURATION
    # ============================================================================
    
    @property
    def QDRANT_COLLECTION_PREFIX(self) -> str:
        """Qdrant collection name prefix"""
        return self._get_cached_value('QDRANT_COLLECTION_PREFIX', 'user_')
    
    @property
    def QDRANT_COMPRESSION(self) -> str:
        """Qdrant compression method (SQ8, IVF_SQ8, or None for no compression)"""
        return self._get_cached_value('QDRANT_COMPRESSION', 'SQ8')
    
    @property
    def DASHSCOPE_EMBEDDING_MODEL(self) -> str:
        """DashScope embedding model (text-embedding-v4 recommended)"""
        return self._get_cached_value('DASHSCOPE_EMBEDDING_MODEL', 'text-embedding-v4')
    
    @property
    def EMBEDDING_DIMENSIONS(self) -> Optional[int]:
        """
        Custom embedding dimensions (for v3, v4). Options: 64, 128, 256, 512, 768, 1024, 1536, 2048
        Default: 768 for optimal compression ratio while maintaining quality
        """
        val = self._get_cached_value('EMBEDDING_DIMENSIONS')
        if val:
            try:
                dim = int(val)
                valid_dims = [64, 128, 256, 512, 768, 1024, 1536, 2048]
                if dim in valid_dims:
                    return dim
                else:
                    logger.warning(f"[Config] Invalid EMBEDDING_DIMENSIONS {dim}, must be one of {valid_dims}")
            except (ValueError, TypeError):
                logger.warning(f"[Config] Invalid EMBEDDING_DIMENSIONS value: {val}")
        # Default to 768 for optimal compression (50% storage reduction vs 1536, maintains quality)
        return 768
    
    @property
    def EMBEDDING_OUTPUT_TYPE(self) -> str:
        """Embedding output type: 'dense', 'sparse', or 'dense&sparse' (for v3, v4)"""
        val = self._get_cached_value('EMBEDDING_OUTPUT_TYPE', 'dense')
        if val not in ['dense', 'sparse', 'dense&sparse']:
            logger.warning(f"[Config] Invalid EMBEDDING_OUTPUT_TYPE {val}, using 'dense'")
            return 'dense'
        return val
    
    @property
    def DASHSCOPE_RERANK_MODEL(self) -> str:
        """DashScope rerank model (qwen3-rerank recommended: cheaper, 100+ languages, instruct param)"""
        return self._get_cached_value('DASHSCOPE_RERANK_MODEL', 'qwen3-rerank')
    
    @property
    def EMBEDDING_BATCH_SIZE(self) -> int:
        """Batch size for embedding API calls"""
        return int(self._get_cached_value('EMBEDDING_BATCH_SIZE', '50'))
    
    @property
    def DEFAULT_RETRIEVAL_METHOD(self) -> str:
        """Default retrieval method (semantic, keyword, hybrid)"""
        return self._get_cached_value('DEFAULT_RETRIEVAL_METHOD', 'hybrid')
    
    @property
    def HYBRID_VECTOR_WEIGHT(self) -> float:
        """Weight for vector search in hybrid search"""
        return float(self._get_cached_value('HYBRID_VECTOR_WEIGHT', '0.5'))
    
    @property
    def HYBRID_KEYWORD_WEIGHT(self) -> float:
        """Weight for keyword search in hybrid search"""
        return float(self._get_cached_value('HYBRID_KEYWORD_WEIGHT', '0.5'))
    
    @property
    def USE_RERANK_MODEL(self) -> bool:
        """Use rerank model vs weighted scores (deprecated: use RERANKING_MODE instead)"""
        return self._get_cached_value('USE_RERANK_MODEL', 'true').lower() == 'true'
    
    @property
    def RERANKING_MODE(self) -> str:
        """Reranking mode: 'reranking_model', 'weighted_score', or 'none'"""
        return self._get_cached_value('RERANKING_MODE', 'reranking_model')
    
    # ============================================================================
    # KNOWLEDGE BASE RATE LIMITING
    # ============================================================================
    
    @property
    def KB_RETRIEVAL_RPM(self) -> int:
        """Knowledge base retrieval requests per minute per user"""
        try:
            return int(self._get_cached_value('KB_RETRIEVAL_RPM', '60'))
        except (ValueError, TypeError):
            return 60
    
    @property
    def KB_EMBEDDING_RPM(self) -> int:
        """Knowledge base embedding generation per minute per user"""
        try:
            return int(self._get_cached_value('KB_EMBEDDING_RPM', '100'))
        except (ValueError, TypeError):
            return 100
    
    @property
    def KB_UPLOAD_PER_HOUR(self) -> int:
        """Knowledge base document uploads per hour per user"""
        try:
            return int(self._get_cached_value('KB_UPLOAD_PER_HOUR', '10'))
        except (ValueError, TypeError):
            return 10
    
    @property
    def DASHSCOPE_MULTIMODAL_MODEL(self) -> str:
        """DashScope multimodal embedding model (for image/video embeddings)"""
        return self._get_cached_value('DASHSCOPE_MULTIMODAL_MODEL', 'tongyi-embedding-vision-plus')
    
    
    @property
    def RERANK_SCORE_THRESHOLD(self) -> float:
        """Minimum score threshold for reranked results"""
        return float(self._get_cached_value('RERANK_SCORE_THRESHOLD', '0.5'))
    
    @property
    def RETRIEVAL_PARALLEL_WORKERS(self) -> int:
        """Number of parallel workers for hybrid search"""
        return int(self._get_cached_value('RETRIEVAL_PARALLEL_WORKERS', '2'))
    
    @property
    def CHUNK_SIZE(self) -> int:
        """Tokens per chunk"""
        return int(self._get_cached_value('CHUNK_SIZE', '500'))
    
    @property
    def CHUNK_OVERLAP(self) -> int:
        """Overlap tokens between chunks"""
        return int(self._get_cached_value('CHUNK_OVERLAP', '50'))
    
    @property
    def MAX_DOCUMENTS_PER_USER(self) -> int:
        """Maximum documents per user"""
        return int(self._get_cached_value('MAX_DOCUMENTS_PER_USER', '5'))
    
    @property
    def MAX_FILE_SIZE(self) -> int:
        """Maximum file size in bytes (10MB)"""
        return int(self._get_cached_value('MAX_FILE_SIZE', '10485760'))
    
    @property
    def MAX_STORAGE_PER_USER(self) -> int:
        """Maximum storage per user in bytes (50MB)"""
        return int(self._get_cached_value('MAX_STORAGE_PER_USER', '52428800'))
    
    @property
    def MAX_CHUNKS_PER_USER(self) -> int:
        """Maximum chunks per user"""
        return int(self._get_cached_value('MAX_CHUNKS_PER_USER', '1000'))
    
    @property
    def KNOWLEDGE_STORAGE_DIR(self) -> str:
        """Directory for storing knowledge documents"""
        return self._get_cached_value('KNOWLEDGE_STORAGE_DIR', './storage/knowledge_documents')
    
    @property
    def QWEN_OMNI_VAD_THRESHOLD(self) -> float:
        """Qwen Omni VAD threshold"""
        return float(self._get_cached_value('QWEN_OMNI_VAD_THRESHOLD', '0.5'))
    
    @property
    def QWEN_OMNI_VAD_SILENCE_MS(self) -> int:
        """Qwen Omni VAD silence duration (ms) - time to wait after user stops speaking"""
        return int(self._get_cached_value('QWEN_OMNI_VAD_SILENCE_MS', '1200'))
    
    @property
    def QWEN_OMNI_VAD_PREFIX_MS(self) -> int:
        """Qwen Omni VAD prefix padding (ms)"""
        return int(self._get_cached_value('QWEN_OMNI_VAD_PREFIX_MS', '300'))
    
    @property
    def QWEN_OMNI_SMOOTH_OUTPUT(self) -> bool:
        """Qwen Omni smooth output (flash models only)"""
        return self._get_cached_value('QWEN_OMNI_SMOOTH_OUTPUT', 'true').lower() == 'true'
    
    @property
    def QWEN_OMNI_INPUT_FORMAT(self) -> str:
        """Qwen Omni input audio format"""
        return self._get_cached_value('QWEN_OMNI_INPUT_FORMAT', 'pcm16')
    
    @property
    def QWEN_OMNI_OUTPUT_FORMAT(self) -> str:
        """Qwen Omni output audio format"""
        return self._get_cached_value('QWEN_OMNI_OUTPUT_FORMAT', 'pcm24')
    
    @property
    def QWEN_OMNI_TRANSCRIPTION_MODEL(self) -> str:
        """Qwen Omni transcription model"""
        return self._get_cached_value('QWEN_OMNI_TRANSCRIPTION_MODEL', 'gummy-realtime-v1')

# Create global configuration instance
config = Config() 