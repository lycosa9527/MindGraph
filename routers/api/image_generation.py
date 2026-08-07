"""
Text-to-image API for Dify / ZhiHui (智绘).

POST /api/generate-text-to-image — X-API-Key or JWT; returns markdown ![](url).
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse

from config.settings import config
from models.domain.auth import User
from models.requests.requests_t2i import GenerateTextToImageRequest
from repositories.zhihui_repo import ZhihuiConversationRepository, ZhihuiGenerationRepository
from routers.api.helpers import build_public_zhihui_asset_url, generate_signed_url
from services.admin.user_usage_activity import schedule_user_usage_activity
from services.diagram.dify_user_resolve import (
    conversation_id_from_request,
    resolve_diagram_save_identity,
)
from services.monitoring.activity_stream import get_activity_stream_service
from services.monitoring.module_activity import schedule_module_activity
from services.redis.redis_token_buffer import get_token_tracker
from services.infrastructure.http.error_handler import (
    LLMAccessDeniedError,
    LLMContentFilterError,
    LLMInvalidParameterError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
    LLMServiceError,
)
from services.t2i.image_service import generate_and_store_image
from services.utils.error_types import (
    BACKGROUND_INFRA_ERRORS,
    DATABASE_ERRORS,
    HTTP_CLIENT_ERRORS,
)
from utils.auth import get_current_user_or_api_key
from utils.auth.admin_panel_permissions import CAP_FEATURE_ZHIHUI, user_panel_capabilities
from utils.db.session_open import actor_rls_session, system_rls_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Image Generation"])

_GENERATION_ERRORS = BACKGROUND_INFRA_ERRORS + HTTP_CLIENT_ERRORS + DATABASE_ERRORS


def _user_facing_error(exc: Exception) -> str:
    """Prefer DashScope parser user_message when present."""
    message = getattr(exc, "user_message", None)
    if isinstance(message, str) and message.strip():
        return message.strip()
    return str(exc)


def _plain_error(exc: Exception, status_code: int) -> PlainTextResponse:
    """Build Dify-friendly plain-text error body."""
    return PlainTextResponse(content=f"Error: {_user_facing_error(exc)}", status_code=status_code)


@router.post("/generate-text-to-image", response_class=PlainTextResponse)
async def generate_text_to_image(
    req: GenerateTextToImageRequest,
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_or_api_key),
) -> PlainTextResponse:
    """
    Generate an image from a text prompt and return markdown ``![](url)``.

    Persists bytes to COS (or local fallback) and records ZhiHui history.

    Auth:
    - X-API-Key (Dify / external): allowed when the key validates.
    - Browser JWT: requires ``feature.zhihui`` (superadmin) and FEATURE_ZHIHUI.
    """
    prompt = req.prompt.strip()
    if not prompt:
        return PlainTextResponse(content="Error: Prompt is required", status_code=400)

    # JWT / mgat user path (not API-key): ZhiHui UI only — not school managers/teachers.
    if current_user is not None:
        if CAP_FEATURE_ZHIHUI not in user_panel_capabilities(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ZhiHui is restricted to platform administrators",
            )
        if not config.FEATURE_ZHIHUI:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ZhiHui disabled")

    language = (req.language or "zh").strip()
    api_key_id = None
    if hasattr(request, "state"):
        api_key_id = getattr(request.state, "api_key_id", None)

    try:
        # Short RLS for identity only — DashScope/COS must not hold an open request txn.
        if current_user is not None and hasattr(current_user, "id"):
            async with actor_rls_session(current_user) as db:
                save_identity = await resolve_diagram_save_identity(db, request, current_user, req)
        else:
            async with system_rls_session() as db:
                save_identity = await resolve_diagram_save_identity(db, request, current_user, req)
        user_id = save_identity.user_id
        organization_id = save_identity.organization_id
        conversation_id = conversation_id_from_request(req)
        dify_key = (save_identity.dify_user_key or "").strip() or None

        if user_id is not None and int(user_id) > 0:
            schedule_module_activity(
                user_id=int(user_id),
                organization_id=organization_id,
                module="zhihui",
                redis_activity_type="export_zhihui",
                request=request,
                details={"endpoint": "generate-text-to-image", "language": language},
                detail=f"zhihui lang={language}",
                persist_usage=False,
            )

        ref_count = len(req.reference_images or [])
        logger.info(
            "[T2I] Start model=%s size=%s prompt_len=%s refs=%s user_id=%s org_id=%s",
            req.model,
            (req.size or "").strip() or "auto",
            len(prompt),
            ref_count,
            user_id,
            organization_id,
        )
        start_time = time.time()
        result = await generate_and_store_image(
            prompt,
            model=req.model,
            size=req.size,
            watermark=bool(req.watermark),
            negative_prompt=req.negative_prompt or "",
            prompt_extend=bool(req.prompt_extend) if req.prompt_extend is not None else True,
            reference_images=req.reference_images,
            user_id=user_id,
            organization_id=organization_id,
            api_key_id=api_key_id,
        )

        # Always record a TokenUsage row so admin 外端API image counts stay accurate
        # even when K12 prompt enhancement is skipped (zero LLM tokens).
        usage_data = result.usage_data or {}
        input_tokens = usage_data.get("prompt_tokens") or usage_data.get("input_tokens") or 0
        output_tokens = usage_data.get("completion_tokens") or usage_data.get("output_tokens") or 0
        total_tokens = usage_data.get("total_tokens")
        if total_tokens is None:
            total_tokens = int(input_tokens) + int(output_tokens)
        total_tokens_int = int(total_tokens)
        try:
            token_tracker = get_token_tracker()
            await token_tracker.track_usage(
                model_alias="qwen",
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
                total_tokens=total_tokens_int,
                request_type="t2i_generation",
                diagram_type=None,
                user_id=user_id,
                organization_id=organization_id,
                api_key_id=api_key_id,
                endpoint_path="/api/generate-text-to-image",
                conversation_id=conversation_id,
                response_time=time.time() - start_time,
                success=True,
            )
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("[T2I] Token tracking failed (non-critical): %s", exc)

        async with system_rls_session() as hist_db:
            conv_repo = ZhihuiConversationRepository(hist_db)
            gen_repo = ZhihuiGenerationRepository(hist_db)
            title = (result.original_prompt or "").replace("\n", " ").strip()[:256] or "Image"
            conversation = await conv_repo.create_conversation(
                mode="image",
                title=title,
                user_id=user_id,
                organization_id=organization_id,
                image_model=req.model or "qwen-image-3.0",
                status="complete",
                language=language,
                commit=False,
            )
            await gen_repo.create_generation(
                generation_id=result.generation_id,
                prompt=result.original_prompt,
                enhanced_prompt=result.enhanced_prompt,
                language=language,
                user_id=user_id,
                organization_id=organization_id,
                conversation_id=conversation.id,
                dify_conversation_id=conversation_id,
                dify_user_id=dify_key,
                cos_logical_key=result.logical_key,
                content_type=result.content_type,
                size=result.size,
                api_key_id=api_key_id,
                slide_index=0,
                slide_title=title[:256],
                commit=True,
            )

        if user_id is not None and int(user_id) > 0:
            try:
                activity_service = get_activity_stream_service()
                user_name = getattr(current_user, "name", None) if current_user else None
                await activity_service.broadcast_activity(
                    user_id=int(user_id),
                    action="generated",
                    diagram_type="zhihui_image",
                    topic=(result.original_prompt[:50].strip() or "Image"),
                    user_name=user_name,
                )
            except BACKGROUND_INFRA_ERRORS as exc:
                logger.debug("[T2I] Failed to broadcast activity: %s", exc)

        signed_path = generate_signed_url(
            result.logical_key,
            expiration_seconds=config.T2I_ASSET_URL_TTL_SECONDS,
        )
        image_url = build_public_zhihui_asset_url(request, signed_path)
        plain_text = f"![]({image_url})"

        if user_id is not None and int(user_id) > 0:
            schedule_user_usage_activity(
                user_id=int(user_id),
                organization_id=organization_id,
                source="zhihui",
                action="t2i_image",
                title=(result.original_prompt[:50].strip() or "Image"),
                prompt_preview=result.original_prompt,
                conversation_id=conversation_id,
                total_tokens=total_tokens_int,
            )

        logger.info(
            "[T2I] Success generation_id=%s user_id=%s bytes=%s refs=%s elapsed_ms=%s",
            result.generation_id,
            user_id,
            result.image_bytes_len,
            ref_count,
            int((time.time() - start_time) * 1000),
        )
        return PlainTextResponse(content=plain_text)

    except ValueError as exc:
        logger.warning("[T2I] Validation error: %s", exc)
        return _plain_error(exc, 400)
    except LLMContentFilterError as exc:
        # 400-DataInspectionFailed / green-net blocks — do not retry.
        logger.warning("[T2I] Content filter: %s", exc)
        return _plain_error(exc, 400)
    except LLMInvalidParameterError as exc:
        logger.warning("[T2I] Invalid parameter: %s", exc)
        return _plain_error(exc, 400)
    except LLMModelNotFoundError as exc:
        logger.error("[T2I] Model not found: %s", exc)
        return _plain_error(exc, 400)
    except (LLMRateLimitError, LLMQuotaExhaustedError) as exc:
        # 429 Throttling / Arrearage / AllocationQuota.
        logger.warning("[T2I] Rate/quota: %s", exc)
        return _plain_error(exc, 429)
    except LLMAccessDeniedError as exc:
        logger.error("[T2I] Access denied: %s", exc)
        return _plain_error(exc, 502)
    except LLMProviderError as exc:
        code = (getattr(exc, "error_code", None) or "").lower()
        # Content filter / invalid param sometimes arrive as generic provider errors.
        if "datainspection" in code or "invalidparameter" in code:
            logger.warning("[T2I] Provider client error code=%s: %s", code, exc)
            return _plain_error(exc, 400)
        if "throttl" in code or "arrearage" in code or "quota" in code:
            logger.warning("[T2I] Provider throttle/billing code=%s: %s", code, exc)
            return _plain_error(exc, 429)
        logger.error("[T2I] Provider error: %s", exc, exc_info=True)
        return _plain_error(exc, 502)
    except LLMServiceError as exc:
        logger.error("[T2I] LLM service error: %s", exc, exc_info=True)
        return _plain_error(exc, 502)
    except _GENERATION_ERRORS as exc:
        logger.error("[T2I] Generation failed: %s", exc, exc_info=True)
        return PlainTextResponse(
            content=f"Error: Failed to generate image - {exc}",
            status_code=500,
        )
