"""MindGraph Configuration Module.

This module provides centralized configuration management for the MindGraph application.
It handles environment variable loading, validation, and provides a clean interface
for accessing configuration values throughout the application.

Features:
- Dynamic environment variable loading with .env support
- Property-based configuration access for real-time updates
- Comprehensive validation for required and optional settings
- Default values for all configuration options
- Support for Qwen LLM configuration

Environment Variables:
- QWEN_API_KEY: Required for core functionality
- See env.example for complete configuration options

Usage:
    from config.settings import config
    api_key = config.QWEN_API_KEY
    is_valid = config.validate_qwen_config()

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from dotenv import load_dotenv

from config.base_config import BaseConfig
from config.dashscope_endpoint_config import DashScopeEndpointConfigMixin
from config.features_config import FeaturesConfigMixin
from config.knowledge_config import KnowledgeConfigMixin
from config.llm_config import LLMConfigMixin
from config.mind_classroom_config import MindClassroomConfigMixin
from config.t2i_config import T2IConfigMixin
from config.rate_limiting import RateLimitingConfigMixin
from utils.env_utils import ensure_utf8_env_file

logger = logging.getLogger(__name__)

# Ensure .env file is UTF-8 encoded before loading
ensure_utf8_env_file()
load_dotenv()  # Load environment variables from .env file


class Config(
    BaseConfig,
    DashScopeEndpointConfigMixin,
    LLMConfigMixin,
    T2IConfigMixin,
    MindClassroomConfigMixin,
    RateLimitingConfigMixin,
    KnowledgeConfigMixin,
    FeaturesConfigMixin,
):
    """
    Centralized configuration management for MindGraph application.

    Combines all configuration mixins to provide a unified interface
    for accessing configuration values throughout the application.
    """

    def print_config_summary(self) -> None:
        """Log application, LLM, and language settings."""
        logger.info(
            "Configuration: v%s | %s:%s | lang=%s | Qwen classification=%s | Qwen generation=%s",
            self.version,
            self.host,
            self.port,
            self.GRAPH_LANGUAGE,
            self.QWEN_MODEL_CLASSIFICATION,
            self.QWEN_MODEL_GENERATION,
        )
        logger.debug("   Qwen: %s", self.QWEN_API_URL)
        endpoint = self.DASHSCOPE_ENDPOINT_SUMMARY
        logger.debug(
            "   DashScope HTTP: mode=%s region=%s workspace=%s",
            endpoint.get("mode"),
            endpoint.get("region"),
            endpoint.get("workspace_id") or "—",
        )
        logger.debug("     - Realtime WS: %s", endpoint.get("realtime_ws_base"))


# Create global configuration instance
config = Config()
