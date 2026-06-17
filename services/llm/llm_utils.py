"""
LLM Utilities
=============

Utility functions for LLM service.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging
from typing import Any, Optional

from services.infrastructure.http.error_handler import LLMTimeoutError

logger = logging.getLogger(__name__)


class LLMUtils:
    """Utility functions for LLM service."""

    @staticmethod
    def stream_enable_thinking(model: str) -> bool:
        """
        Return whether streaming calls should set the provider's thinking/reasoning mode.

        DashScope Qwen3 is kept off app-wide (latency, structured flows). Kimi streams
        without thinking per existing behavior. Other models (e.g. DeepSeek) may
        still stream reasoning when True.
        """
        ml = (model or "").strip().lower()
        if not ml:
            return False
        if ml == "kimi":
            return False
        if ml == "qwen" or ml.startswith("qwen-"):
            return False
        return True

    @staticmethod
    def get_default_timeout(model: str) -> float:
        """
        Get default timeout for model (in seconds).

        Args:
            model: Model name

        Returns:
            Timeout in seconds
        """
        # Generous timeouts for complex diagrams. Qwen3.6+ generation can exceed 70s
        # on large prompts (matches httpx read timeout on the DashScope client).
        timeouts = {
            "qwen": 120.0,
            "qwen-turbo": 120.0,
            "qwen-plus": 120.0,
            "deepseek": 70.0,
            "ark-deepseek": 70.0,  # Volcengine DeepSeek (Route B)
            "ark-kimi": 70.0,  # Volcengine Kimi (both routes)
            "hunyuan": 70.0,
            "kimi": 70.0,
            "doubao": 70.0,
            "chatglm": 70.0,
        }
        return timeouts.get(model, 120.0)

    @staticmethod
    def format_request_failure(exc: BaseException) -> str:
        """
        Human-readable failure text for logs and LLMServiceError.

        asyncio.TimeoutError has an empty str(); several provider errors may be blank.
        """
        if isinstance(exc, asyncio.TimeoutError):
            return "Request timed out (asyncio.TimeoutError)"
        if isinstance(exc, LLMTimeoutError):
            text = str(exc).strip()
            return text if text else "LLM request timed out"
        text = str(exc).strip()
        if text:
            return text
        return type(exc).__name__

    @staticmethod
    def get_rate_limiter(
        model: str,
        actual_model: str,
        provider: Optional[str],
        rate_limiter: Optional[Any],
        load_balancer_rate_limiter: Optional[Any],
        kimi_rate_limiter: Optional[Any],
        doubao_rate_limiter: Optional[Any],
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
        if model == "deepseek":
            if provider == "volcengine" or actual_model == "ark-deepseek":
                # DeepSeek Volcengine route → use load balancer Volcengine limiter
                if load_balancer_rate_limiter and load_balancer_rate_limiter.enabled:
                    return load_balancer_rate_limiter.get_limiter("volcengine")
            elif provider == "dashscope" or actual_model == "deepseek":
                # DeepSeek Dashscope route → use shared Dashscope limiter
                return rate_limiter

        # For Kimi: use Volcengine endpoint-specific rate limiter
        if model == "kimi" or actual_model == "ark-kimi":
            if kimi_rate_limiter and kimi_rate_limiter.enabled:
                return kimi_rate_limiter

        # For Doubao: use Volcengine endpoint-specific rate limiter
        if model == "doubao" or actual_model == "ark-doubao":
            if doubao_rate_limiter and doubao_rate_limiter.enabled:
                return doubao_rate_limiter

        # For Qwen and other Dashscope models, use shared Dashscope rate limiter
        return rate_limiter


def stream_enable_thinking(model: str) -> bool:
    """Whether streaming should use provider thinking mode; delegates to LLMUtils."""
    return LLMUtils.stream_enable_thinking(model)
