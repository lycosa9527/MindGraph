"""
Showcase AI helpers: teaching-design copy from uploaded document text.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)

from models.domain.auth import User
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from services.infrastructure.http.error_handler import (
    LLMAccessDeniedError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from services.showcase.ai_copy import (
    extract_document_text,
    generate_teaching_design_copy,
)
from services.utils.error_types import LLM_PIPELINE_ERRORS
from utils.auth import get_current_user

from .helpers import ALLOWED_DOC_SUFFIXES, ATTACHMENT_MAX_BYTES

logger = logging.getLogger(__name__)

router = APIRouter()

_ENDPOINT_PATH = "/api/showcase/ai/teaching-copy"

_EXTRACT_IO_ERRORS = (
    OSError,
    PermissionError,
    FileNotFoundError,
    IsADirectoryError,
    RuntimeError,
)


@router.post("/ai/teaching-copy")
async def generate_teaching_design_ai_copy(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
    subject: str = Form(""),
    grade: str = Form(""),
    current_user: User = Depends(get_current_user),
):
    """Extract teaching-design text then draft intro / highlights / reflection."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "showcase_ai_teaching_copy",
        identifier,
        max_requests=12,
        window_seconds=60,
    )

    filename = (file.filename or "document.pdf").strip() or "document.pdf"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_DOC_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported document type",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )
    if len(raw) > ATTACHMENT_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Document too large",
        )

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            temp_path = Path(tmp.name)

        try:
            document_text = extract_document_text(str(temp_path))
        except ValueError as exc:
            message = str(exc)
            if message.startswith("unsupported_file_type"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unsupported document type",
                ) from exc
            if message == "no_text_extracted":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="No text extracted from document",
                ) from exc
            logger.warning("[ShowcaseAI] extract failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Failed to extract text from document",
            ) from exc
        except _EXTRACT_IO_ERRORS as exc:
            logger.warning("[ShowcaseAI] extract io failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Failed to extract text from document",
            ) from exc

        try:
            fields = await generate_teaching_design_copy(
                document_text=document_text,
                title=title,
                subject=subject,
                grade=grade,
                user_id=getattr(current_user, "id", None),
                organization_id=getattr(current_user, "organization_id", None),
                endpoint_path=_ENDPOINT_PATH,
            )
        except LLMRateLimitError as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="AI rate limited, please retry shortly",
            ) from exc
        except LLMTimeoutError as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="AI generation timed out",
            ) from exc
        except LLMAccessDeniedError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AI access denied",
            ) from exc
        except LLMProviderError as exc:
            logger.warning("[ShowcaseAI] provider error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI provider error",
            ) from exc
        except LLM_PIPELINE_ERRORS as exc:
            logger.warning("[ShowcaseAI] generate failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI generation failed",
            ) from exc

        return {
            "description": fields["description"],
            "design_highlights": fields["design_highlights"],
            "teaching_reflection": fields["teaching_reflection"],
            "model": "qwen3.7-flash",
        }
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)
