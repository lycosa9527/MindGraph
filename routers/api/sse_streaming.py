"""SSE Streaming API Router.

API endpoint for Server-Sent Events streaming:
- /api/ai_assistant/stream: Stream AI assistant responses using Dify API

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import json
import logging
import time
from asyncio import CancelledError
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from clients.dify import DifyFile
from models import AIAssistantRequest, Messages, get_request_language
from models.domain.auth import User
from services.dify.org_mindmate_client import resolve_mindmate_dify_client_short_lived
from services.admin.user_usage_activity import schedule_user_usage_activity
from services.diagram.generation_session_registry import register_generation_session
from services.infrastructure.monitoring.mindmate_streaming import (
    mindmate_streaming_begin,
    mindmate_streaming_end,
)
from services.infrastructure.http.error_handler import (
    ThinkingCoinInsufficientError,
    UserDailyTokenCapExceededError,
)
from services.auth.thinking_coin.token_usage_link import build_mindmate_usage_snapshot
from services.auth.thinking_coin.usage_wire import (
    assert_llm_usage_budget,
    thinking_coin_post_llm_success_mutation,
    thinking_coins_apply_to_user,
)
from services.auth.thinking_coin.event_hub import mutation_to_footer
from services.redis.redis_activity_tracker import get_activity_tracker
from services.redis.redis_token_buffer import get_token_tracker
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.auth.user_daily_token_quota import daily_token_limit_message
from utils.auth import get_current_user_or_api_key
from utils.dify_mindmate_user_id import mindmate_dify_user_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


@router.post("/ai_assistant/stream")
async def ai_assistant_stream(
    req: AIAssistantRequest,
    request: Request,
    x_language: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key),
) -> StreamingResponse:
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
    if current_user and hasattr(current_user, "id"):
        try:
            tracker = get_activity_tracker()
            await tracker.record_activity(
                user_id=current_user.id,
                user_phone=getattr(current_user, "phone", None) or "",
                activity_type="ai_assistant",
                details={
                    "conversation_id": req.conversation_id,
                    "user_id": req.user_id,
                },
                user_name=getattr(current_user, "name", None),
            )
        except BACKGROUND_INFRA_ERRORS as e:
            logger.debug("Failed to track user activity: %s", e)

    # Handle Dify conversation opener trigger
    # When message is "start" with no conversation_id, this triggers Dify's opener
    if message.lower() == "start" and not req.conversation_id:
        logger.debug("[MindMate] Conversation opener triggered for user %s", req.user_id)
        logger.debug("[MindMate] Dify will respond with configured opening message")

    organization_id_for_dify = None
    if current_user and hasattr(current_user, "organization_id"):
        org_raw = getattr(current_user, "organization_id", None)
        organization_id_for_dify = int(org_raw) if org_raw is not None else None

    # Resolve Dify credentials in a short-lived session. Do not use Depends(get_async_db)
    # here: FastAPI keeps request-scoped sessions open until the SSE body finishes, which
    # leaves a read transaction idle past idle_in_transaction_session_timeout (30s default).
    dify_client = await resolve_mindmate_dify_client_short_lived(
        organization_id_for_dify,
        detail=Messages.error("ai_not_configured", lang),
    )
    logger.debug(
        "MindMate Dify client resolved for org_id=%s url=%s",
        organization_id_for_dify,
        dify_client.api_url,
    )

    message_preview = message[:50] + "..."
    logger.debug("AI assistant request from user %s: %s", req.user_id, message_preview)

    # Get user info for token tracking
    user_id_for_tracking = None
    organization_id_for_tracking = None
    if current_user and hasattr(current_user, "id"):
        user_id_for_tracking = current_user.id
        organization_id_for_tracking = getattr(current_user, "organization_id", None)

    dify_user_id = mindmate_dify_user_id(current_user) if current_user and hasattr(current_user, "id") else req.user_id

    stream_inputs: Dict[str, Any] = dict(req.inputs or {})
    stream_inputs["mg_dify_user"] = dify_user_id
    if req.conversation_id:
        stream_inputs["mg_conversation_id"] = req.conversation_id

    if current_user and hasattr(current_user, "id"):
        await register_generation_session(
            channel="mindmate",
            dify_user_id=dify_user_id,
            user_id=int(current_user.id),
            organization_id=organization_id_for_tracking,
            conversation_id=req.conversation_id,
        )

    async def generate():
        """Async generator function for SSE streaming."""
        logger.debug("[GENERATOR] Async generator function called - starting execution")

        # SSE comment first so the HTTP response is established before any await.
        # Matches node_palette_streaming: avoids ASGI/middleware issues when the
        # client aborts during the first await. EventSource ignores ':' lines.
        yield ": stream_open\n\n"

        chunk_count = 0
        cancelled = False
        no_chunk_response_sent = False
        streaming_counter_held = False
        start_time = time.time()
        captured_usage: Dict[str, Any] = {}
        captured_conversation_id: Optional[str] = None
        reply_parts: list[str] = []
        skip_activity_log = message.lower() == "start" and not req.conversation_id

        try:
            await mindmate_streaming_begin()
            streaming_counter_held = True
        except BACKGROUND_INFRA_ERRORS:
            logger.exception(
                "[STREAM] mindmate_streaming_begin failed after stream_open | user=%s",
                req.user_id,
            )
            err = {
                "event": "error",
                "error": "Internal server error",
                "timestamp": int(time.time() * 1000),
            }
            yield f"data: {json.dumps(err)}\n\n"
            return

        if user_id_for_tracking is not None:
            try:
                await assert_llm_usage_budget(
                    user_id_for_tracking,
                    organization_id_for_tracking,
                    "mindmate",
                    lang=lang,
                )
            except UserDailyTokenCapExceededError as cap_exc:
                err = {
                    "event": "error",
                    "error": daily_token_limit_message(lang, cap_exc.cap),
                    "error_type": "daily_token_cap",
                    "timestamp": int(time.time() * 1000),
                }
                yield f"data: {json.dumps(err)}\n\n"
                return
            except ThinkingCoinInsufficientError as coin_exc:
                err = {
                    "event": "error",
                    "error": coin_exc.user_message,
                    "error_type": "thinking_coin_insufficient",
                    "balance": coin_exc.balance,
                    "cost": coin_exc.cost,
                    "timestamp": int(time.time() * 1000),
                }
                yield f"data: {json.dumps(err)}\n\n"
                return

        try:
            client = dify_client

            dify_files = None
            if req.files:
                dify_files = [
                    DifyFile(
                        type=f.type,
                        transfer_method=f.transfer_method,
                        url=f.url,
                        upload_file_id=f.upload_file_id,
                    )
                    for f in req.files
                ]
                files_count = len(dify_files)
                logger.debug("[STREAM] Attached %s files to request", files_count)

            message_preview = message[:50] + "..."
            logger.debug("[STREAM] Starting async stream_chat for message: %s", message_preview)
            async for chunk in client.stream_chat(
                message=message,
                user_id=dify_user_id,
                conversation_id=req.conversation_id,
                files=dify_files,
                inputs=stream_inputs,
                auto_generate_name=req.auto_generate_name,
                workflow_id=req.workflow_id,
                trace_id=req.trace_id,
            ):
                chunk_count += 1
                event_type = chunk.get("event", "unknown")
                logger.debug("[STREAM] Received chunk %s: %s", chunk_count, event_type)

                chunk_conversation_id = chunk.get("conversation_id")
                if chunk_conversation_id and chunk_conversation_id != captured_conversation_id:
                    # New conversations have no id until Dify assigns one mid-stream; register the
                    # conversation-keyed session once it first appears so the generate_dingtalk tool
                    # can correlate by conversation_id (the start-of-stream dify_user_id registration
                    # already covers the first turn). Guard avoids re-writing on every chunk.
                    captured_conversation_id = chunk_conversation_id
                    if current_user and hasattr(current_user, "id"):
                        await register_generation_session(
                            channel="mindmate",
                            dify_user_id=dify_user_id,
                            user_id=int(current_user.id),
                            organization_id=organization_id_for_tracking,
                            conversation_id=captured_conversation_id,
                        )

                if event_type == "message_end":
                    metadata = chunk.get("metadata", {})
                    usage = metadata.get("usage", {})
                    if usage:
                        captured_usage = usage
                        logger.debug("[STREAM] Captured Dify usage: %s", usage)

                if event_type == "message":
                    answer_part = chunk.get("answer")
                    if isinstance(answer_part, str) and answer_part:
                        reply_parts.append(answer_part)

                yield f"data: {json.dumps(chunk)}\n\n"

            logger.debug("[STREAM] Streaming completed. Total chunks: %s", chunk_count)

            activity_total_tokens: Optional[int] = None
            usage_snapshot = None
            if captured_usage and user_id_for_tracking is not None:
                try:
                    input_tokens = captured_usage.get("prompt_tokens", 0)
                    output_tokens = captured_usage.get("completion_tokens", 0)
                    total_tokens = captured_usage.get("total_tokens", input_tokens + output_tokens)
                    activity_total_tokens = int(total_tokens) if total_tokens is not None else None
                    response_time = time.time() - start_time
                    coins_user = await thinking_coins_apply_to_user(
                        user_id_for_tracking,
                        organization_id_for_tracking,
                    )
                    if coins_user:
                        usage_snapshot = build_mindmate_usage_snapshot(
                            user_id=int(user_id_for_tracking),
                            organization_id=organization_id_for_tracking,
                            conversation_id=captured_conversation_id or req.conversation_id,
                            input_tokens=int(input_tokens),
                            output_tokens=int(output_tokens),
                            total_tokens=int(total_tokens) if total_tokens is not None else None,
                            response_time=response_time,
                        )
                    else:
                        token_tracker = get_token_tracker()
                        await token_tracker.track_usage(
                            model_alias="dify",
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            total_tokens=total_tokens,
                            request_type="mindmate",
                            user_id=user_id_for_tracking,
                            organization_id=organization_id_for_tracking,
                            conversation_id=captured_conversation_id or req.conversation_id,
                            endpoint_path="/api/ai_assistant/stream",
                            response_time=response_time,
                            success=True,
                        )
                    logger.debug(
                        "[STREAM] Tracked Dify token usage: input=%s, output=%s, total=%s",
                        input_tokens,
                        output_tokens,
                        total_tokens,
                    )
                except BACKGROUND_INFRA_ERRORS as track_error:
                    logger.warning("[STREAM] Failed to track token usage: %s", track_error)

            if user_id_for_tracking is not None:
                try:
                    coin_mutation = await thinking_coin_post_llm_success_mutation(
                        user_id_for_tracking,
                        organization_id_for_tracking,
                        "mindmate",
                        usage_snapshot,
                    )
                    if coin_mutation.eligible:
                        coins_event = json.dumps(
                            {
                                "event": "thinking_coins",
                                "thinking_coins": mutation_to_footer(coin_mutation),
                            }
                        )
                        yield f"data: {coins_event}\n\n"
                except BACKGROUND_INFRA_ERRORS as coin_error:
                    logger.warning("[STREAM] Thinking coin settle failed: %s", coin_error)

            if user_id_for_tracking and not skip_activity_log:
                schedule_user_usage_activity(
                    user_id=int(user_id_for_tracking),
                    organization_id=organization_id_for_tracking,
                    source="mindmate",
                    action="chat_turn",
                    prompt_preview=message,
                    reply_preview="".join(reply_parts) or None,
                    conversation_id=captured_conversation_id or req.conversation_id,
                    total_tokens=activity_total_tokens,
                )

            if chunk_count == 0:
                logger.warning(
                    "[STREAM] No chunks from Dify, sending synthetic completion | user=%s",
                    req.user_id,
                )
                complete_payload = {
                    "event": "message_complete",
                    "timestamp": int(time.time() * 1000),
                }
                yield f"data: {json.dumps(complete_payload)}\n\n"
                no_chunk_response_sent = True

        except CancelledError:
            cancelled = True
            no_chunk_response_sent = True
            logger.info(
                "[STREAM] Stream cancelled by client | user=%s | chunks=%s",
                req.user_id,
                chunk_count,
            )
            raise

        except BACKGROUND_INFRA_ERRORS as exc:
            logger.error(
                "[STREAM] AI assistant streaming error: %s",
                exc,
                exc_info=True,
            )
            error_data = {
                "event": "error",
                "error": "Internal server error",
                "timestamp": int(time.time() * 1000),
            }
            yield f"data: {json.dumps(error_data)}\n\n"
            no_chunk_response_sent = True

        finally:
            if streaming_counter_held:
                await mindmate_streaming_end()
            if streaming_counter_held and chunk_count == 0 and not no_chunk_response_sent and not cancelled:
                logger.warning(
                    "[STREAM] No Dify payload and no fallback SSE (after stream_open) | user=%s",
                    req.user_id,
                )

    logger.debug("[SETUP] Creating StreamingResponse with async generator")
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
