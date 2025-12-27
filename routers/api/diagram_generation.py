"""
Diagram Generation API Router
==============================

API endpoint for diagram generation:
- /api/generate_graph: Generate graph specification from user prompt

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from models.auth import User
from utils.auth import get_current_user_or_api_key
from models import GenerateRequest, GenerateResponse, Messages, get_request_language
from agents import main_agent as agent
from .helpers import get_rate_limit_identifier, check_endpoint_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


@router.post('/generate_graph', response_model=GenerateResponse)
async def generate_graph(
    req: GenerateRequest,
    request: Request,
    x_language: str = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Generate graph specification from user prompt using selected LLM model (async).
    
    This endpoint returns JSON with the diagram specification for the frontend editor to render.
    For PNG file downloads, use /api/export_png instead.
    
    Rate limited: 100 requests per minute per user/IP.
    """
    # Rate limiting: 100 requests per minute per user/IP
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit('generate_graph', identifier, max_requests=100, window_seconds=60)
    
    # Get language for error messages
    lang = get_request_language(x_language)
    
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(
            status_code=400,
            detail=Messages.error("invalid_prompt", lang)
        )
    
    request_id = f"gen_{int(time.time()*1000)}"
    llm_model = req.llm.value if hasattr(req.llm, 'value') else str(req.llm)
    language = req.language.value if hasattr(req.language, 'value') else str(req.language)
    
    logger.debug(f"[{request_id}] Request: llm={llm_model!r}, language={language!r}, diagram_type={req.diagram_type}")
    
    if req.dimension_preference:
        logger.debug(f"[{request_id}] Dimension preference: {req.dimension_preference!r}")
    
    logger.debug(f"[{request_id}] Using LLM model: {llm_model!r}")
    
    try:
        # Generate diagram specification - fully async
        # Pass model directly through call chain (no global state)
        # Pass user context for token tracking
        user_id = current_user.id if current_user and hasattr(current_user, 'id') else None
        organization_id = getattr(current_user, 'organization_id', None) if current_user and hasattr(current_user, 'id') else None
        
        # Determine request type for token tracking (default to 'diagram_generation')
        request_type = req.request_type if req.request_type else 'diagram_generation'
        
        # Set request state for middleware slow warning detection
        # This allows middleware to distinguish autocomplete from initial generation
        request.state.is_autocomplete = (request_type == 'autocomplete')
        
        # Track user activity
        if current_user and hasattr(current_user, 'id'):
            try:
                from services.redis_activity_tracker import get_activity_tracker
                tracker = get_activity_tracker()
                activity_type = 'autocomplete' if request_type == 'autocomplete' else 'diagram_generation'
                diagram_type_str = req.diagram_type.value if req.diagram_type else 'unknown'
                tracker.record_activity(
                    user_id=current_user.id,
                    user_phone=getattr(current_user, 'phone', None),
                    activity_type=activity_type,
                    details={'diagram_type': diagram_type_str, 'llm_model': llm_model},
                    user_name=getattr(current_user, 'name', None)
                )
            except Exception as e:
                logger.debug(f"Failed to track user activity: {e}")
        
        # Log auto-complete start at INFO level for user activity tracking
        # Note: AutoComplete fires 5 concurrent requests (one per LLM model)
        # Log once per request with model info to reduce noise
        if request_type == 'autocomplete':
            diagram_type_str = req.diagram_type.value if req.diagram_type else 'auto'
            logger.info(f"[AutoComplete] Started: User {user_id}, Diagram: {diagram_type_str}, Model: {llm_model}, Request: {request_id[:8]}")
        
        # Bridge map specific: pass existing analogies and fixed dimension for auto-complete mode
        existing_analogies = req.existing_analogies if hasattr(req, 'existing_analogies') else None
        fixed_dimension = req.fixed_dimension if hasattr(req, 'fixed_dimension') else None
        # Tree map and brace map: dimension-only mode flag
        dimension_only_mode = req.dimension_only_mode if hasattr(req, 'dimension_only_mode') else None
        
        result = await agent.agent_graph_workflow_with_styles(
            prompt,
            language=language,
            forced_diagram_type=req.diagram_type.value if req.diagram_type else None,
            dimension_preference=req.dimension_preference,
            model=llm_model,  # Pass model explicitly (fixes race condition)
            # Token tracking parameters
            user_id=user_id,
            organization_id=organization_id,
            request_type=request_type,
            endpoint_path='/api/generate_graph',
            # Bridge map specific
            existing_analogies=existing_analogies,
            fixed_dimension=fixed_dimension,
            # Tree map and brace map: dimension-only mode
            dimension_only_mode=dimension_only_mode
        )
        
        diagram_type = result.get('diagram_type', 'unknown')
        logger.debug(f"[{request_id}] Generated {diagram_type} diagram with {llm_model}")
        
        # Log auto-complete operations at INFO level for user activity tracking
        if request_type == 'autocomplete':
            node_count = len(result.get('nodes', [])) if isinstance(result.get('nodes'), list) else 0
            logger.info(f"[AutoComplete] Completed: User {user_id}, Diagram {diagram_type}, Nodes added: {node_count}, Model: {llm_model}, Request: {request_id[:8]}")
        
        # Add metadata
        result['llm_model'] = llm_model
        result['request_id'] = request_id
        
        return result
        
    except Exception as e:
        logger.error(f"[{request_id}] Error generating graph: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=Messages.error("generation_failed", lang, str(e))
        )

