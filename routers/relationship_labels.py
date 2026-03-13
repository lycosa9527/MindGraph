"""
Relationship Labels API Router
==============================

SSE endpoints for concept map relationship label generation.
Catapult-style: fires 3 LLMs concurrently, streams labels progressively.

@author MindSpring Team
Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from agents.relationship_labels import get_relationship_labels_generator
from models.domain.auth import User
from models.requests.requests_thinking import (
    RelationshipLabelsStartRequest,
    RelationshipLabelsNextRequest,
    RelationshipLabelsCleanupRequest,
)
from services.infrastructure.http.error_handler import (
    LLMContentFilterError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMServiceError,
)
from utils.auth import get_current_user

router = APIRouter(tags=["thinking"])
logger = logging.getLogger(__name__)


async def _stream_labels(req, user: User | None, is_next: bool):
    """Async generator yielding SSE chunks from relationship labels generator."""
    generator = get_relationship_labels_generator()
    user_id = user.id if user and hasattr(user, 'id') else None
    org_id = getattr(user, 'organization_id', None) if user else None
    endpoint = (
        '/thinking_mode/relationship_labels/next_batch'
        if is_next
        else '/thinking_mode/relationship_labels/start'
    )
    chunk_count = 0
    try:
        async for chunk in generator.generate_batch(
            session_id=req.session_id,
            concept_a=req.concept_a,
            concept_b=req.concept_b,
            topic=req.topic or '',
            link_direction=req.link_direction,
            language=req.language or 'en',
            user_id=user_id,
            organization_id=org_id,
            endpoint_path=endpoint,
        ):
            chunk_count += 1
            yield f"data: {json.dumps(chunk)}\n\n"
    except LLMContentFilterError as e:
        msg = getattr(e, 'user_message', None) or (
            "无法处理您的请求。" if req.language == 'zh'
            else "Content could not be processed."
        )
        yield f"data: {json.dumps({'event': 'error', 'message': msg})}\n\n"
    except LLMRateLimitError as e:
        msg = getattr(e, 'user_message', None) or (
            "AI服务繁忙，请稍后重试。" if req.language == 'zh'
            else "AI service busy. Please retry."
        )
        yield f"data: {json.dumps({'event': 'error', 'message': msg})}\n\n"
    except LLMTimeoutError as e:
        msg = getattr(e, 'user_message', None) or (
            "请求超时，请重试。" if req.language == 'zh'
            else "Request timed out. Please retry."
        )
        yield f"data: {json.dumps({'event': 'error', 'message': msg})}\n\n"
    except LLMServiceError as e:
        msg = getattr(e, 'user_message', None) or (
            "AI服务错误，请稍后重试。" if req.language == 'zh'
            else "AI service error. Please retry."
        )
        yield f"data: {json.dumps({'event': 'error', 'message': msg})}\n\n"
    except Exception as e:
        logger.error("[RelLabels] Stream error: %s", str(e), exc_info=True)
        msg = "请求失败，请重试。" if req.language == 'zh' else "Request failed. Please retry."
        yield f"data: {json.dumps({'event': 'error', 'message': msg})}\n\n"
    finally:
        if chunk_count == 0:
            yield f"data: {json.dumps({'event': 'error', 'message': 'No response'})}\n\n"


@router.post('/thinking_mode/relationship_labels/start')
async def start_relationship_labels(
    req: RelationshipLabelsStartRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Start relationship labels generation - fires 3 LLMs concurrently.

    Returns SSE stream with label_generated events.
    """
    logger.debug(
        "[RelLabels] Start: %s | %s ↔ %s",
        req.session_id[:8], req.concept_a[:20], req.concept_b[:20]
    )
    return StreamingResponse(
        _stream_labels(req, current_user, is_next=False),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        },
    )


@router.post('/thinking_mode/relationship_labels/next_batch')
async def next_relationship_labels_batch(
    req: RelationshipLabelsNextRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Fetch next batch of relationship labels - fires 3 LLMs again.

    Called when user presses = to go to next page and more labels are needed.
    """
    logger.debug(
        "[RelLabels] Next batch: %s | %s ↔ %s",
        req.session_id[:8], req.concept_a[:20], req.concept_b[:20]
    )
    return StreamingResponse(
        _stream_labels(req, current_user, is_next=True),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        },
    )


@router.post('/thinking_mode/relationship_labels/cleanup')
async def cleanup_relationship_labels(
    req: RelationshipLabelsCleanupRequest,
    _current_user: User = Depends(get_current_user),
):
    """
    Clean up backend session state for given connection IDs.

    Called when connections are deleted or user leaves canvas to avoid memory leaks.
    """
    generator = get_relationship_labels_generator()
    for conn_id in req.connection_ids or []:
        generator.end_session(conn_id, reason="cleanup")
    logger.debug("[RelLabels] Cleanup: %d sessions", len(req.connection_ids or []))
    return {"status": "cleaned", "count": len(req.connection_ids or [])}
