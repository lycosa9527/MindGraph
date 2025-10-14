"""
ThinkGuide API Router
=====================

Handles ALL diagram types through factory pattern.
Provides SSE streaming for Socratic guided thinking workflow.

@author lycosa9527
@made_by MindSpring Team
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
import json

# Import authentication
from models.auth import User
from utils.auth import get_current_user

from agents.thinking_modes.factory import ThinkingAgentFactory
from agents.thinking_modes.node_palette_generator import get_node_palette_generator
from models.requests import (
    ThinkingModeRequest,
    NodePaletteStartRequest,
    NodePaletteNextRequest,
    NodeSelectionRequest,
    NodePaletteFinishRequest
)

router = APIRouter(tags=["thinking"])
logger = logging.getLogger(__name__)


@router.post('/thinking_mode/stream')
async def thinking_mode_stream(
    req: ThinkingModeRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Universal SSE streaming endpoint for ALL diagram types.
    Uses factory pattern to route to correct agent.
    
    Currently supports: circle_map (more coming: bubble_map, tree_map, etc.)
    """
    
    try:
        # Validate diagram type
        supported = ThinkingAgentFactory.get_supported_types()
        if req.diagram_type not in supported:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported diagram type: {req.diagram_type}. Supported: {supported}"
            )
        
        # Get agent from factory
        agent = ThinkingAgentFactory.get_agent(req.diagram_type)
        
        # Log diagram data for debugging
        center_text = req.diagram_data.get('center', {}).get('text', 'N/A')
        child_count = len(req.diagram_data.get('children', []))
        logger.info(f"[ThinkGuide] Starting session: {req.session_id} | Diagram: {req.diagram_type} | State: {req.current_state}")
        logger.info(f"[ThinkGuide] Diagram data - Center: '{center_text}' | Children: {child_count}")
        
        # SSE generator
        async def generate():
            """Async generator for SSE streaming"""
            try:
                async for chunk in agent.process_step(
                    message=req.message,
                    session_id=req.session_id,
                    diagram_data=req.diagram_data,
                    current_state=req.current_state,
                    user_id=req.user_id,
                    is_initial_greeting=req.is_initial_greeting
                ):
                    # Format as SSE
                    yield f"data: {json.dumps(chunk)}\n\n"
                
            except Exception as e:
                logger.error(f"[ThinkGuide] Streaming error: {e}", exc_info=True)
                yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
        
        # Return SSE stream
        return StreamingResponse(
            generate(),
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive'
            }
        )
    
    except ValueError as e:
        # Invalid diagram type from factory
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"[ThinkGuide] Thinking Mode error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get('/thinking_mode/node_learning/{session_id}/{node_id}')
async def get_node_learning_material(
    session_id: str,
    node_id: str,
    diagram_type: str = 'circle_map',
    current_user: User = Depends(get_current_user)
):
    """
    Get learning material for a specific node (for hover tooltip).
    
    Called when user hovers over a node during Thinking Mode.
    Works for ALL diagram types via factory pattern.
    """
    
    try:
        # Get agent from factory using diagram type
        # In production, diagram_type should be stored in session metadata
        agent = ThinkingAgentFactory.get_agent(diagram_type)
        session = agent.get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get learning material for this node
        material = session.get('node_learning_material', {}).get(node_id)
        
        if not material:
            raise HTTPException(
                status_code=404,
                detail=f"Learning material not found for node: {node_id}"
            )
        
        logger.info(f"[ThinkGuide] Retrieved learning material for node: {node_id} | Session: {session_id}")
        return material
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ThinkGuide] Error fetching node learning material: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# NODE PALETTE API ENDPOINTS
# ============================================================================

