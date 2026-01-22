"""
LLM Service Layer
=================

Centralized service for all LLM operations in MindGraph.
Provides unified API, error handling, and performance tracking.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, List, Optional, Any, AsyncGenerator, Tuple
import logging
import time

from services.infrastructure.utils.client_manager import client_manager
from services.infrastructure.http.error_handler import LLMServiceError
from services.monitoring.performance_tracker import performance_tracker
from services.utils.prompt_manager import prompt_manager
from services.llm.llm_message_builder import LLMMessageBuilder
from services.llm.llm_request_executor import LLMRequestExecutor
from services.llm.llm_metrics_tracker import LLMMetricsTracker
from services.llm.llm_load_balancer_helper import LLMLoadBalancerHelper
from services.llm.llm_service_init import LLMServiceInitializer
from services.llm.llm_multi_service import LLMMultiService
from services.llm.llm_health import LLMHealthChecker
from services.llm.llm_utils import LLMUtils

logger = logging.getLogger(__name__)


class LLMService:
    """
    Centralized LLM service for all MindGraph agents.

    Usage:
        from services.llm import llm_service

        # Simple chat
        response = await llm_service.chat("Hello", model='qwen')
    """

    def __init__(self):
        """Initialize LLM Service."""
        self.client_manager = client_manager
        self.prompt_manager = prompt_manager
        self.performance_tracker = performance_tracker

        # Initialize helper components
        self.message_builder = LLMMessageBuilder()
        self.request_executor = LLMRequestExecutor()
        self.metrics_tracker = LLMMetricsTracker()
        self.load_balancer_helper = LLMLoadBalancerHelper()
        self.initializer = LLMServiceInitializer()
        self.multi_service = None  # Initialized after self is ready
        self.health_checker = None  # Initialized after self is ready

        # Rate limiters and load balancer (initialized in initialize())
        self.rate_limiter = None
        self.load_balancer = None
        self.load_balancer_rate_limiter = None
        self.kimi_rate_limiter = None
        self.doubao_rate_limiter = None

        logger.info("[LLMService] Initialized")

    def initialize(self) -> None:
        """Initialize LLM Service (called at app startup)."""
        logger.info("[LLMService] Initializing...")

        # Initialize components using initializer
        init_result = self.initializer.initialize(
            client_manager=self.client_manager,
            prompt_manager=self.prompt_manager
        )

        # Set rate limiters and load balancer from initializer
        self.rate_limiter = init_result['rate_limiter']
        self.load_balancer = init_result['load_balancer']
        self.load_balancer_rate_limiter = init_result['load_balancer_rate_limiter']
        self.kimi_rate_limiter = init_result['kimi_rate_limiter']
        self.doubao_rate_limiter = init_result['doubao_rate_limiter']

        # Initialize multi-service and health checker (need self reference)
        self.multi_service = LLMMultiService(self)
        self.health_checker = LLMHealthChecker(self)

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
        prompt: str = '',
        model: str = 'qwen',
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        system_message: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,  # Multi-turn conversation history
        timeout: Optional[float] = None,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        api_key_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        diagram_type: Optional[str] = None,
        endpoint_path: Optional[str] = None,
        session_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        skip_load_balancing: bool = False,  # Skip load balancing if already applied
        use_knowledge_base: bool = True,  # Enable RAG context injection
        **kwargs
    ) -> str:
        """
        Simple chat completion (single response).

        Supports both single-turn and multi-turn conversations.

        Args:
            prompt: User message/prompt (used if messages is not provided)
            model: LLM model to use
            temperature: Sampling temperature (None uses model default)
            max_tokens: Maximum tokens in response
            system_message: Optional system message (used if messages is not provided)
            messages: Optional list of message dicts for multi-turn conversations.
                     If provided, overrides prompt and system_message.
                     Format: [{"role": "system/user/assistant", "content": "..."}]

                     Multi-turn conversation example:
                     [
                         {"role": "user", "content": "推荐一部关于太空探索的科幻电影。"},
                         {"role": "assistant", "content": "我推荐《xxx》，这是一部经典的科幻作品。"},
                         {"role": "user", "content": "这部电影的导演是谁？"}
                     ]

                     Important for thinking models (Qwen3, DeepSeek R1, Kimi K2):
                     - Only include 'content' field in assistant messages, NOT 'reasoning_content'
                     - reasoning_content is for display only and should not be added to conversation history

                     Supports multimodal content:
                     - Images: [{"type": "image_url", "image_url": {"url": "..."}}]
                     - Videos: [{"type": "video", "video": ["url1", "url2"]}]
                     - Mixed: [{"type": "text", "text": "..."}, {"type": "image_url", ...}]
            timeout: Request timeout in seconds (None uses default)
            use_knowledge_base: Enable RAG context injection from user's knowledge space
            **kwargs: Additional model-specific parameters:
                - top_p: Nucleus sampling threshold (0.0 to 1.0)
                - top_k: Top-k sampling (DashScope-specific, via extra_body)
                - presence_penalty: Repetition control (-2.0 to 2.0)
                - stop: Stop sequences (string or list)
                - seed: Random seed for reproducibility
                - n: Number of completions (1-4, qwen-plus/Qwen3 only)
                - logprobs: Return token log probabilities
                - top_logprobs: Number of top logprobs (0-5)
                - tools: Function calling tools array
                - tool_choice: Tool selection strategy
                - parallel_tool_calls: Enable parallel tool calls
                - response_format: JSON mode ({"type": "json_object"} or {"type": "json_schema"})
                - enable_search: Web search (DashScope-specific, via extra_body)
                - search_options: Search configuration (DashScope-specific, via extra_body)
                - vl_high_resolution_images: High-res images (DashScope-specific, via extra_body)
                - modalities: Output modalities for Qwen-Omni (DashScope-specific, via extra_body)
                - audio: Audio output config for Qwen-Omni (DashScope-specific, via extra_body)
                - enable_code_interpreter: Code interpreter (DashScope-specific, via extra_body)
                - thinking_budget: Limit thinking length (DashScope-specific, via extra_body)

        Returns:
            Complete response string (or list of strings if n > 1)

        Example:
            # Single-turn conversation
            response = await llm_service.chat(
                prompt="Explain photosynthesis",
                model='qwen',
                temperature=0.7
            )

            # Multi-turn conversation
            messages = [
                {"role": "user", "content": "推荐一部关于太空探索的科幻电影。"},
                {"role": "assistant", "content": "我推荐《xxx》，这是一部经典的科幻作品。"},
                {"role": "user", "content": "这部电影的导演是谁？"}
            ]
            response = await llm_service.chat(
                messages=messages,
                model='qwen'
            )
        """
        start_time = time.time()

        # Build messages with RAG context injection
        chat_messages = self.message_builder.build_with_rag(
            prompt=prompt,
            system_message=system_message,
            messages=messages,
            user_id=user_id,
            use_knowledge_base=use_knowledge_base
        )

        try:
            logger.debug(
                "[LLMService] chat() - model=%s, messages_count=%s",
                model, len(chat_messages)
            )

            # Apply load balancing
            actual_model, provider = self.load_balancer_helper.apply_load_balancing(
                model=model,
                skip_load_balancing=skip_load_balancing,
                load_balancer=self.load_balancer
            )

            # Get client for actual model
            client = self.client_manager.get_client(actual_model)

            # Set timeout (per-model defaults)
            if timeout is None:
                timeout = LLMUtils.get_default_timeout(model)

            # Get appropriate rate limiter
            rate_limiter = LLMUtils.get_rate_limiter(
                model=model,
                actual_model=actual_model,
                provider=provider,
                rate_limiter=self.rate_limiter,
                load_balancer_rate_limiter=self.load_balancer_rate_limiter,
                kimi_rate_limiter=self.kimi_rate_limiter,
                doubao_rate_limiter=self.doubao_rate_limiter
            )

            # Execute request
            response = await self.request_executor.execute_chat_request(
                client=client,
                messages=chat_messages,
                rate_limiter=rate_limiter,
                timeout=timeout,
                model=model,
                actual_model=actual_model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

            duration = time.time() - start_time

            # Extract content and usage from response
            if isinstance(response, dict):
                content = response.get('content', '')
                usage_data = response.get('usage', {})
            else:
                content = str(response)
                usage_data = {}

            logger.info("[LLMService] %s responded in %.2fs", model, duration)

            # Track all metrics
            metadata = {
                'user_id': user_id,
                'organization_id': organization_id,
                'api_key_id': api_key_id,
                'request_type': request_type,
                'diagram_type': diagram_type,
                'endpoint_path': endpoint_path,
                'session_id': session_id,
                'conversation_id': conversation_id
            }
            await self.metrics_tracker.track_all(
                model=model,
                usage_data=usage_data,
                metadata=metadata,
                provider=provider,
                load_balancer=self.load_balancer,
                success=True,
                duration=duration
            )

            return content

        except ValueError:
            raise
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "[LLMService] %s failed after %.2fs: %s",
                model, duration, e
            )

            # Track failed request
            metadata = {
                'user_id': user_id,
                'organization_id': organization_id,
                'api_key_id': api_key_id,
                'request_type': request_type,
                'diagram_type': diagram_type,
                'endpoint_path': endpoint_path,
                'session_id': session_id,
                'conversation_id': conversation_id
            }
            await self.metrics_tracker.track_all(
                model=model,
                usage_data=None,
                metadata=metadata,
                provider=provider,
                load_balancer=self.load_balancer,
                success=False,
                duration=duration,
                error=str(e)
            )

            raise LLMServiceError(f"Chat failed for model {model}: {e}") from e

    async def chat_with_usage(
        self,
        prompt: str = '',
        model: str = 'qwen',
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        system_message: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,  # Multi-turn conversation history
        timeout: Optional[float] = None,
        **kwargs
    ) -> Tuple[str, dict]:
        """
        Chat completion that returns both content and usage data.

        This method is useful when you need to track tokens with diagram_type
        that is only known after parsing the response.

        Supports both single-turn and multi-turn conversations.

        Args:
            prompt: User message/prompt (used if messages is not provided)
            model: LLM model to use
            temperature: Sampling temperature (None uses model default)
            max_tokens: Maximum tokens in response
            system_message: Optional system message (used if messages is not provided)
            messages: Optional list of message dicts for multi-turn conversations.
                     If provided, overrides prompt and system_message.
                     Format: [{"role": "system/user/assistant", "content": "..."}]
            timeout: Request timeout in seconds (None uses default)
            **kwargs: Additional model-specific parameters (see chat() method for full list)

        Returns:
            Tuple of (content: str, usage_data: dict)
            usage_data contains: prompt_tokens, completion_tokens, total_tokens
        """
        start_time = time.time()

        # Build messages (no RAG for chat_with_usage - caller handles tracking)
        chat_messages = self.message_builder.build_chat_messages(
            prompt=prompt,
            system_message=system_message,
            messages=messages
        )

        try:
            logger.debug(
                "[LLMService] chat_with_usage() - model=%s, messages_count=%s",
                model, len(chat_messages)
            )

            # Apply load balancing
            actual_model, provider = self.load_balancer_helper.apply_load_balancing(
                model=model,
                skip_load_balancing=False,
                load_balancer=self.load_balancer
            )

            # Get client for actual model
            client = self.client_manager.get_client(actual_model)

            # Set timeout
            if timeout is None:
                timeout = LLMUtils.get_default_timeout(model)

            # Get appropriate rate limiter
            rate_limiter = LLMUtils.get_rate_limiter(
                model=model,
                actual_model=actual_model,
                provider=provider,
                rate_limiter=self.rate_limiter,
                load_balancer_rate_limiter=self.load_balancer_rate_limiter,
                kimi_rate_limiter=self.kimi_rate_limiter,
                doubao_rate_limiter=self.doubao_rate_limiter
            )

            # Execute request
            response = await self.request_executor.execute_chat_request(
                client=client,
                messages=chat_messages,
                rate_limiter=rate_limiter,
                timeout=timeout,
                model=model,
                actual_model=actual_model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

            duration = time.time() - start_time

            # Extract content and usage from response
            if isinstance(response, dict):
                content = response.get('content', '')
                usage_data = response.get('usage', {})
            else:
                content = str(response)
                usage_data = {}

            logger.info("[LLMService] %s responded in %.2fs", model, duration)

            # Record performance metrics only (caller tracks tokens)
            self.metrics_tracker.record_performance_metrics(
                model=model,
                duration=duration,
                success=True
            )

            # Record provider metrics for load balancing
            if provider and self.load_balancer:
                self.metrics_tracker.record_provider_metrics(
                    provider=provider,
                    load_balancer=self.load_balancer,
                    success=True,
                    duration=duration
                )

            return content, usage_data

        except ValueError:
            raise
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "[LLMService] %s failed after %.2fs: %s",
                model, duration, e
            )

            self.metrics_tracker.record_performance_metrics(
                model=model,
                duration=duration,
                success=False,
                error=str(e)
            )

            if provider and self.load_balancer:
                self.metrics_tracker.record_provider_metrics(
                    provider=provider,
                    load_balancer=self.load_balancer,
                    success=False,
                    duration=duration,
                    error=str(e)
                )

            raise LLMServiceError(f"Chat failed for model {model}: {e}") from e

    async def chat_stream(
        self,
        prompt: str = '',
        model: str = 'qwen',
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        timeout: Optional[float] = None,
        system_message: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,  # Multi-turn messages array
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        diagram_type: Optional[str] = None,
        endpoint_path: Optional[str] = None,
        session_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        skip_load_balancing: bool = False,  # Skip load balancing if already applied (e.g., from stream_progressive)
        enable_thinking: bool = False,  # Enable thinking mode for reasoning models (DeepSeek R1, Qwen3, Kimi K2)
        yield_structured: bool = False,  # If True, yield dicts with 'type' key; if False, yield plain strings
        use_knowledge_base: bool = True,  # Enable RAG context injection
        **kwargs
    ):
        """
        Stream chat completion from a specific LLM.

        Args:
            prompt: User prompt (used if messages is not provided)
            model: Model identifier (qwen, deepseek, etc.)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
            system_message: Optional system message (used if messages is not provided)
            messages: Optional list of message dicts for multi-turn conversations.
                      If provided, overrides prompt and system_message.
                      Format: [{"role": "system/user/assistant", "content": "..."}]
            enable_thinking: Enable thinking mode for reasoning models (yields 'thinking' chunks)
            yield_structured: If True, yield structured dicts; if False, yield plain content strings
            use_knowledge_base: Enable RAG context injection from user's knowledge space
            **kwargs: Additional model-specific parameters:
                - top_p: Nucleus sampling threshold (0.0 to 1.0)
                - top_k: Top-k sampling (DashScope-specific, via extra_body)
                - presence_penalty: Repetition control (-2.0 to 2.0)
                - stop: Stop sequences (string or list)
                - seed: Random seed for reproducibility
                - logprobs: Return token log probabilities
                - top_logprobs: Number of top logprobs (0-5)
                - tools: Function calling tools array
                - tool_choice: Tool selection strategy
                - parallel_tool_calls: Enable parallel tool calls
                - response_format: JSON mode ({"type": "json_object"} or {"type": "json_schema"})
                - enable_search: Web search (DashScope-specific, via extra_body)
                - search_options: Search configuration (DashScope-specific, via extra_body)
                - vl_high_resolution_images: High-res images (DashScope-specific, via extra_body)
                - modalities: Output modalities for Qwen-Omni (DashScope-specific, via extra_body)
                - audio: Audio output config for Qwen-Omni (DashScope-specific, via extra_body)
                - enable_code_interpreter: Code interpreter (DashScope-specific, via extra_body)
                - thinking_budget: Limit thinking length (DashScope-specific, via extra_body)

        Yields:
            If yield_structured=False (default): Plain content strings
            If yield_structured=True: Dicts with 'type' key:
                - {'type': 'thinking', 'content': '...'} - Reasoning content
                - {'type': 'token', 'content': '...'} - Response content
                - {'type': 'usage', 'usage': {...}} - Token usage stats
        """
        start_time = time.time()

        # Enhance prompt with RAG for streaming (if enabled)
        if use_knowledge_base and user_id and messages is None:
            prompt = self.message_builder.enhance_prompt_for_streaming(
                prompt=prompt,
                user_id=user_id,
                use_knowledge_base=use_knowledge_base
            )

        try:
            logger.debug(
                "[LLMService] chat_stream() - model=%s, prompt_len=%s",
                model, len(prompt) if isinstance(prompt, str) else 0
            )

            # Apply load balancing
            actual_model, provider = self.load_balancer_helper.apply_load_balancing(
                model=model,
                skip_load_balancing=skip_load_balancing,
                load_balancer=self.load_balancer
            )

            # Get client for actual model
            client = self.client_manager.get_client(actual_model)

            # Build messages
            chat_messages = self.message_builder.build_chat_messages(
                prompt=prompt,
                system_message=system_message,
                messages=messages
            )

            # Set timeout
            if timeout is None:
                timeout = LLMUtils.get_default_timeout(model)

            # Get appropriate rate limiter
            rate_limiter = LLMUtils.get_rate_limiter(
                model=model,
                actual_model=actual_model,
                provider=provider,
                rate_limiter=self.rate_limiter,
                load_balancer_rate_limiter=self.load_balancer_rate_limiter,
                kimi_rate_limiter=self.kimi_rate_limiter,
                doubao_rate_limiter=self.doubao_rate_limiter
            )

            # Check if client supports streaming
            if not (hasattr(client, 'async_stream_chat_completion') or
                    hasattr(client, 'stream_chat_completion')):
                # Fallback: get full response and yield it as one chunk
                response = await self.chat(
                    prompt=prompt,
                    model=actual_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    system_message=system_message,
                    skip_load_balancing=True,
                    use_knowledge_base=False,  # Already enhanced
                    **kwargs
                )
                yield response
                return

            # Stream the response and capture usage
            usage_data = None
            async for chunk in self.request_executor.execute_stream_request(
                client=client,
                messages=chat_messages,
                rate_limiter=rate_limiter,
                model=model,
                actual_model=actual_model,
                temperature=temperature,
                max_tokens=max_tokens,
                enable_thinking=enable_thinking,
                yield_structured=yield_structured,
                **kwargs
            ):
                # Capture usage data from final chunk (for tracking)
                if isinstance(chunk, dict):
                    if chunk.get('type') == 'usage':
                        usage_data = chunk.get('usage', {})
                        # Only yield usage chunk if structured mode
                        if yield_structured:
                            yield chunk
                        continue
                yield chunk

            duration = time.time() - start_time
            logger.debug(
                "[LLMService] %s stream completed in %.2fs",
                model, duration
            )

            # Track all metrics
            metadata = {
                'user_id': user_id,
                'organization_id': organization_id,
                'request_type': request_type,
                'diagram_type': diagram_type,
                'endpoint_path': endpoint_path,
                'session_id': session_id,
                'conversation_id': conversation_id
            }
            await self.metrics_tracker.track_all(
                model=model,
                usage_data=usage_data,
                metadata=metadata,
                provider=provider,
                load_balancer=self.load_balancer,
                success=True,
                duration=duration
            )

        except ValueError:
            raise
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "[LLMService] %s stream failed after %.2fs: %s",
                model, duration, e
            )

            # Track failure metrics
            metadata = {
                'user_id': user_id,
                'organization_id': organization_id,
                'request_type': request_type,
                'diagram_type': diagram_type,
                'endpoint_path': endpoint_path,
                'session_id': session_id,
                'conversation_id': conversation_id
            }
            await self.metrics_tracker.track_all(
                model=model,
                usage_data=None,
                metadata=metadata,
                provider=provider,
                load_balancer=self.load_balancer,
                success=False,
                duration=duration,
                error=str(e)
            )

            raise LLMServiceError(f"Chat stream failed for model {model}: {e}") from e

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================

    def get_available_models(self) -> List[str]:
        """
        Get list of all available models.

        Delegates to health checker.
        """
        if self.health_checker:
            return self.health_checker.get_available_models()
        return self.client_manager.get_available_models()

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of all LLM clients in parallel.

        Delegates to health checker.
        """
        if self.health_checker:
            return await self.health_checker.health_check()
        return {'available_models': []}

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
        models: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 2000,
        timeout: Optional[float] = None,
        system_message: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Call multiple LLMs in parallel, wait for all to complete.

        Delegates to multi-service.
        """
        if self.multi_service:
            return await self.multi_service.generate_multi(
                prompt=prompt,
                models=models,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                system_message=system_message,
                **kwargs
            )
        raise LLMServiceError("Multi-service not initialized")

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

        Delegates to multi-service.
        """
        if self.multi_service:
            async for result in self.multi_service.generate_progressive(
                prompt=prompt,
                models=models,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                system_message=system_message,
                **kwargs
            ):
                yield result
        else:
            raise LLMServiceError("Multi-service not initialized")

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

        Delegates to multi-service.
        """
        if self.multi_service:
            async for chunk in self.multi_service.stream_progressive(
                prompt=prompt,
                models=models,
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
                yield chunk
        else:
            raise LLMServiceError("Multi-service not initialized")

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

        Delegates to multi-service.
        """
        if self.multi_service:
            return await self.multi_service.generate_race(
                prompt=prompt,
                models=models,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                system_message=system_message,
                **kwargs
            )
        raise LLMServiceError("Multi-service not initialized")

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

        Delegates to multi-service.
        """
        if self.multi_service:
            return await self.multi_service.compare_responses(
                prompt=prompt,
                models=models,
                temperature=temperature,
                max_tokens=max_tokens,
                system_message=system_message,
                **kwargs
            )
        raise LLMServiceError("Multi-service not initialized")

    def get_performance_metrics(self, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Get performance metrics for models.

        Args:
            model: Specific model name, or None for all models

        Returns:
            Dictionary of performance metrics
        """
        return self.performance_tracker.get_metrics(model)

    def get_fastest_model(self, models: Optional[List[str]] = None) -> Optional[str]:
        """
        Get fastest model based on recent performance.

        Args:
            models: List of models to compare (default: all available)

        Returns:
            Name of fastest model
        """
        if models is None:
            models = self.get_available_models()

        return self.performance_tracker.get_fastest_model(models)


# Singleton instance
llm_service = LLMService()

__all__ = ["llm_service", "LLMService"]
