"""
Shared helpers for Maite Learning API routers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Optional, Tuple, Type

from fastapi import HTTPException, status

from models.domain.auth import User
from services.maite.domain.errors import MaiteConflictError, MaiteForbiddenError, MaiteNotFoundError
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS

logger = logging.getLogger(__name__)

MAITE_DOMAIN_ERRORS: Tuple[Type[Exception], ...] = (
    MaiteNotFoundError,
    MaiteConflictError,
    MaiteForbiddenError,
    *DATABASE_ERRORS,
    *BACKGROUND_INFRA_ERRORS,
    ValueError,
    TypeError,
    KeyError,
    RuntimeError,
)


def organization_id_for(user: User) -> Optional[int]:
    """Return the caller organization id when present."""
    return getattr(user, "organization_id", None)


def raise_maite_http_error(exc: Exception) -> None:
    """Map Maite domain errors to HTTP exceptions."""
    if isinstance(exc, MaiteNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, MaiteConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(exc, MaiteForbiddenError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if isinstance(exc, DATABASE_ERRORS):
        logger.error("Maite database error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed",
        ) from exc
    if isinstance(exc, BACKGROUND_INFRA_ERRORS):
        logger.error("Maite infrastructure error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable",
        ) from exc
    logger.error("Maite unexpected error: %s", exc, exc_info=True)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    ) from exc


def encode_sse_event(event: str, data: dict[str, Any]) -> str:
    """Format a single Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_maite_events(
    events: AsyncGenerator[dict[str, Any], None],
) -> AsyncGenerator[str, None]:
    """Convert Maite mentor stream dicts into SSE frames."""
    try:
        async for item in events:
            event_name = str(item.get("event") or "status")
            payload = item.get("data")
            if not isinstance(payload, dict):
                payload = {"value": payload}
            yield encode_sse_event(event_name, payload)
    except MaiteNotFoundError as exc:
        yield encode_sse_event("error", {"message": str(exc)})
    except (*DATABASE_ERRORS,) as exc:
        logger.error("Maite SSE stream failed: %s", exc, exc_info=True)
        yield encode_sse_event("error", {"message": "Internal server error"})
