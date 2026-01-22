"""
LLM Utilities
=============

Utility functions for LLM service.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class LLMUtils:
    """Utility functions for LLM service."""

    @staticmethod
    def get_default_timeout(model: str) -> float:
        """
        Get default timeout for model (in seconds).

        Args:
            model: Model name

        Returns:
            Timeout in seconds
        """
        # Generous timeouts for complex diagrams
        timeouts = {
            'qwen': 70.0,
            'qwen-turbo': 70.0,
            'qwen-plus': 70.0,
            'deepseek': 70.0,
            'ark-deepseek': 70.0,  # Volcengine DeepSeek (Route B)
            'ark-kimi': 70.0,      # Volcengine Kimi (both routes)
            'hunyuan': 70.0,
            'kimi': 70.0,
            'doubao': 70.0,
            'chatglm': 70.0
        }
        return timeouts.get(model, 70.0)

    @staticmethod
    def get_rate_limiter(
        model: str,
        actual_model: str,
        provider: Optional[str],
        rate_limiter: Optional[Any],
        load_balancer_rate_limiter: Optional[Any],
        kimi_rate_limiter: Optional[Any],
        doubao_rate_limiter: Optional[Any]
    ) -> Optional[Any]:
        """
        Get the appropriate rate limiter for a model request.

        Args:
            model: Logical model name (e.g., 'deepseek', 'qwen')
            actual_model: Physical model name after load balancing
            provider: Provider name if known ('dashscope' or 'volcengine')
            rate_limiter: Shared Dashscope rate limiter
            load_balancer_rate_limiter: Load balancer rate limiter
            kimi_rate_limiter: Kimi-specific rate limiter
            doubao_rate_limiter: Doubao-specific rate limiter

        Returns:
            Rate limiter instance or None
        """
        # For DeepSeek with load balancing, select appropriate rate limiter
        if model == 'deepseek':
            if provider == 'volcengine' or actual_model == 'ark-deepseek':
                # DeepSeek Volcengine route → use load balancer Volcengine limiter
                if (load_balancer_rate_limiter and
                        load_balancer_rate_limiter.enabled):
                    return load_balancer_rate_limiter.get_limiter('volcengine')
            elif provider == 'dashscope' or actual_model == 'deepseek':
                # DeepSeek Dashscope route → use shared Dashscope limiter
                return rate_limiter

        # For Kimi: use Volcengine endpoint-specific rate limiter
        if model == 'kimi' or actual_model == 'ark-kimi':
            if kimi_rate_limiter and kimi_rate_limiter.enabled:
                return kimi_rate_limiter

        # For Doubao: use Volcengine endpoint-specific rate limiter
        if model == 'doubao' or actual_model == 'ark-doubao':
            if doubao_rate_limiter and doubao_rate_limiter.enabled:
                return doubao_rate_limiter

        # For Qwen and other Dashscope models, use shared Dashscope rate limiter
        return rate_limiter
