"""
PNG Export API Router
=====================

API endpoints for PNG export functionality:
- /api/export_png: Export diagram as PNG from diagram data
- /api/generate_png: Generate PNG directly from user prompt
- /api/generate_dingtalk: Generate PNG for DingTalk integration
- /api/temp_images/{filepath}: Serve temporary PNG files

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import os
import time
import uuid

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import Response, PlainTextResponse, FileResponse
import aiofiles
import aiofiles.os

from models import (
    ExportPNGRequest,
    GeneratePNGRequest,
    GenerateDingTalkRequest,
    Messages,
    get_request_language
)
from models.domain.auth import User
from utils.auth import get_current_user_or_api_key
from config.settings import config
from prompts import get_prompt

from agents.core.agent_utils import extract_json_from_response
from agents.core.learning_sheet import _detect_learning_sheet_from_prompt, _clean_prompt_for_learning_sheet
from agents.mind_maps.mind_map_agent import MindMapAgent

from services.llm import llm_service
from services.monitoring.activity_stream import get_activity_stream_service
from services.redis.redis_token_buffer import get_token_tracker

from .helpers import (
    check_endpoint_rate_limit,
    get_rate_limit_identifier,
    generate_signed_url,
    verify_signed_url
)
from .png_export_core import export_png_core

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


async def _export_png_core(
    diagram_data: Dict[str, Any],
    diagram_type: str,
    width: int = 1200,
    height: int = 800,
    scale: int = 2,
    _x_language: Optional[str] = None,
    _base_url: Optional[str] = None
) -> bytes:
    """
    Wrapper for core PNG export function.

    Delegates to png_export_core module to keep this file manageable.
    """
    return await export_png_core(
        diagram_data=diagram_data,
        diagram_type=diagram_type,
        width=width,
        height=height,
        scale=scale,
        _x_language=_x_language,
        _base_url=_base_url
    )


@router.post('/export_png')
async def export_png(
    req: ExportPNGRequest,
    request: Request,
    x_language: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Export diagram as PNG using Playwright browser automation (async).

    Uses the core export function that embeds JS directly for reliability.
    This avoids HTTP script loading issues and ensures consistent behavior.

    Rate limited: 100 requests per minute per user/IP (PNG generation is expensive).
    """
    # Rate limiting: 100 requests per minute per user/IP (PNG generation is expensive)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit('export_png', identifier, max_requests=100, window_seconds=60)

    # Get language for error messages
    accept_language = request.headers.get("Accept-Language", "")
    lang = get_request_language(x_language, accept_language)

    diagram_data = req.diagram_data
    diagram_type = req.diagram_type.value if hasattr(req.diagram_type, 'value') else str(req.diagram_type)

    if not diagram_data:
        raise HTTPException(
            status_code=400,
            detail=Messages.error("diagram_data_required", lang)
        )

    logger.debug("PNG export request - diagram_type: %s, data keys: %s", diagram_type, list(diagram_data.keys()))

    try:
        # Normalize diagram type (same as generate_dingtalk)
        if diagram_type == 'mindmap':
            diagram_type = 'mind_map'

        # Ensure diagram_data is a dict and add any missing metadata (same as generate_dingtalk)
        if isinstance(diagram_data, dict):
            # Add learning sheet metadata if not present (defaults to False/0)
            if 'is_learning_sheet' not in diagram_data:
                diagram_data['is_learning_sheet'] = False
            if 'hidden_node_percentage' not in diagram_data:
                diagram_data['hidden_node_percentage'] = 0

        # Use the core export function which embeds JS directly (more reliable than HTTP loading)
        # Match generate_dingtalk exactly: same defaults, same parameters
        screenshot_bytes = await _export_png_core(
            diagram_data=diagram_data,
            diagram_type=diagram_type,
            width=req.width or 1200,
            height=req.height or 800,
            scale=req.scale or 2,
            _x_language=x_language
        )

        # Return PNG as response
        return Response(
            content=screenshot_bytes,
            media_type="image/png",
            headers={
                'Content-Disposition': 'attachment; filename="diagram.png"'
            }
        )

    except Exception as e:
        logger.error("PNG export error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=Messages.error("export_failed", lang, str(e))
        ) from e


