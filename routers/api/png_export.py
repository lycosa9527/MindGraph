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

import hashlib
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Optional, Tuple

import aiofiles
import aiofiles.os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from agents.core.agent_utils import extract_json_from_response
from agents.core.prompt_to_diagram_result import (
    is_llm_clarification_dict,
    normalize_prompt_to_diagram_result,
)
from agents.core.learning_sheet import (
    _clean_prompt_for_learning_sheet,
    _detect_learning_sheet_from_prompt,
)
from config.settings import config
from config.database import get_async_db
from models import (
    ExportPNGRequest,
    GenerateDingTalkRequest,
    GeneratePNGRequest,
    Messages,
    get_request_language,
)
from models.domain.auth import User
from prompts import get_prompt
from services.llm import llm_service
from services.monitoring.activity_stream import get_activity_stream_service
from services.redis.redis_token_buffer import get_token_tracker
from services.diagram.dify_user_resolve import (
    library_save_limit_notice,
    library_save_skip_reason,
    library_save_skip_user_notice,
    resolve_diagram_save_identity,
)
from services.diagram.generation_library_save import SAVE_LIMIT_REACHED, try_save_diagram_to_library
from services.diagram.generation_library_claim import (
    CLAIM_ERROR_LIMIT,
    CLAIM_ERROR_NOT_FOUND,
    CLAIM_ERROR_NO_SPEC,
    CLAIM_ERROR_SAVE,
    claim_generation_preview_for_user,
)
from services.diagram.generation_skip_registry import (
    get_generation_library_skip,
    store_generation_preview_outcome,
)
from services.admin.user_usage_activity import schedule_user_usage_activity
from services.diagram.library_save_user_notices import library_save_user_notice
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.auth import get_current_user, get_current_user_or_api_key
from .helpers import (
    build_public_temp_image_url,
    check_endpoint_rate_limit,
    generate_signed_url,
    get_rate_limit_identifier,
    verify_signed_url,
)
from .vueflow_screenshot import capture_diagram_screenshot

logger = logging.getLogger(__name__)


def _prompt_meta_for_log(text: str) -> str:
    """Length and SHA-256 prefix for logs (does not log raw user prompt text)."""
    stripped = (text or "").strip()
    if not stripped:
        return "len=0"
    digest = hashlib.sha256(stripped.encode("utf-8")).hexdigest()[:12]
    return f"len={len(stripped)} sha256_12={digest}"


def _resolve_prompt_to_diagram_payload(
    result: Any,
    *,
    endpoint_label: str,
    lang: str,
) -> Tuple[dict, str]:
    """Normalize LLM JSON and return (spec, diagram_type) or raise HTTPException."""
    if isinstance(result, dict) and result.get("_error") == "non_json_response":
        logger.warning("%s LLM returned non-JSON response asking for more info", endpoint_label)
        raise HTTPException(
            status_code=400,
            detail=Messages.error("generate_png_unclear_intent", lang=lang),
        )

    if isinstance(result, dict) and is_llm_clarification_dict(result):
        logger.warning(
            "%s LLM returned clarification/error dict keys=%s",
            endpoint_label,
            list(result.keys()),
        )
        raise HTTPException(
            status_code=400,
            detail=Messages.error("generate_png_unclear_intent", lang=lang),
        )

    normalized = normalize_prompt_to_diagram_result(result)
    if not normalized or "spec" not in normalized:
        keys = list(result.keys()) if isinstance(result, dict) else None
        logger.error(
            "%s Invalid response format from LLM: type=%s keys=%s",
            endpoint_label,
            type(result),
            keys,
        )
        raise HTTPException(
            status_code=500,
            detail=Messages.error("generate_png_unclear_intent", lang=lang),
        )

    spec = normalized.get("spec", {})
    diagram_type = normalized.get("diagram_type", "bubble_map")
    if diagram_type == "mindmap":
        diagram_type = "mind_map"

    if isinstance(spec, dict) and spec.get("error"):
        error_from_spec = spec.get("error")
        logger.warning("%s Spec contains error field: %s", endpoint_label, error_from_spec)
        raise HTTPException(
            status_code=400,
            detail=Messages.error("generate_png_unclear_intent", lang=lang),
        )

    return spec, diagram_type


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEMP_IMAGES_DIR = _PROJECT_ROOT / "temp_images"

