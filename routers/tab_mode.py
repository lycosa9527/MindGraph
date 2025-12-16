"""
Tab Mode Router
===============

API endpoints for Tab Mode feature:
- /api/tab_suggestions: Autocomplete suggestions for editing mode
- /api/tab_expand: Node expansion for viewing mode

@author MindGraph Team
"""

import logging
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from models.auth import User
from utils.auth import get_current_user_or_api_key
from models.requests import TabSuggestionRequest, TabExpandRequest
from models.responses import TabSuggestionResponse, TabExpandResponse, TabSuggestionItem, TabExpandChild
from models import Messages, get_request_language
from agents.tab_mode import TabAgent
from services.error_handler import (
    LLMServiceError,
    LLMContentFilterError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMInvalidParameterError,
    LLMQuotaExhaustedError,
    LLMModelNotFoundError,
    LLMAccessDeniedError
)
from config.settings import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["tab_mode"])


@router.post('/tab_suggestions', response_model=TabSuggestionResponse)
async def tab_suggestions(
    req: TabSuggestionRequest,
    x_language: str = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Get autocomplete suggestions for editing mode.
    
    Provides context-aware completion suggestions when users type in node inputs.
    """
    # Check if Tab Mode feature is enabled
    if not config.FEATURE_TAB_MODE:
        lang = get_request_language(x_language)
        raise HTTPException(
            status_code=403,
            detail=Messages.error("invalid_request", lang) + " (Tab Mode feature is disabled)"
        )
    
    lang = get_request_language(x_language)
    request_id = f"tab_{int(time.time()*1000)}"
    
    try:
        # Validate request
        if not req.partial_input or len(req.partial_input.strip()) < 1:
            req.partial_input = ""  # Empty input for general suggestions
        
        # Get user context
        user_id = current_user.id if current_user else None
        organization_id = current_user.organization_id if current_user else None
        
        # Determine model (default to qwen-plus for generation)
        model = 'qwen-plus'
        if req.llm:
            if hasattr(req.llm, 'value'):
                model_str = req.llm.value
            else:
                model_str = str(req.llm)
            # Map 'qwen' to 'qwen-plus' for generation tasks
            if model_str == 'qwen':
                model = 'qwen-plus'
            else:
                model = model_str
        
        # Create agent
        agent = TabAgent(model=model)
        
        # Generate suggestions
        suggestions_text = await agent.generate_suggestions(
            diagram_type=req.diagram_type.value if hasattr(req.diagram_type, 'value') else str(req.diagram_type),
            main_topics=req.main_topics,
            partial_input=req.partial_input,
            node_category=req.node_category,
            existing_nodes=req.existing_nodes,
            language=req.language.value if hasattr(req.language, 'value') else str(req.language),
            user_id=user_id,
            organization_id=organization_id
        )
        
        # Format suggestions
        suggestions = [
            TabSuggestionItem(text=text, confidence=0.9 - (idx * 0.1))
            for idx, text in enumerate(suggestions_text)
        ]
        
        logger.debug(f"[{request_id}] Generated {len(suggestions)} suggestions")
        
        return TabSuggestionResponse(
            success=True,
            mode="autocomplete",
            suggestions=suggestions,
            request_id=request_id
        )
        
    except LLMContentFilterError as e:
        logger.warning(f"[{request_id}] Content filter: {e}")
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = Messages.error("llm_service_error", lang)
        raise HTTPException(status_code=400, detail=user_message)
    
    except LLMRateLimitError as e:
        logger.warning(f"[{request_id}] Rate limit: {e}")
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "AI服务繁忙，请稍后重试。" if lang == 'zh' else "AI service is busy. Please try again later."
        raise HTTPException(status_code=429, detail=user_message)
    
    except LLMTimeoutError as e:
        logger.warning(f"[{request_id}] Timeout: {e}")
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "请求超时，请重试。" if lang == 'zh' else "Request timed out. Please try again."
        raise HTTPException(status_code=504, detail=user_message)
    
    except LLMInvalidParameterError as e:
        logger.warning(f"[{request_id}] Invalid parameter: {e}")
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "参数错误，请检查输入。" if lang == 'zh' else "Invalid parameter. Please check input."
        raise HTTPException(status_code=400, detail=user_message)
    
    except LLMQuotaExhaustedError as e:
        logger.warning(f"[{request_id}] Quota exhausted: {e}")
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "配额已用完，请检查账户。" if lang == 'zh' else "Quota exhausted. Please check account."
        raise HTTPException(status_code=402, detail=user_message)
    
    except LLMModelNotFoundError as e:
        logger.warning(f"[{request_id}] Model not found: {e}")
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "模型不存在，请检查配置。" if lang == 'zh' else "Model not found. Please check configuration."
        raise HTTPException(status_code=404, detail=user_message)
    
    except LLMAccessDeniedError as e:
        logger.warning(f"[{request_id}] Access denied: {e}")
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "访问被拒绝，请检查权限。" if lang == 'zh' else "Access denied. Please check permissions."
        raise HTTPException(status_code=403, detail=user_message)
    
    except LLMServiceError as e:
        logger.error(f"[{request_id}] LLM service error: {e}")
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = Messages.error("llm_service_error", lang)
        raise HTTPException(status_code=503, detail=user_message)
    except ValueError as e:
        logger.error(f"[{request_id}] Validation error: {e}")
        raise HTTPException(
            status_code=400,
            detail=Messages.error("validation_error", lang)
        )
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=Messages.error("internal_error", lang)
        )


@router.post('/tab_expand', response_model=TabExpandResponse)
async def tab_expand(
    req: TabExpandRequest,
    x_language: str = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Expand a node by generating child nodes.
    
    Returns generated child nodes for hierarchical diagrams (mindmap, tree map, flow map, brace map).
    """
    # Check if Tab Mode feature is enabled
    if not config.FEATURE_TAB_MODE:
        lang = get_request_language(x_language)
        raise HTTPException(
            status_code=403,
            detail=Messages.error("invalid_request", lang) + " (Tab Mode feature is disabled)"
        )
    
    lang = get_request_language(x_language)
    request_id = f"tab_expand_{int(time.time()*1000)}"
    
    try:
        # Get user context
        user_id = current_user.id if current_user else None
        organization_id = current_user.organization_id if current_user else None
        
        # Determine model (default to qwen-plus for generation)
        model = 'qwen-plus'
        if req.llm:
            if hasattr(req.llm, 'value'):
                model_str = req.llm.value
            else:
                model_str = str(req.llm)
            # Map 'qwen' to 'qwen-plus' for generation tasks
            if model_str == 'qwen':
                model = 'qwen-plus'
            else:
                model = model_str
        
        # Create agent
        agent = TabAgent(model=model)
        
        # Generate expansion
        children = await agent.generate_expansion(
            diagram_type=req.diagram_type.value if hasattr(req.diagram_type, 'value') else str(req.diagram_type),
            node_text=req.node_text,
            main_topic=req.main_topic,
            node_type=req.node_type,
            existing_children=req.existing_children,
            num_children=req.num_children or 4,
            language=req.language.value if hasattr(req.language, 'value') else str(req.language),
            user_id=user_id,
            organization_id=organization_id
        )
        
        logger.debug(f"[{request_id}] Generated {len(children)} children for node {req.node_id}")
        
        return TabExpandResponse(
            success=True,
            mode="expansion",
            children=[TabExpandChild(text=c['text'], id=c['id']) for c in children],
            request_id=request_id
        )
        
    except LLMContentFilterError as e:
        logger.warning(f"[{request_id}] Content filter: {e}")
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = Messages.error("llm_service_error", lang)
        raise HTTPException(status_code=400, detail=user_message)
    
    except LLMRateLimitError as e:
        logger.warning(f"[{request_id}] Rate limit: {e}")
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "AI服务繁忙，请稍后重试。" if lang == 'zh' else "AI service is busy. Please try again later."
        raise HTTPException(status_code=429, detail=user_message)
    
    except LLMTimeoutError as e:
        logger.warning(f"[{request_id}] Timeout: {e}")
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "请求超时，请重试。" if lang == 'zh' else "Request timed out. Please try again."
        raise HTTPException(status_code=504, detail=user_message)
    
    except LLMInvalidParameterError as e:
        logger.warning(f"[{request_id}] Invalid parameter: {e}")
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "参数错误，请检查输入。" if lang == 'zh' else "Invalid parameter. Please check input."
        raise HTTPException(status_code=400, detail=user_message)
    
    except LLMQuotaExhaustedError as e:
        logger.warning(f"[{request_id}] Quota exhausted: {e}")
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "配额已用完，请检查账户。" if lang == 'zh' else "Quota exhausted. Please check account."
        raise HTTPException(status_code=402, detail=user_message)
    
    except LLMModelNotFoundError as e:
        logger.warning(f"[{request_id}] Model not found: {e}")
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "模型不存在，请检查配置。" if lang == 'zh' else "Model not found. Please check configuration."
        raise HTTPException(status_code=404, detail=user_message)
    
    except LLMAccessDeniedError as e:
        logger.warning(f"[{request_id}] Access denied: {e}")
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "访问被拒绝，请检查权限。" if lang == 'zh' else "Access denied. Please check permissions."
        raise HTTPException(status_code=403, detail=user_message)
    
    except LLMServiceError as e:
        logger.error(f"[{request_id}] LLM service error: {e}")
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = Messages.error("llm_service_error", lang)
        raise HTTPException(status_code=503, detail=user_message)
    except ValueError as e:
        logger.error(f"[{request_id}] Validation error: {e}")
        raise HTTPException(
            status_code=400,
            detail=Messages.error("validation_error", lang)
        )
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=Messages.error("internal_error", lang)
        )

