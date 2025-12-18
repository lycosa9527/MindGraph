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
from agents.thinking_modes.node_palette.circle_map_palette import get_circle_map_palette_generator
from agents.thinking_modes.node_palette.bubble_map_palette import get_bubble_map_palette_generator
from agents.thinking_modes.node_palette.double_bubble_palette import get_double_bubble_palette_generator
from agents.thinking_modes.node_palette.multi_flow_palette import get_multi_flow_palette_generator
from agents.thinking_modes.node_palette.tree_map_palette import get_tree_map_palette_generator
from agents.thinking_modes.node_palette.flow_map_palette import get_flow_map_palette_generator
from agents.thinking_modes.node_palette.brace_map_palette import get_brace_map_palette_generator
from agents.thinking_modes.node_palette.bridge_map_palette import get_bridge_map_palette_generator
from agents.thinking_modes.node_palette.mindmap_palette import get_mindmap_palette_generator
from services.error_handler import (
    LLMContentFilterError, 
    LLMRateLimitError,
    LLMTimeoutError,
    LLMInvalidParameterError,
    LLMQuotaExhaustedError,
    LLMModelNotFoundError,
    LLMAccessDeniedError,
    LLMServiceError
)
from models.requests import (
    ThinkingModeRequest,
    NodePaletteStartRequest,
    NodePaletteNextRequest,
    NodeSelectionRequest,
    NodePaletteFinishRequest,
    NodePaletteCleanupRequest
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
        
        # Log diagram data for debugging - handle different diagram type structures
        if req.diagram_type in ['tree_map', 'mindmap']:
            center_text = req.diagram_data.get('topic', 'N/A')
        elif req.diagram_type == 'flow_map':
            center_text = req.diagram_data.get('title', 'N/A')
        elif req.diagram_type == 'brace_map':
            center_text = req.diagram_data.get('whole', 'N/A')
        elif req.diagram_type == 'double_bubble_map':
            left_topic = req.diagram_data.get('left', '')
            right_topic = req.diagram_data.get('right', '')
            center_text = f"{left_topic} vs {right_topic}"
        elif req.diagram_type == 'multi_flow_map':
            center_text = req.diagram_data.get('event', 'N/A')
        elif req.diagram_type == 'bridge_map':
            center_text = req.diagram_data.get('dimension', 'N/A')
        else:
            # For circle_map, bubble_map and others
            center_text = req.diagram_data.get('center', {}).get('text', 'N/A')
        
        child_count = len(req.diagram_data.get('children', []))
        logger.debug(f"[ThinkGuide] Starting session: {req.session_id} | Diagram: {req.diagram_type} | State: {req.current_state}")
        logger.debug(f"[ThinkGuide] Diagram data - Center: '{center_text}' | Children: {child_count}")
        
        # Get user context for token tracking
        user_id = current_user.id if current_user else (req.user_id if hasattr(req, 'user_id') else None)
        organization_id = current_user.organization_id if current_user else None
        
        # SSE generator
        async def generate():
            """Async generator for SSE streaming"""
            chunk_count = 0
            try:
                async for chunk in agent.process_step(
                    message=req.message,
                    session_id=req.session_id,
                    diagram_data=req.diagram_data,
                    current_state=req.current_state,
                    user_id=user_id,
                    organization_id=organization_id,  # Pass organization_id for token tracking
                    is_initial_greeting=req.is_initial_greeting,
                    language=req.language
                ):
                    # Format as SSE
                    chunk_count += 1
                    yield f"data: {json.dumps(chunk)}\n\n"
                
                # Ensure at least one event is yielded to prevent RuntimeError
                if chunk_count == 0:
                    logger.warning(f"[ThinkGuide] No chunks yielded, sending completion event")
                    yield f"data: {json.dumps({'event': 'message_complete', 'new_state': req.current_state})}\n\n"
                
            except LLMContentFilterError as e:
                # Content filter - don't retry, use user_message if available
                logger.warning(f"[ThinkGuide] Content filter triggered: {e}")
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "无法处理您的请求，请尝试修改主题描述。" if req.language == 'zh' else "Your request couldn't be processed. Please try rephrasing your topic."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'content_filter', 'message': user_message})}\n\n"
            
            except LLMRateLimitError as e:
                # Rate limit - can retry, use user_message if available
                logger.warning(f"[ThinkGuide] Rate limit hit: {e}")
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "AI服务繁忙，请稍后重试。" if req.language == 'zh' else "AI service is busy. Please try again in a few seconds."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'rate_limit', 'message': user_message})}\n\n"
            
            except LLMTimeoutError as e:
                logger.warning(f"[ThinkGuide] Timeout error: {e}")
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "请求超时，请重试。" if req.language == 'zh' else "Request timed out. Please try again."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'timeout', 'message': user_message})}\n\n"
            
            except LLMInvalidParameterError as e:
                logger.warning(f"[ThinkGuide] Invalid parameter: {e}")
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "参数错误，请检查输入。" if req.language == 'zh' else "Invalid parameter. Please check input."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'invalid_parameter', 'message': user_message})}\n\n"
            
            except LLMQuotaExhaustedError as e:
                logger.warning(f"[ThinkGuide] Quota exhausted: {e}")
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "配额已用完，请检查账户。" if req.language == 'zh' else "Quota exhausted. Please check account."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'quota_exhausted', 'message': user_message})}\n\n"
            
            except LLMModelNotFoundError as e:
                logger.warning(f"[ThinkGuide] Model not found: {e}")
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "模型不存在，请检查配置。" if req.language == 'zh' else "Model not found. Please check configuration."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'model_not_found', 'message': user_message})}\n\n"
            
            except LLMAccessDeniedError as e:
                logger.warning(f"[ThinkGuide] Access denied: {e}")
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "访问被拒绝，请检查权限。" if req.language == 'zh' else "Access denied. Please check permissions."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'access_denied', 'message': user_message})}\n\n"
            
            except LLMServiceError as e:
                logger.error(f"[ThinkGuide] LLM service error: {e}")
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "AI服务错误，请稍后重试。" if req.language == 'zh' else "AI service error. Please try again later."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'service_error', 'message': user_message})}\n\n"
            
            except Exception as e:
                logger.error(f"[ThinkGuide] Streaming error: {e}", exc_info=True)
                # Fallback for unknown errors
                user_message = "出现问题，请重试。" if req.language == 'zh' else "Something went wrong. Please try again."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'unknown', 'message': user_message})}\n\n"
            finally:
                # Always ensure at least one event is yielded to prevent RuntimeError
                if chunk_count == 0:
                    logger.warning(f"[ThinkGuide] Generator completed without yielding, sending error event")
                    user_message = "请求处理失败，请重试。" if req.language == 'zh' else "Request processing failed. Please try again."
                    yield f"data: {json.dumps({'event': 'error', 'error_type': 'no_response', 'message': user_message})}\n\n"
        
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
        
        logger.debug(f"[ThinkGuide] Retrieved learning material for node: {node_id} | Session: {session_id}")
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
    Initialize Node Palette and fire ALL 5 LLMs concurrently.
    
    Returns SSE stream with progressive results as each LLM completes.
    No limits - this is the start of infinite scrolling!
    """
    session_id = req.session_id
    user_id = getattr(req, 'user_id', 'anonymous')
    
    logger.debug("[NodePalette-API] POST /start (V2 Concurrent) | Session: %s | User: %s", 
               session_id[:8], user_id)
    
    # Debug: Log received diagram data structure
    logger.debug("[NodePalette-API] Diagram type: %s", req.diagram_type)
    logger.debug("[NodePalette-API] Diagram data keys: %s", list(req.diagram_data.keys()))
    logger.debug("[NodePalette-API] Diagram data: %s", str(req.diagram_data)[:200])
    
    try:
        # Extract center topic based on diagram type
        if req.diagram_type == 'double_bubble_map':
            # Double bubble map uses left and right topics
            left_topic = req.diagram_data.get('left', '')
            right_topic = req.diagram_data.get('right', '')
            center_topic = f"{left_topic} vs {right_topic}"
        elif req.diagram_type == 'multi_flow_map':
            # Multi flow map uses event
            center_topic = req.diagram_data.get('event', '')
        elif req.diagram_type == 'flow_map':
            # Flow map uses title
            center_topic = req.diagram_data.get('title', '')
        elif req.diagram_type == 'brace_map':
            # Brace map uses whole
            center_topic = req.diagram_data.get('whole', '')
        elif req.diagram_type == 'bridge_map':
            # Bridge map uses dimension (can be empty for diverse relationships)
            center_topic = req.diagram_data.get('dimension', '')
            # Empty dimension is OK for bridge map - it means "generate diverse relationships"
            if center_topic is None:
                center_topic = ''  # Ensure it's a string, not None
        elif req.diagram_type == 'tree_map' or req.diagram_type == 'mindmap':
            # Tree map and mindmap use topic
            center_topic = req.diagram_data.get('topic', '')
        else:
            # Most diagrams use center/topic field - try multiple fallbacks
            center_topic = (
                req.diagram_data.get('center', {}).get('text', '') or
                req.diagram_data.get('topic', '') or
                req.diagram_data.get('title', '') or
                req.diagram_data.get('main_topic', '')
            )
        
        # For bridge_map, empty dimension is OK (means diverse relationships)
        if req.diagram_type != 'bridge_map':
            if not center_topic or not center_topic.strip():
                logger.error("[NodePalette-API] No center topic for session %s", session_id[:8])
                raise HTTPException(status_code=400, detail=f"{req.diagram_type} has no center topic")
        
        # Special logging for bridge map
        if req.diagram_type == 'bridge_map':
            if center_topic and center_topic.strip():
                logger.debug("[NodePalette-API] Type: bridge_map | Dimension: '%s' (SPECIFIC) | Firing 5 LLMs concurrently", center_topic)
            else:
                logger.debug("[NodePalette-API] Type: bridge_map | Dimension: (EMPTY - DIVERSE mode) | Firing 5 LLMs concurrently")
        else:
            logger.debug("[NodePalette-API] Type: %s | Topic: '%s' | Firing 5 LLMs concurrently", 
                       req.diagram_type, center_topic)
        
        # Get appropriate generator based on diagram type (with fallback)
        if req.diagram_type == 'circle_map':
            generator = get_circle_map_palette_generator()
        elif req.diagram_type == 'bubble_map':
            generator = get_bubble_map_palette_generator()
        elif req.diagram_type == 'double_bubble_map':
            generator = get_double_bubble_palette_generator()
        elif req.diagram_type == 'multi_flow_map':
            generator = get_multi_flow_palette_generator()
        elif req.diagram_type == 'tree_map':
            generator = get_tree_map_palette_generator()
        elif req.diagram_type == 'flow_map':
            generator = get_flow_map_palette_generator()
        elif req.diagram_type == 'brace_map':
            generator = get_brace_map_palette_generator()
        elif req.diagram_type == 'bridge_map':
            generator = get_bridge_map_palette_generator()
        elif req.diagram_type == 'mindmap':
            generator = get_mindmap_palette_generator()
        else:
            # Fallback to circle map generator for unsupported types
            logger.warning(f"[NodePalette-API] No specialized generator for {req.diagram_type}, using circle_map fallback")
            generator = get_circle_map_palette_generator()
        
        # Stream with concurrent execution
        async def generate():
            logger.debug("[NodePalette-API] SSE stream starting | Session: %s", session_id[:8])
            node_count = 0
            chunk_count = 0
            
            try:
                # Get mode from request (default to 'similarities' for double bubble, 'causes' for multi flow)
                mode = getattr(req, 'mode', 'similarities' if req.diagram_type == 'double_bubble_map' else 'causes')
                
                # Get stage parameters for multi-stage diagrams (tree_map, brace_map, flow_map, mindmap)
                # Default stage depends on diagram type
                if req.diagram_type == 'mindmap':
                    default_stage = 'branches'  # mindmap uses 'branches' and 'children'
                elif req.diagram_type == 'brace_map':
                    default_stage = 'parts'  # brace map uses 'parts' and 'subparts'
                elif req.diagram_type == 'flow_map':
                    default_stage = 'steps'  # flow map uses 'steps'
                else:  # tree_map
                    default_stage = 'categories'  # tree map uses 'categories' and 'items'
                
                stage = getattr(req, 'stage', default_stage)
                stage_data = getattr(req, 'stage_data', None)
                
                # Call generate_batch with appropriate parameters based on diagram type
                if req.diagram_type in ['double_bubble_map', 'multi_flow_map']:
                    # Tab-enabled diagrams: pass mode parameter
                    async for chunk in generator.generate_batch(
                        session_id=session_id,
                        center_topic=center_topic,
                        educational_context=req.educational_context,
                        nodes_per_llm=15,  # Each LLM generates 15 nodes = 60 total per batch
                        mode=mode,  # Pass mode for tab-enabled diagrams
                        user_id=current_user.id if current_user else None,
                        organization_id=current_user.organization_id if current_user else None,
                        diagram_type=req.diagram_type
                    ):
                        if chunk.get('event') == 'node_generated':
                            node_count += 1
                        
                        yield f"data: {json.dumps(chunk)}\n\n"
                elif req.diagram_type in ['tree_map', 'brace_map', 'flow_map', 'mindmap']:
                    # Multi-stage diagrams: pass stage and stage_data for progressive workflow
                    logger.debug("[NodePalette-API] %s stage: %s | Stage data: %s", req.diagram_type, stage, stage_data)
                    async for chunk in generator.generate_batch(
                        session_id=session_id,
                        center_topic=center_topic,
                        educational_context=req.educational_context,
                        nodes_per_llm=15,
                        stage=stage,  # Current stage (dimensions, categories, parts, etc.)
                        stage_data=stage_data,  # Stage-specific data (dimension, category_name, part_name, etc.)
                        user_id=current_user.id if current_user else None,
                        organization_id=current_user.organization_id if current_user else None,
                        diagram_type=req.diagram_type
                    ):
                        if chunk.get('event') == 'node_generated':
                            node_count += 1
                        
                        yield f"data: {json.dumps(chunk)}\n\n"
                else:
                    # Other diagram types: standard call
                    async for chunk in generator.generate_batch(
                        session_id=session_id,
                        center_topic=center_topic,
                        educational_context=req.educational_context,
                        nodes_per_llm=15,  # Each LLM generates 15 nodes = 60 total per batch
                        user_id=current_user.id if current_user else None,
                        organization_id=current_user.organization_id if current_user else None,
                        diagram_type=req.diagram_type
                    ):
                        chunk_count += 1
                        if chunk.get('event') == 'node_generated':
                            node_count += 1
                        
                        yield f"data: {json.dumps(chunk)}\n\n"
                
                # Ensure at least one event is yielded to prevent RuntimeError
                if chunk_count == 0:
                    logger.warning("[NodePalette-API] No chunks yielded, sending completion event | Session: %s", session_id[:8])
                    yield f"data: {json.dumps({'event': 'batch_complete', 'nodes': node_count})}\n\n"
                
                logger.debug("[NodePalette-API] Batch complete | Session: %s | Nodes: %d", 
                           session_id[:8], node_count)
                
            except LLMContentFilterError as e:
                logger.warning("[NodePalette-API] Content filter | Session: %s | Error: %s", 
                             session_id[:8], str(e))
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "无法处理您的请求，请尝试修改主题描述。" if req.language == 'zh' else "Content could not be processed. Please try a different topic."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'content_filter', 'message': user_message})}\n\n"
            
            except LLMRateLimitError as e:
                logger.warning("[NodePalette-API] Rate limit | Session: %s | Error: %s", 
                             session_id[:8], str(e))
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "AI服务繁忙，请稍后重试。" if req.language == 'zh' else "AI service is busy. Please try again in a few seconds."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'rate_limit', 'message': user_message})}\n\n"
            
            except LLMTimeoutError as e:
                logger.warning("[NodePalette-API] Timeout | Session: %s | Error: %s", 
                             session_id[:8], str(e))
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "请求超时，请重试。" if req.language == 'zh' else "Request timed out. Please try again."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'timeout', 'message': user_message})}\n\n"
            
            except LLMInvalidParameterError as e:
                logger.warning("[NodePalette-API] Invalid parameter | Session: %s | Error: %s", 
                             session_id[:8], str(e))
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "参数错误，请检查输入。" if req.language == 'zh' else "Invalid parameter. Please check input."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'invalid_parameter', 'message': user_message})}\n\n"
            
            except LLMQuotaExhaustedError as e:
                logger.warning("[NodePalette-API] Quota exhausted | Session: %s | Error: %s", 
                             session_id[:8], str(e))
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "配额已用完，请检查账户。" if req.language == 'zh' else "Quota exhausted. Please check account."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'quota_exhausted', 'message': user_message})}\n\n"
            
            except LLMModelNotFoundError as e:
                logger.warning("[NodePalette-API] Model not found | Session: %s | Error: %s", 
                             session_id[:8], str(e))
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "模型不存在，请检查配置。" if req.language == 'zh' else "Model not found. Please check configuration."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'model_not_found', 'message': user_message})}\n\n"
            
            except LLMAccessDeniedError as e:
                logger.warning("[NodePalette-API] Access denied | Session: %s | Error: %s", 
                             session_id[:8], str(e))
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "访问被拒绝，请检查权限。" if req.language == 'zh' else "Access denied. Please check permissions."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'access_denied', 'message': user_message})}\n\n"
            
            except LLMServiceError as e:
                logger.error("[NodePalette-API] LLM service error | Session: %s | Error: %s", 
                            session_id[:8], str(e))
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "AI服务错误，请稍后重试。" if req.language == 'zh' else "AI service error. Please try again later."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'service_error', 'message': user_message})}\n\n"
            
            except Exception as e:
                logger.error("[NodePalette-API] Stream error | Session: %s | Error: %s", 
                            session_id[:8], str(e), exc_info=True)
                # Fallback for unknown errors
                user_message = "出现问题，请重试。" if req.language == 'zh' else "Something went wrong. Please try again."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'unknown', 'message': user_message})}\n\n"
            finally:
                # Always ensure at least one event is yielded to prevent RuntimeError
                if chunk_count == 0:
                    logger.warning("[NodePalette-API] Generator completed without yielding, sending error event | Session: %s", session_id[:8])
                    user_message = "请求处理失败，请重试。" if req.language == 'zh' else "Request processing failed. Please try again."
                    yield f"data: {json.dumps({'event': 'error', 'error_type': 'no_response', 'message': user_message})}\n\n"
        
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
    logger.debug("[NodePalette-API] POST /next_batch (V2 Concurrent) | Session: %s", session_id[:8])
    
    try:
        # Get appropriate generator based on diagram type (with fallback)
        if req.diagram_type == 'circle_map':
            generator = get_circle_map_palette_generator()
        elif req.diagram_type == 'bubble_map':
            generator = get_bubble_map_palette_generator()
        elif req.diagram_type == 'double_bubble_map':
            generator = get_double_bubble_palette_generator()
        elif req.diagram_type == 'multi_flow_map':
            generator = get_multi_flow_palette_generator()
        elif req.diagram_type == 'tree_map':
            generator = get_tree_map_palette_generator()
        elif req.diagram_type == 'flow_map':
            generator = get_flow_map_palette_generator()
        elif req.diagram_type == 'brace_map':
            generator = get_brace_map_palette_generator()
        elif req.diagram_type == 'bridge_map':
            generator = get_bridge_map_palette_generator()
        elif req.diagram_type == 'mindmap':
            generator = get_mindmap_palette_generator()
        else:
            # Fallback to circle map generator for unsupported types
            logger.warning(f"[NodePalette-API] No specialized generator for {req.diagram_type}, using circle_map fallback")
            generator = get_circle_map_palette_generator()
        
        logger.debug("[NodePalette-API] Type: %s | Firing 4 LLMs concurrently for next batch...", req.diagram_type)
        
        # Stream next batch with concurrent execution
        async def generate():
            node_count = 0
            try:
                # Get mode from request (default to 'similarities' for double bubble, 'causes' for multi flow)
                mode = getattr(req, 'mode', 'similarities' if req.diagram_type == 'double_bubble_map' else 'causes')
                
                # Get stage parameters for multi-stage diagrams (tree_map, brace_map, flow_map, mindmap)
                # Default stage depends on diagram type
                if req.diagram_type == 'mindmap':
                    default_stage = 'branches'  # mindmap uses 'branches' and 'children'
                elif req.diagram_type == 'brace_map':
                    default_stage = 'parts'  # brace map uses 'parts' and 'subparts'
                elif req.diagram_type == 'flow_map':
                    default_stage = 'steps'  # flow map uses 'steps'
                else:  # tree_map
                    default_stage = 'categories'  # tree map uses 'categories' and 'items'
                
                stage = getattr(req, 'stage', default_stage)
                stage_data = getattr(req, 'stage_data', None)
                
                if req.diagram_type in ['double_bubble_map', 'multi_flow_map']:
                    # Tab-enabled diagrams: pass mode parameter
                    async for chunk in generator.generate_batch(
                        session_id=session_id,
                        center_topic=req.center_topic,
                        educational_context=req.educational_context,
                        nodes_per_llm=15,  # 60 total nodes per scroll trigger
                        mode=mode,  # Pass mode for tab-enabled diagrams
                        user_id=current_user.id if current_user else None,
                        organization_id=current_user.organization_id if current_user else None,
                        diagram_type=req.diagram_type
                    ):
                        if chunk.get('event') == 'node_generated':
                            node_count += 1
                        
                        yield f"data: {json.dumps(chunk)}\n\n"
                elif req.diagram_type in ['tree_map', 'brace_map', 'flow_map', 'mindmap']:
                    # Multi-stage diagrams: pass stage and stage_data for progressive workflow
                    logger.debug("[NodePalette-API] %s next batch | Stage: %s | Stage data: %s", req.diagram_type, stage, stage_data)
                    async for chunk in generator.generate_batch(
                        session_id=session_id,
                        center_topic=req.center_topic,
                        educational_context=req.educational_context,
                        nodes_per_llm=15,
                        stage=stage,  # Current stage (dimensions, categories, parts, etc.)
                        stage_data=stage_data,  # Stage-specific data (dimension, category_name, part_name, etc.)
                        user_id=current_user.id if current_user else None,
                        organization_id=current_user.organization_id if current_user else None,
                        diagram_type=req.diagram_type
                    ):
                        if chunk.get('event') == 'node_generated':
                            node_count += 1
                        
                        yield f"data: {json.dumps(chunk)}\n\n"
                else:
                    # Other diagram types: standard call
                    async for chunk in generator.generate_batch(
                        session_id=session_id,
                        center_topic=req.center_topic,
                        educational_context=req.educational_context,
                        nodes_per_llm=15,  # 60 total nodes per scroll trigger
                        user_id=current_user.id if current_user else None,
                        organization_id=current_user.organization_id if current_user else None,
                        diagram_type=req.diagram_type
                    ):
                        if chunk.get('event') == 'node_generated':
                            node_count += 1
                        
                        yield f"data: {json.dumps(chunk)}\n\n"
                
                logger.debug("[NodePalette-API] Next batch complete | Session: %s | Nodes: %d", 
                           session_id[:8], node_count)
                
            except LLMContentFilterError as e:
                logger.warning("[NodePalette-API] Next batch content filter | Session: %s | Error: %s", 
                             session_id[:8], str(e))
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "无法处理您的请求，请尝试修改主题描述。" if req.language == 'zh' else "Content could not be processed."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'content_filter', 'message': user_message})}\n\n"
            
            except LLMRateLimitError as e:
                logger.warning("[NodePalette-API] Next batch rate limit | Session: %s | Error: %s", 
                             session_id[:8], str(e))
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "AI服务繁忙，请稍后重试。" if req.language == 'zh' else "AI service is busy. Please retry."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'rate_limit', 'message': user_message})}\n\n"
            
            except LLMTimeoutError as e:
                logger.warning("[NodePalette-API] Next batch timeout | Session: %s | Error: %s", 
                             session_id[:8], str(e))
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "请求超时，请重试。" if req.language == 'zh' else "Request timed out. Please try again."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'timeout', 'message': user_message})}\n\n"
            
            except LLMInvalidParameterError as e:
                logger.warning("[NodePalette-API] Next batch invalid parameter | Session: %s | Error: %s", 
                             session_id[:8], str(e))
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "参数错误，请检查输入。" if req.language == 'zh' else "Invalid parameter. Please check input."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'invalid_parameter', 'message': user_message})}\n\n"
            
            except LLMQuotaExhaustedError as e:
                logger.warning("[NodePalette-API] Next batch quota exhausted | Session: %s | Error: %s", 
                             session_id[:8], str(e))
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "配额已用完，请检查账户。" if req.language == 'zh' else "Quota exhausted. Please check account."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'quota_exhausted', 'message': user_message})}\n\n"
            
            except LLMModelNotFoundError as e:
                logger.warning("[NodePalette-API] Next batch model not found | Session: %s | Error: %s", 
                             session_id[:8], str(e))
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "模型不存在，请检查配置。" if req.language == 'zh' else "Model not found. Please check configuration."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'model_not_found', 'message': user_message})}\n\n"
            
            except LLMAccessDeniedError as e:
                logger.warning("[NodePalette-API] Next batch access denied | Session: %s | Error: %s", 
                             session_id[:8], str(e))
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "访问被拒绝，请检查权限。" if req.language == 'zh' else "Access denied. Please check permissions."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'access_denied', 'message': user_message})}\n\n"
            
            except LLMServiceError as e:
                logger.error("[NodePalette-API] Next batch LLM service error | Session: %s | Error: %s", 
                            session_id[:8], str(e))
                user_message = getattr(e, 'user_message', None)
                if not user_message:
                    user_message = "AI服务错误，请稍后重试。" if req.language == 'zh' else "AI service error. Please try again later."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'service_error', 'message': user_message})}\n\n"
            
            except Exception as e:
                logger.error("[NodePalette-API] Next batch error | Session: %s | Error: %s", 
                            session_id[:8], str(e), exc_info=True)
                # Fallback for unknown errors
                user_message = "出现问题，请重试。" if req.language == 'zh' else "Something went wrong. Please try again."
                yield f"data: {json.dumps({'event': 'error', 'error_type': 'unknown', 'message': user_message})}\n\n"
        
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
    logger.debug("[NodePalette-Selection] User %s node | Session: %s | Node: '%s' | ID: %s", 
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
    
    logger.debug("[NodePalette-Finish] User closed palette | Session: %s", session_id[:8])
    logger.debug("[NodePalette-Finish]   Selected: %d/%d nodes | Batches: %d | Selection rate: %.1f%%", 
               selected_count, total_generated, batches_loaded, 
               (selected_count/max(total_generated,1))*100)
    
    # NOTE: Do NOT end the session here!
    # Session should persist throughout the entire canvas session.
    # User may return to Node Palette multiple times to add more nodes.
    # Session will be properly cleaned up when user leaves canvas (backToGallery).
    
    return {"status": "palette_closed"}


@router.post("/thinking_mode/node_palette/cancel")
async def node_palette_cancel(
    request: NodePaletteFinishRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Handle Node Palette cancellation.
    
    User clicked Cancel button - log the event and end session without adding nodes.
    """
    session_id = request.session_id
    selected_count = len(request.selected_node_ids)  # Use the correct field from request model
    total_generated = request.total_nodes_generated
    batches_loaded = request.batches_loaded
    
    logger.debug("[NodePalette-Cancel] User cancelled palette | Session: %s", session_id[:8])
    logger.debug("[NodePalette-Cancel]   Selected: %d/%d nodes (NOT added) | Batches: %d", 
               selected_count, total_generated, batches_loaded)
    
    # NOTE: Do NOT end the session here!
    # User may have clicked Cancel by mistake and want to reopen.
    # Session will be properly cleaned up when user leaves canvas (backToGallery).
    
    return {"status": "palette_cancelled"}


