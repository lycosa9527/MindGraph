"""
Layout Recalculation API Router
================================

API endpoint for recalculating mind map layouts:
- /api/recalculate_mindmap_layout: Recalculate layout after node changes

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from models.auth import User
from utils.auth import get_current_user_or_api_key
from models import RecalculateLayoutRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


@router.post('/recalculate_mindmap_layout')
async def recalculate_mindmap_layout(
    req: RecalculateLayoutRequest,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Recalculate mind map layout after nodes are added/removed via node palette.
    
    This endpoint takes the current spec with new branches and recalculates
    the _layout and positioning data using the MindMapAgent.
    """
    try:
        spec = req.spec
        
        # Validate that it's a mindmap
        # Use isinstance check to allow empty string (for empty button functionality)
        if not isinstance(spec.get('topic'), str):
            raise HTTPException(
                status_code=400,
                detail="Invalid spec: 'topic' field is required for mindmaps"
            )
        
        # Import MindMapAgent
        from agents.mind_maps.mind_map_agent import MindMapAgent
        
        # Create agent instance
        mind_map_agent = MindMapAgent(model='qwen')
        
        # Use enhance_spec to recalculate layout
        enhanced_spec = await mind_map_agent.enhance_spec(spec)
        
        if not enhanced_spec.get('_layout'):
            raise HTTPException(
                status_code=500,
                detail="Failed to calculate layout"
            )
        
        logger.debug(f"[RecalculateLayout] Layout recalculated for {len(spec.get('children', []))} branches")
        
        return {
            'success': True,
            'spec': enhanced_spec
        }
        
    except Exception as e:
        logger.error(f"[RecalculateLayout] Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Layout recalculation failed: {str(e)}"
        )

