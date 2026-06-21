"""Diagram Generation API Router.

API endpoint for diagram generation:
- /api/generate_graph: Generate graph specification from user prompt
- /api/generate_graph/stream: SSE phase events for auto-complete only

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import json
import logging
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from agents.core.workflow import agent_graph_workflow_with_styles
from models import GenerateRequest, GenerateResponse, Messages, get_request_language
from models.domain.auth import User
from models.domain.diagrams import Diagram
from services.admin.user_usage_activity import schedule_user_usage_activity
from services.auth.thinking_coin.usage_wire import thinking_coin_post_diagram_generation
from services.infrastructure.http.error_handler import (
    LLMContentFilterError,
    LLMRateLimitError,
    LLMServiceError,
    LLMTimeoutError,
    ThinkingCoinInsufficientError,
)
from services.monitoring.activity_stream import get_activity_stream_service
from services.redis.redis_activity_tracker import get_activity_tracker
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.auth import get_current_user_or_api_key, is_superadmin
from utils.db.session_open import system_rls_session

from .helpers import check_endpoint_rate_limit, get_rate_limit_identifier

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


async def _query_diagram_ownership(diagram_id):
    """Query diagram ownership info using a short-lived async session."""
    async with system_rls_session() as db:
        result = await db.execute(select(Diagram).where(Diagram.id == diagram_id, ~Diagram.is_deleted))
        diagram = result.scalar_one_or_none()
        if diagram:
            return diagram.workshop_code, diagram.user_id
        return None, None


def _build_workflow_kwargs(req: GenerateRequest, prepared: dict[str, Any]) -> dict[str, Any]:
    """Build kwargs for agent_graph_workflow_with_styles from request + prepared context."""
    return {
        "user_prompt": prepared["prompt"],
        "language": prepared["language"],
        "forced_diagram_type": req.diagram_type.value if req.diagram_type else None,
        "dimension_preference": req.dimension_preference,
        "model": prepared["llm_model"],
        "user_id": prepared["user_id"],
        "organization_id": prepared["organization_id"],
        "request_type": prepared["request_type"],
        "endpoint_path": prepared["endpoint_path"],
        "existing_analogies": req.existing_analogies if hasattr(req, "existing_analogies") else None,
        "fixed_dimension": req.fixed_dimension if hasattr(req, "fixed_dimension") else None,
        "dimension_only_mode": req.dimension_only_mode if hasattr(req, "dimension_only_mode") else None,
        "concept_map_relationship_only": (
            req.concept_map_relationship_only if hasattr(req, "concept_map_relationship_only") else None
        ),
        "concept_a": req.concept_a if hasattr(req, "concept_a") else None,
        "concept_b": req.concept_b if hasattr(req, "concept_b") else None,
        "concept_map_topic": req.concept_map_topic if hasattr(req, "concept_map_topic") else None,
        "link_direction": req.link_direction if hasattr(req, "link_direction") else None,
        "use_rag": req.use_rag if req.use_rag else False,
        "rag_top_k": req.rag_top_k if req.rag_top_k else 5,
    }


async def _prepare_generate_graph(
    req: GenerateRequest,
    request: Request,
    current_user: Optional[User],
    x_language: Optional[str],
    *,
    endpoint_path: str,
) -> dict[str, Any]:
    """Shared rate limit, collab owner check, and request context for generate_graph handlers."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("generate_graph", identifier, max_requests=100, window_seconds=60)

    if req.diagram_id and current_user:
        workshop_code, diagram_user_id = await _query_diagram_ownership(req.diagram_id)
        if workshop_code:
            if not is_superadmin(current_user) and diagram_user_id != current_user.id:
                raise HTTPException(
                    status_code=403,
                    detail=("Only the diagram owner can use AI generation during collaboration"),
                )

    accept_language = request.headers.get("Accept-Language", "")
    lang = get_request_language(x_language, accept_language)
    language = req.language

    prompt = (req.prompt or "").strip()
    generation_instructions = (req.generation_instructions or "").strip()
    if generation_instructions:
        if req.language.startswith("zh"):
            marker = "【用户要求】"
        else:
            marker = "User requirements:"
        if prompt:
            prompt = f"{prompt}\n\n{marker}\n{generation_instructions}"
        else:
            prompt = generation_instructions
    request_id = f"gen_{int(time.time() * 1000)}"
    llm_model = req.llm.value if hasattr(req.llm, "value") else str(req.llm)

    logger.debug(
        "[%s] Request: llm=%r, language=%r, diagram_type=%s",
        request_id,
        llm_model,
        language,
        req.diagram_type,
    )

    if req.dimension_preference:
        logger.debug("[%s] Dimension preference: %r", request_id, req.dimension_preference)

    user_id = current_user.id if current_user and hasattr(current_user, "id") else None
    organization_id = (
        getattr(current_user, "organization_id", None) if current_user and hasattr(current_user, "id") else None
    )
    request_type = req.request_type if req.request_type else "diagram_generation"

    request.state.is_autocomplete = request_type == "autocomplete"

    if current_user and hasattr(current_user, "id"):
        try:
            tracker = get_activity_tracker()
            activity_type = "autocomplete" if request_type == "autocomplete" else "diagram_generation"
            diagram_type_str = req.diagram_type.value if req.diagram_type else "unknown"
            await tracker.record_activity(
                user_id=current_user.id,
                user_phone=getattr(current_user, "phone", None) or "",
                activity_type=activity_type,
                details={"diagram_type": diagram_type_str, "llm_model": llm_model},
                user_name=getattr(current_user, "name", None),
            )
        except BACKGROUND_INFRA_ERRORS as e:
            logger.debug("Failed to track user activity: %s", e)

    if request_type == "autocomplete":
        diagram_type_str = req.diagram_type.value if req.diagram_type else "auto"
        logger.info(
            "[AutoComplete] Started: User %s, Diagram: %s, Model: %s, Request: %s",
            user_id,
            diagram_type_str,
            llm_model,
            request_id[:8],
        )

    prepared: dict[str, Any] = {
        "lang": lang,
        "prompt": prompt,
        "request_id": request_id,
        "llm_model": llm_model,
        "language": language,
        "user_id": user_id,
        "organization_id": organization_id,
        "request_type": request_type,
        "endpoint_path": endpoint_path,
        "req": req,
        "current_user": current_user,
    }
    prepared["workflow_kwargs"] = _build_workflow_kwargs(req, prepared)
    return prepared