@router.post("/thinking_mode/node_palette/cleanup")
async def node_palette_cleanup(
    request: NodePaletteCleanupRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Clean up Node Palette session when user leaves canvas.
    
    Called from diagram-selector.js backToGallery() to properly end session
    and free memory when user exits to gallery.
    """
    session_id = request.session_id
    diagram_type = request.diagram_type or 'circle_map'
    
    logger.debug("[NodePalette-Cleanup] Ending session (user left canvas) | Session: %s", session_id[:8])
    
    # Get appropriate generator and end session
    if diagram_type == 'circle_map':
        generator = get_circle_map_palette_generator()
    elif diagram_type == 'bubble_map':
        generator = get_bubble_map_palette_generator()
    elif diagram_type == 'double_bubble_map':
        generator = get_double_bubble_palette_generator()
    elif diagram_type == 'multi_flow_map':
        generator = get_multi_flow_palette_generator()
    elif diagram_type == 'tree_map':
        generator = get_tree_map_palette_generator()
    elif diagram_type == 'flow_map':
        generator = get_flow_map_palette_generator()
    elif diagram_type == 'brace_map':
        generator = get_brace_map_palette_generator()
    elif diagram_type == 'bridge_map':
        generator = get_bridge_map_palette_generator()
    elif diagram_type == 'mindmap':
        generator = get_mindmap_palette_generator()
    else:
        generator = get_circle_map_palette_generator()
    
    generator.end_session(session_id, reason="canvas_exit")
    
    return {"status": "session_cleaned"}


# Debug endpoint removed - V2 generator uses different session tracking
# Use browser console logs and server logs for debugging instead
# @router.get('/thinking_mode/node_palette/debug/{session_id}')
# async def debug_node_palette_session(session_id: str):
#     """Debug endpoint (deprecated - use logs instead)"""
#     pass

