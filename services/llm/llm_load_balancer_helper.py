"""
LLM Load Balancer Helper
========================

Handles load balancing and provider detection logic.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Tuple, Optional, Any
import logging

logger = logging.getLogger(__name__)


class LLMLoadBalancerHelper:
    """Helper for load balancing and provider detection."""

    @staticmethod
    def apply_load_balancing(
        model: str,
        skip_load_balancing: bool,
        load_balancer: Optional[Any]
    ) -> Tuple[str, Optional[str]]:
        """
        Apply load balancing to map logical model to physical model.

        Args:
            model: Logical model name (e.g., 'deepseek', 'qwen')
            skip_load_balancing: Whether to skip load balancing
            load_balancer: Optional load balancer instance

        Returns:
            Tuple of (actual_model, provider)
            - actual_model: Physical model name after load balancing
            - provider: Provider name ('dashscope' or 'volcengine') or None
        """
        if skip_load_balancing:
            # Model is already a physical model
            actual_model = model
            logger.debug(
                "[LLMLoadBalancerHelper] Skipping load balancing "
                "(already applied): %s",
                model
            )
            # Determine provider from physical model name
            provider = LLMLoadBalancerHelper._get_provider_from_model_name(
                actual_model, load_balancer
            )
            return actual_model, provider

        if load_balancer and load_balancer.enabled:
            actual_model = load_balancer.map_model(model)
            logger.debug(
                "[LLMLoadBalancerHelper] Load balanced: %s → %s",
                model, actual_model
            )
            # Track provider for DeepSeek load balancing metrics
            if model == 'deepseek':
                provider = (
                    'dashscope' if actual_model == 'deepseek' else 'volcengine'
                )
            else:
                provider = LLMLoadBalancerHelper._get_provider_from_model_name(
                    actual_model, load_balancer
                )
            return actual_model, provider

        # No load balancing
        return model, None

    @staticmethod
    def _get_provider_from_model_name(
        actual_model: str,
        load_balancer: Optional[Any]
    ) -> Optional[str]:
        """
        Get provider name from physical model name.

        Args:
            actual_model: Physical model name
            load_balancer: Optional load balancer instance

        Returns:
            Provider name ('dashscope' or 'volcengine') or None
        """
        if actual_model == 'ark-deepseek':
            return 'volcengine'
        if actual_model == 'deepseek':
            return 'dashscope'
        if actual_model.startswith('ark-'):
            return 'volcengine'

        # Try to get from load balancer if available
        if load_balancer and hasattr(load_balancer, 'get_provider_from_model'):
            return load_balancer.get_provider_from_model(actual_model)

        return None