@router.post('/generate_png')
async def generate_png_from_prompt(
    req: GeneratePNGRequest,
    request: Request,
    x_language: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Generate PNG directly from user prompt using simplified prompt-to-diagram agent.

    Uses only Qwen in a single LLM call for fast, efficient diagram generation.

    Rate limited: 100 requests per minute per user/IP (PNG generation is expensive).
    """
    # Rate limiting: 100 requests per minute per user/IP (PNG generation is expensive)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit('generate_png', identifier, max_requests=100, window_seconds=60)

    accept_language = request.headers.get("Accept-Language", "")
    lang = get_request_language(x_language, accept_language)
    prompt = req.prompt.strip()

    if not prompt:
        raise HTTPException(status_code=400, detail=Messages.error("invalid_prompt", lang))

    if req.language and hasattr(req.language, 'value'):
        language = req.language.value
    elif req.language:
        language = str(req.language)
    else:
        language = 'zh'
    if language not in ['zh', 'en']:
        raise HTTPException(status_code=400, detail="Invalid language. Must be 'zh' or 'en'")

    logger.info("[GeneratePNG] Request: prompt='%s', language='%s'", prompt, language)

    try:
        # Use simplified prompt-to-diagram approach (single Qwen call)
        user_id = current_user.id if current_user and hasattr(current_user, 'id') else None
        if current_user and hasattr(current_user, 'id'):
            organization_id = getattr(current_user, 'organization_id', None)
        else:
            organization_id = None

        # Detect learning sheet from prompt
        is_learning_sheet = _detect_learning_sheet_from_prompt(prompt, language)
        logger.debug("[GeneratePNG] Learning sheet detected: %s", is_learning_sheet)

        # Clean prompt for learning sheets to generate actual content, not meta-content
        generation_prompt = _clean_prompt_for_learning_sheet(prompt) if is_learning_sheet else prompt
        if is_learning_sheet:
            logger.debug("[GeneratePNG] Using cleaned prompt for generation: '%s'", generation_prompt)

        # Get prompt from centralized system
        prompt_template = get_prompt('prompt_to_diagram', language, 'generation')

        if not prompt_template:
            error_detail = Messages.error(
                "generation_failed", lang,
                f"No prompt template found for language {language}"
            )
            raise HTTPException(status_code=500, detail=error_detail)

        # Format prompt with cleaned user input
        formatted_prompt = prompt_template.format(user_prompt=generation_prompt)

        # Call LLM service - single call with Qwen only

        # Get API key ID from request state if API key was used
        api_key_id = None
        if hasattr(request, 'state'):
            api_key_id = getattr(request.state, 'api_key_id', None)
            if api_key_id:
                logger.debug("[GeneratePNG] Using API key ID %s for token tracking", api_key_id)
        else:
            logger.debug("[GeneratePNG] Request state not available")

        start_time = time.time()
        response, usage_data = await llm_service.chat_with_usage(
            prompt=formatted_prompt,
            model='qwen',  # Force Qwen only
            max_tokens=2000,
            temperature=config.LLM_TEMPERATURE,
            user_id=user_id,
            organization_id=organization_id,
            api_key_id=api_key_id,
            request_type='diagram_generation',
            endpoint_path='/api/generate_png'
        )

        if not response:
            if lang == 'zh':
                error_msg = (
                    "无法理解您的意图，请更具体地说明图表类型和主题，"
                    "或点击下方的图表卡片。"
                )
            else:
                error_msg = (
                    "Unable to process user's intention, please be more specific "
                    "about the diagram type and topic, or click the diagrams card below."
                )
            raise HTTPException(status_code=500, detail=error_msg)

        # Extract JSON from response
        result = extract_json_from_response(response)

        # Check for non-JSON response (LLM asking for more information)
        if isinstance(result, dict) and result.get('_error') == 'non_json_response':
            logger.warning("[GeneratePNG] LLM returned non-JSON response asking for more info")
            if lang == 'zh':
                error_msg = (
                    "无法理解您的意图，请更具体地说明图表类型和主题，"
                    "或点击下方的图表卡片。"
                )
            else:
                error_msg = (
                    "Unable to process user's intention, please be more specific "
                    "about the diagram type and topic, or click the diagrams card below."
                )
            raise HTTPException(status_code=400, detail=error_msg)

        # Check if JSON extraction failed
        if not isinstance(result, dict) or 'spec' not in result:
            logger.error("[GeneratePNG] Invalid response format from LLM: %s", type(result))
            if lang == 'zh':
                error_msg = (
                    "无法理解您的意图，请更具体地说明图表类型和主题，"
                    "或点击下方的图表卡片。"
                )
            else:
                error_msg = (
                    "Unable to process user's intention, please be more specific "
                    "about the diagram type and topic, or click the diagrams card below."
                )
            raise HTTPException(status_code=500, detail=error_msg)

        spec = result.get('spec', {})
        diagram_type = result.get('diagram_type', 'bubble_map')

        # Normalize diagram type
        if diagram_type == 'mindmap':
            diagram_type = 'mind_map'

        # Check if spec contains an error field (from LLM)
        if isinstance(spec, dict) and spec.get('error'):
            error_from_spec = spec.get('error')
            logger.warning("[GeneratePNG] Spec contains error field: %s", error_from_spec)
            # Use user-friendly message instead of raw error
            if lang == 'zh':
                error_msg = (
                    "无法理解您的意图，请更具体地说明图表类型和主题，"
                    "或点击下方的图表卡片。"
                )
            else:
                error_msg = (
                    "Unable to process user's intention, please be more specific "
                    "about the diagram type and topic, or click the diagrams card below."
                )
            raise HTTPException(status_code=400, detail=error_msg)

        # Add learning sheet metadata to spec object so renderers can access it
        if isinstance(spec, dict):
            hidden_percentage = 0.2 if is_learning_sheet else 0
            spec['is_learning_sheet'] = is_learning_sheet
            spec['hidden_node_percentage'] = hidden_percentage
            logger.debug(
                "[GeneratePNG] Added learning sheet metadata to spec: is_learning_sheet=%s, hidden_percentage=%s",
                is_learning_sheet, hidden_percentage
            )

        # Track tokens with correct diagram_type
        if usage_data:
            try:
                input_tokens = usage_data.get('prompt_tokens') or usage_data.get('input_tokens') or 0
                output_tokens = usage_data.get('completion_tokens') or usage_data.get('output_tokens') or 0
                total_tokens = usage_data.get('total_tokens') or None
                response_time = time.time() - start_time

                token_tracker = get_token_tracker()
                await token_tracker.track_usage(
                    model_alias='qwen',
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    request_type='diagram_generation',
                    diagram_type=diagram_type,
                    user_id=user_id,
                    organization_id=organization_id,
                    api_key_id=api_key_id,
                    endpoint_path='/api/generate_png',
                    response_time=response_time,
                    success=True
                )
            except Exception as e:
                logger.warning("[GeneratePNG] Token tracking failed (non-critical): %s", e, exc_info=False)

        # For mindmaps, enhance spec with layout data if missing
        if diagram_type == 'mind_map' and isinstance(spec, dict):
            if not spec.get('_layout') or not spec.get('_layout', {}).get('positions'):
                logger.debug("[GeneratePNG] Mindmap spec missing layout data, enhancing with MindMapAgent")
                try:
                    mind_map_agent = MindMapAgent(model='qwen')
                    enhanced_spec = await mind_map_agent.enhance_spec(spec)

                    if enhanced_spec.get('_layout'):
                        spec = enhanced_spec
                        logger.debug("[GeneratePNG] Mindmap layout data added successfully")
                    else:
                        logger.warning("[GeneratePNG] MindMapAgent failed to generate layout data")
                except Exception as e:
                    logger.error("[GeneratePNG] Error enhancing mindmap spec: %s", e, exc_info=True)
                    # Continue with original spec - renderer will show error message

        # Export PNG using core function
        screenshot_bytes = await _export_png_core(
            diagram_data=spec,
            diagram_type=diagram_type,
            width=req.width or 1200,
            height=req.height or 800,
            scale=req.scale or 2,
            _x_language=x_language
        )

        # Broadcast activity to dashboard stream (if user is authenticated)
        if user_id:
            try:
                activity_service = get_activity_stream_service()
                user_name = getattr(current_user, 'name', None) if current_user else None

                # Format topic based on diagram type
                topic_display = prompt[:50]  # Default: truncate prompt
                if diagram_type == 'double_bubble_map' and isinstance(spec, dict):
                    left = spec.get('left', '')
                    right = spec.get('right', '')
                    if left and right:
                        # Format as "Left vs Right" (English) or "左和右" (Chinese)
                        topic_display = f"{left} vs {right}" if language == 'en' else f"{left}和{right}"
                    elif left or right:
                        topic_display = left or right

                await activity_service.broadcast_activity(
                    user_id=user_id,
                    action="generated",
                    diagram_type=diagram_type,
                    topic=topic_display[:50],  # Truncate to 50 chars
                    user_name=user_name
                )
            except Exception as e:
                logger.debug("Failed to broadcast activity: %s", e)

        return Response(
            content=screenshot_bytes,
            media_type="image/png",
            headers={'Content-Disposition': 'attachment; filename="diagram.png"'}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[GeneratePNG] Error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=Messages.error("generation_failed", lang, str(e))) from e


@router.post('/generate_dingtalk')
async def generate_dingtalk_png(
    req: GenerateDingTalkRequest,
    request: Request,
    x_language: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Generate PNG for DingTalk integration using simplified prompt-to-diagram agent.

    Uses only Qwen in a single LLM call. Saves PNG to temp folder and returns
    plain text in ![]() format for DingTalk bot integration.
    """
    accept_language = request.headers.get("Accept-Language", "")
    lang = get_request_language(x_language, accept_language)
    prompt = req.prompt.strip()

    if not prompt:
        raise HTTPException(
            status_code=400,
            detail=Messages.error("invalid_prompt", lang)
        )

    try:
        # Handle language - default to 'zh' if not provided
        if req.language and hasattr(req.language, 'value'):
            language = req.language.value
        elif req.language:
            language = str(req.language)
        else:
            language = 'zh'
        if language not in ['zh', 'en']:
            raise HTTPException(status_code=400, detail="Invalid language. Must be 'zh' or 'en'")

        logger.info("[GenerateDingTalk] Request: prompt='%s', language='%s'", prompt, language)

        # Handle current_user
        user_id = None
        organization_id = None
        if current_user and hasattr(current_user, 'id'):
            user_id = current_user.id
            organization_id = getattr(current_user, 'organization_id', None)

        # Detect learning sheet from prompt
        is_learning_sheet = _detect_learning_sheet_from_prompt(prompt, language)
        logger.debug("[GenerateDingTalk] Learning sheet detected: %s", is_learning_sheet)

        # Clean prompt for learning sheets to generate actual content, not meta-content
        generation_prompt = _clean_prompt_for_learning_sheet(prompt) if is_learning_sheet else prompt
        if is_learning_sheet:
            logger.debug("[GenerateDingTalk] Using cleaned prompt for generation: '%s'", generation_prompt)

        # Use simplified prompt-to-diagram approach (single Qwen call)
        prompt_template = get_prompt('prompt_to_diagram', language, 'generation')

        if not prompt_template:
            raise HTTPException(
                status_code=500,
                detail=Messages.error("generation_failed", lang, f"No prompt template found for language {language}")
            )

        # Format prompt with cleaned user input
        formatted_prompt = prompt_template.format(user_prompt=generation_prompt)

        # Call LLM service - single call with Qwen only

        # Get API key ID from request state if API key was used
        api_key_id = None
        if hasattr(request, 'state'):
            api_key_id = getattr(request.state, 'api_key_id', None)

        start_time = time.time()
        response, usage_data = await llm_service.chat_with_usage(
            prompt=formatted_prompt,
            model='qwen',  # Force Qwen only
            max_tokens=2000,
            temperature=config.LLM_TEMPERATURE,
            user_id=user_id,
            organization_id=organization_id,
            api_key_id=api_key_id,
            request_type='diagram_generation',
            endpoint_path='/api/generate_dingtalk'
        )

        if not response:
            if lang == 'zh':
                error_msg = (
                    "无法理解您的意图，请更具体地说明图表类型和主题，"
                    "或点击下方的图表卡片。"
                )
            else:
                error_msg = (
                    "Unable to process user's intention, please be more specific "
                    "about the diagram type and topic, or click the diagrams card below."
                )
            raise HTTPException(status_code=500, detail=error_msg)

        # Extract JSON from response
        result = extract_json_from_response(response)

        # Check for non-JSON response (LLM asking for more information)
        if isinstance(result, dict) and result.get('_error') == 'non_json_response':
            logger.warning("[GenerateDingTalk] LLM returned non-JSON response asking for more info")
            if lang == 'zh':
                error_msg = (
                    "无法理解您的意图，请更具体地说明图表类型和主题，"
                    "或点击下方的图表卡片。"
                )
            else:
                error_msg = (
                    "Unable to process user's intention, please be more specific "
                    "about the diagram type and topic, or click the diagrams card below."
                )
            raise HTTPException(status_code=400, detail=error_msg)

        # Check if JSON extraction failed
        if not isinstance(result, dict) or 'spec' not in result:
            logger.error("[GenerateDingTalk] Invalid response format from LLM: %s", type(result))
            if lang == 'zh':
                error_msg = (
                    "无法理解您的意图，请更具体地说明图表类型和主题，"
                    "或点击下方的图表卡片。"
                )
            else:
                error_msg = (
                    "Unable to process user's intention, please be more specific "
                    "about the diagram type and topic, or click the diagrams card below."
                )
            raise HTTPException(status_code=500, detail=error_msg)

        spec = result.get('spec', {})
        diagram_type = result.get('diagram_type', 'bubble_map')

        # Normalize diagram type
        if diagram_type == 'mindmap':
            diagram_type = 'mind_map'

        # Check if spec contains an error field (from LLM)
        if isinstance(spec, dict) and spec.get('error'):
            error_from_spec = spec.get('error')
            logger.warning("[GenerateDingTalk] Spec contains error field: %s", error_from_spec)
            # Use user-friendly message instead of raw error
            if lang == 'zh':
                error_msg = (
                    "无法理解您的意图，请更具体地说明图表类型和主题，"
                    "或点击下方的图表卡片。"
                )
            else:
                error_msg = (
                    "Unable to process user's intention, please be more specific "
                    "about the diagram type and topic, or click the diagrams card below."
                )
            raise HTTPException(status_code=400, detail=error_msg)

        # Add learning sheet metadata to spec object so renderers can access it
        if isinstance(spec, dict):
            hidden_percentage = 0.2 if is_learning_sheet else 0
            spec['is_learning_sheet'] = is_learning_sheet
            spec['hidden_node_percentage'] = hidden_percentage
            logger.debug(
                "[GenerateDingTalk] Added learning sheet metadata to spec: is_learning_sheet=%s, hidden_percentage=%s",
                is_learning_sheet, hidden_percentage
            )

        # Track tokens with correct diagram_type
        if usage_data:
            try:
                input_tokens = usage_data.get('prompt_tokens') or usage_data.get('input_tokens') or 0
                output_tokens = usage_data.get('completion_tokens') or usage_data.get('output_tokens') or 0
                total_tokens = usage_data.get('total_tokens') or None
                response_time = time.time() - start_time

                token_tracker = get_token_tracker()
                await token_tracker.track_usage(
                    model_alias='qwen',
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    request_type='diagram_generation',
                    diagram_type=diagram_type,
                    user_id=user_id,
                    organization_id=organization_id,
                    api_key_id=api_key_id,
                    endpoint_path='/api/generate_dingtalk',
                    response_time=response_time,
                    success=True
                )
            except Exception as e:
                logger.warning("[GenerateDingTalk] Token tracking failed (non-critical): %s", e, exc_info=False)

        # For mindmaps, enhance spec with layout data if missing
        if diagram_type == 'mind_map' and isinstance(spec, dict):
            if not spec.get('_layout') or not spec.get('_layout', {}).get('positions'):
                logger.debug("[GenerateDingTalk] Mindmap spec missing layout data, enhancing with MindMapAgent")
                try:
                    mind_map_agent = MindMapAgent(model='qwen')
                    enhanced_spec = await mind_map_agent.enhance_spec(spec)

                    if enhanced_spec.get('_layout'):
                        spec = enhanced_spec
                        logger.debug("[GenerateDingTalk] Mindmap layout data added successfully")
                    else:
                        logger.warning("[GenerateDingTalk] MindMapAgent failed to generate layout data")
                except Exception as e:
                    logger.error("[GenerateDingTalk] Error enhancing mindmap spec: %s", e, exc_info=True)
                    # Continue with original spec - renderer will show error message

        # Export PNG using core helper function
        screenshot_bytes = await _export_png_core(
            diagram_data=spec,
            diagram_type=diagram_type,
            width=1200,
            height=800,
            scale=2,
            _x_language=x_language
        )

        # Broadcast activity to dashboard stream (if user is authenticated)
        if user_id:
            try:
                activity_service = get_activity_stream_service()
                user_name = getattr(current_user, 'name', None) if current_user else None

                # Format topic based on diagram type
                topic_display = prompt[:50]  # Default: truncate prompt
                if diagram_type == 'double_bubble_map' and isinstance(spec, dict):
                    left = spec.get('left', '')
                    right = spec.get('right', '')
                    if left and right:
                        # Format as "Left vs Right" (English) or "左和右" (Chinese)
                        topic_display = f"{left} vs {right}" if language == 'en' else f"{left}和{right}"
                    elif left or right:
                        topic_display = left or right

                await activity_service.broadcast_activity(
                    user_id=user_id,
                    action="generated",
                    diagram_type=diagram_type,
                    topic=topic_display[:50],  # Truncate to 50 chars
                    user_name=user_name
                )
            except Exception as e:
                logger.debug("Failed to broadcast activity: %s", e)

        # Save PNG to temp directory (ASYNC file I/O)
        temp_dir = Path("temp_images")
        temp_dir.mkdir(exist_ok=True)

        # Generate unique filename
        unique_id = uuid.uuid4().hex[:8]
        timestamp = int(time.time())
        filename = f"dingtalk_{unique_id}_{timestamp}.png"
        temp_path = temp_dir / filename

        # Write PNG content to file using aiofiles (100% async, non-blocking)
        async with aiofiles.open(temp_path, 'wb') as f:
            await f.write(screenshot_bytes)

        # Generate signed URL for security (24 hour expiration)
        signed_path = generate_signed_url(filename, expiration_seconds=86400)

        # Build plain text response in ![](url) format (empty alt text)
        # Priority order: EXTERNAL_BASE_URL → X-Forwarded-* headers → EXTERNAL_HOST:PORT
        # This ensures HTTPS URLs are used when EXTERNAL_BASE_URL is set, preventing mixed content issues
        external_base_url = os.getenv('EXTERNAL_BASE_URL', '').rstrip('/')

        if external_base_url:
            # Explicit override - use EXTERNAL_BASE_URL directly (highest priority)
            image_url = f"{external_base_url}/api/temp_images/{signed_path}"
        else:
            # Try reverse proxy headers
            forwarded_proto = request.headers.get('X-Forwarded-Proto')
            forwarded_host = request.headers.get('X-Forwarded-Host')

            if forwarded_proto and forwarded_host:
                # Behind reverse proxy - use forwarded values (no port needed)
                protocol = forwarded_proto
                image_url = f"{protocol}://{forwarded_host}/api/temp_images/{signed_path}"
            else:
                # Direct access - use backend protocol and EXTERNAL_HOST with port
                protocol = request.url.scheme
                external_host = os.getenv('EXTERNAL_HOST', 'localhost')
                port = os.getenv('PORT', '9527')
                image_url = f"{protocol}://{external_host}:{port}/api/temp_images/{signed_path}"

        plain_text = f"![]({image_url})"

        logger.info("[GenerateDingTalk] Success: %s", image_url)

        return PlainTextResponse(content=plain_text)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[GenerateDingTalk] Error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=Messages.error("generation_failed", lang, str(e))
        ) from e


