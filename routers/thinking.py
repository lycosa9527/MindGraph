"""
ThinkGuide API Router
=====================

Handles ALL diagram types through factory pattern.
Provides SSE streaming for Socratic guided thinking workflow.

@author lycosa9527
@made_by MindSpring Team
"""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json

from agents.thinking_modes.factory import ThinkingAgentFactory
from agents.thinking_modes.circle_map_agent import CircleMapThinkingAgent
from models.requests import ThinkingModeRequest

router = APIRouter(tags=["thinking"])
logger = logging.getLogger(__name__)


@router.post('/thinking_mode/stream')
async def thinking_mode_stream(req: ThinkingModeRequest):
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
                    user_id=req.user_id
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
async def get_node_learning_material(session_id: str, node_id: str):
    """
    Get learning material for a specific node (for hover tooltip).
    
    Called when user hovers over a node during Thinking Mode.
    Works for ALL diagram types (session stores the data).
    """
    
    try:
        # For MVP, get from Circle Map agent instance
        # In production, use shared Redis/DB session store
        agent = CircleMapThinkingAgent()
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

