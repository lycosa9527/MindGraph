"""
LLM Service Initializer
=======================

Handles service initialization and configuration.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any
import logging

from config.settings import config
from services.infrastructure.utils.load_balancer import initialize_load_balancer
from services.infrastructure.rate_limiting.rate_limiter import (
    initialize_rate_limiter,
    DashscopeRateLimiter,
    LoadBalancerRateLimiter
)

logger = logging.getLogger(__name__)


class LLMServiceInitializer:
    """Handles LLM service initialization."""

    def __init__(self):
        """Initialize the initializer."""
        self.rate_limiter = None
        self.load_balancer = None
        self.load_balancer_rate_limiter = None
        self.kimi_rate_limiter = None
        self.doubao_rate_limiter = None

    def initialize(
        self,
        client_manager: Any,
        prompt_manager: Any
    ) -> Dict[str, Any]:
        """
        Initialize LLM service components.

        Args:
            client_manager: Client manager instance
            prompt_manager: Prompt manager instance

        Returns:
            Dict with initialized components:
            {
                'rate_limiter': ...,
                'load_balancer': ...,
                'load_balancer_rate_limiter': ...,
                'kimi_rate_limiter': ...,
                'doubao_rate_limiter': ...
            }
        """
        logger.info("[LLMServiceInitializer] Initializing...")

        # Initialize client manager
        client_manager.initialize()

        # Initialize prompt manager
        prompt_manager.initialize()

        # Initialize rate limiter for Dashscope platform
        if config.DASHSCOPE_RATE_LIMITING_ENABLED:
            logger.debug(
                "[LLMServiceInitializer] Configuring Dashscope rate limiting"
            )
            logger.debug(
                "[LLMServiceInitializer] QPM=%s, Concurrent=%s",
                config.DASHSCOPE_QPM_LIMIT,
                config.DASHSCOPE_CONCURRENT_LIMIT
            )

            self.rate_limiter = initialize_rate_limiter(
                qpm_limit=config.DASHSCOPE_QPM_LIMIT,
                concurrent_limit=config.DASHSCOPE_CONCURRENT_LIMIT,
                enabled=config.DASHSCOPE_RATE_LIMITING_ENABLED
            )
        else:
            logger.debug(
                "[LLMServiceInitializer] Rate limiting disabled"
            )
            self.rate_limiter = None

        # Initialize load balancer
        if config.LOAD_BALANCING_ENABLED:
            # Initialize load balancer rate limiter if enabled
            # Note: Only Volcengine route is managed here.
            # Dashscope route uses shared rate limiter.
            if config.LOAD_BALANCING_RATE_LIMITING_ENABLED:
                self.load_balancer_rate_limiter = LoadBalancerRateLimiter(
                    volcengine_qpm=config.DEEPSEEK_VOLCENGINE_QPM_LIMIT,
                    volcengine_concurrent=config.DEEPSEEK_VOLCENGINE_CONCURRENT_LIMIT,
                    enabled=True
                )
                logger.info(
                    "[LLMServiceInitializer] Load balancer rate limiting enabled: "
                    "Volcengine(QPM=%s, Concurrent=%s). "
                    "Note: Dashscope route uses shared Dashscope rate limiter.",
                    config.DEEPSEEK_VOLCENGINE_QPM_LIMIT,
                    config.DEEPSEEK_VOLCENGINE_CONCURRENT_LIMIT
                )
            else:
                self.load_balancer_rate_limiter = None
                logger.info(
                    "[LLMServiceInitializer] Load balancer rate limiting disabled"
                )

            self.load_balancer = initialize_load_balancer(
                strategy=config.LOAD_BALANCING_STRATEGY,
                weights=config.LOAD_BALANCING_WEIGHTS,
                enabled=True,
                dashscope_rate_limiter=self.rate_limiter,
                load_balancer_rate_limiter=self.load_balancer_rate_limiter,
                rate_limit_aware=config.LOAD_BALANCING_RATE_LIMITING_ENABLED
            )
            logger.info(
                "[LLMServiceInitializer] Load balancer enabled: "
                "strategy=%s, weights=%s, rate_limit_aware=%s",
                config.LOAD_BALANCING_STRATEGY,
                config.LOAD_BALANCING_WEIGHTS,
                config.LOAD_BALANCING_RATE_LIMITING_ENABLED
            )
        else:
            logger.info(
                "[LLMServiceInitializer] Load balancing disabled"
            )
            self.load_balancer = None
            self.load_balancer_rate_limiter = None

        # Initialize Volcengine endpoint-specific rate limiters
        # Each endpoint has independent limits per Volcengine provider
        if config.DASHSCOPE_RATE_LIMITING_ENABLED:
            # Kimi Volcengine endpoint rate limiter
            self.kimi_rate_limiter = DashscopeRateLimiter(
                qpm_limit=config.KIMI_VOLCENGINE_QPM_LIMIT,
                concurrent_limit=config.KIMI_VOLCENGINE_CONCURRENT_LIMIT,
                enabled=True,
                provider='volcengine',
                endpoint='ark-kimi'
            )
            logger.info(
                "[LLMServiceInitializer] Kimi Volcengine rate limiting enabled: "
                "QPM=%s, Concurrent=%s",
                config.KIMI_VOLCENGINE_QPM_LIMIT,
                config.KIMI_VOLCENGINE_CONCURRENT_LIMIT
            )

            # Doubao Volcengine endpoint rate limiter
            self.doubao_rate_limiter = DashscopeRateLimiter(
                qpm_limit=config.DOUBAO_VOLCENGINE_QPM_LIMIT,
                concurrent_limit=config.DOUBAO_VOLCENGINE_CONCURRENT_LIMIT,
                enabled=True,
                provider='volcengine',
                endpoint='ark-doubao'
            )
            logger.info(
                "[LLMServiceInitializer] Doubao Volcengine rate limiting enabled: "
                "QPM=%s, Concurrent=%s",
                config.DOUBAO_VOLCENGINE_QPM_LIMIT,
                config.DOUBAO_VOLCENGINE_CONCURRENT_LIMIT
            )
        else:
            self.kimi_rate_limiter = None
            self.doubao_rate_limiter = None

        logger.debug("[LLMServiceInitializer] Ready")

        return {
            'rate_limiter': self.rate_limiter,
            'load_balancer': self.load_balancer,
            'load_balancer_rate_limiter': self.load_balancer_rate_limiter,
            'kimi_rate_limiter': self.kimi_rate_limiter,
            'doubao_rate_limiter': self.doubao_rate_limiter
        }