@router.post('/thinking_mode/node_palette/start')
async def start_node_palette(
    req: NodePaletteStartRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Initialize Node Palette and fire ALL 4 LLMs concurrently.
    
    Returns SSE stream with progressive results as each LLM completes.
    No limits - this is the start of infinite scrolling!
    """
    session_id = req.session_id
    user_id = getattr(req, 'user_id', 'anonymous')
    
    logger.info("[NodePalette-API] POST /start (V2 Concurrent) | Session: %s | User: %s", 
               session_id[:8], user_id)
    
    try:
        # Extract center topic
        center_topic = req.diagram_data.get('center', {}).get('text', '')
        
        if not center_topic:
            logger.error("[NodePalette-API] No center topic for session %s", session_id[:8])
            raise HTTPException(status_code=400, detail="Circle map has no center topic")
        
        logger.info("[NodePalette-API] Topic: '%s' | 🚀 Firing 4 LLMs concurrently", center_topic)
        
        # Get generator
        generator = get_node_palette_generator()
        
        # Stream with concurrent execution
        async def generate():
            logger.info("[NodePalette-API] SSE stream starting | Session: %s", session_id[:8])
            node_count = 0
            
            try:
                async for chunk in generator.generate_batch(
                    session_id=session_id,
                    center_topic=center_topic,
                    educational_context=req.educational_context,
                    nodes_per_llm=15  # Each LLM generates 15 nodes = 60 total per batch
                ):
                    if chunk.get('event') == 'node_generated':
                        node_count += 1
                    
                    yield f"data: {json.dumps(chunk)}\n\n"
                
                logger.info("[NodePalette-API] Batch complete | Session: %s | Nodes: %d", 
                           session_id[:8], node_count)
                
            except Exception as e:
                logger.error("[NodePalette-API] Stream error | Session: %s | Error: %s", 
                            session_id[:8], str(e), exc_info=True)
                error_event = {
                    'event': 'error',
                    'message': str(e)
                }
                yield f"data: {json.dumps(error_event)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[NodePalette-API] Start error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/thinking_mode/node_palette/next_batch')
async def get_next_batch(
    req: NodePaletteNextRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Generate next batch - fires ALL 4 LLMs concurrently again!
    
    Called when user scrolls to 2/3 of content.
    Infinite scroll - keeps firing 4 concurrent LLMs on each trigger.
    """
    session_id = req.session_id
    logger.info("[NodePalette-API] POST /next_batch (V2 Concurrent) | Session: %s", session_id[:8])
    
    try:
        # Get generator
        generator = get_node_palette_generator()
        
        logger.info("[NodePalette-API] 🚀 Firing 4 LLMs concurrently for next batch...")
        
        # Stream next batch with concurrent execution
        async def generate():
            node_count = 0
            try:
                async for chunk in generator.generate_batch(
                    session_id=session_id,
                    center_topic=req.center_topic,
                    educational_context=req.educational_context,
                    nodes_per_llm=15  # 60 total nodes per scroll trigger
                ):
                    if chunk.get('event') == 'node_generated':
                        node_count += 1
                    
                    yield f"data: {json.dumps(chunk)}\n\n"
                
                logger.info("[NodePalette-API] Next batch complete | Session: %s | Nodes: %d", 
                           session_id[:8], node_count)
                
            except Exception as e:
                logger.error("[NodePalette-API] Next batch error | Session: %s | Error: %s", 
                            session_id[:8], str(e), exc_info=True)
                yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive'
            }
        )
    
    except Exception as e:
        logger.error("[NodePalette-API] Next batch error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/thinking_mode/node_palette/select_node')
async def log_node_selection(
    req: NodeSelectionRequest,
    current_user: User = Depends(get_current_user)
):
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
    logger.info("[NodePalette-Selection] User %s node | Session: %s | Node: '%s' | ID: %s", 
               action, session_id[:8], node_text[:50], node_id)
    
    return {"status": "logged"}


@router.post('/thinking_mode/node_palette/finish')
async def log_finish_selection(
    req: NodePaletteFinishRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Log when user finishes Node Palette and return to Circle Map.
    
    Called when user clicks "Finish" button.
    Logs final metrics and cleans up session.
    """
    session_id = req.session_id
    selected_count = len(req.selected_node_ids)
    total_generated = req.total_nodes_generated
    batches_loaded = req.batches_loaded
    
    logger.info("[NodePalette-Finish] User completed session | Session: %s", session_id[:8])
    logger.info("[NodePalette-Finish]   Selected: %d/%d nodes | Batches: %d | Selection rate: %.1f%%", 
               selected_count, total_generated, batches_loaded, 
               (selected_count/max(total_generated,1))*100)
    
    # End session in generator
    generator = get_node_palette_generator_v2()
    generator.end_session(session_id, reason="user_finished")
    
    return {"status": "session_ended"}


# Debug endpoint removed - V2 generator uses different session tracking
# Use browser console logs and server logs for debugging instead
# @router.get('/thinking_mode/node_palette/debug/{session_id}')
# async def debug_node_palette_session(session_id: str):
#     """Debug endpoint (deprecated - use logs instead)"""
#     pass

