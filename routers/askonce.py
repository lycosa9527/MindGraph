from typing import List, Optional
import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from routers.auth.dependencies import get_current_user_optional
from services.llm import llm_service

"""
AskOnce Router - Multi-LLM Streaming Chat Endpoints
====================================================

Provides SSE streaming endpoints for simultaneous chat with multiple LLMs
(Qwen, DeepSeek, Kimi). Includes thinking process display for supported models.

Uses MindGraph's centralized LLM infrastructure:
- Rate limiting (prevents quota exhaustion)
- Load balancing (DeepSeek → Dashscope/Volcengine, Kimi → Volcengine)
- Error handling (comprehensive error parsing)
- Token tracking (automatic usage tracking)

Chinese name: 多应
English name: AskOnce

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""




logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/askonce", tags=["AskOnce"])

# ============================================================================
# Request/Response Models
# ============================================================================

class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class HealthResponse(BaseModel):
    status: str
    models: List[str]


# ============================================================================
# Model Configuration
# ============================================================================

ASKONCE_MODELS = {
    'qwen': {
        'model_name': 'qwen3-235b-a22b-thinking',
        'default_temperature': 0.9,
        'enable_thinking': True,
        'display_name': 'Qwen'
    },
    'deepseek': {
        # Load balanced: Dashscope=deepseek-v3.2, Volcengine=ep-20251222212434-cxpzb
        'model_name': 'deepseek-v3.2',
        'default_temperature': 0.6,
        'enable_thinking': True,
        'display_name': 'DeepSeek'
    },
    'kimi': {
        'model_name': 'ark-kimi',  # Always uses Volcengine endpoint ep-20251222212350-wxbks
        'default_temperature': 1.0,
        'enable_thinking': True,
        'display_name': 'Kimi'
    }
}


# ============================================================================
# Streaming Implementation (using LLMService)
# ============================================================================

async def stream_from_llm(
    model_id: str,
    messages: List[dict],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    user_id: Optional[int] = None
):
    """
    Stream chat completion from specified LLM using MindGraph's LLMService.

    Benefits:
    - Rate limiting (prevents quota exhaustion)
    - Load balancing (DeepSeek → Dashscope/Volcengine, Kimi → Volcengine)
    - Error handling (comprehensive error parsing)
    - Token tracking (automatic usage tracking)

    Yields SSE-formatted chunks:
    - {"type": "thinking", "content": "..."} - Reasoning/thinking content
    - {"type": "token", "content": "..."} - Response content
    - {"type": "usage", "usage": {...}} - Token usage stats
    - {"type": "done"} - Stream complete
    - {"type": "error", "error": "..."} - Error occurred
    """
    model_config = ASKONCE_MODELS.get(model_id)
    if not model_config:
        yield f'data: {json.dumps({"type": "error", "error": f"Unknown model: {model_id}"})}\n\n'
        return

    default_temp = model_config['default_temperature']
    enable_thinking = model_config['enable_thinking']

    # Use provided temperature or default
    if temperature is None:
        temperature = default_temp
    if max_tokens is None:
        max_tokens = 2000

    try:
        logger.debug("[ASKONCE:%s] Starting stream via LLMService with %s messages", model_id.upper(), len(messages))

        # Stream from LLMService with full messages array for proper multi-turn support
        async for chunk in llm_service.chat_stream(
            messages=messages,  # Pass full messages array for multi-turn context
            model=model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            enable_thinking=enable_thinking,
            yield_structured=True,  # Get structured chunks (thinking, token, usage)
            # Token tracking parameters
            user_id=user_id,
            request_type='askonce',
            endpoint_path=f'/api/askonce/stream/{model_id}'
        ):
            if isinstance(chunk, dict):
                chunk_type = chunk.get('type', 'token')

                if chunk_type == 'thinking':
                    # Forward thinking chunk as SSE
                    yield f'data: {json.dumps(chunk)}\n\n'
                elif chunk_type == 'token':
                    # Forward token chunk as SSE
                    yield f'data: {json.dumps(chunk)}\n\n'
                elif chunk_type == 'usage':
                    # Forward usage chunk as SSE
                    yield f'data: {json.dumps(chunk)}\n\n'
            else:
                # Plain string (backward compatibility)
                yield f'data: {json.dumps({"type": "token", "content": chunk})}\n\n'

        # Send done signal
        logger.info("[ASKONCE:%s] Stream complete", model_id.upper())
        yield f'data: {json.dumps({"type": "done"})}\n\n'

    except asyncio.CancelledError:
        logger.info("[ASKONCE:%s] Stream cancelled by client", model_id.upper())
        raise
    except Exception as e:
        logger.error("[ASKONCE:%s] Streaming error: %s", model_id.upper(), e)
        yield f'data: {json.dumps({"type": "error", "error": str(e)})}\n\n'


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for AskOnce service."""
    return HealthResponse(
        status="healthy",
        models=list(ASKONCE_MODELS.keys())
    )


@router.get("/models")
async def get_models():
    """Get available models with their display names."""
    return {
        "models": [
            {"id": model_id, "name": cfg["display_name"], "model": cfg["model_name"]}
            for model_id, cfg in ASKONCE_MODELS.items()
        ]
    }


@router.post("/stream/{model}")
async def stream_chat(
    model: str,
    chat_request: ChatRequest,
    current_user = Depends(get_current_user_optional)
):
    """
    Stream chat completion from specified LLM.

    Uses MindGraph's centralized LLM infrastructure with:
    - Rate limiting (prevents quota exhaustion)
    - Load balancing (DeepSeek → Dashscope/Volcengine, Kimi → Volcengine)
    - Error handling (comprehensive error parsing)
    - Token tracking (automatic usage tracking)

    Supports thinking process display for DeepSeek R1, Qwen3, and Kimi K2.

    Args:
        model: LLM identifier (qwen, deepseek, kimi)
        chat_request: Chat messages and parameters

    Returns:
        StreamingResponse with SSE-formatted chunks
    """
    # Validate model
    if model not in ASKONCE_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model: {model}. Available: {', '.join(ASKONCE_MODELS.keys())}"
        )

    # Convert messages to dict format
    messages = [{"role": m.role, "content": m.content} for m in chat_request.messages]

    # Get user ID for token tracking
    user_id = current_user.id if current_user else None

    # Log request (user ID if authenticated)
    user_info = f"user={user_id}" if user_id else "anonymous"
    logger.info(
        "[ASKONCE:%s] Starting stream (%s messages, %s)",
        model.upper(),
        len(messages),
        user_info
    )

    return StreamingResponse(
        stream_from_llm(
            model_id=model,
            messages=messages,
            temperature=chat_request.temperature,
            max_tokens=chat_request.max_tokens,
            user_id=user_id
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
