"""
Node Palette API Router
========================

Provides API endpoints for Node Palette feature.
Fires multiple LLMs concurrently to generate node suggestions.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from agents.node_palette.brace_map_palette import get_brace_map_palette_generator
from agents.node_palette.bridge_map_palette import get_bridge_map_palette_generator
from agents.node_palette.bubble_map_palette import get_bubble_map_palette_generator
from agents.node_palette.circle_map_palette import get_circle_map_palette_generator
from agents.node_palette.concept_map_palette import get_concept_map_palette_generator
from agents.node_palette.double_bubble_palette import (
    get_double_bubble_palette_generator,
)
from agents.node_palette.flow_map_palette import get_flow_map_palette_generator
from agents.node_palette.mindmap_palette import get_mindmap_palette_generator
from agents.node_palette.multi_flow_palette import get_multi_flow_palette_generator
from agents.node_palette.tree_map_palette import get_tree_map_palette_generator
from config.database import get_async_db
from routers.node_palette_streaming import stream_node_palette
from models.domain.auth import User
from models.domain.user_activity_log import UserActivityLog
from models.requests.requests_thinking import (
    NodePaletteStartRequest,
    NodePaletteNextRequest,
    NodeSelectionRequest,
    NodePaletteFinishRequest,
    NodePaletteCleanupRequest,
)
from services.redis.redis_activity_tracker import get_activity_tracker
from utils.auth import get_current_user
from utils.placeholder import is_placeholder_text

router = APIRouter(tags=["thinking"])
logger = logging.getLogger(__name__)

_GENERATOR_MAP = {
    "circle_map": get_circle_map_palette_generator,
    "bubble_map": get_bubble_map_palette_generator,
    "double_bubble_map": get_double_bubble_palette_generator,
    "multi_flow_map": get_multi_flow_palette_generator,
    "tree_map": get_tree_map_palette_generator,
    "flow_map": get_flow_map_palette_generator,
    "brace_map": get_brace_map_palette_generator,
    "bridge_map": get_bridge_map_palette_generator,
    "mindmap": get_mindmap_palette_generator,
    "concept_map": get_concept_map_palette_generator,
}


def _extract_center_topic(req: NodePaletteStartRequest) -> str:
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


def _get_palette_generator(diagram_type: str):
    """Get palette generator for diagram type, fallback to circle_map."""
    getter = _GENERATOR_MAP.get(diagram_type)
    if getter is None:
        logger.warning(
            "[NodePalette-API] No specialized generator for %s, using circle_map fallback",
            diagram_type,
        )
        return get_circle_map_palette_generator()
    return getter()


def _log_topic_and_firing(req: NodePaletteStartRequest, center_topic: str, session_id: str) -> None:
    """Log topic info and LLM firing debug message."""
    if req.diagram_type == "bridge_map":
        if center_topic and center_topic.strip():
            logger.info(
                "[NodePalette] Topic: '%s' (Bridge map dimension) | Session: %s",
                center_topic[:50],
                session_id[:8],
            )
        else:
            logger.info(
                "[NodePalette] Topic: (Diverse relationships mode) | Session: %s",
                session_id[:8],
            )
    else:
        logger.info(
            "[NodePalette] Topic: '%s' | Session: %s",
            center_topic[:50] if center_topic else "(empty)",
            session_id[:8],
        )
    if req.diagram_type == "bridge_map":
        if center_topic and center_topic.strip():
            logger.debug(
                "[NodePalette-API] Type: bridge_map | Dimension: '%s' (SPECIFIC) | "
                "Firing 3 LLMs concurrently (qwen, deepseek, doubao)",
                center_topic,
            )
        else:
            logger.debug(
                "[NodePalette-API] Type: bridge_map | Dimension: (EMPTY - DIVERSE mode) | "
                "Firing 3 LLMs concurrently (qwen, deepseek, doubao)"
            )
    else:
        logger.debug(
            "[NodePalette-API] Type: %s | Topic: '%s' | Firing 3 LLMs concurrently (qwen, deepseek, doubao)",
            req.diagram_type,
            center_topic,
        )


# ============================================================================
# NODE PALETTE API ENDPOINTS
# ============================================================================


@router.post("/thinking_mode/node_palette/start")
async def start_node_palette(
    req: NodePaletteStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Initialize Node Palette and fire 3 LLMs concurrently (qwen, deepseek, doubao).

    Returns SSE stream with progressive results as each LLM completes.
    No limits - this is the start of infinite scrolling!
    NOTE: Kimi removed due to Volcengine server load issues
    """
    session_id = req.session_id
    user_id = current_user.id if current_user else None

    # Track user activity
    if current_user:
        try:
            tracker = get_activity_tracker()
            await tracker.record_activity(
                user_id=current_user.id,
                user_phone=current_user.phone,
                activity_type="node_palette",
                details={"diagram_type": req.diagram_type, "session_id": session_id},
                user_name=getattr(current_user, "name", None),
            )
        except Exception as e:
            logger.debug("Failed to track user activity: %s", e)

    # Log at INFO level for user activity tracking
    logger.info(
        "[NodePalette] Started: Session %s (User: %s, Diagram: %s)",
        session_id[:8],
        user_id,
        req.diagram_type,
    )

    # Debug: Log received diagram data structure
    logger.debug("[NodePalette-API] Diagram type: %s", req.diagram_type)
    logger.debug("[NodePalette-API] Diagram data keys: %s", list(req.diagram_data.keys()))
    logger.debug("[NodePalette-API] Diagram data: %s", str(req.diagram_data)[:200])

    try:
        center_topic = _extract_center_topic(req)
        if req.diagram_type != "bridge_map" and (not center_topic or not center_topic.strip()):
            logger.error("[NodePalette-API] No center topic for session %s", session_id[:8])
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
        if (
            current_user
            and getattr(current_user, "role", None) == "user"
            and is_concept_map_bootstrap
        ):
            try:
                log_entry = UserActivityLog(
                    user_id=current_user.id,
                    activity_type="concept_generation",
                    created_at=datetime.now(UTC),
                )
                db.add(log_entry)
                await db.commit()
            except Exception as e:
                logger.debug("Failed to log concept_generation: %s", e)
                try:
                    await db.rollback()
                except Exception as exc:
                    logger.debug("Rollback after concept_generation log failure: %s", exc)

        _log_topic_and_firing(req, center_topic, session_id)
        generator = _get_palette_generator(req.diagram_type)

        return StreamingResponse(
            stream_node_palette(
                req=req,
                session_id=session_id,
                center_topic=center_topic,
                generator=generator,
                current_user=current_user,
                endpoint_path="/thinking_mode/node_palette/start",
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[NodePalette-API] Start error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/thinking_mode/node_palette/next_batch")
async def get_next_batch(req: NodePaletteNextRequest, current_user: User = Depends(get_current_user)):
    """
    Generate next batch - fires 3 LLMs concurrently again (qwen, deepseek, doubao)!

    Called when user scrolls to 2/3 of content.
    Infinite scroll - keeps firing 3 concurrent LLMs on each trigger.
    NOTE: Kimi removed due to Volcengine server load issues
    """
    session_id = req.session_id
    logger.debug(
        "[NodePalette-API] POST /next_batch (V2 Concurrent) | Session: %s",
        session_id[:8],
    )

    try:
        generator = _get_palette_generator(req.diagram_type)
        logger.debug(
            "[NodePalette-API] Type: %s | Firing 3 LLMs concurrently for next batch (qwen, deepseek, doubao)...",
            req.diagram_type,
        )

        return StreamingResponse(
            stream_node_palette(
                req=req,
                session_id=session_id,
                center_topic=req.center_topic,
                generator=generator,
                current_user=current_user,
                endpoint_path="/thinking_mode/node_palette/next_batch",
                log_prefix="[NodePalette-API] Next batch",
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    except Exception as e:
        logger.error("[NodePalette-API] Next batch error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/thinking_mode/node_palette/select_node")
async def log_node_selection(req: NodeSelectionRequest, _current_user: User = Depends(get_current_user)):
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
        "[NodePalette-Selection] User %s node | Session: %s | Node: '%s' | ID: %s",
        action,
        session_id[:8],
        node_text[:50],
        node_id,
    )

    return {"status": "logged"}


@router.post("/thinking_mode/node_palette/finish")
async def log_finish_selection(req: NodePaletteFinishRequest, current_user: User = Depends(get_current_user)):
    """
    Log when user finishes Node Palette and return to diagram.

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
        "[NodePalette] Completed: Session %s (User: %s, Generated: %d nodes, "
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
    # User may return to Node Palette multiple times to add more nodes.
    # Session will be properly cleaned up when user leaves canvas (backToGallery).

    return {"status": "palette_closed"}


@router.post("/thinking_mode/node_palette/cancel")
async def node_palette_cancel(request: NodePaletteFinishRequest, current_user: User = Depends(get_current_user)):
    """
    Handle Node Palette cancellation.

    User clicked Cancel button - log the event and end session without adding nodes.
    """
    session_id = request.session_id
    selected_count = len(request.selected_node_ids)  # Use the correct field from request model
    total_generated = request.total_nodes_generated
    batches_loaded = request.batches_loaded
    user_id = current_user.id if current_user else None

    # Log at INFO level for user activity tracking
    logger.info(
        "[NodePalette] Cancelled: Session %s (User: %s, Generated: %d nodes, "
        "Selected: %d nodes, NOT added, Batches: %d)",
        session_id[:8],
        user_id,
        total_generated,
        selected_count,
        batches_loaded,
    )

    # NOTE: Do NOT end the session here!
    # User may have clicked Cancel by mistake and want to reopen.
    # Session will be properly cleaned up when user leaves canvas (backToGallery).

    return {"status": "palette_cancelled"}


@router.post("/thinking_mode/node_palette/cleanup")
async def node_palette_cleanup(request: NodePaletteCleanupRequest, _current_user: User = Depends(get_current_user)):
    """
    Clean up Node Palette session when user leaves canvas.

    Called from diagram-selector.js backToGallery() to properly end session
    and free memory when user exits to gallery.
    """
    session_id = request.session_id
    diagram_type = request.diagram_type or "circle_map"

    logger.debug(
        "[NodePalette-Cleanup] Ending session (user left canvas) | Session: %s",
        session_id[:8],
    )

    # Get appropriate generator and end session
    if diagram_type == "circle_map":
        generator = get_circle_map_palette_generator()
    elif diagram_type == "bubble_map":
        generator = get_bubble_map_palette_generator()
    elif diagram_type == "double_bubble_map":
        generator = get_double_bubble_palette_generator()
    elif diagram_type == "multi_flow_map":
        generator = get_multi_flow_palette_generator()
    elif diagram_type == "tree_map":
        generator = get_tree_map_palette_generator()
    elif diagram_type == "flow_map":
        generator = get_flow_map_palette_generator()
    elif diagram_type == "brace_map":
        generator = get_brace_map_palette_generator()
    elif diagram_type == "bridge_map":
        generator = get_bridge_map_palette_generator()
    elif diagram_type == "mindmap":
        generator = get_mindmap_palette_generator()
    elif diagram_type == "concept_map":
        generator = get_concept_map_palette_generator()
    else:
        generator = get_circle_map_palette_generator()

    generator.end_session(session_id, reason="canvas_exit")

    return {"status": "session_cleaned"}
