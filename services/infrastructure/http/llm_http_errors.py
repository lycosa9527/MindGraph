"""Map LLM service exceptions to HTTPException for API routes.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging

from typing import NoReturn

from fastapi import HTTPException

from services.infrastructure.http.error_handler import (
    LLMAccessDeniedError,
    LLMContentFilterError,
    LLMInvalidParameterError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
    LLMServiceError,
    LLMTimeoutError,
    ThinkingCoinInsufficientError,
    UserDailyTokenCapExceededError,
)

logger = logging.getLogger(__name__)


def http_exception_for_llm_error(exc: BaseException) -> HTTPException:
    """Map typed LLM failures to stable HTTP status codes for API clients."""
    if isinstance(exc, UserDailyTokenCapExceededError):
        return HTTPException(status_code=429, detail=str(exc.user_message))
    if isinstance(exc, ThinkingCoinInsufficientError):
        return HTTPException(status_code=402, detail=str(exc.user_message))
    if isinstance(exc, LLMRateLimitError):
        return HTTPException(status_code=429, detail=str(exc) or "AI rate limited, please retry shortly")
    if isinstance(exc, LLMQuotaExhaustedError):
        return HTTPException(status_code=429, detail=str(exc) or "AI quota exhausted")
    if isinstance(exc, LLMTimeoutError):
        return HTTPException(status_code=504, detail=str(exc) or "AI generation timed out")
    if isinstance(exc, LLMAccessDeniedError):
        # Upstream provider / server API key — not client MindGraph auth.
        logger.error("[LLM HTTP] Access denied: %s", exc)
        return HTTPException(status_code=502, detail=str(exc) or "AI access denied")
    if isinstance(exc, (LLMContentFilterError, LLMInvalidParameterError, LLMModelNotFoundError)):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, LLMProviderError):
        code = (getattr(exc, "error_code", None) or "").lower()
        if "datainspection" in code or "invalidparameter" in code:
            return HTTPException(status_code=400, detail=str(exc))
        if "throttl" in code or "arrearage" in code or "quota" in code:
            return HTTPException(status_code=429, detail=str(exc))
        logger.error("[LLM HTTP] Provider error: %s", exc)
        return HTTPException(status_code=502, detail=str(exc) or "AI provider error")
    if isinstance(exc, LLMServiceError):
        logger.error("[LLM HTTP] Service error: %s", exc)
        return HTTPException(status_code=502, detail=str(exc) or "AI generation failed")
    logger.error("[LLM HTTP] Unexpected LLM failure type=%s: %s", type(exc).__name__, exc)
    return HTTPException(status_code=502, detail="AI generation failed")


def raise_http_for_llm_error(exc: BaseException) -> NoReturn:
    """Raise the mapped HTTPException (never returns)."""
    raise http_exception_for_llm_error(exc) from exc
