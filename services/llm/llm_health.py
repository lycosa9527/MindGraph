"""
LLM Health Checker
==================

Health check functionality for LLM models.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, List, Any
import asyncio
import logging
import socket
import time

from clients.omni_client import OmniRealtimeClient, TurnDetectionMode
from services.infrastructure.http.error_handler import (
    LLMServiceError,
    LLMRateLimitError,
    LLMQuotaExhaustedError
)

logger = logging.getLogger(__name__)


class LLMHealthChecker:
    """Health checker for LLM models."""

    def __init__(self, llm_service: Any):
        """
        Initialize health checker.

        Args:
            llm_service: LLMService instance for health checks
        """
        self.llm_service = llm_service

    def get_available_models(self) -> List[str]:
        """
        Get list of all available models.

        When load balancing is enabled, filters out physical models (ark-*)
        to avoid redundant health checks and duplicate entries.

        Returns:
            List of available model names
        """
        all_models = self.llm_service.client_manager.get_available_models()

        # Filter out physical models when load balancing is enabled
        # This prevents health_check() from checking both 'deepseek' and 'ark-deepseek'
        if (self.llm_service.load_balancer and
                self.llm_service.load_balancer.enabled):
            logical_models = [
                m for m in all_models
                if not m.startswith('ark-')
            ]
            return logical_models

        return all_models

    def _categorize_error(self, e: Exception) -> Dict[str, Any]:
        """
        Categorize errors for better health reporting.

        Avoids exposing sensitive details in error messages.

        Args:
            e: Exception that occurred

        Returns:
            Dict with status, error message, and error type
        """
        # Don't expose sensitive details - use generic messages
        # Check for DNS resolution errors (gaierror)
        if isinstance(e, socket.gaierror):
            return {
                'status': 'unhealthy',
                'error': 'DNS resolution failed',
                'error_type': 'dns_error'
            }
        if isinstance(e, (ConnectionError, TimeoutError)):
            return {
                'status': 'unhealthy',
                'error': 'Connection failed',
                'error_type': 'connection_error'
            }
        if isinstance(e, asyncio.TimeoutError):
            return {
                'status': 'unhealthy',
                'error': 'Request timeout',
                'error_type': 'timeout'
            }
        if isinstance(e, LLMServiceError):
            # Use error handler's categorization
            if isinstance(e, LLMRateLimitError):
                return {
                    'status': 'unhealthy',
                    'error': 'Rate limit exceeded',
                    'error_type': 'rate_limit'
                }
            if isinstance(e, LLMQuotaExhaustedError):
                return {
                    'status': 'unhealthy',
                    'error': 'Quota exhausted',
                    'error_type': 'quota_exhausted'
                }
            return {
                'status': 'unhealthy',
                'error': 'Service unavailable',
                'error_type': 'service_error'
            }

        # Generic error - don't expose details
        return {
            'status': 'unhealthy',
            'error': 'Service unavailable',
            'error_type': 'unknown'
        }

    async def _check_omni_health(self, model: str) -> Dict[str, Any]:
        """
        Check health of Omni model via WebSocket.

        Args:
            model: Model name ('omni')

        Returns:
            Health status dict
        """
        try:
            start = time.time()
            omni_client = self.llm_service.client_manager.get_client('omni')

            # Test WebSocket connection by attempting to create and close a session
            async def test_omni_connection():
                native_client = None
                try:
                    native_client = OmniRealtimeClient(
                        api_key=omni_client.api_key,
                        model=omni_client.model,
                        turn_detection_mode=TurnDetectionMode.SERVER_VAD
                    )
                    await native_client.connect()
                    # Connection successful, close it
                    await native_client.close()
                    return True
                except Exception as e:
                    logger.debug("Omni WebSocket health check failed: %s", e)
                    if native_client:
                        try:
                            await native_client.close()
                        except Exception:
                            pass
                    raise

            await asyncio.wait_for(test_omni_connection(), timeout=5.0)
            latency = time.time() - start
            return {
                'status': 'healthy',
                'latency': round(latency, 2),
                'note': 'WebSocket-based real-time voice service'
            }
        except Exception as e:
            logger.warning("Health check failed for %s: %s", model, e)
            result = self._categorize_error(e)
            result['note'] = 'WebSocket-based real-time voice service'
            return result

    async def _check_model_health(self, model: str) -> Dict[str, Any]:
        """
        Check health of a single HTTP-based model.

        Args:
            model: Model name

        Returns:
            Health status dict
        """
        try:
            start = time.time()
            await self.llm_service.chat(
                prompt="Test",
                model=model,
                max_tokens=10,
                timeout=5.0
            )
            latency = time.time() - start
            return {
                'status': 'healthy',
                'latency': round(latency, 2)
            }
        except Exception as e:
            logger.warning("Health check failed for %s: %s", model, e)
            return self._categorize_error(e)

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of all LLM clients in parallel for better performance.

        Note: Omni model uses WebSocket for real-time voice and is checked separately.

        Returns:
            Status dict for each model with available_models list
        """
        available_models = self.get_available_models()
        results: Dict[str, Any] = {'available_models': available_models}

        # Create health check tasks for all models (parallel execution)
        tasks = []
        for model in available_models:
            if model == 'omni':
                tasks.append(self._check_omni_health(model))
            else:
                tasks.append(self._check_model_health(model))

        # Execute all health checks in parallel
        health_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for model, result in zip(available_models, health_results):
            if isinstance(result, Exception):
                logger.error(
                    "Health check exception for %s: %s",
                    model, result, exc_info=True
                )
                results[model] = self._categorize_error(result)
            else:
                results[model] = result

        return results
