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
- D3.js visualization customization options

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
from config.features_config import FeaturesConfigMixin
from config.knowledge_config import KnowledgeConfigMixin
from config.llm_config import LLMConfigMixin
from config.rate_limiting import RateLimitingConfigMixin
from config.visualization_config import VisualizationConfigMixin
from utils.env_utils import ensure_utf8_env_file

logger = logging.getLogger(__name__)

# Ensure .env file is UTF-8 encoded before loading
ensure_utf8_env_file()
load_dotenv()  # Load environment variables from .env file


class Config(
    BaseConfig,
    LLMConfigMixin,
    RateLimitingConfigMixin,
    KnowledgeConfigMixin,
    VisualizationConfigMixin,
    FeaturesConfigMixin,
):
    """
    Centralized configuration management for MindGraph application.

    Combines all configuration mixins to provide a unified interface
    for accessing configuration values throughout the application.
    """

    def print_config_summary(self) -> None:
        """Log application, LLM, language, and visualization settings."""
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


# Create global configuration instance
config = Config()