async def _finalize_generate_graph_result(result: dict[str, Any], prepared: dict[str, Any]) -> dict[str, Any]:
    """Post-process workflow result: logging, activity broadcast, metadata."""
    req = prepared["req"]
    prompt = prepared["prompt"]
    user_id = prepared["user_id"]
    organization_id = prepared["organization_id"]
    request_type = prepared["request_type"]
    request_id = prepared["request_id"]
    llm_model = prepared["llm_model"]
    current_user = prepared["current_user"]

    diagram_type = result.get("diagram_type", "unknown")
    logger.debug("[%s] Generated %s diagram with %s", request_id, diagram_type, llm_model)

    if request_type == "autocomplete":
        node_count = len(result.get("nodes", [])) if isinstance(result.get("nodes"), list) else 0
        logger.info(
            "[AutoComplete] Completed: User %s, Diagram %s, Nodes added: %d, Model: %s, Request: %s",
            user_id,
            diagram_type,
            node_count,
            llm_model,
            request_id[:8],
        )

    if user_id:
        try:
            activity_service = get_activity_stream_service()
            user_name = getattr(current_user, "name", None) if current_user else None

            topic_display = prompt[:50]
            if diagram_type == "double_bubble_map":
                spec = result.get("spec", {})
                if isinstance(spec, dict):
                    left = spec.get("left", "")
                    right = spec.get("right", "")
                    if left and right:
                        topic_display = f"{left} vs {right}"
                    elif left or right:
                        topic_display = left or right

            await activity_service.broadcast_activity(
                user_id=user_id,
                action="generated",
                diagram_type=diagram_type,
                topic=topic_display[:50],
                user_name=user_name,
            )
        except BACKGROUND_INFRA_ERRORS as e:
            logger.debug("Failed to broadcast activity: %s", e)

    if user_id and request_type != "autocomplete":
        topic_for_activity = prompt[:50] if prompt else ""
        if diagram_type == "double_bubble_map":
            spec_data = result.get("spec", {})
            if isinstance(spec_data, dict):
                left = spec_data.get("left", "")
                right = spec_data.get("right", "")
                if left and right:
                    topic_for_activity = f"{left} vs {right}"
                elif left or right:
                    topic_for_activity = str(left or right)
        dtype_value = req.diagram_type.value if req.diagram_type else str(diagram_type)
        schedule_user_usage_activity(
            user_id=int(user_id),
            organization_id=organization_id,
            source="mindgraph",
            action="diagram_generate",
            title=topic_for_activity or None,
            prompt_preview=prompt or None,
            diagram_type=dtype_value,
        )

        try:
            await thinking_coin_post_diagram_generation(
                int(user_id),
                organization_id,
                result,
            )
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.debug("Failed to credit learning sheet diagram earn: %s", exc)

    result["llm_model"] = llm_model
    result["request_id"] = request_id
    return result


