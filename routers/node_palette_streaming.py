"""
Node Palette streaming helpers.

Extracted streaming logic for node palette SSE endpoints to reduce complexity
and fix type checker issues (reportGeneralTypeIssues, ContentStream).
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Dict, Optional, Type

from services.infrastructure.http.error_handler import (
    LLMAccessDeniedError,
    LLMContentFilterError,
    LLMInvalidParameterError,
    LLMModelNotFoundError,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
    LLMServiceError,
    LLMTimeoutError,
)
from utils.chinese_language_policy import (
    collect_node_palette_text_blobs,
    effective_language_for_thinking_user,
    is_chinese_ui_error_language,
)
from utils.placeholder import is_placeholder_text
from utils.prompt_output_languages import is_prompt_output_language

logger = logging.getLogger(__name__)

_LLM_ERROR_MAP: dict[Type[Exception], str] = {
    LLMContentFilterError: "content_filter",
    LLMRateLimitError: "rate_limit",
    LLMTimeoutError: "timeout",
    LLMInvalidParameterError: "invalid_parameter",
    LLMQuotaExhaustedError: "quota_exhausted",
    LLMModelNotFoundError: "model_not_found",
    LLMAccessDeniedError: "access_denied",
    LLMServiceError: "service_error",
}

_ERROR_MESSAGES: dict[str, tuple[str, str]] = {
    "content_filter": (
        "无法处理您的请求，请尝试修改主题描述。",
        "Content could not be processed. Please try a different topic.",
    ),
    "rate_limit": (
        "AI服务繁忙，请稍后重试。",
        "AI service is busy. Please try again in a few seconds.",
    ),
    "timeout": ("请求超时，请重试。", "Request timed out. Please try again."),
    "invalid_parameter": (
        "参数错误，请检查输入。",
        "Invalid parameter. Please check input.",
    ),
    "quota_exhausted": (
        "配额已用完，请检查账户。",
        "Quota exhausted. Please check account.",
    ),
    "model_not_found": (
        "模型不存在，请检查配置。",
        "Model not found. Please check configuration.",
    ),
    "access_denied": (
        "访问被拒绝，请检查权限。",
        "Access denied. Please check permissions.",
    ),
    "service_error": (
        "AI服务错误，请稍后重试。",
        "AI service error. Please try again later.",
    ),
    "unknown": ("出现问题，请重试。", "Something went wrong. Please try again."),
    "no_response": (
        "请求处理失败，请重试。",
        "Request processing failed. Please try again.",
    ),
}


def _get_default_stage(diagram_type: str) -> str:
    """Return default stage for multi-stage diagram types."""
    if diagram_type == "mindmap":
        return "branches"
    if diagram_type == "flow_map":
        return "steps"
    if diagram_type in ("tree_map", "brace_map", "bridge_map"):
        return "dimensions"
    return "categories"


def _resolve_stage_and_data(
    req: Any,
    diagram_type: str,
    default_stage: str,
) -> tuple[str, dict[str, Any]]:
    """Resolve stage and stage_data from request for multi-stage diagrams."""
    stage = getattr(req, "stage", default_stage)
    stage_data = getattr(req, "stage_data", None) or {}
    diagram_data = getattr(req, "diagram_data", None) or {}
    raw_dim = (diagram_data.get("dimension") or "").strip()
    diagram_dim = "" if is_placeholder_text(raw_dim) else raw_dim

    if stage == "dimensions" and diagram_type in ("tree_map", "brace_map", "bridge_map") and diagram_dim:
        stage = "parts" if diagram_type == "brace_map" else "categories" if diagram_type == "tree_map" else "pairs"
        stage_data = {
            **(stage_data if isinstance(stage_data, dict) else {}),
            "dimension": diagram_dim,
        }
        logger.debug(
            "[NodePalette-API] Dimension already fixed '%s', skipping to stage: %s",
            diagram_dim[:30],
            stage,
        )
    elif isinstance(stage_data, dict) and diagram_type in (
        "tree_map",
        "brace_map",
        "bridge_map",
    ):
        if diagram_dim and not stage_data.get("dimension"):
            stage_data = {**stage_data, "dimension": diagram_dim}
        if diagram_type == "bridge_map" and stage == "dimensions":
            analogies = diagram_data.get("analogies")
            if analogies and isinstance(analogies, list) and not stage_data.get("analogies"):
                stage_data = {**stage_data, "analogies": analogies}

    return stage, stage_data if isinstance(stage_data, dict) else {}


def _get_error_message(req: Any, error_type: str, language_for_ui: str | None = None) -> str:
    """Get localized error message for given error type."""
    language = language_for_ui if language_for_ui is not None else getattr(req, "language", "en")
    zh_msg, en_msg = _ERROR_MESSAGES.get(error_type, _ERROR_MESSAGES["unknown"])
    return zh_msg if is_chinese_ui_error_language(str(language)) else en_msg


def _yield_error_event(
    req: Any,
    error_type: str,
    user_message: str | None = None,
    language_for_ui: str | None = None,
) -> str:
    """Format error event as SSE data string."""
    msg = user_message or _get_error_message(req, error_type, language_for_ui)
    return f"data: {json.dumps({'event': 'error', 'error_type': error_type, 'message': msg})}\n\n"


def _merged_educational_context(req: Any, effective_language: str | None = None) -> Optional[Dict[str, Any]]:
    """Merge educational_context with concept_map fields and request generation language."""
    edu: Dict[str, Any] = {}
    raw = getattr(req, "educational_context", None)
    if isinstance(raw, dict):
        edu = dict(raw)
    if getattr(req, "diagram_type", None) == "concept_map":
        dd = getattr(req, "diagram_data", None) or {}
        if isinstance(dd, dict):
            fq = str(dd.get("focus_question") or "").strip()
            rc = str(dd.get("root_concept") or "").strip()
            if fq:
                edu["focus_question"] = fq
            if rc:
                edu["root_concept"] = rc
    req_lang = effective_language if effective_language is not None else getattr(req, "language", None)
    if isinstance(req_lang, str):
        stripped = req_lang.strip().lower()
        if is_prompt_output_language(stripped):
            edu["language"] = stripped
    return edu if edu else None


def _build_batch_kwargs(
    req: Any,
    session_id: str,
    center_topic: str,
    endpoint_path: str,
    current_user: Any,
    effective_language: str,
) -> dict[str, Any]:
    """Build common kwargs for generate_batch based on diagram type."""
    default_stage = _get_default_stage(req.diagram_type)
    stage, stage_data = _resolve_stage_and_data(req, req.diagram_type, default_stage)
    user_id = current_user.id if current_user else None
    org_id = current_user.organization_id if current_user else None
    base = {
        "session_id": session_id,
        "center_topic": center_topic,
        "educational_context": _merged_educational_context(req, effective_language),
        "nodes_per_llm": 15,
        "user_id": user_id,
        "organization_id": org_id,
        "diagram_type": req.diagram_type,
        "endpoint_path": endpoint_path,
    }
    if req.diagram_type in ["double_bubble_map", "multi_flow_map"]:
        mode = getattr(
            req,
            "mode",
            "similarities" if req.diagram_type == "double_bubble_map" else "causes",
        )
        return {**base, "_mode": mode}
    if req.diagram_type in [
        "tree_map",
        "brace_map",
        "flow_map",
        "mindmap",
        "bridge_map",
    ]:
        return {**base, "_stage": stage, "_stage_data": stage_data}
    if req.diagram_type == "concept_map":
        concept_mode = getattr(req, "mode", None)
        concept_stage = getattr(req, "stage_data", None) or {}
        return {
            **base,
            "_mode": concept_mode,
            "_stage_data": concept_stage if isinstance(concept_stage, dict) else {},
        }
    return base


async def stream_node_palette(
    req: Any,
    session_id: str,
    center_topic: str,
    generator: Any,
    current_user: Any,
    endpoint_path: str,
    log_prefix: str = "[NodePalette-API]",
) -> AsyncIterator[str]:
    """
    Async generator yielding SSE chunks from node palette generator.

    Reduces complexity for type checker and provides proper AsyncIterator type.
    """
    logger.debug("%s SSE stream starting | Session: %s", log_prefix, session_id[:8])

    # Yield an SSE comment IMMEDIATELY to establish the HTTP response before
    # any awaitable operation. This prevents Starlette's BaseHTTPMiddleware
    # from raising "RuntimeError: No response returned" when the client
    # aborts the request (asyncio.CancelledError / GeneratorExit) before the
    # LLM yields its first chunk. SSE comment lines start with ':' and are
    # ignored by browser EventSource parsers, so the frontend is unaffected.
    # Without this, a cancellation during the first __anext__() of the inner
    # generator escapes as BaseException (not caught by `except Exception`),
    # leaving the ASGI response start message unsent.
    yield ": stream_open\n\n"

    node_count = 0
    chunk_count = 0
    # Tracks whether a fallback event was already sent when no chunks arrived.
    # Used to prevent double-sending from both the try/except block and the
    # finally block, and to avoid yielding in finally (which raises
    # RuntimeError: async generator ignored GeneratorExit when aclose() is
    # called due to client disconnect or CancelledError).
    no_chunk_response_sent = False
    cancelled = False

    raw_lang = (getattr(req, "language", None) or "en").strip().lower()
    text_blobs = collect_node_palette_text_blobs(req, center_topic)
    effective_lang = effective_language_for_thinking_user(current_user, raw_lang, *text_blobs)

    try:
        batch_kwargs = _build_batch_kwargs(req, session_id, center_topic, endpoint_path, current_user, effective_lang)
        if req.diagram_type in [
            "tree_map",
            "brace_map",
            "flow_map",
            "mindmap",
            "bridge_map",
        ]:
            logger.debug(
                "%s %s stage: %s | Stage data: %s",
                log_prefix,
                req.diagram_type,
                batch_kwargs.get("_stage"),
                batch_kwargs.get("_stage_data"),
            )

        async for chunk in generator.generate_batch(**batch_kwargs):
            chunk_count += 1
            if chunk.get("event") == "node_generated":
                node_count += 1
            yield f"data: {json.dumps(chunk)}\n\n"

        if chunk_count == 0:
            logger.warning(
                "%s No chunks yielded, sending completion event | Session: %s",
                log_prefix,
                session_id[:8],
            )
            no_chunk_response_sent = True
            yield f"data: {json.dumps({'event': 'batch_complete', 'nodes': node_count})}\n\n"

        logger.debug(
            "%s Batch complete | Session: %s | Nodes: %d",
            log_prefix,
            session_id[:8],
            node_count,
        )

    except asyncio.CancelledError:
        # Client aborted the request (e.g. frontend streaming abort / disconnect).
        # This is a BaseException in Python 3.8+, so `except Exception` below
        # does not catch it. Handle it explicitly to log a clean info message
        # and re-raise so asyncio preserves cancellation semantics. Do NOT
        # yield here: the caller is gone. The initial SSE heartbeat yielded
        # at the top of this function already established the HTTP response,
        # so Starlette will not raise "No response returned".
        cancelled = True
        no_chunk_response_sent = True
        logger.info(
            "%s Stream cancelled by client | Session: %s | Chunks yielded: %d",
            log_prefix,
            session_id[:8],
            chunk_count,
        )
        raise

    except (
        LLMContentFilterError,
        LLMRateLimitError,
        LLMTimeoutError,
        LLMInvalidParameterError,
        LLMQuotaExhaustedError,
        LLMModelNotFoundError,
        LLMAccessDeniedError,
        LLMServiceError,
    ) as exc:
        error_type = _LLM_ERROR_MAP.get(type(exc), "unknown")
        is_service_error = isinstance(exc, LLMServiceError)
        log_fn = logger.error if is_service_error else logger.warning
        log_fn(
            "%s %s | Session: %s | Error: %s",
            log_prefix,
            error_type.replace("_", " ").title(),
            session_id[:8],
            str(exc),
        )
        no_chunk_response_sent = True
        yield _yield_error_event(req, error_type, getattr(exc, "user_message", None), language_for_ui=effective_lang)

    except Exception as exc:
        logger.error(
            "%s Stream error | Session: %s | Error: %s",
            log_prefix,
            session_id[:8],
            str(exc),
            exc_info=True,
        )
        no_chunk_response_sent = True
        yield _yield_error_event(req, "unknown", language_for_ui=effective_lang)

    finally:
        # NEVER yield inside a finally block of an async generator.
        # If the generator is being closed via aclose() (client disconnect,
        # CancelledError, etc.), a yield here raises:
        #   RuntimeError: async generator ignored GeneratorExit
        # which Starlette re-wraps as "No response returned."
        # All response paths are already covered by the try/except blocks above,
        # and the initial SSE heartbeat at function entry guarantees the HTTP
        # response is always established even if no data chunks are produced.
        if chunk_count == 0 and not no_chunk_response_sent and not cancelled:
            logger.warning(
                "%s Generator completed without yielding, no response sent | Session: %s",
                log_prefix,
                session_id[:8],
            )
