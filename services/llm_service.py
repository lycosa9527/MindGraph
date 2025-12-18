"""
LLM Service Layer
=================

Centralized service for all LLM operations in MindGraph.
Provides unified API, error handling, and performance tracking.

@author lycosa9527
@made_by MindSpring Team
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, AsyncGenerator

from services.client_manager import client_manager
from services.error_handler import error_handler, LLMServiceError
from services.rate_limiter import initialize_rate_limiter, get_rate_limiter
from services.prompt_manager import prompt_manager
from services.performance_tracker import performance_tracker
from services.token_tracker import get_token_tracker
from config.settings import config

logger = logging.getLogger(__name__)


class LLMService:
    """
    Centralized LLM service for all MindGraph agents.
    
    Usage:
        from services.llm_service import llm_service
        
        # Simple chat
        response = await llm_service.chat("Hello", model='qwen')
    """
    
    def __init__(self):
        self.client_manager = client_manager
        self.prompt_manager = prompt_manager
        self.performance_tracker = performance_tracker
        self.rate_limiter = None
        logger.info("[LLMService] Initialized")
    
    def initialize(self) -> None:
        """Initialize LLM Service (called at app startup)."""
        logger.info("[LLMService] Initializing...")
        
        # Initialize client manager
        self.client_manager.initialize()
        
        # Initialize prompt manager
        self.prompt_manager.initialize()
        
        # Initialize rate limiter for Dashscope platform
        if config.DASHSCOPE_RATE_LIMITING_ENABLED:
            logger.debug("[LLMService] Configuring Dashscope rate limiting")
            logger.debug(
                f"[LLMService] QPM={config.DASHSCOPE_QPM_LIMIT}, "
                f"Concurrent={config.DASHSCOPE_CONCURRENT_LIMIT}"
            )
            
            self.rate_limiter = initialize_rate_limiter(
                qpm_limit=config.DASHSCOPE_QPM_LIMIT,
                concurrent_limit=config.DASHSCOPE_CONCURRENT_LIMIT,
                enabled=config.DASHSCOPE_RATE_LIMITING_ENABLED
            )
        else:
            logger.debug("[LLMService] Rate limiting disabled")
            self.rate_limiter = None
        
        logger.debug("[LLMService] Ready")
    
    def cleanup(self) -> None:
        """Cleanup LLM Service (called at app shutdown)."""
        logger.info("[LLMService] Cleaning up...")
        self.client_manager.cleanup()
        logger.info("[LLMService] Cleanup complete")
    
    # ============================================================================
    # BASIC METHODS
    # ============================================================================
    
    async def chat(
        self,
        prompt: str,
        model: str = 'qwen',
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        system_message: Optional[str] = None,
        timeout: Optional[float] = None,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        diagram_type: Optional[str] = None,
        endpoint_path: Optional[str] = None,
        session_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Simple chat completion (single response).
        
        Args:
            prompt: User message/prompt
            model: LLM model to use
            temperature: Sampling temperature (None uses model default)
            max_tokens: Maximum tokens in response
            system_message: Optional system message
            timeout: Request timeout in seconds (None uses default)
            **kwargs: Additional model-specific parameters
            
        Returns:
            Complete response string
            
        Example:
            response = await llm_service.chat(
                prompt="Explain photosynthesis",
                model='qwen',
                temperature=0.7
            )
        """
        start_time = time.time()
        
        try:
            logger.debug(f"[LLMService] chat() - model={model}, prompt_len={len(prompt)}")
            
            # Get client
            client = self.client_manager.get_client(model)
            
            # Build messages
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": prompt})
            
            # Set timeout (per-model defaults)
            if timeout is None:
                timeout = self._get_default_timeout(model)
            
            # Use rate limiter if available
            if self.rate_limiter:
                async with self.rate_limiter:
                    # Execute with retry and timeout
                    async def _call():
                        # DeepSeek and Kimi use async_chat_completion
                        if hasattr(client, 'async_chat_completion'):
                            return await client.async_chat_completion(
                                messages=messages,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                **kwargs
                            )
                        else:
                            # Qwen and Hunyuan use chat_completion
                            return await client.chat_completion(
                                messages=messages,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                **kwargs
                            )
                    
                    # Properly await with_retry inside timeout
                    response = await asyncio.wait_for(
                        error_handler.with_retry(_call),
                        timeout=timeout
                    )
            else:
                # No rate limiting
                async def _call():
                    if hasattr(client, 'async_chat_completion'):
                        return await client.async_chat_completion(
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            **kwargs
                        )
                    else:
                        return await client.chat_completion(
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            **kwargs
                        )
                
                # Properly await with_retry inside timeout
                response = await asyncio.wait_for(
                    error_handler.with_retry(_call),
                    timeout=timeout
                )
            
            # Validate response
            response = error_handler.validate_response(response)
            
            duration = time.time() - start_time
            
            # Extract content and usage from response (new format: dict with 'content' and 'usage')
            content = response
            usage_data = {}
            
            if isinstance(response, dict):
                content = response.get('content', '')
                usage_data = response.get('usage', {})
            else:
                # Backward compatibility: plain string response
                content = str(response)
                usage_data = {}
            
            logger.info(f"[LLMService] {model} responded in {duration:.2f}s")
            
            # Track token usage (async, non-blocking)
            if usage_data:
                try:
                    # Normalize token field names (API uses prompt_tokens/completion_tokens, we use input_tokens/output_tokens)
                    input_tokens = usage_data.get('prompt_tokens') or usage_data.get('input_tokens') or 0
                    output_tokens = usage_data.get('completion_tokens') or usage_data.get('output_tokens') or 0
                    # Use API's total_tokens (authoritative billing value) - may include overhead tokens
                    total_tokens = usage_data.get('total_tokens') or None
                    
                    token_tracker = get_token_tracker()
                    await token_tracker.track_usage(
                        model_alias=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        request_type=request_type,
                        diagram_type=diagram_type,
                        user_id=user_id,
                        organization_id=organization_id,
                        session_id=session_id,
                        conversation_id=conversation_id,
                        endpoint_path=endpoint_path,
                        response_time=duration,
                        success=True
                    )
                except Exception as e:
                    logger.debug(f"[LLMService] Token tracking failed (non-critical): {e}")
            
            # Record performance metrics
            self.performance_tracker.record_request(
                model=model,
                duration=duration,
                success=True
            )
            
            return content
            
        except ValueError as e:
            # Let ValueError pass through (e.g., invalid model)
            raise
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"[LLMService] {model} failed after {duration:.2f}s: {e}")
            
            # Record failure metrics
            self.performance_tracker.record_request(
                model=model,
                duration=duration,
                success=False,
                error=str(e)
            )
            
            raise LLMServiceError(f"Chat failed for model {model}: {e}") from e
    
    async def chat_stream(
        self,
        prompt: str,
        model: str = 'qwen',
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        timeout: Optional[float] = None,
        system_message: Optional[str] = None,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        diagram_type: Optional[str] = None,
        endpoint_path: Optional[str] = None,
        session_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        **kwargs
    ):
        """
        Stream chat completion from a specific LLM.
        
        Args:
            prompt: User prompt
            model: Model identifier (qwen, deepseek, etc.)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
            system_message: Optional system message
            **kwargs: Additional model-specific parameters
            
        Yields:
            Response chunks as they arrive
        """
        start_time = time.time()
        
        try:
            logger.debug(f"[LLMService] chat_stream() - model={model}, prompt_len={len(prompt)}")
            
            # Get client
            client = self.client_manager.get_client(model)
            
            # Build messages
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": prompt})
            
            # Set timeout
            if timeout is None:
                timeout = self._get_default_timeout(model)
            
            # Check if client supports streaming
            if hasattr(client, 'async_stream_chat_completion'):
                stream_method = client.async_stream_chat_completion
            elif hasattr(client, 'stream_chat_completion'):
                stream_method = client.stream_chat_completion
            else:
                # Fallback: get full response and yield it as one chunk
                response = await self.chat(
                    prompt=prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    system_message=system_message,
                    **kwargs
                )
                yield response
                return
            
            # Stream the response and capture usage
            usage_data = None
            async for chunk in stream_method(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            ):
                # Handle new format: chunk can be dict with 'type' and content/usage
                if isinstance(chunk, dict):
                    chunk_type = chunk.get('type', 'token')
                    if chunk_type == 'usage':
                        # Capture usage data from final chunk
                        usage_data = chunk.get('usage', {})
                    elif chunk_type == 'token':
                        # Yield content token
                        content = chunk.get('content', '')
                        if content:
                            yield content
                else:
                    # Backward compatibility: plain string chunk
                    yield chunk
            
            duration = time.time() - start_time
            logger.debug(f"[LLMService] {model} stream completed in {duration:.2f}s")
            
            # Track token usage (async, non-blocking)
            if usage_data:
                try:
                    # Normalize token field names
                    input_tokens = usage_data.get('prompt_tokens') or usage_data.get('input_tokens') or 0
                    output_tokens = usage_data.get('completion_tokens') or usage_data.get('output_tokens') or 0
                    # Use API's total_tokens (authoritative billing value) - may include overhead tokens
                    total_tokens = usage_data.get('total_tokens') or None
                    
                    token_tracker = get_token_tracker()
                    await token_tracker.track_usage(
                        model_alias=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        request_type=request_type,
                        diagram_type=diagram_type,
                        user_id=user_id,
                        organization_id=organization_id,
                        session_id=session_id,
                        conversation_id=conversation_id,
                        endpoint_path=endpoint_path,
                        response_time=duration,
                        success=True
                    )
                except Exception as e:
                    logger.debug(f"[LLMService] Token tracking failed (non-critical): {e}")
            
            # Record performance metrics
            self.performance_tracker.record_request(
                model=model,
                duration=duration,
                success=True
            )
            
        except ValueError as e:
            # Let ValueError pass through (e.g., invalid model)
            raise
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"[LLMService] {model} stream failed after {duration:.2f}s: {e}")
            
            # Record failure metrics
            self.performance_tracker.record_request(
                model=model,
                duration=duration,
                success=False,
                error=str(e)
            )
            
            raise LLMServiceError(f"Chat stream failed for model {model}: {e}") from e
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def _get_default_timeout(self, model: str) -> float:
        """Get default timeout for model (in seconds)."""
        # Generous timeouts for complex diagrams (mind maps, tree maps with deep hierarchies)
        timeouts = {
            'qwen': 70.0,
            'qwen-turbo': 70.0,
            'qwen-plus': 70.0,
            'deepseek': 70.0,
            'hunyuan': 70.0,
            'kimi': 70.0,
            'doubao': 70.0,
            'chatglm': 70.0
        }
        return timeouts.get(model, 70.0)
    
    def get_available_models(self) -> List[str]:
        """Get list of all available models."""
        return self.client_manager.get_available_models()
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of all LLM clients.
        
        Returns:
            Status dict for each model with available_models list
        """
        available_models = self.get_available_models()
        results = {'available_models': available_models}
        
        for model in available_models:
            try:
                start = time.time()
                await self.chat(
                    prompt="Test",
                    model=model,
                    max_tokens=10,
                    timeout=5.0
                )
                latency = time.time() - start
                results[model] = {
                    'status': 'healthy',
                    'latency': round(latency, 2)
                }
            except Exception as e:
                results[model] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
        
        return results
    
    def get_rate_limiter_stats(self) -> Optional[Dict[str, Any]]:
        """Get rate limiter statistics if available."""
        if self.rate_limiter:
            return self.rate_limiter.get_stats()
        return None
    
    def get_prompt(
        self,
        category: str,
        function: str,
        name: str = 'default',
        language: str = 'en',
        **kwargs
    ) -> str:
        """
        Get a formatted prompt from the prompt manager.
        
        Convenience method that wraps prompt_manager.get_prompt().
        
        Args:
            category: Prompt category
            function: Function name
            name: Specific prompt name
            language: Language code
            **kwargs: Variables to fill in template
            
        Returns:
            Formatted prompt string
            
        Example:
            prompt = llm_service.get_prompt(
                category='thinkguide',
                function='welcome',
                language='zh',
                diagram_type='圆圈图',
                topic='汽车'
            )
        """
        return self.prompt_manager.get_prompt(
            category=category,
            function=function,
            name=name,
            language=language,
            **kwargs
        )
    
    # ============================================================================
    # MULTI-LLM METHODS (Phase 2: Async Orchestration)
    # ============================================================================
    
    async def generate_multi(
        self,
        prompt: str,
        models: List[str] = None,
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
            Dict mapping model names to results:
            {
                'qwen': {
                    'response': 'Generated text...',
                    'duration': 2.3,
                    'success': True
                },
                'deepseek': {
                    'response': None,
                    'error': 'Timeout',
                    'duration': 20.0,
                    'success': False
                },
                ...
            }
            
        Example:
            results = await llm_service.generate_multi(
                prompt="Generate 10 ideas",
                models=['qwen', 'deepseek', 'kimi']
            )
            successful = [r for r in results.values() if r['success']]
        """
        if models is None:
            models = ['qwen', 'deepseek', 'kimi']
        
        start_time = time.time()
        logger.debug(f"[LLMService] generate_multi() - {len(models)} models in parallel")
        
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
                logger.error(f"[LLMService] {model} failed: {e}")
        
        duration = time.time() - start_time
        successful = sum(1 for r in results.values() if r['success'])
        logger.info(
            f"[LLMService] generate_multi() complete: "
            f"{successful}/{len(models)} succeeded in {duration:.2f}s"
        )
        
        return results
    
    async def generate_progressive(
        self,
        prompt: str,
        models: List[str] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        timeout: Optional[float] = None,
        system_message: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Call multiple LLMs in parallel, yield results as each completes.
        
        This provides the best user experience - results appear progressively!
        
        Args:
            prompt: Prompt to send to all LLMs
            models: List of model names (default: ['qwen', 'deepseek', 'kimi'])
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            timeout: Per-LLM timeout
            system_message: Optional system message
            **kwargs: Additional parameters
            
        Yields:
            Dict for each completed LLM:
            {
                'llm': 'qwen',
                'response': 'Generated text...',
                'duration': 2.3,
                'success': True,
                'timestamp': 1234567890.123
            }
            
        Example:
            async for result in llm_service.generate_progressive(
                prompt="Generate ideas",
                models=['qwen', 'deepseek', 'kimi']
            ):
                if result['success']:
                    print(f"{result['llm']}: {result['response'][:50]}...")
        """
        if models is None:
            models = ['qwen', 'deepseek', 'kimi']
        
        logger.debug(f"[LLMService] generate_progressive() - {len(models)} models")
        
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
        model_map = {task: model for task, model in task_model_pairs}
        
        for coro in asyncio.as_completed(tasks):
            # Get the task that completed from the awaited coro
            try:
                result = await coro
                # Find which model this result belongs to by checking completed tasks
                completed_model = None
                for task, model in task_model_pairs:
                    if task.done() and not hasattr(task, '_yielded'):
                        task._yielded = True
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
                    logger.debug(f"[LLMService] {completed_model} completed in {result['duration']:.2f}s")
                
            except Exception as e:
                # Find which model failed
                failed_model = None
                for task, model in task_model_pairs:
                    if task.done() and task.exception() and not hasattr(task, '_yielded'):
                        task._yielded = True
                        failed_model = model
                        break
                
                if failed_model:
                    logger.error(f"[LLMService] {failed_model} failed: {e}")
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
        models: List[str] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        timeout: Optional[float] = None,
        system_message: Optional[str] = None,
        # Token tracking parameters
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
        
        This is the STREAMING version of generate_progressive().
        Fires all LLMs simultaneously and yields tokens progressively.
        Perfect for real-time rendering from multiple LLMs.
        
        Args:
            prompt: Prompt to send to all LLMs
            models: List of model names (default: ['qwen', 'deepseek', 'kimi', 'hunyuan', 'doubao'])
            temperature: Sampling temperature (None uses model default)
            max_tokens: Maximum tokens to generate
            timeout: Per-LLM timeout in seconds (None uses default)
            system_message: Optional system message
            **kwargs: Additional model-specific parameters
            
        Yields:
            Dict for each token/event:
            {
                'event': 'token',        # Event type: 'token', 'complete', or 'error'
                'llm': 'qwen',           # Which LLM produced this
                'token': 'Generated',    # The token (if event='token')
                'duration': 2.3,         # Time taken (if event='complete')
                'error': 'msg',          # Error message (if event='error')
                'timestamp': 1234567890  # Unix timestamp
            }
            
        Example:
            async for chunk in llm_service.stream_progressive(
                prompt="Generate observations about cars",
                models=['qwen', 'deepseek', 'hunyuan', 'kimi']
            ):
                if chunk['event'] == 'token':
                    print(f"{chunk['llm']}: {chunk['token']}", end='', flush=True)
                elif chunk['event'] == 'complete':
                    print(f"\n{chunk['llm']} done in {chunk['duration']:.2f}s")
                elif chunk['event'] == 'error':
                    print(f"\n{chunk['llm']} error: {chunk['error']}")
        """
        if models is None:
            models = ['qwen', 'deepseek', 'kimi', 'hunyuan', 'doubao']
        
        logger.debug(f"[LLMService] stream_progressive() - streaming from {len(models)} models concurrently")
        
        queue = asyncio.Queue()
        
        async def stream_single(model: str):
            """Stream from one LLM, put chunks in queue."""
            start_time = time.time()
            token_count = 0
            
            try:
                # Use existing chat_stream (rate limiter & error handling automatic!)
                # Pass token tracking parameters
                async for token in self.chat_stream(
                    prompt=prompt,
                    model=model,
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
                    **kwargs
                ):
                    token_count += 1
                    await queue.put({
                        'event': 'token',
                        'llm': model,
                        'token': token,
                        'timestamp': time.time()
                    })
                
                # LLM completed successfully
                duration = time.time() - start_time
                await queue.put({
                    'event': 'complete',
                    'llm': model,
                    'duration': duration,
                    'token_count': token_count,
                    'timestamp': time.time()
                })
                
                # Smart logging: summary only, no token spam
                logger.info(
                    f"[LLMService] {model} stream complete - "
                    f"{token_count} tokens in {duration:.2f}s "
                    f"({token_count/duration:.1f} tok/s)"
                )
                
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"[LLMService] {model} stream error: {str(e)}")
                await queue.put({
                    'event': 'error',
                    'llm': model,
                    'error': str(e),
                    'duration': duration,
                    'timestamp': time.time()
                })
        
        # Fire all LLM tasks concurrently
        tasks = [asyncio.create_task(stream_single(model)) for model in models]
        
        completed = 0
        success_count = 0
        total_start = time.time()
        
        # Yield tokens as they arrive from queue
        while completed < len(models):
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
            f"[LLMService] stream_progressive() complete: "
            f"{success_count}/{len(models)} succeeded in {total_duration:.2f}s"
        )
    
    async def generate_race(
        self,
        prompt: str,
        models: List[str] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        timeout: Optional[float] = None,
        system_message: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Call multiple LLMs in parallel, return first successful result.
        
        Useful when you want the fastest response and don't care which model.
        
        Args:
            prompt: Prompt to send to all LLMs
            models: List of model names (default: ['qwen-turbo', 'qwen', 'deepseek'])
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            timeout: Per-LLM timeout
            system_message: Optional system message
            **kwargs: Additional parameters
            
        Returns:
            Dict with first successful result:
            {
                'llm': 'qwen-turbo',
                'response': 'Generated text...',
                'duration': 1.8,
                'success': True
            }
            
        Example:
            # Get fastest response from any model
            result = await llm_service.generate_race(
                prompt="Quick question: What is 2+2?",
                models=['qwen-turbo', 'qwen', 'deepseek']
            )
            print(f"Fastest was {result['llm']}: {result['response']}")
        """
        if models is None:
            models = ['qwen-turbo', 'qwen', 'deepseek']
        
        logger.debug(f"[LLMService] generate_race() - first of {len(models)} models")
        
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
                    
                    logger.debug(f"[LLMService] {completed_model} won the race in {result['duration']:.2f}s")
                    
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
                        logger.debug(f"[LLMService] {model} failed in race: {e}")
                        break
                continue
        
        # All failed
        logger.error("[LLMService] All models failed in race")
        raise LLMServiceError("All models failed to generate response")
    
    async def compare_responses(
        self,
        prompt: str,
        models: List[str] = None,
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
            {
                'prompt': 'Original prompt',
                'responses': {
                    'qwen': 'Response from Qwen...',
                    'deepseek': 'Response from DeepSeek...',
                    'kimi': 'Response from Kimi...'
                },
                'metrics': {
                    'qwen': {'duration': 2.1, 'success': True},
                    'deepseek': {'duration': 3.5, 'success': True},
                    'kimi': {'duration': 4.2, 'success': True}
                }
            }
            
        Example:
            comparison = await llm_service.compare_responses(
                prompt="Explain quantum computing in simple terms",
                models=['qwen', 'deepseek']
            )
            for model, response in comparison['responses'].items():
                print(f"{model}: {response}")
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
    
    # ============================================================================
    # INTERNAL HELPER METHODS
    # ============================================================================
    
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
        Used by multi-LLM methods.
        """
        # Check circuit breaker
        if not self.performance_tracker.can_call_model(model):
            logger.warning(f"[LLMService] Circuit breaker OPEN for {model}, skipping call")
            return {
                'response': None,
                'duration': 0.0,
                'success': False,
                'error': 'Circuit breaker open'
            }
        
        start_time = time.time()
        
        try:
            response = await self.chat(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                system_message=system_message,
                **kwargs
            )
            
            duration = time.time() - start_time
            
            # Record success
            self.performance_tracker.record_request(
                model=model,
                duration=duration,
                success=True
            )
            
            return {
                'response': response,
                'duration': round(duration, 2),
                'success': True,
                'error': None
            }
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Record failure
            self.performance_tracker.record_request(
                model=model,
                duration=duration,
                success=False,
                error=str(e)
            )
            
            return {
                'response': None,
                'duration': round(duration, 2),
                'success': False,
                'error': str(e)
            }
    
    def get_performance_metrics(self, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Get performance metrics for models.
        
        Args:
            model: Specific model name, or None for all models
            
        Returns:
            Dictionary of performance metrics
            
        Example:
            # Get metrics for all models
            all_metrics = llm_service.get_performance_metrics()
            
            # Get metrics for specific model
            qwen_metrics = llm_service.get_performance_metrics('qwen')
        """
        return self.performance_tracker.get_metrics(model)
    
    def get_fastest_model(self, models: List[str] = None) -> Optional[str]:
        """
        Get fastest model based on recent performance.
        
        Args:
            models: List of models to compare (default: all available)
            
        Returns:
            Name of fastest model
            
        Example:
            fastest = llm_service.get_fastest_model(['qwen', 'deepseek', 'kimi'])
            print(f"Fastest model: {fastest}")
        """
        if models is None:
            models = self.get_available_models()
        
        return self.performance_tracker.get_fastest_model(models)


# Singleton instance
llm_service = LLMService()


