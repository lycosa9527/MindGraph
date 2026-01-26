"""Tab Mode Router.

API endpoints for Tab Mode feature:
- /api/tab_suggestions: Autocomplete suggestions for editing mode
- /api/tab_expand: Node expansion for viewing mode

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved.
Proprietary License.
"""

from typing import Optional
import logging
import time

from fastapi import APIRouter, Depends, HTTPException

from agents.tab_mode import TabAgent
from config.settings import config
from models import Messages, get_request_language
from models.domain.auth import User
from models.requests.requests_thinking import TabExpandRequest, TabSuggestionRequest
from models.responses import TabExpandChild, TabExpandResponse, TabSuggestionItem, TabSuggestionResponse
from utils.auth import get_current_user_or_api_key
from services.infrastructure.http.error_handler import (
    LLMServiceError,
    LLMContentFilterError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMInvalidParameterError,
    LLMQuotaExhaustedError,
    LLMModelNotFoundError,
    LLMAccessDeniedError
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["tab_mode"])


@router.post('/tab_suggestions', response_model=TabSuggestionResponse)
async def tab_suggestions(
    req: TabSuggestionRequest,
    x_language: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Get autocomplete suggestions for editing mode.

    Provides context-aware completion suggestions when users type in node inputs.
    """
    # Check if Tab Mode feature is enabled
    if not config.FEATURE_TAB_MODE:
        lang = get_request_language(x_language, "")
        raise HTTPException(
            status_code=403,
            detail=Messages.error("invalid_request", lang) + " (Tab Mode feature is disabled)"
        )

    lang = get_request_language(x_language, "")
    request_id = f"tab_{int(time.time()*1000)}"

    try:
        # Validate request
        if not req.partial_input or len(req.partial_input.strip()) < 1:
            req.partial_input = ""  # Empty input for general suggestions

        # Get user context
        user_id = current_user.id if current_user and hasattr(current_user, 'id') else None
        organization_id = (
            getattr(current_user, 'organization_id', None)
            if current_user and hasattr(current_user, 'id') else None
        )

        # Determine model (default to doubao for generation)
        model = 'doubao'
        if req.llm:
            if hasattr(req.llm, 'value'):
                model_str = req.llm.value
            else:
                model_str = str(req.llm)
            # Use specified model (doubao is default)
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
            organization_id=organization_id,
            page_offset=req.page_offset
        )

        # Format suggestions
        suggestions = [
            TabSuggestionItem(text=text, confidence=0.9 - (idx * 0.1))
            for idx, text in enumerate(suggestions_text)
        ]

        logger.debug("[%s] Generated %s suggestions", request_id, len(suggestions))

        return TabSuggestionResponse(
            success=True,
            mode="autocomplete",
            suggestions=suggestions,
            request_id=request_id
        )

    except LLMContentFilterError as e:
        logger.warning("[%s] Content filter: %s", request_id, e)
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = Messages.error("llm_service_error", lang)
        raise HTTPException(status_code=400, detail=user_message) from e

    except LLMRateLimitError as e:
        logger.warning("[%s] Rate limit: %s", request_id, e)
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "AI服务繁忙，请稍后重试。" if lang == 'zh' else "AI service is busy. Please try again later."
        raise HTTPException(status_code=429, detail=user_message) from e

    except LLMTimeoutError as e:
        logger.warning("[%s] Timeout: %s", request_id, e)
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "请求超时，请重试。" if lang == 'zh' else "Request timed out. Please try again."
        raise HTTPException(status_code=504, detail=user_message) from e

    except LLMInvalidParameterError as e:
        logger.warning("[%s] Invalid parameter: %s", request_id, e)
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "参数错误，请检查输入。" if lang == 'zh' else "Invalid parameter. Please check input."
        raise HTTPException(status_code=400, detail=user_message) from e

    except LLMQuotaExhaustedError as e:
        logger.warning("[%s] Quota exhausted: %s", request_id, e)
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "配额已用完，请检查账户。" if lang == 'zh' else "Quota exhausted. Please check account."
        raise HTTPException(status_code=402, detail=user_message) from e

    except LLMModelNotFoundError as e:
        logger.warning("[%s] Model not found: %s", request_id, e)
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "模型不存在，请检查配置。" if lang == 'zh' else "Model not found. Please check configuration."
        raise HTTPException(status_code=404, detail=user_message) from e

    except LLMAccessDeniedError as e:
        logger.warning("[%s] Access denied: %s", request_id, e)
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "访问被拒绝，请检查权限。" if lang == 'zh' else "Access denied. Please check permissions."
        raise HTTPException(status_code=403, detail=user_message) from e

    except LLMServiceError as e:
        logger.error("[%s] LLM service error: %s", request_id, e)
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = Messages.error("llm_service_error", lang)
        raise HTTPException(status_code=503, detail=user_message) from e
    except ValueError as e:
        logger.error("[%s] Validation error: %s", request_id, e)
        raise HTTPException(
            status_code=400,
            detail=Messages.error("validation_error", lang)
        ) from e
    except Exception as e:
        logger.error("[%s] Unexpected error: %s", request_id, e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=Messages.error("internal_error", lang)
        ) from e


@router.post('/tab_expand', response_model=TabExpandResponse)
async def tab_expand(
    req: TabExpandRequest,
    x_language: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Expand a node by generating child nodes.

    Returns generated child nodes for hierarchical diagrams (mindmap, tree map, flow map, brace map).
    """
    # Check if Tab Mode feature is enabled
    if not config.FEATURE_TAB_MODE:
        lang = get_request_language(x_language, "")
        raise HTTPException(
            status_code=403,
            detail=Messages.error("invalid_request", lang) + " (Tab Mode feature is disabled)"
        )

    lang = get_request_language(x_language, "")
    request_id = f"tab_expand_{int(time.time()*1000)}"

    try:
        # Get user context
        user_id = current_user.id if current_user and hasattr(current_user, 'id') else None
        organization_id = (
            getattr(current_user, 'organization_id', None)
            if current_user and hasattr(current_user, 'id') else None
        )

        # Determine model (default to doubao for generation)
        model = 'doubao'
        if req.llm:
            if hasattr(req.llm, 'value'):
                model_str = req.llm.value
            else:
                model_str = str(req.llm)
            # Use specified model (doubao is default)
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

        logger.debug("[%s] Generated %s children for node %s", request_id, len(children), req.node_id)

        return TabExpandResponse(
            success=True,
            mode="expansion",
            children=[TabExpandChild(text=c['text'], id=c['id']) for c in children],
            request_id=request_id
        )

    except LLMContentFilterError as e:
        logger.warning("[%s] Content filter: %s", request_id, e)
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = Messages.error("llm_service_error", lang)
        raise HTTPException(status_code=400, detail=user_message) from e

    except LLMRateLimitError as e:
        logger.warning("[%s] Rate limit: %s", request_id, e)
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "AI服务繁忙，请稍后重试。" if lang == 'zh' else "AI service is busy. Please try again later."
        raise HTTPException(status_code=429, detail=user_message) from e

    except LLMTimeoutError as e:
        logger.warning("[%s] Timeout: %s", request_id, e)
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "请求超时，请重试。" if lang == 'zh' else "Request timed out. Please try again."
        raise HTTPException(status_code=504, detail=user_message) from e

    except LLMInvalidParameterError as e:
        logger.warning("[%s] Invalid parameter: %s", request_id, e)
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "参数错误，请检查输入。" if lang == 'zh' else "Invalid parameter. Please check input."
        raise HTTPException(status_code=400, detail=user_message) from e

    except LLMQuotaExhaustedError as e:
        logger.warning("[%s] Quota exhausted: %s", request_id, e)
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "配额已用完，请检查账户。" if lang == 'zh' else "Quota exhausted. Please check account."
        raise HTTPException(status_code=402, detail=user_message) from e

    except LLMModelNotFoundError as e:
        logger.warning("[%s] Model not found: %s", request_id, e)
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "模型不存在，请检查配置。" if lang == 'zh' else "Model not found. Please check configuration."
        raise HTTPException(status_code=404, detail=user_message) from e

    except LLMAccessDeniedError as e:
        logger.warning("[%s] Access denied: %s", request_id, e)
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = "访问被拒绝，请检查权限。" if lang == 'zh' else "Access denied. Please check permissions."
        raise HTTPException(status_code=403, detail=user_message) from e

    except LLMServiceError as e:
        logger.error("[%s] LLM service error: %s", request_id, e)
        user_message = getattr(e, 'user_message', None)
        if not user_message:
            user_message = Messages.error("llm_service_error", lang)
        raise HTTPException(status_code=503, detail=user_message) from e
    except ValueError as e:
        logger.error("[%s] Validation error: %s", request_id, e)
        raise HTTPException(
            status_code=400,
            detail=Messages.error("validation_error", lang)
        ) from e
    except Exception as e:
        logger.error("[%s] Unexpected error: %s", request_id, e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=Messages.error("internal_error", lang)
        ) from e