router = APIRouter(tags=["api"])


@router.post("/export_png")
async def export_png(
    req: ExportPNGRequest,
    request: Request,
    x_language: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key),
):
    """
    Export diagram as PNG using Vue Flow frontend rendering via Playwright (async).

    Loads the Vue Flow frontend in headless Chromium, renders the diagram,
    and captures a screenshot for pixel-perfect output matching the editor.

    Rate limited: 100 requests per minute per user/IP (PNG generation is expensive).
    """
    # Rate limiting: 100 requests per minute per user/IP (PNG generation is expensive)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("export_png", identifier, max_requests=100, window_seconds=60)

    # Get language for error messages
    accept_language = request.headers.get("Accept-Language", "")
    lang = get_request_language(x_language, accept_language)

    diagram_data = req.diagram_data
    diagram_type = req.diagram_type.value if hasattr(req.diagram_type, "value") else str(req.diagram_type)

    if not diagram_data:
        raise HTTPException(status_code=400, detail=Messages.error("diagram_data_required", lang))

    logger.debug(
        "PNG export request - diagram_type: %s, data keys: %s",
        diagram_type,
        list(diagram_data.keys()),
    )

    try:
        # Normalize diagram type (same as generate_dingtalk)
        if diagram_type == "mindmap":
            diagram_type = "mind_map"

        # Ensure diagram_data is a dict and add any missing metadata (same as generate_dingtalk)
        if isinstance(diagram_data, dict):
            # Add learning sheet metadata if not present (defaults to False/0)
            if "is_learning_sheet" not in diagram_data:
                diagram_data["is_learning_sheet"] = False
            if "hidden_node_percentage" not in diagram_data:
                diagram_data["hidden_node_percentage"] = 0

        # Render via Vue Flow frontend and capture screenshot
        screenshot_bytes = await capture_diagram_screenshot(
            diagram_data=diagram_data,
            diagram_type=diagram_type,
            width=req.width or 1200,
            height=req.height or 800,
        )

        # Return PNG as response
        return Response(
            content=screenshot_bytes,
            media_type="image/png",
            headers={"Content-Disposition": 'attachment; filename="diagram.png"'},
        )

    except BACKGROUND_INFRA_ERRORS as e:
        logger.error("PNG export error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=Messages.error("export_failed", lang, str(e))) from e


@router.post("/generate_png")
async def generate_png_from_prompt(
    req: GeneratePNGRequest,
    request: Request,
    x_language: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key),
):
    """
    Generate PNG directly from user prompt using simplified prompt-to-diagram agent.

    Uses only Qwen in a single LLM call for fast, efficient diagram generation.

    Rate limited: 100 requests per minute per user/IP (PNG generation is expensive).
    """
    # Rate limiting: 100 requests per minute per user/IP (PNG generation is expensive)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("generate_png", identifier, max_requests=100, window_seconds=60)

    accept_language = request.headers.get("Accept-Language", "")
    lang = get_request_language(x_language, accept_language)
    prompt = req.prompt.strip()

    if not prompt:
        raise HTTPException(status_code=400, detail=Messages.error("invalid_prompt", lang))

    language = (req.language or "zh").strip()

    logger.info(
        "[GeneratePNG] Request: prompt_meta=%s language=%s",
        _prompt_meta_for_log(prompt),
        language,
    )

    try:
        # Use simplified prompt-to-diagram approach (single Qwen call)
        user_id = current_user.id if current_user and hasattr(current_user, "id") else None
        if current_user and hasattr(current_user, "id"):
            organization_id = getattr(current_user, "organization_id", None)
        else:
            organization_id = None

        # Detect learning sheet from prompt
        is_learning_sheet = _detect_learning_sheet_from_prompt(prompt, language)
        logger.debug("[GeneratePNG] Learning sheet detected: %s", is_learning_sheet)

        # Clean prompt for learning sheets to generate actual content, not meta-content
        generation_prompt = _clean_prompt_for_learning_sheet(prompt) if is_learning_sheet else prompt
        if is_learning_sheet:
            logger.debug(
                "[GeneratePNG] Using cleaned prompt for generation: %s",
                _prompt_meta_for_log(generation_prompt),
            )

        # Get prompt from centralized system
        prompt_template = get_prompt("prompt_to_diagram", language, "generation")

        if not prompt_template:
            error_detail = Messages.error(
                "generation_failed",
                f"No prompt template found for language {language}",
                lang=lang,
            )
            raise HTTPException(status_code=500, detail=error_detail)

        # Format prompt with cleaned user input
        formatted_prompt = prompt_template.format(user_prompt=generation_prompt)

        # Call LLM service - single call with Qwen only

        # Get API key ID from request state if API key was used
        api_key_id = None
        if hasattr(request, "state"):
            api_key_id = getattr(request.state, "api_key_id", None)
            if api_key_id:
                logger.debug("[GeneratePNG] Using API key ID %s for token tracking", api_key_id)
        else:
            logger.debug("[GeneratePNG] Request state not available")

        start_time = time.time()
        response, usage_data = await llm_service.chat_with_usage(
            prompt=formatted_prompt,
            model="qwen",  # Force Qwen only
            max_tokens=2000,
            temperature=config.LLM_TEMPERATURE,
            user_id=user_id,
            organization_id=organization_id,
            api_key_id=api_key_id,
            request_type="diagram_generation",
            endpoint_path="/api/generate_png",
        )

        if not response:
            raise HTTPException(
                status_code=500,
                detail=Messages.error("generate_png_unclear_intent", lang=lang),
            )

        # Extract JSON from response
        result = extract_json_from_response(response)
        spec, diagram_type = _resolve_prompt_to_diagram_payload(
            result,
            endpoint_label="[GeneratePNG]",
            lang=lang,
        )

        # Add learning sheet metadata to spec object so renderers can access it
        if isinstance(spec, dict):
            hidden_percentage = 0.2 if is_learning_sheet else 0
            spec["is_learning_sheet"] = is_learning_sheet
            spec["hidden_node_percentage"] = hidden_percentage
            logger.debug(
                "[GeneratePNG] Added learning sheet metadata to spec: is_learning_sheet=%s, hidden_percentage=%s",
                is_learning_sheet,
                hidden_percentage,
            )

        # Track tokens with correct diagram_type
        if usage_data:
            try:
                input_tokens = usage_data.get("prompt_tokens") or usage_data.get("input_tokens") or 0
                output_tokens = usage_data.get("completion_tokens") or usage_data.get("output_tokens") or 0
                total_tokens = usage_data.get("total_tokens") or None
                response_time = time.time() - start_time

                token_tracker = get_token_tracker()
                await token_tracker.track_usage(
                    model_alias="qwen",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    request_type="diagram_generation",
                    diagram_type=diagram_type,
                    user_id=user_id,
                    organization_id=organization_id,
                    api_key_id=api_key_id,
                    endpoint_path="/api/generate_png",
                    response_time=response_time,
                    success=True,
                )
            except BACKGROUND_INFRA_ERRORS as e:
                logger.warning(
                    "[GeneratePNG] Token tracking failed (non-critical): %s",
                    e,
                    exc_info=False,
                )

        # Render via Vue Flow frontend and capture screenshot
        screenshot_bytes = await capture_diagram_screenshot(
            diagram_data=spec,
            diagram_type=diagram_type,
            width=req.width or 1200,
            height=req.height or 800,
        )

        # Broadcast activity to dashboard stream (if user is authenticated)
        if user_id:
            try:
                activity_service = get_activity_stream_service()
                user_name = getattr(current_user, "name", None) if current_user else None

                # Format topic based on diagram type
                topic_display = prompt[:50]  # Default: truncate prompt
                if diagram_type == "double_bubble_map" and isinstance(spec, dict):
                    left = spec.get("left", "")
                    right = spec.get("right", "")
                    if left and right:
                        # Format as "Left vs Right" (English) or "左和右" (Chinese)
                        topic_display = f"{left}和{right}" if language == "zh" else f"{left} vs {right}"
                    elif left or right:
                        topic_display = left or right

                await activity_service.broadcast_activity(
                    user_id=user_id,
                    action="generated",
                    diagram_type=diagram_type,
                    topic=topic_display[:50],  # Truncate to 50 chars
                    user_name=user_name,
                )
            except BACKGROUND_INFRA_ERRORS as e:
                logger.debug("Failed to broadcast activity: %s", e)

        if user_id:
            topic_for_activity = prompt[:50]
            if diagram_type == "double_bubble_map" and isinstance(spec, dict):
                left = spec.get("left", "")
                right = spec.get("right", "")
                if left and right:
                    topic_for_activity = f"{left} vs {right}" if language != "zh" else f"{left}和{right}"
                elif left or right:
                    topic_for_activity = str(left or right)
            schedule_user_usage_activity(
                user_id=int(user_id),
                organization_id=organization_id,
                source="mindgraph",
                action="diagram_generate",
                title=topic_for_activity or None,
                prompt_preview=prompt or None,
                diagram_type=diagram_type,
            )

        return Response(
            content=screenshot_bytes,
            media_type="image/png",
            headers={"Content-Disposition": 'attachment; filename="diagram.png"'},
        )

    except BACKGROUND_INFRA_ERRORS as e:
        logger.error("[GeneratePNG] Error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=Messages.error("generation_failed", lang, str(e))) from e


@router.post("/generate_dingtalk")
async def generate_dingtalk_png(
    req: GenerateDingTalkRequest,
    request: Request,
    x_language: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key),
    db: AsyncSession = Depends(get_async_db),
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
        raise HTTPException(status_code=400, detail=Messages.error("invalid_prompt", lang))

    try:
        language = (req.language or "zh").strip()

        logger.info(
            "[GenerateDingTalk] Request: prompt_meta=%s language=%s",
            _prompt_meta_for_log(prompt),
            language,
        )

        save_identity = await resolve_diagram_save_identity(db, request, current_user, req)
        user_id = save_identity.user_id
        organization_id = save_identity.organization_id

        # Detect learning sheet from prompt
        is_learning_sheet = _detect_learning_sheet_from_prompt(prompt, language)
        logger.debug("[GenerateDingTalk] Learning sheet detected: %s", is_learning_sheet)

        # Clean prompt for learning sheets to generate actual content, not meta-content
        generation_prompt = _clean_prompt_for_learning_sheet(prompt) if is_learning_sheet else prompt
        if is_learning_sheet:
            logger.debug(
                "[GenerateDingTalk] Using cleaned prompt for generation: %s",
                _prompt_meta_for_log(generation_prompt),
            )

        # Use simplified prompt-to-diagram approach (single Qwen call)
        prompt_template = get_prompt("prompt_to_diagram", language, "generation")

        if not prompt_template:
            raise HTTPException(
                status_code=500,
                detail=Messages.error(
                    "generation_failed",
                    f"No prompt template found for language {language}",
                    lang=lang,
                ),
            )

        # Format prompt with cleaned user input
        formatted_prompt = prompt_template.format(user_prompt=generation_prompt)

        # Call LLM service - single call with Qwen only

        # Get API key ID from request state if API key was used
        api_key_id = None
        if hasattr(request, "state"):
            api_key_id = getattr(request.state, "api_key_id", None)

        start_time = time.time()
        response, usage_data = await llm_service.chat_with_usage(
            prompt=formatted_prompt,
            model="qwen",  # Force Qwen only
            max_tokens=2000,
            temperature=config.LLM_TEMPERATURE,
            user_id=user_id,
            organization_id=organization_id,
            api_key_id=api_key_id,
            request_type="diagram_generation",
            endpoint_path="/api/generate_dingtalk",
        )

        if not response:
            raise HTTPException(
                status_code=500,
                detail=Messages.error("generate_png_unclear_intent", lang=lang),
            )

        # Extract JSON from response
        result = extract_json_from_response(response)
        spec, diagram_type = _resolve_prompt_to_diagram_payload(
            result,
            endpoint_label="[GenerateDingTalk]",
            lang=lang,
        )

        # Add learning sheet metadata to spec object so renderers can access it
        if isinstance(spec, dict):
            hidden_percentage = 0.2 if is_learning_sheet else 0
            spec["is_learning_sheet"] = is_learning_sheet
            spec["hidden_node_percentage"] = hidden_percentage
            logger.debug(
                "[GenerateDingTalk] Added learning sheet metadata to spec: is_learning_sheet=%s, hidden_percentage=%s",
                is_learning_sheet,
                hidden_percentage,
            )

        # Track tokens with correct diagram_type
        if usage_data:
            try:
                input_tokens = usage_data.get("prompt_tokens") or usage_data.get("input_tokens") or 0
                output_tokens = usage_data.get("completion_tokens") or usage_data.get("output_tokens") or 0
                total_tokens = usage_data.get("total_tokens") or None
                response_time = time.time() - start_time

                token_tracker = get_token_tracker()
                await token_tracker.track_usage(
                    model_alias="qwen",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    request_type="diagram_generation",
                    diagram_type=diagram_type,
                    user_id=user_id,
                    organization_id=organization_id,
                    api_key_id=api_key_id,
                    endpoint_path="/api/generate_dingtalk",
                    response_time=response_time,
                    success=True,
                )
            except BACKGROUND_INFRA_ERRORS as e:
                logger.warning(
                    "[GenerateDingTalk] Token tracking failed (non-critical): %s",
                    e,
                    exc_info=False,
                )

        # Export PNG via Vue Flow frontend rendering (replaces old D3 pipeline)
        screenshot_bytes = await capture_diagram_screenshot(
            diagram_data=spec,
            diagram_type=diagram_type,
            width=1200,
            height=800,
        )

        # Broadcast activity to dashboard stream (if user is authenticated)
        if user_id:
            try:
                activity_service = get_activity_stream_service()
                user_name = getattr(current_user, "name", None) if current_user else None

                # Format topic based on diagram type
                topic_display = prompt[:50]  # Default: truncate prompt
                if diagram_type == "double_bubble_map" and isinstance(spec, dict):
                    left = spec.get("left", "")
                    right = spec.get("right", "")
                    if left and right:
                        # Format as "Left vs Right" (English) or "左和右" (Chinese)
                        topic_display = f"{left}和{right}" if language == "zh" else f"{left} vs {right}"
                    elif left or right:
                        topic_display = left or right

                await activity_service.broadcast_activity(
                    user_id=user_id,
                    action="generated",
                    diagram_type=diagram_type,
                    topic=topic_display[:50],  # Truncate to 50 chars
                    user_name=user_name,
                )
            except BACKGROUND_INFRA_ERRORS as e:
                logger.debug("Failed to broadcast activity: %s", e)

        # Save PNG to temp directory (ASYNC file I/O)
        TEMP_IMAGES_DIR.mkdir(exist_ok=True)

        # Generate unique filename (unique_id keys Redis skip metadata for MindBot)
        unique_id = uuid.uuid4().hex[:8]
        timestamp = int(time.time())
        filename = f"dingtalk_{unique_id}_{timestamp}.png"
        temp_path = TEMP_IMAGES_DIR / filename

        save_title = prompt[:50].strip() or "Diagram"
        saved_id = await try_save_diagram_to_library(
            user_id,
            title=save_title,
            diagram_type=diagram_type,
            spec=spec if isinstance(spec, dict) else {},
            language=language,
            organization_id=organization_id,
            http_request_id=getattr(getattr(request, "state", None), "request_id", None),
            log_prefix="generate_dingtalk",
        )
        skip_reason = library_save_skip_reason(
            user_id=user_id,
            saved_id=saved_id,
            dify_user_key=save_identity.dify_user_key,
        )
        if skip_reason:
            log_fn = logger.warning if skip_reason == "no_user" else logger.info
            log_fn(
                "[GenerateDingTalk] Library save skipped reason=%s user_id=%s dify_key=%s "
                "(Dify tool should pass conversation_id={{sys.conversation_id}} or dify_user_id={{sys.user_id}})",
                skip_reason,
                user_id,
                save_identity.dify_user_key[:64] if save_identity.dify_user_key else "none",
            )

        stored_diagram_id = saved_id if saved_id and saved_id != SAVE_LIMIT_REACHED else None
        await store_generation_preview_outcome(
            unique_id,
            reason=skip_reason,
            language=language,
            diagram_id=stored_diagram_id,
            diagram_type=diagram_type,
            title=save_title,
            spec=spec if isinstance(spec, dict) and not stored_diagram_id else None,
            user_id=user_id,
            organization_id=organization_id,
            db=db,
        )

        # Write PNG content to file using aiofiles (100% async, non-blocking)
        async with aiofiles.open(temp_path, "wb") as f:
            await f.write(screenshot_bytes)

        # Generate signed URL for security (24 hour expiration)
        signed_path = generate_signed_url(filename, expiration_seconds=86400)
        if stored_diagram_id:
            # Survives in Dify message history when alt text / HTML comments are stripped.
            signed_path = f"{signed_path}&mgdid={stored_diagram_id}"

        image_url = build_public_temp_image_url(request, signed_path)

        # Alt text carries library id (Dify often strips HTML comments from assistant markdown).
        if saved_id and saved_id != SAVE_LIMIT_REACHED:
            plain_text = f"![mg:{saved_id}]({image_url})\n<!-- mg-diagram-id:{saved_id} -->"
        else:
            plain_text = f"![]({image_url})"
            if saved_id == SAVE_LIMIT_REACHED:
                plain_text += f"\n{library_save_limit_notice(language)}"
            else:
                notice = library_save_skip_user_notice(skip_reason, language)
                if notice:
                    plain_text += f"\n{notice}"

        logger.info("[GenerateDingTalk] Success: %s saved=%s", image_url, saved_id or "none")

        if user_id is not None and int(user_id) > 0:
            schedule_user_usage_activity(
                user_id=int(user_id),
                organization_id=organization_id,
                source="dingtalk",
                action="dingtalk_diagram",
                title=save_title,
                prompt_preview=prompt,
                diagram_type=diagram_type,
                diagram_id=stored_diagram_id,
            )

        return PlainTextResponse(content=plain_text)

    except BACKGROUND_INFRA_ERRORS as e:
        logger.error("[GenerateDingTalk] Error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=Messages.error("generation_failed", lang, str(e))) from e


@router.get("/generation_library_skip/{unique_id}")
async def read_generation_library_skip(unique_id: str) -> dict[str, str]:
    """Return library-save outcome metadata for a generate_dingtalk temp PNG id."""
    data = await get_generation_library_skip(unique_id)
    if not data:
        raise HTTPException(status_code=404, detail="Skip metadata not found")
    reason = data.get("reason", "")
    language = data.get("language", "zh")
    diagram_id = data.get("diagram_id", "")
    notice = ""
    if reason:
        notice = library_save_user_notice(reason, language, audience="mindmate")
    result: dict[str, str] = {
        "reason": reason,
        "language": language,
        "notice": notice,
    }
    if diagram_id:
        result["diagram_id"] = diagram_id
    return result


@router.post("/generation_library_claim/{unique_id}")
async def claim_generation_library_preview(
    unique_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Save a pending generate_dingtalk preview into the logged-in user's library."""
    diagram_id, err_code = await claim_generation_preview_for_user(unique_id, current_user)
    if err_code == CLAIM_ERROR_NOT_FOUND:
        raise HTTPException(status_code=404, detail="Preview metadata not found")
    if err_code == CLAIM_ERROR_NO_SPEC:
        raise HTTPException(status_code=409, detail="Preview is not reclaimable")
    if err_code == CLAIM_ERROR_LIMIT:
        raise HTTPException(status_code=409, detail="Diagram library is full")
    if err_code == CLAIM_ERROR_SAVE:
        raise HTTPException(status_code=500, detail="Library save failed")
    return {"diagram_id": diagram_id or ""}


@router.get("/temp_images/{filepath:path}")
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
    if "?" in filepath:
        filename = filepath.split("?")[0]
    else:
        filename = filepath

    # Security: Validate filename to prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    temp_path = TEMP_IMAGES_DIR / filename

    # Step 1: Check if file exists (cleaner may have deleted it)
    # This check happens FIRST to distinguish between "file deleted" (404) and "URL expired" (403)
    if not temp_path.exists():
        # File doesn't exist - could be deleted by cleaner or never existed
        # Check if this is a signed URL to provide better error message
        if sig and exp:
            # Signed URL but file doesn't exist - likely deleted by cleaner
            logger.debug("Temp image file not found (may have been cleaned): %s", filename)
        elif filename.startswith("dingtalk_"):
            logger.warning(
                "[GenerateDingTalk] Temp PNG missing locally: %s "
                "(Dify HTTP tool may target another MindGraph host, or EXTERNAL_BASE_URL "
                "on the generating server pointed at localhost while files live elsewhere)",
                filename,
            )
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
                logger.warning(
                    "Legacy temp image URL expired: %s (age: %.1fh)",
                    filename,
                    file_age_hours,
                )
                raise HTTPException(status_code=403, detail="Image URL expired")
        except BACKGROUND_INFRA_ERRORS as e:
            logger.error("Failed to check file age: %s", e)
            raise HTTPException(status_code=404, detail="Image not found") from e

    return FileResponse(
        path=str(temp_path),
        media_type="image/png",
        filename=filename,
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        },
    )
