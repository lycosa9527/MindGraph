"""
AI brainstorm API Router
========================

Provides API endpoints for AI brainstorm feature.
Fires multiple LLMs concurrently to generate node suggestions.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from agents.ai_brainstorm.brace_map import get_brace_map_brainstorm_generator
from agents.ai_brainstorm.bridge_map import get_bridge_map_brainstorm_generator
from agents.ai_brainstorm.bubble_map import get_bubble_map_brainstorm_generator
from agents.ai_brainstorm.circle_map import get_circle_map_brainstorm_generator
from agents.ai_brainstorm.concept_map import get_concept_map_brainstorm_generator
from agents.ai_brainstorm.double_bubble import (
    get_double_bubble_brainstorm_generator,
)
from agents.ai_brainstorm.flow_map import get_flow_map_brainstorm_generator
from agents.ai_brainstorm.mindmap import get_mindmap_brainstorm_generator
from agents.ai_brainstorm.multi_flow import get_multi_flow_brainstorm_generator
from agents.ai_brainstorm.tree_map import get_tree_map_brainstorm_generator
from config.database import get_async_db
from models.domain.auth import User
from models.domain.user_activity_log import UserActivityLog
from models.requests.requests_thinking import (
    AiBrainstormCleanupRequest,
    AiBrainstormFinishRequest,
    AiBrainstormNextRequest,
    AiBrainstormSelectionRequest,
    AiBrainstormStartRequest,
)
from routers.ai_brainstorm_streaming import stream_ai_brainstorm
from routers.api.diagram_generation import assert_collab_blocks_canvas_ai
from services.learning_space.ai_gate import assert_student_ai_capability
from services.monitoring.module_activity import track_module_activity
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from utils.auth import get_current_user, is_teacher
from utils.placeholder import is_placeholder_text

router = APIRouter(tags=["thinking"])
logger = logging.getLogger(__name__)

_GENERATOR_MAP = {
    "circle_map": get_circle_map_brainstorm_generator,
    "bubble_map": get_bubble_map_brainstorm_generator,
    "double_bubble_map": get_double_bubble_brainstorm_generator,
    "multi_flow_map": get_multi_flow_brainstorm_generator,
    "tree_map": get_tree_map_brainstorm_generator,
    "flow_map": get_flow_map_brainstorm_generator,
    "brace_map": get_brace_map_brainstorm_generator,
    "bridge_map": get_bridge_map_brainstorm_generator,
    "mindmap": get_mindmap_brainstorm_generator,
    "concept_map": get_concept_map_brainstorm_generator,
}


def _extract_center_topic(req: AiBrainstormStartRequest) -> str:
    """Extract center topic from request based on diagram type."""
    data = req.diagram_data
    diagram_type = req.diagram_type
    topic = ""

    if diagram_type == "double_bubble_map":
        topic = f"{data.get('left', '')} vs {data.get('right', '')}"
    elif diagram_type == "multi_flow_map":
        topic = data.get("event", "")
    elif diagram_type == "flow_map":
        topic = data.get("title", "")
    elif diagram_type == "brace_map":
        topic = data.get("whole", "")
    elif diagram_type == "bridge_map":
        raw_dim = data.get("dimension", "")
        raw_dim = "" if raw_dim is None else str(raw_dim)
        topic = "" if is_placeholder_text(raw_dim) else raw_dim
    elif diagram_type in ("tree_map", "mindmap", "concept_map"):
        stage_data = getattr(req, "stage_data", None) or {}
        if diagram_type == "concept_map" and isinstance(stage_data, dict) and stage_data.get("center_topic"):
            topic = str(stage_data.get("center_topic", ""))
        else:
            topic = data.get("topic", "")
    else:
        center = data.get("center", {}) or {}
        topic = center.get("text", "") or data.get("topic", "") or data.get("title", "") or data.get("main_topic", "")
    return topic


def _get_brainstorm_generator(diagram_type: str):
    """Get the brainstorm generator for a diagram type, fallback to circle_map."""
    getter = _GENERATOR_MAP.get(diagram_type)
    if getter is None:
        logger.warning(
            "[AiBrainstorm-API] No specialized generator for %s, using circle_map fallback",
            diagram_type,
        )
        return get_circle_map_brainstorm_generator()
    return getter()


def _log_topic_and_firing(req: AiBrainstormStartRequest, center_topic: str, session_id: str) -> None:
    """Log topic info and LLM firing debug message."""
    if req.diagram_type == "bridge_map":
        if center_topic and center_topic.strip():
            logger.info(
                "[AiBrainstorm] Topic: '%s' (Bridge map dimension) | Session: %s",
                center_topic[:50],
                session_id[:8],
            )
        else:
            logger.info(
                "[AiBrainstorm] Topic: (Diverse relationships mode) | Session: %s",
                session_id[:8],
            )
    else:
        logger.info(
            "[AiBrainstorm] Topic: '%s' | Session: %s",
            center_topic[:50] if center_topic else "(empty)",
            session_id[:8],
        )
    if req.diagram_type == "bridge_map":
        if center_topic and center_topic.strip():
            logger.debug(
                "[AiBrainstorm-API] Type: bridge_map | Dimension: '%s' (SPECIFIC) | "
                "Firing Express LLM (DashScope deepseek-v4.1-flash)",
                center_topic,
            )
        else:
            logger.debug(
                "[AiBrainstorm-API] Type: bridge_map | Dimension: (EMPTY - DIVERSE mode) | "
                "Firing Express LLM (DashScope deepseek-v4.1-flash)"
            )
    else:
        logger.debug(
            "[AiBrainstorm-API] Type: %s | Topic: '%s' | Firing Express LLM (DashScope deepseek-v4.1-flash)",
            req.diagram_type,
            center_topic,
        )


# ============================================================================
# AI BRAINSTORM API ENDPOINTS
# ============================================================================


@router.post("/thinking_mode/ai_brainstorm/start")
async def start_ai_brainstorm(
    req: AiBrainstormStartRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Initialize AI brainstorm and fire the Express LLM.

    Returns SSE stream with progressive results as each LLM completes.
    No limits - this is the start of infinite scrolling!
    NOTE: Kimi removed due to Volcengine server load issues
    """
    await assert_student_ai_capability(db, current_user, request, "ai_brainstorm")
    session_id = req.session_id
    await assert_collab_blocks_canvas_ai(req.diagram_id, current_user)

    if current_user:
        await track_module_activity(
            user=current_user,
            module="canvas",
            redis_activity_type="ai_brainstorm",
            request=request,
            details={"diagram_type": req.diagram_type, "session_id": session_id},
            detail=f"{req.diagram_type} session={session_id[:8]}",
            persist_usage=False,
        )

    # Debug: Log received diagram data structure
    logger.debug("[AiBrainstorm-API] Diagram type: %s", req.diagram_type)
    logger.debug("[AiBrainstorm-API] Diagram data keys: %s", list(req.diagram_data.keys()))
    logger.debug("[AiBrainstorm-API] Diagram data: %s", str(req.diagram_data)[:200])

    try:
        center_topic = _extract_center_topic(req)
        if req.diagram_type != "bridge_map" and (not center_topic or not center_topic.strip()):
            logger.error("[AiBrainstorm-API] No center topic for session %s", session_id[:8])
            raise HTTPException(status_code=400, detail=f"{req.diagram_type} has no center topic")

        # Log concept_generation for concept map (teacher usage tracking).
        # Log ONLY on the one-shot domain-bootstrap call (user action "Generate
        # Concepts" or "Add Domain"). The per-tab streams that follow share the
        # same user intent and must not each produce a separate row. Logging
        # after topic validation also prevents orphan rows from HTTP 400 paths.
        stage_data = getattr(req, "stage_data", None) or {}
        is_concept_map_bootstrap = (
            req.diagram_type == "concept_map"
            and isinstance(stage_data, dict)
            and bool(stage_data.get("bootstrap_domains"))
        )
        if current_user and is_teacher(current_user) and is_concept_map_bootstrap:
            try:
                log_entry = UserActivityLog(
                    user_id=current_user.id,
                    activity_type="concept_generation",
                    created_at=datetime.now(UTC),
                )
                db.add(log_entry)
                await db.commit()
            except DATABASE_ERRORS as e:
                logger.debug("Failed to log concept_generation: %s", e)
                try:
                    await db.rollback()
                except DATABASE_ERRORS as exc:
                    logger.debug("Rollback after concept_generation log failure: %s", exc)

        _log_topic_and_firing(req, center_topic, session_id)
        generator = _get_brainstorm_generator(req.diagram_type)

        return StreamingResponse(
            stream_ai_brainstorm(
                req=req,
                session_id=session_id,
                center_topic=center_topic,
                generator=generator,
                current_user=current_user,
                endpoint_path="/thinking_mode/ai_brainstorm/start",
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    except BACKGROUND_INFRA_ERRORS as e:
        logger.error("[AiBrainstorm-API] Start error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/thinking_mode/ai_brainstorm/next_batch")
async def get_next_batch(req: AiBrainstormNextRequest, current_user: User = Depends(get_current_user)):
    """
    Generate next batch with the Express LLM.

    Called when user scrolls to 2/3 of content.
    Infinite scroll - keeps firing 3 concurrent LLMs on each trigger.
    NOTE: Kimi removed due to Volcengine server load issues
    """
    session_id = req.session_id
    await assert_collab_blocks_canvas_ai(req.diagram_id, current_user)
    logger.debug(
        "[AiBrainstorm-API] POST /next_batch (V2 Concurrent) | Session: %s",
        session_id[:8],
    )

    try:
        generator = _get_brainstorm_generator(req.diagram_type)
        logger.debug(
            "[AiBrainstorm-API] Type: %s | Firing Express LLM for next batch...",
            req.diagram_type,
        )

        return StreamingResponse(
            stream_ai_brainstorm(
                req=req,
                session_id=session_id,
                center_topic=req.center_topic,
                generator=generator,
                current_user=current_user,
                endpoint_path="/thinking_mode/ai_brainstorm/next_batch",
                log_prefix="[AiBrainstorm-API] Next batch",
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    except BACKGROUND_INFRA_ERRORS as e:
        logger.error("[AiBrainstorm-API] Next batch error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/thinking_mode/ai_brainstorm/select_node")
async def log_node_selection(req: AiBrainstormSelectionRequest, _current_user: User = Depends(get_current_user)):
    """
    Log node selection/deselection event for analytics.

    Called from frontend when user selects/deselects nodes.
    Frontend batches these calls (every 5 selections).
    """
    session_id = req.session_id
    node_id = req.node_id
    selected = req.selected
    node_text = req.node_text

    action = "selected" if selected else "deselected"
    logger.debug(
        "[AiBrainstorm-Selection] User %s node | Session: %s | Node: '%s' | ID: %s",
        action,
        session_id[:8],
        node_text[:50],
        node_id,
    )

    return {"status": "logged"}


@router.post("/thinking_mode/ai_brainstorm/finish")
async def log_finish_selection(req: AiBrainstormFinishRequest, current_user: User = Depends(get_current_user)):
    """
    Log when user finishes AI brainstorm and return to diagram.

    Called when user clicks "Finish" button.
    Logs final metrics and cleans up session.
    """
    session_id = req.session_id
    selected_count = len(req.selected_node_ids)
    total_generated = req.total_nodes_generated
    batches_loaded = req.batches_loaded
    user_id = current_user.id if current_user else None
    selection_rate = (selected_count / max(total_generated, 1)) * 100

    # Log at INFO level for user activity tracking
    logger.info(
        "[AiBrainstorm] Completed: Session %s (User: %s, Generated: %d nodes, "
        "Selected: %d nodes, Selection rate: %.1f%%, Batches: %d)",
        session_id[:8],
        user_id,
        total_generated,
        selected_count,
        selection_rate,
        batches_loaded,
    )

    # NOTE: Do NOT end the session here!
    # Session should persist throughout the entire canvas session.
    # User may return to AI brainstorm multiple times to add more nodes.
    # The session stays open so the user can reopen AI brainstorm on the same canvas.
    # Idle sweep or POST /cleanup ends it.

    return {"status": "closed"}


@router.post("/thinking_mode/ai_brainstorm/cancel")
async def ai_brainstorm_cancel(request: AiBrainstormFinishRequest, current_user: User = Depends(get_current_user)):
    """
    Handle AI brainstorm cancellation.

    User clicked Cancel button - log the event and end session without adding nodes.
    """
    session_id = request.session_id
    selected_count = len(request.selected_node_ids)  # Use the correct field from request model
    total_generated = request.total_nodes_generated
    batches_loaded = request.batches_loaded
    user_id = current_user.id if current_user else None

    # Log at INFO level for user activity tracking
    logger.info(
        "[AiBrainstorm] Cancelled: Session %s (User: %s, Generated: %d nodes, "
        "Selected: %d nodes, NOT added, Batches: %d)",
        session_id[:8],
        user_id,
        total_generated,
        selected_count,
        batches_loaded,
    )

    # NOTE: Do NOT end the session here!
    # User may have clicked Cancel by mistake and want to reopen.
    # The session stays open so a mistaken cancel can be reopened.
    # Idle sweep or POST /cleanup ends it.

    return {"status": "cancelled"}


@router.post("/thinking_mode/ai_brainstorm/cleanup")
async def ai_brainstorm_cleanup(request: AiBrainstormCleanupRequest, _current_user: User = Depends(get_current_user)):
    """
    Clean up AI brainstorm session when user leaves canvas.

    Ends the generator session for this diagram type. The canvas relies on the
    idle sweep when the tab closes without this call.
    """
    session_id = request.session_id
    diagram_type = request.diagram_type or "circle_map"

    logger.debug(
        "[AiBrainstorm-Cleanup] Ending session (user left canvas) | Session: %s",
        session_id[:8],
    )

    generator = _get_brainstorm_generator(diagram_type)
    generator.end_session(session_id, reason="canvas_exit")

    return {"status": "session_cleaned"}