async def _stream_generate_graph_events(prepared: dict[str, Any]):
    """Async generator yielding SSE chunks for auto-complete phase UI."""
    queue: asyncio.Queue = asyncio.Queue()
    lang = prepared["lang"]

    async def phase_emit(event: str) -> None:
        payload: dict[str, Any] = {"event": event}
        if event == "streaming":
            payload["model"] = prepared["llm_model"]
        await queue.put(payload)

    async def run_workflow() -> None:
        try:
            result = await agent_graph_workflow_with_styles(
                **prepared["workflow_kwargs"],
                phase_emit=phase_emit,
            )
            final = await _finalize_generate_graph_result(result, prepared)
            await queue.put({"event": "complete", **final})
        except ThinkingCoinInsufficientError as coin_exc:
            await queue.put(
                {
                    "event": "error",
                    "message": coin_exc.user_message,
                    "error_type": "thinking_coin_insufficient",
                    "balance": coin_exc.balance,
                    "cost": coin_exc.cost,
                }
            )
        except LLMContentFilterError as e:
            msg = getattr(e, "user_message", None) or Messages.error("internal_error", lang)
            await queue.put({"event": "error", "message": msg})
        except LLMRateLimitError as e:
            msg = getattr(e, "user_message", None) or Messages.error("internal_error", lang)
            await queue.put({"event": "error", "message": msg})
        except LLMTimeoutError as e:
            msg = getattr(e, "user_message", None) or Messages.error("internal_error", lang)
            await queue.put({"event": "error", "message": msg})
        except LLMServiceError as e:
            msg = getattr(e, "user_message", None) or Messages.error("internal_error", lang)
            await queue.put({"event": "error", "message": msg})
        except BACKGROUND_INFRA_ERRORS as e:
            logger.error("[%s] Stream generate_graph error: %s", prepared["request_id"], e, exc_info=True)
            await queue.put({"event": "error", "message": Messages.error("internal_error", lang)})
        except HTTPException as exc:
            await queue.put({"event": "error", "message": str(exc.detail)})
        finally:
            await queue.put(None)

    await queue.put({"event": "accepted"})
    task = asyncio.create_task(run_workflow())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item, default=str)}\n\n"
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@router.post("/generate_graph", response_model=GenerateResponse)
async def generate_graph(
    req: GenerateRequest,
    request: Request,
    x_language: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key),
):
    """
    Generate graph specification from user prompt using selected LLM model (async).

    This endpoint returns JSON with the diagram specification for the frontend editor to render.
    For PNG file downloads, use /api/export_png instead.

    Rate limited: 100 requests per minute per user/IP.
    """
    try:
        prepared = await _prepare_generate_graph(
            req,
            request,
            current_user,
            x_language,
            endpoint_path="/api/generate_graph",
        )
        result = await agent_graph_workflow_with_styles(**prepared["workflow_kwargs"])
        return await _finalize_generate_graph_result(result, prepared)
    except BACKGROUND_INFRA_ERRORS as e:
        request_id = f"gen_{int(time.time() * 1000)}"
        accept_language = request.headers.get("Accept-Language", "")
        lang = get_request_language(x_language, accept_language)
        logger.error("[%s] Error generating graph: %s", request_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=Messages.error("internal_error", lang)) from e


@router.post("/generate_graph/stream")
async def generate_graph_stream(
    req: GenerateRequest,
    request: Request,
    x_language: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key),
):
    """
    SSE stream for auto-complete: phase events (accepted/waiting/streaming) + final complete payload.

    JSON ``POST /api/generate_graph`` is unchanged for landing, subgraph, and other callers.
    """
    try:
        prepared = await _prepare_generate_graph(
            req,
            request,
            current_user,
            x_language,
            endpoint_path="/api/generate_graph/stream",
        )
        if prepared["request_type"] != "autocomplete":
            raise HTTPException(
                status_code=400,
                detail="Stream endpoint supports autocomplete requests only",
            )
        return StreamingResponse(
            _stream_generate_graph_events(prepared),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except BACKGROUND_INFRA_ERRORS as e:
        accept_language = request.headers.get("Accept-Language", "")
        lang = get_request_language(x_language, accept_language)
        logger.error("Error starting generate_graph stream: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=Messages.error("internal_error", lang)) from e