@router.get('/temp_images/{filepath:path}')
async def serve_temp_image(filepath: str, sig: Optional[str] = None, exp: Optional[int] = None):
    """
    Serve temporary PNG files for DingTalk integration.

    Images require signed URLs with expiration for security.
    Images auto-cleanup after 24 hours via background cleaner task.

    Security Flow:
    1. Check file exists (cleaner may have deleted it) → 404 if not found
    2. Verify signed URL expiration → 403 if expired
    3. Verify signature → 403 if invalid
    4. Serve file if all checks pass

    Coordination with Temp Image Cleaner:
    - Cleaner deletes files older than 24h based on file mtime
    - Signed URLs expire after 24h from generation time
    - Both use same 24-hour window for consistency
    - If cleaner deleted file → 404 (file not found)
    - If URL expired but file exists → 403 (URL expired)
    """
    # Parse filename and signature from path
    # Path format: filename.png?sig=...&exp=...
    if '?' in filepath:
        filename = filepath.split('?')[0]
    else:
        filename = filepath

    # Security: Validate filename to prevent directory traversal
    if '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    temp_path = Path("temp_images") / filename

    # Step 1: Check if file exists (cleaner may have deleted it)
    # This check happens FIRST to distinguish between "file deleted" (404) and "URL expired" (403)
    if not temp_path.exists():
        # File doesn't exist - could be deleted by cleaner or never existed
        # Check if this is a signed URL to provide better error message
        if sig and exp:
            # Signed URL but file doesn't exist - likely deleted by cleaner
            logger.debug("Temp image file not found (may have been cleaned): %s", filename)
        raise HTTPException(status_code=404, detail="Image not found or expired")

    # Step 2: Verify signed URL if signature provided (new format)
    if sig and exp:
        # Verify signature and expiration
        if not verify_signed_url(filename, sig, exp):
            logger.warning("Invalid or expired signed URL for temp image: %s", filename)
            raise HTTPException(status_code=403, detail="Invalid or expired image URL")
    else:
        # Legacy support: Check if file exists and is not too old (max 24 hours)
        # This allows existing URLs to work temporarily
        # Uses same logic as temp_image_cleaner (24 hour max age)
        try:
            stat_result = await aiofiles.os.stat(temp_path)
            file_age = time.time() - stat_result.st_mtime
            if file_age > 86400:  # 24 hours (matches cleanup threshold)
                file_age_hours = file_age / 3600
                logger.warning("Legacy temp image URL expired: %s (age: %.1fh)", filename, file_age_hours)
                raise HTTPException(status_code=403, detail="Image URL expired")
        except Exception as e:
            logger.error("Failed to check file age: %s", e)
            raise HTTPException(status_code=404, detail="Image not found") from e

    return FileResponse(
        path=str(temp_path),
        media_type="image/png",
        headers={
            'Cache-Control': 'public, max-age=86400',
            'X-Content-Type-Options': 'nosniff'
        }
        )
