"""
LLM Multi-Service
=================

Multi-LLM orchestration methods for parallel and progressive generation.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, List, Optional, Any, AsyncGenerator
import asyncio
import logging
import time

from services.infrastructure.monitoring.critical_alert import CriticalAlertService
from services.infrastructure.http.error_handler import LLMServiceError

logger = logging.getLogger(__name__)


class LLMMultiService:
    """Multi-LLM orchestration service."""

    def __init__(self, llm_service: Any):
        """
        Initialize multi-service with reference to main LLM service.

        Args:
            llm_service: LLMService instance for single model calls
        """
        self.llm_service = llm_service

    async def generate_multi(
        self,
        prompt: str,
        models: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        timeout: Optional[float] = None,
        system_message: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Call multiple LLMs in parallel, wait for all to complete.

        Args:
            prompt: Prompt to send to all LLMs
            models: List of model names (default: ['qwen', 'deepseek', 'kimi'])
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            timeout: Per-LLM timeout
            system_message: Optional system message
            **kwargs: Additional parameters

        Returns:
            Dict mapping model names to results
        """
        if models is None:
            models = ['qwen', 'deepseek', 'kimi']

        start_time = time.time()
        logger.debug(
            "[LLMMultiService] generate_multi() - %s models in parallel",
            len(models)
        )

        # Create tasks for all models
        tasks = {}
        for model in models:
            task = asyncio.create_task(
                self._call_single_model_with_timing(
                    model=model,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    system_message=system_message,
                    **kwargs
                )
            )
            tasks[model] = task

        # Wait for all tasks
        results = {}
        for model, task in tasks.items():
            try:
                result = await task
                results[model] = result
            except Exception as e:
                results[model] = {
                    'response': None,
                    'success': False,
                    'error': str(e),
                    'duration': 0.0
                }
                logger.error("[LLMMultiService] %s failed: %s", model, e)

        duration = time.time() - start_time
        successful = sum(1 for r in results.values() if r['success'])
        logger.info(
            "[LLMMultiService] generate_multi() complete: %s/%s succeeded in %.2fs",
            successful, len(models), duration
        )

        return results

    async def generate_progressive(
        self,
        prompt: str,
        models: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        timeout: Optional[float] = None,
        system_message: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Call multiple LLMs in parallel, yield results as each completes.

        Args:
            prompt: Prompt to send to all LLMs
            models: List of model names (default: ['qwen', 'deepseek', 'kimi'])
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            timeout: Per-LLM timeout
            system_message: Optional system message
            **kwargs: Additional parameters

        Yields:
            Dict for each completed LLM
        """
        if models is None:
            models = ['qwen', 'deepseek', 'kimi']

        logger.debug(
            "[LLMMultiService] generate_progressive() - %s models",
            len(models)
        )

        # Create tasks with model info
        task_model_pairs = []
        for model in models:
            task = asyncio.create_task(
                self._call_single_model_with_timing(
                    model=model,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    system_message=system_message,
                    **kwargs
                )
            )
            task_model_pairs.append((task, model))

        # Yield results as they complete
        tasks = [task for task, _ in task_model_pairs]
        yielded_tasks = set()

        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                # Find which model this result belongs to
                completed_model = None
                for task, model in task_model_pairs:
                    if task.done() and task not in yielded_tasks:
                        yielded_tasks.add(task)
                        completed_model = model
                        break

                if completed_model:
                    yield {
                        'llm': completed_model,
                        'response': result['response'],
                        'duration': result['duration'],
                        'success': True,
                        'error': None,
                        'timestamp': time.time()
                    }
                    logger.debug(
                        "[LLMMultiService] %s completed in %.2fs",
                        completed_model, result['duration']
                    )

            except Exception as e:
                # Find which model failed
                failed_model = None
                for task, model in task_model_pairs:
                    if task.done() and task.exception() and task not in yielded_tasks:
                        yielded_tasks.add(task)
                        failed_model = model
                        break

                if failed_model:
                    logger.error(
                        "[LLMMultiService] %s failed: %s",
                        failed_model, e
                    )
                    yield {
                        'llm': failed_model,
                        'response': None,
                        'duration': 0.0,
                        'success': False,
                        'error': str(e),
                        'timestamp': time.time()
                    }

    async def stream_progressive(
        self,
        prompt: str,
        models: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        timeout: Optional[float] = None,
        system_message: Optional[str] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'node_palette',
        diagram_type: Optional[str] = None,
        endpoint_path: Optional[str] = None,
        session_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream from multiple LLMs concurrently, yield tokens as they arrive.

        Args:
            prompt: Prompt to send to all LLMs
            models: List of model names (default: ['qwen', 'deepseek', 'doubao'])
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            timeout: Per-LLM timeout
            system_message: Optional system message
            user_id: User ID for token tracking
            organization_id: Organization ID for token tracking
            request_type: Request type for token tracking
            diagram_type: Diagram type for token tracking
            endpoint_path: Endpoint path for token tracking
            session_id: Session ID for token tracking
            conversation_id: Conversation ID for token tracking
            **kwargs: Additional parameters

        Yields:
            Dict for each token/event
        """
        # NOTE: Hunyuan disabled due to 5 concurrent connection limit
        # NOTE: Kimi removed from node palette default
        if models is None:
            models = ['qwen', 'deepseek', 'doubao']

        # Map logical models to physical models
        physical_models = models
        physical_to_logical = {m: m for m in models}

        if self.llm_service.load_balancer and self.llm_service.load_balancer.enabled:
            physical_models = [
                self.llm_service.load_balancer.map_model(m)
                for m in models
            ]
            physical_to_logical = {
                physical: logical
                for logical, physical in zip(models, physical_models)
            }
            logger.info(
                "[LLMMultiService] stream_progressive: models=%s → %s",
                models, physical_models
            )

        logger.debug(
            "[LLMMultiService] stream_progressive() - streaming from %s models concurrently",
            len(physical_models)
        )

        queue = asyncio.Queue()

        async def stream_single(physical_model: str):
            """Stream from one LLM, put chunks in queue."""
            start_time = time.time()
            token_count = 0

            try:
                async for token in self.llm_service.chat_stream(
                    prompt=prompt,
                    model=physical_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    system_message=system_message,
                    user_id=user_id,
                    organization_id=organization_id,
                    request_type=request_type,
                    diagram_type=diagram_type,
                    endpoint_path=endpoint_path,
                    session_id=session_id,
                    conversation_id=conversation_id,
                    skip_load_balancing=True,
                    **kwargs
                ):
                    token_count += 1
                    logical_model = physical_to_logical.get(
                        physical_model, physical_model
                    )
                    await queue.put({
                        'event': 'token',
                        'llm': logical_model,
                        'token': token,
                        'timestamp': time.time()
                    })

                # LLM completed successfully
                duration = time.time() - start_time
                logical_model = physical_to_logical.get(
                    physical_model, physical_model
                )
                await queue.put({
                    'event': 'complete',
                    'llm': logical_model,
                    'duration': duration,
                    'token_count': token_count,
                    'timestamp': time.time()
                })

                tokens_per_sec = token_count / duration if duration > 0 else 0
                logger.info(
                    "[LLMMultiService] %s stream complete - %s tokens in %.2fs (%.1f tok/s)",
                    logical_model, token_count, duration, tokens_per_sec
                )

            except Exception as e:
                duration = time.time() - start_time
                logical_model = physical_to_logical.get(
                    physical_model, physical_model
                )
                logger.error(
                    "[LLMMultiService] %s stream error: %s",
                    logical_model, str(e)
                )
                await queue.put({
                    'event': 'error',
                    'llm': logical_model,
                    'error': str(e),
                    'duration': duration,
                    'timestamp': time.time()
                })

        # Fire all LLM tasks concurrently
        tasks = [
            asyncio.create_task(stream_single(model))
            for model in physical_models
        ]

        completed = 0
        success_count = 0
        total_start = time.time()

        # Yield tokens as they arrive from queue
        while completed < len(physical_models):
            chunk = await queue.get()

            if chunk['event'] == 'complete':
                completed += 1
                success_count += 1
            elif chunk['event'] == 'error':
                completed += 1

            yield chunk

        # Wait for all tasks to finish (cleanup)
        await asyncio.gather(*tasks, return_exceptions=True)

        total_duration = time.time() - total_start
        logger.info(
            "[LLMMultiService] stream_progressive() complete: %s/%s succeeded in %.2fs",
            success_count, len(physical_models), total_duration
        )

    async def generate_race(
        self,
        prompt: str,
        models: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        timeout: Optional[float] = None,
        system_message: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Call multiple LLMs in parallel, return first successful result.

        Args:
            prompt: Prompt to send to all LLMs
            models: List of model names (default: ['qwen-turbo', 'qwen', 'deepseek'])
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            timeout: Per-LLM timeout
            system_message: Optional system message
            **kwargs: Additional parameters

        Returns:
            Dict with first successful result
        """
        if models is None:
            models = ['qwen-turbo', 'qwen', 'deepseek']

        logger.debug(
            "[LLMMultiService] generate_race() - first of %s models",
            len(models)
        )

        # Create tasks with model info
        task_model_pairs = []
        for model in models:
            task = asyncio.create_task(
                self._call_single_model_with_timing(
                    model=model,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    system_message=system_message,
                    **kwargs
                )
            )
            task_model_pairs.append((task, model))

        tasks = [task for task, _ in task_model_pairs]

        # Wait for first successful result
        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro

                # Find which model completed
                completed_model = None
                for task, model in task_model_pairs:
                    if task.done() and not task.exception():
                        completed_model = model
                        break

                if completed_model:
                    # Cancel remaining tasks
                    for task in tasks:
                        if not task.done():
                            task.cancel()

                    logger.debug(
                        "[LLMMultiService] %s won the race in %.2fs",
                        completed_model, result['duration']
                    )

                    return {
                        'llm': completed_model,
                        'response': result['response'],
                        'duration': result['duration'],
                        'success': True,
                        'error': None
                    }

            except Exception as e:
                # Find which model failed
                for task, model in task_model_pairs:
                    if task.done() and task.exception():
                        logger.debug(
                            "[LLMMultiService] %s failed in race: %s",
                            model, e
                        )
                        break
                continue

        # All failed
        logger.error("[LLMMultiService] All models failed in race")
        try:
            await CriticalAlertService.send_runtime_error_alert(
                component="LLM",
                error_message="All LLM models failed - complete LLM service outage",
                details=(
                    "All configured LLM models are unavailable. "
                    "Check API keys, network connectivity, and provider status."
                )
            )
        except Exception as alert_error:
            logger.error(
                "[LLMMultiService] Failed to send critical alert: %s",
                alert_error
            )
        raise LLMServiceError("All models failed to generate response")

    async def compare_responses(
        self,
        prompt: str,
        models: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        system_message: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate responses from multiple LLMs and return for comparison.

        Args:
            prompt: Prompt to send
            models: Models to compare (default: ['qwen', 'deepseek', 'kimi'])
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            system_message: Optional system message
            **kwargs: Additional parameters

        Returns:
            Dict with prompt, responses, and metrics
        """
        if models is None:
            models = ['qwen', 'deepseek', 'kimi']

        results = await self.generate_multi(
            prompt=prompt,
            models=models,
            temperature=temperature,
            max_tokens=max_tokens,
            system_message=system_message,
            **kwargs
        )

        responses = {}
        metrics = {}

        for model, result in results.items():
            if result['success']:
                responses[model] = result['response']
                metrics[model] = {
                    'duration': result['duration'],
                    'success': True
                }
            else:
                responses[model] = None
                metrics[model] = {
                    'duration': result['duration'],
                    'success': False,
                    'error': result.get('error')
                }

        return {
            'prompt': prompt,
            'responses': responses,
            'metrics': metrics
        }

    async def _call_single_model_with_timing(
        self,
        model: str,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        timeout: Optional[float] = None,
        system_message: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Internal method to call a single model with timing.

        CRITICAL: Circuit breaker tracks by PHYSICAL model name to prevent
        one failing route from blocking both routes in load balancing.

        Args:
            model: Logical model name
            prompt: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            timeout: Request timeout
            system_message: Optional system message
            **kwargs: Additional parameters

        Returns:
            Dict with response, duration, success, error
        """
        # Apply load balancing FIRST to get physical model name
        actual_model = model
        provider = None

        if self.llm_service.load_balancer and self.llm_service.load_balancer.enabled:
            actual_model = self.llm_service.load_balancer.map_model(model)
            if hasattr(self.llm_service.load_balancer, 'get_provider_from_model'):
                provider = self.llm_service.load_balancer.get_provider_from_model(
                    actual_model
                )

        # Check circuit breaker using PHYSICAL model name
        if not self.llm_service.performance_tracker.can_call_model(actual_model):
            logger.warning(
                "[LLMMultiService] Circuit breaker OPEN for %s, skipping call",
                actual_model
            )
            return {
                'response': None,
                'duration': 0.0,
                'success': False,
                'error': 'Circuit breaker open'
            }

        start_time = time.time()

        try:
            # Pass actual_model and skip load balancing since already applied
            response = await self.llm_service.chat(
                prompt=prompt,
                model=actual_model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                system_message=system_message,
                skip_load_balancing=True,
                **kwargs
            )

            duration = time.time() - start_time

            # Record success using PHYSICAL model name for circuit breaker
            self.llm_service.performance_tracker.record_request(
                model=actual_model,
                duration=duration,
                success=True
            )

            # Record provider metrics for load balancing (if DeepSeek)
            if provider and self.llm_service.load_balancer:
                self.llm_service.load_balancer.record_provider_metrics(
                    provider=provider,
                    success=True,
                    duration=duration
                )

            return {
                'response': response,
                'duration': round(duration, 2),
                'success': True,
                'error': None
            }

        except Exception as e:
            duration = time.time() - start_time

            # Record failure using PHYSICAL model name for circuit breaker
            self.llm_service.performance_tracker.record_request(
                model=actual_model,
                duration=duration,
                success=False,
                error=str(e)
            )

            # Record provider metrics for load balancing (if DeepSeek)
            if provider and self.llm_service.load_balancer:
                self.llm_service.load_balancer.record_provider_metrics(
                    provider=provider,
                    success=False,
                    duration=duration,
                    error=str(e)
                )

            return {
                'response': None,
                'duration': round(duration, 2),
                'success': False,
                'error': str(e)
            }
