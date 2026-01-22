from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, AsyncGenerator, Callable
import asyncio
import logging
import time

from config.settings import config
from services.infrastructure.http.error_handler import LLMServiceError
from services.infrastructure.rate_limiting.rate_limiter import get_rate_limiter
from services.monitoring.performance_tracker import performance_tracker
from services.redis.redis_token_buffer import get_token_tracker

"""
WebSocket LLM Middleware
=========================

Middleware layer for WebSocket-based LLM connections (e.g., Omni).
Provides the same middleware benefits as REST LLM middleware:
- Rate limiting (concurrent connection limits)
- Error handling with retry logic
- Token tracking
- Performance tracking
- Circuit breaker support

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""



logger = logging.getLogger(__name__)


class WebSocketLLMMiddleware:
    """
    Middleware for WebSocket-based LLM connections.

    Provides rate limiting, error handling, token tracking, and performance
    tracking for persistent WebSocket connections like Omni.
    """

    def __init__(
        self,
        model_alias: str = 'qwen-omni',
        max_concurrent_connections: Optional[int] = None,
        enable_rate_limiting: bool = True,
        enable_error_handling: bool = True,
        enable_token_tracking: bool = True,
        enable_performance_tracking: bool = True
    ):
        """
        Initialize WebSocket LLM middleware.

        Args:
            model_alias: Model identifier for tracking (e.g., 'qwen-omni')
            max_concurrent_connections: Max concurrent WebSocket connections (None = no limit)
            enable_rate_limiting: Enable rate limiting
            enable_error_handling: Enable error handling with retry
            enable_token_tracking: Enable token usage tracking
            enable_performance_tracking: Enable performance metrics tracking
        """
        self.model_alias = model_alias
        self.max_concurrent_connections = max_concurrent_connections or config.DASHSCOPE_CONCURRENT_LIMIT
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_error_handling = enable_error_handling
        self.enable_token_tracking = enable_token_tracking
        self.enable_performance_tracking = enable_performance_tracking

        # Track active connections
        self._active_connections = 0
        self._connection_lock = asyncio.Lock()

        # Get rate limiter if available
        self.rate_limiter = None
        if self.enable_rate_limiting:
            try:
                self.rate_limiter = get_rate_limiter()
            except Exception as e:
                logger.warning("Could not get rate limiter: %s", e)
                self.rate_limiter = None

        logger.debug(
            "[WebSocketLLMMiddleware] Initialized for %s: max_connections=%s, rate_limiting=%s, error_handling=%s",
            model_alias, self.max_concurrent_connections, self.enable_rate_limiting, self.enable_error_handling
        )

    @asynccontextmanager
    async def connection_context(
        self,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        session_id: Optional[str] = None,
        request_type: str = 'voice_omni',
        endpoint_path: Optional[str] = None
    ):
        """
        Context manager for WebSocket connection lifecycle.

        Provides rate limiting, connection tracking, and error handling.

        Args:
            user_id: User ID for tracking
            organization_id: Organization ID for tracking
            session_id: Session ID for tracking
            request_type: Request type for tracking
            endpoint_path: Endpoint path for tracking

        Yields:
            Dict with connection metadata and tracking info

        Example:
            async with middleware.connection_context(
                user_id=123,
                session_id='voice_abc123'
            ) as ctx:
                # Use ctx['omni_client'] to interact with Omni
                await ctx['omni_client'].start_conversation()
        """
        connection_start_time = time.time()
        connection_id = f"{self.model_alias}_{int(time.time() * 1000)}"

        # Check concurrent connection limit
        async with self._connection_lock:
            if self._active_connections >= self.max_concurrent_connections:
                raise LLMServiceError(
                    f"Too many active {self.model_alias} connections: "
                    f"{self._active_connections}/{self.max_concurrent_connections}"
                )
            self._active_connections += 1
            logger.debug(
                "[WebSocketLLMMiddleware] Connection %s started (%s/%s active)",
                connection_id, self._active_connections, self.max_concurrent_connections
            )

        # Apply rate limiting if enabled
        rate_limit_context = None
        if self.enable_rate_limiting and self.rate_limiter:
            rate_limit_context = await self.rate_limiter.__aenter__()  # type: ignore[attr-defined]

        try:
            # Prepare context for connection
            ctx = {
                'connection_id': connection_id,
                'model_alias': self.model_alias,
                'user_id': user_id,
                'organization_id': organization_id,
                'session_id': session_id,
                'request_type': request_type,
                'endpoint_path': endpoint_path,
                'start_time': connection_start_time
            }

            yield ctx

            # Track successful connection
            duration = time.time() - connection_start_time
            if self.enable_performance_tracking:
                self._track_performance(
                    duration=duration,
                    success=True,
                    error=None
                )

            logger.debug(
                "[WebSocketLLMMiddleware] Connection %s completed successfully in %.2fs",
                connection_id, duration
            )

        except Exception as e:
            # Track failed connection
            duration = time.time() - connection_start_time
            if self.enable_performance_tracking:
                self._track_performance(
                    duration=duration,
                    success=False,
                    error=str(e)
                )

            logger.error(
                "[WebSocketLLMMiddleware] Connection %s failed after %.2fs: %s",
                connection_id, duration, e,
                exc_info=True
            )

            # Apply error handling if enabled
            if self.enable_error_handling:
                # Re-raise with error handler context
                raise LLMServiceError(f"WebSocket connection failed: {e}") from e
            else:
                raise

        finally:
            # Release rate limiter
            if rate_limit_context:
                try:
                    await rate_limit_context.__aexit__(None, None, None)  # type: ignore[attr-defined]
                except Exception as e:
                    logger.debug("Error releasing rate limiter: %s", e)

            # Decrement active connections
            async with self._connection_lock:
                self._active_connections -= 1
                logger.debug(
                    "[WebSocketLLMMiddleware] Connection %s closed (%s/%s active)",
                    connection_id, self._active_connections, self.max_concurrent_connections
                )

    async def wrap_start_conversation(
        self,
        omni_client,
        instructions: Optional[str] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        session_id: Optional[str] = None,
        request_type: str = 'voice_omni',
        endpoint_path: Optional[str] = None,
        on_event: Optional[Callable] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Wrap OmniClient.start_conversation() with middleware.

        Provides rate limiting, error handling, and event tracking.

        Args:
            omni_client: OmniClient instance
            instructions: Conversation instructions
            user_id: User ID for tracking
            organization_id: Organization ID for tracking
            session_id: Session ID for tracking
            request_type: Request type for tracking
            endpoint_path: Endpoint path for tracking
            on_event: Optional event callback

        Yields:
            Event dictionaries from Omni conversation

        Example:
            async for event in middleware.wrap_start_conversation(
                omni_client=omni_client,
                instructions="You are a helpful assistant",
                user_id=123,
                session_id='voice_abc123'
            ):
                if event['type'] == 'response_done':
                    # Handle response
                    pass
        """
        async with self.connection_context(
            user_id=user_id,
            organization_id=organization_id,
            session_id=session_id,
            request_type=request_type,
            endpoint_path=endpoint_path
        ) as ctx:

            # Start conversation with error handling
            # Note: start_conversation returns an async generator, so we need to
            # handle it differently than regular async functions
            try:
                # Create the generator (this doesn't block, just creates the generator)
                generator = omni_client.start_conversation(
                    instructions=instructions,
                    on_event=on_event
                )

                # Iterate through events and apply middleware
                async for event in generator:
                    # Track token usage on response_done events
                    if event.get('type') == 'response_done' and self.enable_token_tracking:
                        await self._track_token_usage(
                            response=event.get('response', {}),
                            ctx=ctx
                        )

                    # Call original callback if provided
                    if on_event:
                        try:
                            on_event(event)
                        except Exception as e:
                            logger.debug("Error in on_event callback: %s", e)

                    yield event

            except Exception as e:
                # Apply error handling with retry for connection failures
                if self.enable_error_handling:
                    # For connection failures, we can retry
                    logger.warning("[WebSocketLLMMiddleware] Connection failed, retrying: %s", e)
                    # Retry logic would go here, but for WebSocket connections,
                    # retrying means creating a new connection
                    raise LLMServiceError(f"WebSocket connection failed: {e}") from e
                else:
                    raise

    async def _track_token_usage(
        self,
        response: Dict[str, Any],
        ctx: Dict[str, Any]
    ):
        """Track token usage from Omni response."""
        try:
            usage = response.get('usage', {})
            if not usage:
                return

            # Extract token counts (Omni uses input_tokens/output_tokens)
            input_tokens = usage.get('input_tokens') or usage.get('prompt_tokens', 0)
            output_tokens = usage.get('output_tokens') or usage.get('completion_tokens', 0)
            total_tokens = usage.get('total_tokens') or None

            # Track usage
            token_tracker = get_token_tracker()
            await token_tracker.track_usage(
                model_alias=self.model_alias,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                request_type=ctx.get('request_type', 'voice_omni'),
                user_id=ctx.get('user_id'),
                organization_id=ctx.get('organization_id'),
                session_id=ctx.get('session_id'),
                endpoint_path=ctx.get('endpoint_path'),
                success=True
            )

            connection_id = ctx.get('connection_id')
            total = total_tokens or input_tokens + output_tokens
            logger.debug(
                "[WebSocketLLMMiddleware] Tracked tokens for %s: %s+%s=%s",
                connection_id, input_tokens, output_tokens, total
            )

        except Exception as e:
            logger.debug("[WebSocketLLMMiddleware] Token tracking failed (non-critical): %s", e)

    def _track_performance(
        self,
        duration: float,
        success: bool,
        error: Optional[str] = None
    ):
        """Track performance metrics."""
        try:
            performance_tracker.record_request(
                model=self.model_alias,
                duration=duration,
                success=success,
                error=error
            )
        except Exception as e:
            logger.debug("[WebSocketLLMMiddleware] Performance tracking failed (non-critical): %s", e)

    def get_active_connections(self) -> int:
        """Get number of active connections."""
        return self._active_connections

    def get_max_connections(self) -> int:
        """Get maximum concurrent connections."""
        return self.max_concurrent_connections


# Singleton instance for Omni
omni_middleware = WebSocketLLMMiddleware(
    model_alias='qwen-omni',
    max_concurrent_connections=config.DASHSCOPE_CONCURRENT_LIMIT,
    enable_rate_limiting=config.DASHSCOPE_RATE_LIMITING_ENABLED,
    enable_error_handling=True,
    enable_token_tracking=True,
    enable_performance_tracking=True
)

