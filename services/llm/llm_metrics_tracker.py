"""
LLM Metrics Tracker
==================

Centralizes token tracking and performance metrics recording.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Optional, Any
import logging

from services.monitoring.performance_tracker import performance_tracker
from services.redis.redis_token_buffer import get_token_tracker

logger = logging.getLogger(__name__)


class LLMMetricsTracker:
    """Tracks token usage and performance metrics for LLM requests."""

    def __init__(self):
        """Initialize metrics tracker."""
        self.performance_tracker = performance_tracker

    async def track_token_usage(
        self,
        model: str,
        usage_data: Dict[str, Any],
        metadata: Dict[str, Any],
        success: bool,
        duration: float
    ) -> None:
        """
        Track token usage for a request.

        Args:
            model: Model alias (logical model name)
            usage_data: Usage data dict with token counts
            metadata: Metadata dict with tracking parameters:
                - user_id: Optional[int]
                - organization_id: Optional[int]
                - api_key_id: Optional[int]
                - request_type: str
                - diagram_type: Optional[str]
                - endpoint_path: Optional[str]
                - session_id: Optional[str]
                - conversation_id: Optional[str]
            success: Whether request succeeded
            duration: Request duration in seconds
        """
        if not usage_data:
            return

        try:
            # Normalize token field names
            # (API uses prompt_tokens/completion_tokens,
            # we use input_tokens/output_tokens)
            input_tokens = (
                usage_data.get('prompt_tokens') or
                usage_data.get('input_tokens') or
                0
            )
            output_tokens = (
                usage_data.get('completion_tokens') or
                usage_data.get('output_tokens') or
                0
            )
            # Use API's total_tokens (authoritative billing value)
            # - may include overhead tokens
            total_tokens = usage_data.get('total_tokens') or None

            token_tracker = get_token_tracker()
            await token_tracker.track_usage(
                model_alias=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                request_type=metadata.get('request_type', 'diagram_generation'),
                diagram_type=metadata.get('diagram_type'),
                user_id=metadata.get('user_id'),
                organization_id=metadata.get('organization_id'),
                api_key_id=metadata.get('api_key_id'),
                session_id=metadata.get('session_id'),
                conversation_id=metadata.get('conversation_id'),
                endpoint_path=metadata.get('endpoint_path'),
                response_time=duration,
                success=success
            )
        except Exception as e:
            logger.debug(
                "[LLMMetricsTracker] Token tracking failed (non-critical): %s",
                e
            )

    def record_performance_metrics(
        self,
        model: str,
        duration: float,
        success: bool,
        error: Optional[str] = None
    ) -> None:
        """
        Record performance metrics for a request.

        Args:
            model: Model name (logical or physical)
            duration: Request duration in seconds
            success: Whether request succeeded
            error: Optional error message if failed
        """
        self.performance_tracker.record_request(
            model=model,
            duration=duration,
            success=success,
            error=error
        )

    def record_provider_metrics(
        self,
        provider: str,
        load_balancer: Any,
        success: bool,
        duration: float,
        error: Optional[str] = None
    ) -> None:
        """
        Record provider metrics for load balancing.

        Args:
            provider: Provider name ('dashscope' or 'volcengine')
            load_balancer: Load balancer instance
            success: Whether request succeeded
            duration: Request duration in seconds
            error: Optional error message if failed
        """
        if load_balancer:
            load_balancer.record_provider_metrics(
                provider=provider,
                success=success,
                duration=duration,
                error=error
            )

    async def track_all(
        self,
        model: str,
        usage_data: Optional[Dict[str, Any]],
        metadata: Dict[str, Any],
        provider: Optional[str],
        load_balancer: Optional[Any],
        success: bool,
        duration: float,
        error: Optional[str] = None
    ) -> None:
        """
        Track all metrics (tokens, performance, provider) in one call.

        Convenience method that calls all tracking methods.

        Args:
            model: Model name (logical)
            usage_data: Optional usage data dict
            metadata: Metadata dict for token tracking
            provider: Optional provider name for load balancing metrics
            load_balancer: Optional load balancer instance
            success: Whether request succeeded
            duration: Request duration in seconds
            error: Optional error message if failed
        """
        # Track token usage
        if usage_data:
            await self.track_token_usage(
                model=model,
                usage_data=usage_data,
                metadata=metadata,
                success=success,
                duration=duration
            )

        # Record performance metrics
        self.record_performance_metrics(
            model=model,
            duration=duration,
            success=success,
            error=error
        )

        # Record provider metrics (if load balancing enabled)
        if provider and load_balancer:
            self.record_provider_metrics(
                provider=provider,
                load_balancer=load_balancer,
                success=success,
                duration=duration,
                error=error
            )
