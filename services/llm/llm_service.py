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
import asyncio
import logging
import socket
import time

from config.database import SessionLocal
from config.settings import config
from clients.omni_client import OmniRealtimeClient, TurnDetectionMode
from services.infrastructure.client_manager import client_manager
from services.infrastructure.error_handler import (
    error_handler,
    LLMServiceError,
    LLMRateLimitError,
    LLMQuotaExhaustedError
)
from services.infrastructure.load_balancer import (
    initialize_load_balancer
)
from services.infrastructure.rate_limiter import initialize_rate_limiter, DashscopeRateLimiter
from services.infrastructure.rate_limiter import LoadBalancerRateLimiter
from services.llm.rag_service import get_rag_service
from services.monitoring.performance_tracker import performance_tracker
from services.redis.redis_token_buffer import get_token_tracker
from services.utils.prompt_manager import prompt_manager

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
        self.client_manager = client_manager
        self.prompt_manager = prompt_manager
        self.performance_tracker = performance_tracker
        self.rate_limiter = None
        self.load_balancer = None  # Initialized in initialize()
        self.load_balancer_rate_limiter = None  # Initialized in initialize() if load balancing enabled
        self.kimi_rate_limiter = None  # Initialized in initialize() if rate limiting enabled
        self.doubao_rate_limiter = None  # Initialized in initialize() if rate limiting enabled
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
                "[LLMService] QPM=%s, Concurrent=%s",
                config.DASHSCOPE_QPM_LIMIT, config.DASHSCOPE_CONCURRENT_LIMIT
            )

            self.rate_limiter = initialize_rate_limiter(
                qpm_limit=config.DASHSCOPE_QPM_LIMIT,
                concurrent_limit=config.DASHSCOPE_CONCURRENT_LIMIT,
                enabled=config.DASHSCOPE_RATE_LIMITING_ENABLED
            )
        else:
            logger.debug("[LLMService] Rate limiting disabled")
            self.rate_limiter = None

        # Initialize load balancer
        if config.LOAD_BALANCING_ENABLED:
            # Initialize load balancer rate limiter if enabled
            # Note: Only Volcengine route is managed here. Dashscope route uses shared rate limiter.
            if config.LOAD_BALANCING_RATE_LIMITING_ENABLED:
                self.load_balancer_rate_limiter = LoadBalancerRateLimiter(
                    volcengine_qpm=config.DEEPSEEK_VOLCENGINE_QPM_LIMIT,
                    volcengine_concurrent=config.DEEPSEEK_VOLCENGINE_CONCURRENT_LIMIT,
                    enabled=True
                )
                logger.info(
                    "[LLMService] Load balancer rate limiting enabled: "
                    "Volcengine(QPM=%s, Concurrent=%s). "
                    "Note: Dashscope route uses shared Dashscope rate limiter.",
                    config.DEEPSEEK_VOLCENGINE_QPM_LIMIT, config.DEEPSEEK_VOLCENGINE_CONCURRENT_LIMIT
                )
            else:
                self.load_balancer_rate_limiter = None
                logger.info("[LLMService] Load balancer rate limiting disabled")

            self.load_balancer = initialize_load_balancer(
                strategy=config.LOAD_BALANCING_STRATEGY,
                weights=config.LOAD_BALANCING_WEIGHTS,
                enabled=True,
                dashscope_rate_limiter=self.rate_limiter,  # Pass shared Dashscope limiter
                load_balancer_rate_limiter=self.load_balancer_rate_limiter,  # Volcengine limiter only
                rate_limit_aware=config.LOAD_BALANCING_RATE_LIMITING_ENABLED
            )
            logger.info(
                "[LLMService] Load balancer enabled: "
                "strategy=%s, weights=%s, rate_limit_aware=%s",
                config.LOAD_BALANCING_STRATEGY, config.LOAD_BALANCING_WEIGHTS,
                config.LOAD_BALANCING_RATE_LIMITING_ENABLED
            )
        else:
            logger.info("[LLMService] Load balancing disabled")
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
                "[LLMService] Kimi Volcengine rate limiting enabled: "
                "QPM=%s, Concurrent=%s",
                config.KIMI_VOLCENGINE_QPM_LIMIT, config.KIMI_VOLCENGINE_CONCURRENT_LIMIT
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
                "[LLMService] Doubao Volcengine rate limiting enabled: "
                "QPM=%s, Concurrent=%s",
                config.DOUBAO_VOLCENGINE_QPM_LIMIT, config.DOUBAO_VOLCENGINE_CONCURRENT_LIMIT
            )
        else:
            self.kimi_rate_limiter = None
            self.doubao_rate_limiter = None

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

        # Build messages array - support both single-turn (prompt) and multi-turn (messages)
        if messages is not None:
            # Multi-turn conversation: use provided messages directly
            # Make a copy to avoid mutating the original
            chat_messages = list(messages)
            # Extract prompt from last user message for RAG (if enabled)
            last_user_msg = None
            for msg in reversed(chat_messages):
                if msg.get('role') == 'user':
                    last_user_msg = msg.get('content', '')
                    if isinstance(last_user_msg, list):
                        # Multimodal: extract text content
                        for item in last_user_msg:
                            if item.get('type') == 'text':
                                last_user_msg = item.get('text', '')
                                break
                        else:
                            last_user_msg = ''
                    break
            query_for_rag = last_user_msg if last_user_msg else prompt
        else:
            # Single-turn conversation: build from prompt and system_message
            chat_messages = []
            if system_message:
                chat_messages.append({"role": "system", "content": system_message})
            if prompt:
                chat_messages.append({"role": "user", "content": prompt})
            query_for_rag = prompt

        # Inject RAG context if enabled and user_id provided
        if use_knowledge_base and user_id and query_for_rag:
            try:
                rag_service = get_rag_service()
                db = SessionLocal()
                try:
                    # Check if user has knowledge base
                    if rag_service.has_knowledge_base(db, user_id):
                        # Retrieve context
                        context_chunks = rag_service.retrieve_context(
                            db=db,
                            user_id=user_id,
                            query=query_for_rag,
                            top_k=5,
                            method='hybrid'
                        )
                        if context_chunks:
                            # Enhance prompt with context
                            enhanced_prompt = rag_service.enhance_prompt(
                                user_id=user_id,
                                prompt=query_for_rag,
                                context_chunks=context_chunks,
                                max_context_length=2000
                            )
                            # Update the last user message with enhanced prompt
                            if messages is not None:
                                # Multi-turn: update last user message
                                for msg in reversed(chat_messages):
                                    if msg.get('role') == 'user':
                                        if isinstance(msg.get('content'), str):
                                            msg['content'] = enhanced_prompt
                                        elif isinstance(msg.get('content'), list):
                                            # Multimodal: update text content
                                            for item in msg['content']:
                                                if item.get('type') == 'text':
                                                    item['text'] = enhanced_prompt
                                                    break
                                        break
                            else:
                                # Single-turn: update prompt in messages
                                chat_messages[-1]['content'] = enhanced_prompt
                            logger.debug("[LLMService] Injected RAG context: %s chunks", len(context_chunks))
                finally:
                    db.close()
            except Exception as e:
                # If RAG fails, continue with original prompt
                logger.warning("[LLMService] RAG failed, using original prompt: %s", e)

        try:
            logger.debug("[LLMService] chat() - model=%s, messages_count=%s", model, len(chat_messages))

            # Apply load balancing (skip if already applied)
            actual_model = model
            provider = None  # Track provider for metrics

            if not skip_load_balancing and self.load_balancer and self.load_balancer.enabled:
                actual_model = self.load_balancer.map_model(model)
                logger.debug("[LLMService] Load balanced: %s → %s", model, actual_model)
                # Track provider for DeepSeek load balancing metrics
                if model == 'deepseek':
                    provider = 'dashscope' if actual_model == 'deepseek' else 'volcengine'
                    # Use load balancer rate limiter for DeepSeek when load balancing
            elif skip_load_balancing:
                # Model is already a physical model
                actual_model = model
                logger.debug("[LLMService] Skipping load balancing (already applied): %s", model)
                # Determine provider from physical model name for rate limiting
                if actual_model == 'ark-deepseek':
                    provider = 'volcengine'
                elif actual_model == 'deepseek':
                    provider = 'dashscope'

            # Get client for actual model
            client = self.client_manager.get_client(actual_model)

            # Set timeout (per-model defaults)
            if timeout is None:
                timeout = self._get_default_timeout(model)

            # Get appropriate rate limiter
            rate_limiter = self._get_rate_limiter(model, actual_model, provider)

            if rate_limiter:
                # Time rate limiter operations to diagnose delays
                rate_limit_start = time.time()
                async with rate_limiter:
                    rate_limit_duration = time.time() - rate_limit_start
                    # Always log rate limiter timing for Kimi to diagnose delays
                    if model == 'kimi' or rate_limit_duration > 0.1:
                        logger.info(
                            "[LLMService] Rate limiter acquire: %.3fs for %s (%s)",
                            rate_limit_duration, model, actual_model
                        )

                    # Execute with retry and timeout
                    api_start = time.time()
                    async def _call():
                        # DeepSeek and Kimi use async_chat_completion
                        if hasattr(client, 'async_chat_completion'):
                            return await client.async_chat_completion(
                                messages=chat_messages,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                **kwargs
                            )
                        else:
                            # Qwen and Hunyuan use chat_completion
                            return await client.chat_completion(
                                messages=chat_messages,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                **kwargs
                            )

                    # Properly await with_retry inside timeout
                    response = await asyncio.wait_for(
                        error_handler.with_retry(_call),
                        timeout=timeout
                    )
                    api_duration = time.time() - api_start
                    # Always log API timing for Kimi to diagnose delays
                    if model == 'kimi' or api_duration > 2.0:
                        logger.info(
                            "[LLMService] API call duration: %.2fs for %s (%s)",
                            api_duration, model, actual_model
                        )
            else:
                # No rate limiting
                async def _call():
                    if hasattr(client, 'async_chat_completion'):
                        return await client.async_chat_completion(
                            messages=chat_messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            **kwargs
                        )
                    else:
                        return await client.chat_completion(
                            messages=chat_messages,
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

            logger.info("[LLMService] %s responded in %.2fs", model, duration)

            # Track token usage (async, non-blocking)
            if usage_data:
                try:
                    # Normalize token field names
                    # (API uses prompt_tokens/completion_tokens,
                    # we use input_tokens/output_tokens)
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
                        api_key_id=api_key_id,
                        session_id=session_id,
                        conversation_id=conversation_id,
                        endpoint_path=endpoint_path,
                        response_time=duration,
                        success=True
                    )
                except Exception as e:
                    logger.debug("[LLMService] Token tracking failed (non-critical): %s", e)

            # Record performance metrics
            self.performance_tracker.record_request(
                model=model,
                duration=duration,
                success=True
            )

            # Record provider metrics for load balancing (if DeepSeek)
            if provider and self.load_balancer:
                self.load_balancer.record_provider_metrics(
                    provider=provider,
                    success=True,
                    duration=duration
                )

            return content

        except ValueError:
            # Let ValueError pass through (e.g., invalid model)
            raise
        except Exception as e:
            duration = time.time() - start_time
            # Track failed request
            try:
                token_tracker = get_token_tracker()
                await token_tracker.track_usage(
                    model_alias=model,
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    request_type=request_type,
                    diagram_type=diagram_type,
                    user_id=user_id,
                    organization_id=organization_id,
                    session_id=session_id,
                    conversation_id=conversation_id,
                    endpoint_path=endpoint_path,
                    response_time=duration,
                    success=False
                )
            except Exception:
                pass  # Non-critical
            logger.error("[LLMService] %s failed after %.2fs: %s", model, duration, e)

            # Record failure metrics
            self.performance_tracker.record_request(
                model=model,
                duration=duration,
                success=False,
                error=str(e)
            )

            # Record provider metrics for load balancing (if DeepSeek)
            if provider and self.load_balancer:
                self.load_balancer.record_provider_metrics(
                    provider=provider,
                    success=False,
                    duration=duration,
                    error=str(e)
                )

            raise LLMServiceError("Chat failed for model %s: %s" % (model, e)) from e

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

        # Build messages array - support both single-turn (prompt) and multi-turn (messages)
        if messages is not None:
            # Multi-turn conversation: use provided messages directly
            chat_messages = list(messages)  # Copy to avoid mutation
        else:
            # Single-turn conversation: build from prompt and system_message
            chat_messages = []
            if system_message:
                chat_messages.append({"role": "system", "content": system_message})
            if prompt:
                chat_messages.append({"role": "user", "content": prompt})

        try:
            logger.debug("[LLMService] chat_with_usage() - model=%s, messages_count=%s", model, len(chat_messages))

            # Apply load balancing
            actual_model = model
            provider = None  # Track provider for metrics

            if self.load_balancer and self.load_balancer.enabled:
                actual_model = self.load_balancer.map_model(model)
                logger.debug("[LLMService] Load balanced: %s → %s", model, actual_model)
                # Track provider for DeepSeek load balancing metrics
                if model == 'deepseek':
                    provider = 'dashscope' if actual_model == 'deepseek' else 'volcengine'

            # Get client for actual model
            client = self.client_manager.get_client(actual_model)

            # Set timeout (per-model defaults)
            if timeout is None:
                timeout = self._get_default_timeout(model)

            # Get appropriate rate limiter
            rate_limiter = self._get_rate_limiter(model, actual_model, provider)

            if rate_limiter:
                async with rate_limiter:
                    async def _call():
                        if hasattr(client, 'async_chat_completion'):
                            return await client.async_chat_completion(
                                messages=chat_messages,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                **kwargs
                            )
                        else:
                            return await client.chat_completion(
                                messages=chat_messages,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                **kwargs
                            )

                    response = await asyncio.wait_for(
                        error_handler.with_retry(_call),
                        timeout=timeout
                    )
            else:
                async def _call():
                    if hasattr(client, 'async_chat_completion'):
                        return await client.async_chat_completion(
                            messages=chat_messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            **kwargs
                        )
                    else:
                        return await client.chat_completion(
                            messages=chat_messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            **kwargs
                        )

                response = await asyncio.wait_for(
                    error_handler.with_retry(_call),
                    timeout=timeout
                )

            # Validate response
            response = error_handler.validate_response(response)

            duration = time.time() - start_time

            # Extract content and usage from response
            content = response
            usage_data = {}

            if isinstance(response, dict):
                content = response.get('content', '')
                usage_data = response.get('usage', {})
            else:
                content = str(response)
                usage_data = {}

            logger.info("[LLMService] %s responded in %.2fs", model, duration)

            # Don't track tokens here - caller will track with correct diagram_type
            # Record performance metrics
            self.performance_tracker.record_request(
                model=model,
                duration=duration,
                success=True
            )

            # Record provider metrics for load balancing (if DeepSeek)
            if provider and self.load_balancer:
                self.load_balancer.record_provider_metrics(
                    provider=provider,
                    success=True,
                    duration=duration
                )

            return content, usage_data

        except ValueError:
            raise
        except Exception as e:
            duration = time.time() - start_time
            logger.error("[LLMService] %s failed after %.2fs: %s", model, duration, e)

            self.performance_tracker.record_request(
                model=model,
                duration=duration,
                success=False,
                error=str(e)
            )

            # Record provider metrics for load balancing (if DeepSeek)
            if provider and self.load_balancer:
                self.load_balancer.record_provider_metrics(
                    provider=provider,
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

        # Inject RAG context if enabled and user_id provided (before streaming starts)
        if use_knowledge_base and user_id and messages is None:
            try:
                rag_service = get_rag_service()
                db = SessionLocal()
                try:
                    # Check if user has knowledge base
                    if rag_service.has_knowledge_base(db, user_id):
                        # Retrieve context
                        context_chunks = rag_service.retrieve_context(
                            db=db,
                            user_id=user_id,
                            query=prompt,
                            top_k=5,
                            method='hybrid'
                        )
                        if context_chunks:
                            # Enhance prompt with context
                            prompt = rag_service.enhance_prompt(
                                user_id=user_id,
                                prompt=prompt,
                                context_chunks=context_chunks,
                                max_context_length=2000
                            )
                            logger.debug(
                                "[LLMService] Injected RAG context for "
                                "streaming: %s chunks",
                                len(context_chunks)
                            )
                finally:
                    db.close()
            except Exception as e:
                # If RAG fails, continue with original prompt
                logger.warning("[LLMService] RAG failed for streaming, using original prompt: %s", e)

        try:
            logger.debug("[LLMService] chat_stream() - model=%s, prompt_len=%s", model, len(prompt))

            # Apply load balancing (skip if already applied, e.g., from stream_progressive)
            actual_model = model
            provider = None  # Track provider for metrics

            if not skip_load_balancing and self.load_balancer and self.load_balancer.enabled:
                actual_model = self.load_balancer.map_model(model)
                logger.debug("[LLMService] Load balanced: %s → %s", model, actual_model)
                # Track provider for DeepSeek load balancing metrics
                if model == 'deepseek':
                    provider = 'dashscope' if actual_model == 'deepseek' else 'volcengine'
            elif skip_load_balancing:
                # Model is already a physical model from stream_progressive
                actual_model = model
                logger.debug("[LLMService] Skipping load balancing (already applied): %s", model)
                # Track provider from physical model name
                if self.load_balancer:
                    provider = self.load_balancer.get_provider_from_model(actual_model)

            # Get client for actual model
            client = self.client_manager.get_client(actual_model)

            # Build messages - use provided messages array if available, otherwise build from prompt
            if messages is not None:
                # Use provided messages directly (for multi-turn conversations)
                chat_messages = list(messages)  # Copy to avoid mutation
            else:
                # Build single-turn messages from prompt and system_message
                chat_messages = []
                if system_message:
                    chat_messages.append({"role": "system", "content": system_message})
                if prompt:
                    chat_messages.append({"role": "user", "content": prompt})

            # Set timeout
            if timeout is None:
                timeout = self._get_default_timeout(model)

            # Get appropriate rate limiter
            rate_limiter = self._get_rate_limiter(model, actual_model, provider)

            # Check if client supports streaming
            if hasattr(client, 'async_stream_chat_completion'):
                stream_method = client.async_stream_chat_completion
            elif hasattr(client, 'stream_chat_completion'):
                stream_method = client.stream_chat_completion
            else:
                # Fallback: get full response and yield it as one chunk
                # Use actual_model to ensure load balancing is applied
                # Note: This fallback path uses chat() which already has rate limiting
                response = await self.chat(
                    prompt=prompt,
                    model=actual_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    system_message=system_message,
                    **kwargs
                )
                yield response
                return

            # Stream the response with rate limiting and capture usage
            usage_data = None

            # Apply rate limiting if available
            if rate_limiter:
                # Time rate limiter operations to diagnose delays
                rate_limit_start = time.time()
                async with rate_limiter:
                    rate_limit_duration = time.time() - rate_limit_start
                    # Log rate limiter timing for debugging
                    if model == 'kimi' or rate_limit_duration > 0.1:
                        logger.info(
                            "[LLMService] Rate limiter acquire: %.3fs for %s (%s) [stream]",
                            rate_limit_duration, model, actual_model
                        )

                    # Stream with rate limiting applied
                    async for chunk in stream_method(
                        messages=chat_messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        enable_thinking=enable_thinking,
                        **kwargs
                    ):
                        # Handle new format: chunk can be dict with 'type' and content/usage
                        if isinstance(chunk, dict):
                            chunk_type = chunk.get('type', 'token')
                            if chunk_type == 'usage':
                                # Capture usage data from final chunk
                                usage_data = chunk.get('usage', {})
                                if yield_structured:
                                    yield chunk  # Forward usage to caller if structured mode
                            elif chunk_type == 'thinking':
                                # Yield thinking/reasoning content
                                if yield_structured:
                                    yield chunk
                                # Note: In non-structured mode, thinking is discarded
                                # (for backward compatibility with existing callers)
                            elif chunk_type == 'token':
                                # Yield content token
                                content = chunk.get('content', '')
                                if content:
                                    if yield_structured:
                                        yield chunk
                                    else:
                                        yield content
                        else:
                            # Backward compatibility: plain string chunk
                            yield chunk
            else:
                # Stream without rate limiting (if rate limiter not available)
                async for chunk in stream_method(
                    messages=chat_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    enable_thinking=enable_thinking,
                    **kwargs
                ):
                    # Handle new format: chunk can be dict with 'type' and content/usage
                    if isinstance(chunk, dict):
                        chunk_type = chunk.get('type', 'token')
                        if chunk_type == 'usage':
                            # Capture usage data from final chunk
                            usage_data = chunk.get('usage', {})
                            if yield_structured:
                                yield chunk  # Forward usage to caller if structured mode
                        elif chunk_type == 'thinking':
                            # Yield thinking/reasoning content
                            if yield_structured:
                                yield chunk
                            # Note: In non-structured mode, thinking is discarded
                            # (for backward compatibility with existing callers)
                        elif chunk_type == 'token':
                            # Yield content token
                            content = chunk.get('content', '')
                            if content:
                                if yield_structured:
                                    yield chunk
                                else:
                                    yield content
                    else:
                        # Backward compatibility: plain string chunk
                        yield chunk

            duration = time.time() - start_time
            logger.debug("[LLMService] %s stream completed in %.2fs", model, duration)

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
                    logger.debug("[LLMService] Token tracking failed (non-critical): %s", e)

            # Record performance metrics
            self.performance_tracker.record_request(
                model=model,
                duration=duration,
                success=True
            )

            # Record provider metrics for load balancing (if DeepSeek)
            if provider and self.load_balancer:
                self.load_balancer.record_provider_metrics(
                    provider=provider,
                    success=True,
                    duration=duration
                )

        except ValueError:
            # Let ValueError pass through (e.g., invalid model)
            raise
        except Exception as e:
            duration = time.time() - start_time
            logger.error("[LLMService] %s stream failed after %.2fs: %s", model, duration, e)

            # Record failure metrics
            self.performance_tracker.record_request(
                model=model,
                duration=duration,
                success=False,
                error=str(e)
            )

            # Record provider metrics for load balancing (if DeepSeek)
            if provider and self.load_balancer:
                self.load_balancer.record_provider_metrics(
                    provider=provider,
                    success=False,
                    duration=duration,
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
            'ark-deepseek': 70.0,  # Volcengine DeepSeek (Route B)
            'ark-kimi': 70.0,      # Volcengine Kimi (both routes)
            'hunyuan': 70.0,
            'kimi': 70.0,
            'doubao': 70.0,
            'chatglm': 70.0
        }
        return timeouts.get(model, 70.0)

    def get_available_models(self) -> List[str]:
        """
        Get list of all available models.

        When load balancing is enabled, filters out physical models (ark-*)
        to avoid redundant health checks and duplicate entries.
        """
        all_models = self.client_manager.get_available_models()

        # Filter out physical models when load balancing is enabled
        # This prevents health_check() from checking both 'deepseek' and 'ark-deepseek'
        if self.load_balancer and self.load_balancer.enabled:
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
        elif isinstance(e, (ConnectionError, TimeoutError)):
            return {
                'status': 'unhealthy',
                'error': 'Connection failed',
                'error_type': 'connection_error'
            }
        elif isinstance(e, asyncio.TimeoutError):
            return {
                'status': 'unhealthy',
                'error': 'Request timeout',
                'error_type': 'timeout'
            }
        elif isinstance(e, LLMServiceError):
            # Use error handler's categorization
            if isinstance(e, LLMRateLimitError):
                return {
                    'status': 'unhealthy',
                    'error': 'Rate limit exceeded',
                    'error_type': 'rate_limit'
                }
            elif isinstance(e, LLMQuotaExhaustedError):
                return {
                    'status': 'unhealthy',
                    'error': 'Quota exhausted',
                    'error_type': 'quota_exhausted'
                }
            else:
                return {
                    'status': 'unhealthy',
                    'error': 'Service unavailable',
                    'error_type': 'service_error'
                }
        else:
            # Generic error - don't expose details
            return {
                'status': 'unhealthy',
                'error': 'Service unavailable',
                'error_type': 'unknown'
            }

    async def _check_omni_health(self, model: str) -> Dict[str, Any]:
        """Check health of Omni model via WebSocket."""
        try:
            start = time.time()
            omni_client = self.client_manager.get_client('omni')

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
        """Check health of a single HTTP-based model."""
        try:
            start = time.time()
            await self.chat(
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
                logger.error("Health check exception for %s: %s", model, result, exc_info=True)
                results[model] = self._categorize_error(result)
            else:
                results[model] = result

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
                category='assistant',
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
        logger.debug("[LLMService] generate_multi() - %s models in parallel", len(models))

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
                logger.error("[LLMService] %s failed: %s", model, e)

        duration = time.time() - start_time
        successful = sum(1 for r in results.values() if r['success'])
        logger.info(
            "[LLMService] generate_multi() complete: %s/%s succeeded in %.2fs",
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

        logger.debug("[LLMService] generate_progressive() - %s models", len(models))

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
            # Get the task that completed from the awaited coro
            try:
                result = await coro
                # Find which model this result belongs to by checking completed tasks
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
                    logger.debug("[LLMService] %s completed in %.2fs", completed_model, result['duration'])

            except Exception as e:
                # Find which model failed
                failed_model = None
                for task, model in task_model_pairs:
                    if task.done() and task.exception() and not hasattr(task, '_yielded'):
                        task._yielded = True
                        failed_model = model
                        break

                if failed_model:
                    logger.error("[LLMService] %s failed: %s", failed_model, e)
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
            models: List of model names (default: ['qwen', 'deepseek', 'doubao'])
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
                models=['qwen', 'deepseek', 'doubao']
            ):
                if chunk['event'] == 'token':
                    print(f"{chunk['llm']}: {chunk['token']}", end='', flush=True)
                elif chunk['event'] == 'complete':
                    print(f"\n{chunk['llm']} done in {chunk['duration']:.2f}s")
                elif chunk['event'] == 'error':
                    print(f"\n{chunk['llm']} error: {chunk['error']}")
        """
        # NOTE: Hunyuan disabled due to 5 concurrent connection limit
        # NOTE: Kimi removed from node palette default - Volcengine server cannot handle load
        if models is None:
            models = ['qwen', 'deepseek', 'doubao']

        # Map logical models to physical models (each DeepSeek independently selects provider)
        physical_models = models
        # Map physical models back to logical names for responses
        physical_to_logical = {m: m for m in models}

        if self.load_balancer and self.load_balancer.enabled:
            physical_models = [
                self.load_balancer.map_model(m)
                for m in models
            ]
            # Create mapping for converting physical back to logical
            physical_to_logical = {
                physical: logical
                for logical, physical in zip(models, physical_models)
            }
            logger.info("[LLMService] stream_progressive: models=%s → %s", models, physical_models)

        logger.debug("[LLMService] stream_progressive() - streaming from %s models concurrently", len(physical_models))

        queue = asyncio.Queue()

        async def stream_single(physical_model: str):
            """Stream from one LLM, put chunks in queue."""
            start_time = time.time()
            token_count = 0

            try:
                # Use existing chat_stream (rate limiter & error handling automatic!)
                # Pass token tracking parameters
                # Skip load balancing since we already applied it in stream_progressive
                async for token in self.chat_stream(
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
                    skip_load_balancing=True,  # Skip since already balanced
                    **kwargs
                ):
                    token_count += 1
                    # Use logical model name for response (users shouldn't see 'ark-deepseek')
                    logical_model = physical_to_logical.get(physical_model, physical_model)
                    await queue.put({
                        'event': 'token',
                        'llm': logical_model,
                        'token': token,
                        'timestamp': time.time()
                    })

                # LLM completed successfully
                duration = time.time() - start_time
                # Use logical model name for response
                logical_model = physical_to_logical.get(physical_model, physical_model)
                await queue.put({
                    'event': 'complete',
                    'llm': logical_model,
                    'duration': duration,
                    'token_count': token_count,
                    'timestamp': time.time()
                })

                # Smart logging: summary only, no token spam
                tokens_per_sec = token_count / duration if duration > 0 else 0
                logger.info(
                    "[LLMService] %s stream complete - %s tokens in %.2fs (%.1f tok/s)",
                    logical_model, token_count, duration, tokens_per_sec
                )

            except Exception as e:
                duration = time.time() - start_time
                logical_model = physical_to_logical.get(physical_model, physical_model)
                logger.error("[LLMService] %s stream error: %s", logical_model, str(e))
                await queue.put({
                    'event': 'error',
                    'llm': logical_model,
                    'error': str(e),
                    'duration': duration,
                    'timestamp': time.time()
                })

        # Fire all LLM tasks concurrently
        tasks = [asyncio.create_task(stream_single(model)) for model in physical_models]

        completed = 0
        success_count = 0
        total_start = time.time()

        # Yield tokens as they arrive from queue
        # Use len(physical_models) to ensure we wait for all physical models to complete
        # (even though current mappings are 1:1, this is more correct)
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
            "[LLMService] stream_progressive() complete: %s/%s succeeded in %.2fs",
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

        logger.debug("[LLMService] generate_race() - first of %s models", len(models))

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

                    logger.debug("[LLMService] %s won the race in %.2fs", completed_model, result['duration'])

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
                        logger.debug("[LLMService] %s failed in race: %s", model, e)
                        break
                continue

        # All failed
        logger.error("[LLMService] All models failed in race")
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

    def _get_rate_limiter(self, model: str, actual_model: str, provider: Optional[str] = None) -> Optional[Any]:
        """
        Get the appropriate rate limiter for a model request.

        Args:
            model: Logical model name (e.g., 'deepseek', 'qwen')
            actual_model: Physical model name after load balancing (e.g., 'deepseek', 'ark-deepseek')
            provider: Provider name if known ('dashscope' or 'volcengine')

        Returns:
            Rate limiter instance or None
        """
        # For DeepSeek with load balancing, select appropriate rate limiter
        if model == 'deepseek':
            if provider == 'volcengine' or actual_model == 'ark-deepseek':
                # DeepSeek Volcengine route → use load balancer Volcengine limiter
                if self.load_balancer_rate_limiter and self.load_balancer_rate_limiter.enabled:
                    return self.load_balancer_rate_limiter.get_limiter('volcengine')
            elif provider == 'dashscope' or actual_model == 'deepseek':
                # DeepSeek Dashscope route → use shared Dashscope limiter (same as Qwen)
                return self.rate_limiter

        # For Kimi: use Volcengine endpoint-specific rate limiter
        if model == 'kimi' or actual_model == 'ark-kimi':
            if self.kimi_rate_limiter and self.kimi_rate_limiter.enabled:
                return self.kimi_rate_limiter

        # For Doubao: use Volcengine endpoint-specific rate limiter
        if model == 'doubao' or actual_model == 'ark-doubao':
            if self.doubao_rate_limiter and self.doubao_rate_limiter.enabled:
                return self.doubao_rate_limiter

        # For Qwen and other Dashscope models, use shared Dashscope rate limiter
        return self.rate_limiter

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

        CRITICAL: Circuit breaker tracks by PHYSICAL model name to prevent
        one failing route from blocking both routes in load balancing.
        """
        # Apply load balancing FIRST to get physical model name
        # Circuit breaker must track by physical model, not logical
        actual_model = model
        provider = None  # Track provider for metrics

        if self.load_balancer and self.load_balancer.enabled:
            actual_model = self.load_balancer.map_model(model)
            # Track provider from physical model name (for DeepSeek)
            provider = self.load_balancer.get_provider_from_model(actual_model)

        # Check circuit breaker using PHYSICAL model name
        # This ensures failures from one route don't block the other route
        if not self.performance_tracker.can_call_model(actual_model):
            logger.warning("[LLMService] Circuit breaker OPEN for %s, skipping call", actual_model)
            return {
                'response': None,
                'duration': 0.0,
                'success': False,
                'error': 'Circuit breaker open'
            }

        start_time = time.time()

        try:
            # Pass actual_model and skip load balancing since we already applied it
            # This ensures circuit breaker check and actual request use the same physical model
            # Note: chat() will track performance by the model parameter (actual_model/physical)
            # but we also track here by physical model for circuit breaker granularity
            response = await self.chat(
                prompt=prompt,
                model=actual_model,  # Pass physical model (chat() will track by this)
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                system_message=system_message,
                skip_load_balancing=True,  # Skip since already balanced
                **kwargs
            )

            duration = time.time() - start_time

            # Record success using PHYSICAL model name for circuit breaker tracking
            # chat() also tracks by actual_model (physical), but that's for general metrics
            # We track here specifically for circuit breaker granularity
            self.performance_tracker.record_request(
                model=actual_model,  # Use physical model for circuit breaker
                duration=duration,
                success=True
            )

            # Record provider metrics for load balancing (if DeepSeek)
            if provider and self.load_balancer:
                self.load_balancer.record_provider_metrics(
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

            # Record failure using PHYSICAL model name for circuit breaker tracking
            self.performance_tracker.record_request(
                model=actual_model,  # Use physical model for circuit breaker
                duration=duration,
                success=False,
                error=str(e)
            )

            # Record provider metrics for load balancing (if DeepSeek)
            if provider and self.load_balancer:
                self.load_balancer.record_provider_metrics(
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

    def get_fastest_model(self, models: Optional[List[str]] = None) -> Optional[str]:
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
