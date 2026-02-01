"""SSE Streaming API Router.

API endpoint for Server-Sent Events streaming:
- /api/ai_assistant/stream: Stream AI assistant responses using Dify API

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional
import json
import logging
import os
import time
import traceback

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse

from clients.dify import AsyncDifyClient, DifyFile
from models import AIAssistantRequest, Messages, get_request_language
from models.domain.auth import User
from services.redis.redis_activity_tracker import get_activity_tracker
from services.redis.redis_token_buffer import get_token_tracker
from utils.auth import get_current_user_or_api_key


logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


@router.post('/ai_assistant/stream')
async def ai_assistant_stream(
    req: AIAssistantRequest,
    request: Request,
    x_language: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Stream AI assistant responses using Dify API with SSE (async version).

    This is the CRITICAL endpoint for supporting 100+ concurrent SSE connections.
    Uses AsyncDifyClient for non-blocking streaming.
    """

    # Get language for error messages
    accept_language = request.headers.get("Accept-Language", "")
    lang = get_request_language(x_language, accept_language)

    # Get message
    message = req.message.strip()

    # Track user activity
    if current_user and hasattr(current_user, 'id'):
        try:
            tracker = get_activity_tracker()
            tracker.record_activity(
                user_id=current_user.id,
                user_phone=getattr(current_user, 'phone', None) or "",
                activity_type='ai_assistant',
                details={'conversation_id': req.conversation_id, 'user_id': req.user_id},
                user_name=getattr(current_user, 'name', None)
            )
        except Exception as e:
            logger.debug("Failed to track user activity: %s", e)

    # Handle Dify conversation opener trigger
    # When message is "start" with no conversation_id, this triggers Dify's opener
    if message.lower() == 'start' and not req.conversation_id:
        logger.debug("[MindMate] Conversation opener triggered for user %s", req.user_id)
        logger.debug("[MindMate] Dify will respond with configured opening message")

    # Get Dify configuration from environment
    api_key = os.getenv('DIFY_API_KEY')
    api_url = os.getenv('DIFY_API_URL', 'https://api.dify.ai/v1')
    timeout = int(os.getenv('DIFY_TIMEOUT', '30'))

    has_api_key = bool(api_key)
    logger.debug("Dify Configuration - API URL: %s, Has API Key: %s, Timeout: %s", api_url, has_api_key, timeout)

    if not api_key:
        logger.error("DIFY_API_KEY not configured in environment")
        raise HTTPException(
            status_code=500,
            detail=Messages.error("ai_not_configured", lang)
        )

    message_preview = message[:50] + "..."
    logger.debug("AI assistant request from user %s: %s", req.user_id, message_preview)

    # Get user info for token tracking
    user_id_for_tracking = None
    organization_id_for_tracking = None
    if current_user and hasattr(current_user, 'id'):
        user_id_for_tracking = current_user.id
        organization_id_for_tracking = getattr(current_user, 'organization_id', None)

    async def generate():
        """Async generator function for SSE streaming"""
        logger.debug("[GENERATOR] Async generator function called - starting execution")
        chunk_count = 0  # Initialize outside try block for finally access
        start_time = time.time()
        captured_usage: Dict[str, Any] = {}  # Store usage from message_end
        captured_conversation_id: Optional[str] = None

        try:
            logger.debug("[STREAM] Creating AsyncDifyClient with URL: %s", api_url)
            client = AsyncDifyClient(api_key=api_key, api_url=api_url, timeout=timeout)
            logger.debug("[STREAM] AsyncDifyClient created successfully")

            # Convert request files to DifyFile objects
            dify_files = None
            if req.files:
                dify_files = [
                    DifyFile(
                        type=f.type,
                        transfer_method=f.transfer_method,
                        url=f.url,
                        upload_file_id=f.upload_file_id
                    )
                    for f in req.files
                ]
                files_count = len(dify_files)
                logger.debug("[STREAM] Attached %s files to request", files_count)

            message_preview = message[:50] + "..."
            logger.debug("[STREAM] Starting async stream_chat for message: %s", message_preview)
            async for chunk in client.stream_chat(
                message=message,
                user_id=req.user_id,
                conversation_id=req.conversation_id,
                files=dify_files,
                inputs=req.inputs,
                auto_generate_name=req.auto_generate_name,
                workflow_id=req.workflow_id,
                trace_id=req.trace_id
            ):
                chunk_count += 1
                event_type = chunk.get('event', 'unknown')
                logger.debug("[STREAM] Received chunk %s: %s", chunk_count, event_type)

                # Capture conversation_id from any event
                if chunk.get('conversation_id'):
                    captured_conversation_id = chunk.get('conversation_id')

                # Capture usage data from message_end event
                if event_type == 'message_end':
                    metadata = chunk.get('metadata', {})
                    usage = metadata.get('usage', {})
                    if usage:
                        captured_usage = usage
                        logger.debug("[STREAM] Captured Dify usage: %s", usage)

                # Format as SSE
                yield f"data: {json.dumps(chunk)}\n\n"

            logger.debug("[STREAM] Streaming completed. Total chunks: %s", chunk_count)

            # Track token usage after streaming completes
            if captured_usage:
                try:
                    token_tracker = get_token_tracker()
                    input_tokens = captured_usage.get('prompt_tokens', 0)
                    output_tokens = captured_usage.get('completion_tokens', 0)
                    total_tokens = captured_usage.get('total_tokens', input_tokens + output_tokens)
                    response_time = time.time() - start_time

                    await token_tracker.track_usage(
                        model_alias='dify',
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        request_type='mindmate',
                        user_id=user_id_for_tracking,
                        organization_id=organization_id_for_tracking,
                        conversation_id=captured_conversation_id or req.conversation_id,
                        endpoint_path='/api/ai_assistant/stream',
                        response_time=response_time,
                        success=True
                    )
                    logger.debug(
                        "[STREAM] Tracked Dify token usage: input=%s, output=%s, total=%s",
                        input_tokens, output_tokens, total_tokens
                    )
                except Exception as track_error:
                    logger.warning("[STREAM] Failed to track token usage: %s", track_error)

            # Ensure at least one event is yielded to prevent RuntimeError
            if chunk_count == 0:
                logger.warning("[STREAM] No chunks yielded, sending completion event")
                yield f"data: {json.dumps({'event': 'message_complete', 'timestamp': int(time.time() * 1000)})}\n\n"

        except Exception as e:
            logger.error("[STREAM] AI assistant streaming error: %s", e, exc_info=True)
            logger.error("[STREAM] Full traceback: %s", traceback.format_exc())
            error_data = {
                'event': 'error',
                'error': str(e),
                'error_type': type(e).__name__,
                'timestamp': int(time.time() * 1000)
            }
            yield f"data: {json.dumps(error_data)}\n\n"
            chunk_count += 1  # Count error event as a chunk
        finally:
            # Always ensure at least one event is yielded to prevent RuntimeError
            if chunk_count == 0:
                logger.warning("[STREAM] Generator completed without yielding, sending error event")
                error_data = {
                    'event': 'error',
                    'error': 'No response returned from stream',
                    'error_type': 'NoResponse',
                    'timestamp': int(time.time() * 1000)
                }
                yield f"data: {json.dumps(error_data)}\n\n"

    logger.debug("[SETUP] Creating StreamingResponse with async generator")
    return StreamingResponse(
        generate(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )
