"""
Showcase AI helpers: teaching-design / diagram copy drafts for publish modal.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, NoReturn

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
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from models.domain.auth import User
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from services.infrastructure.http.error_handler import (
    LLMAccessDeniedError,
    LLMContentFilterError,
    LLMProviderError,
    LLMRateLimitError,
    LLMServiceError,
    LLMTimeoutError,
)
from services.infrastructure.http.llm_http_errors import http_exception_for_llm_error
from services.showcase.ai_copy import (
    extract_document_text,
    generate_teaching_design_copy,
    stream_teaching_design_copy,
)
from services.showcase.diagram_ai_copy import (
    extract_diagram_text_from_images,
    extract_diagram_texts,
    generate_diagram_case_copy,
    stream_diagram_case_copy,
)
from services.utils.error_types import LLM_PIPELINE_ERRORS
from utils.auth import get_current_user

from .helpers import (
    ALLOWED_DOC_SUFFIXES,
    ATTACHMENT_MAX_BYTES,
    GALLERY_IMAGE_SUFFIXES,
    _validate_magic_bytes,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_ENDPOINT_PATH = "/api/showcase/ai/teaching-copy"
_STREAM_ENDPOINT_PATH = "/api/showcase/ai/teaching-copy/stream"
_DIAGRAM_ENDPOINT_PATH = "/api/showcase/ai/diagram-copy"
_DIAGRAM_STREAM_ENDPOINT_PATH = "/api/showcase/ai/diagram-copy/stream"
_DIAGRAM_IMAGES_ENDPOINT_PATH = "/api/showcase/ai/diagram-copy/images"
_DIAGRAM_IMAGES_STREAM_ENDPOINT_PATH = "/api/showcase/ai/diagram-copy/images/stream"
# Keep in sync with frontend DIAGRAM_GALLERY_MAX_ITEMS.
_MAX_DIAGRAM_SPECS = 15
_MAX_DIAGRAM_OCR_IMAGES = 8
_MAX_DIAGRAM_OCR_TOTAL_BYTES = 40 * 1024 * 1024
_IMAGE_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


class DiagramCopyBody(BaseModel):
    """JSON body for diagram AI copy (specs from personal library / .mg / canvas)."""

    title: str = ""
    subject: str = ""
    grade: str = ""
    diagram_type: str = ""
    specs: list[dict[str, Any]] = Field(default_factory=list)


_EXTRACT_IO_ERRORS = (
    OSError,
    PermissionError,
    FileNotFoundError,
    IsADirectoryError,
    RuntimeError,
)


def _raise_extract_http(exc: Exception) -> NoReturn:
    """Map document extract failures to HTTPException (never returns)."""
    if isinstance(exc, ValueError):
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
    if isinstance(exc, _EXTRACT_IO_ERRORS):
        logger.warning("[ShowcaseAI] extract io failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to extract text from document",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Failed to extract text from document",
    ) from exc


async def _prepare_teaching_copy_document(
    *,
    request: Request,
    file: UploadFile,
    current_user: User,
) -> tuple[str, Path]:
    """
    Rate-limit, validate upload, extract text.

    Returns ``(document_text, temp_path)``. Caller must unlink ``temp_path``.
    """
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
    _validate_magic_bytes(raw, suffix)

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(raw)
        temp_path = Path(tmp.name)

    try:
        document_text = await asyncio.to_thread(extract_document_text, str(temp_path))
    except (ValueError, *_EXTRACT_IO_ERRORS) as exc:
        temp_path.unlink(missing_ok=True)
        _raise_extract_http(exc)

    return document_text, temp_path


def _map_llm_http(exc: Exception) -> HTTPException:
    return http_exception_for_llm_error(exc)


def _sse_line(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream_teaching_copy_events(
    *,
    http_request: Request,
    document_text: str,
    title: str,
    subject: str,
    grade: str,
    user_id: int | None,
    organization_id: int | None,
    temp_path: Path,
) -> AsyncIterator[str]:
    """Yield SSE chunks; cancel LLM work when the client disconnects."""
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    cancel_event = asyncio.Event()

    async def run_stream() -> None:
        try:
            await queue.put({"event": "phase", "phase": "generating"})
            async for event in stream_teaching_design_copy(
                document_text=document_text,
                title=title,
                subject=subject,
                grade=grade,
                user_id=user_id,
                organization_id=organization_id,
                endpoint_path=_STREAM_ENDPOINT_PATH,
            ):
                if cancel_event.is_set():
                    break
                await queue.put(event)
        except asyncio.CancelledError:
            logger.debug("[ShowcaseAI] stream cancelled")
        except LLMContentFilterError as exc:
            msg = getattr(exc, "user_message", None) or "AI content filtered"
            await queue.put({"event": "error", "message": msg, "error_type": "content_filter"})
        except LLMRateLimitError as exc:
            msg = getattr(exc, "user_message", None) or "AI rate limited, please retry shortly"
            await queue.put({"event": "error", "message": msg, "error_type": "rate_limit"})
        except LLMTimeoutError as exc:
            msg = getattr(exc, "user_message", None) or "AI generation timed out"
            await queue.put({"event": "error", "message": msg, "error_type": "timeout"})
        except LLMAccessDeniedError as exc:
            msg = getattr(exc, "user_message", None) or "AI access denied"
            await queue.put({"event": "error", "message": msg, "error_type": "access_denied"})
        except (LLMProviderError, LLMServiceError, *LLM_PIPELINE_ERRORS) as exc:
            logger.warning("[ShowcaseAI] stream failed: %s", exc)
            await queue.put(
                {
                    "event": "error",
                    "message": "AI generation failed",
                    "error_type": "service_error",
                }
            )
        finally:
            await queue.put(None)

    task = asyncio.create_task(run_stream())

    async def monitor_disconnect() -> None:
        while not task.done():
            if await http_request.is_disconnected():
                cancel_event.set()
                task.cancel()
                return
            await asyncio.sleep(0.25)

    monitor_task = asyncio.create_task(monitor_disconnect())
    try:
        yield _sse_line({"event": "phase", "phase": "extracting"})
        while True:
            item = await queue.get()
            if item is None:
                break
            yield _sse_line(item)
    finally:
        monitor_task.cancel()
        if not task.done():
            cancel_event.set()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        temp_path.unlink(missing_ok=True)


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
    document_text, temp_path = await _prepare_teaching_copy_document(
        request=request,
        file=file,
        current_user=current_user,
    )
    try:
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
        except (
            LLMRateLimitError,
            LLMTimeoutError,
            LLMAccessDeniedError,
            LLMContentFilterError,
            LLMProviderError,
            *LLM_PIPELINE_ERRORS,
        ) as exc:
            raise _map_llm_http(exc) from exc

        return {
            "description": fields["description"],
            "design_highlights": fields["design_highlights"],
            "teaching_reflection": fields["teaching_reflection"],
            "model": "qwen3.7-flash",
        }
    finally:
        temp_path.unlink(missing_ok=True)


@router.post("/ai/teaching-copy/stream")
async def generate_teaching_design_ai_copy_stream(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
    subject: str = Form(""),
    grade: str = Form(""),
    current_user: User = Depends(get_current_user),
):
    """
    SSE stream: phase + incremental fields + done.

    Multipart validation and text extraction run before the stream opens.
    """
    document_text, temp_path = await _prepare_teaching_copy_document(
        request=request,
        file=file,
        current_user=current_user,
    )
    return StreamingResponse(
        _stream_teaching_copy_events(
            http_request=request,
            document_text=document_text,
            title=title,
            subject=subject,
            grade=grade,
            user_id=getattr(current_user, "id", None),
            organization_id=getattr(current_user, "organization_id", None),
            temp_path=temp_path,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _prepare_diagram_copy_text_async(
    *,
    request: Request,
    body: DiagramCopyBody,
    current_user: User,
) -> str:
    """Rate-limit and extract node text from diagram specs."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "showcase_ai_diagram_copy",
        identifier,
        max_requests=12,
        window_seconds=60,
    )

    if not body.specs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Diagram spec required",
        )
    if len(body.specs) > _MAX_DIAGRAM_SPECS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At most {_MAX_DIAGRAM_SPECS} diagram specs",
        )

    try:
        return await asyncio.to_thread(
            extract_diagram_texts,
            body.specs,
            body.diagram_type or "mind_map",
        )
    except ValueError as exc:
        if str(exc) == "no_text_extracted":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No text extracted from diagram",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to extract text from diagram",
        ) from exc


async def _read_validated_gallery_image(
    upload: UploadFile,
) -> tuple[bytes, str]:
    """Validate one gallery image upload; return ``(bytes, mime_type)``."""
    filename = (upload.filename or "image.png").strip() or "image.png"
    suffix = Path(filename).suffix.lower()
    if suffix not in GALLERY_IMAGE_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported image type",
        )
    raw = await upload.read()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty image",
        )
    if len(raw) > ATTACHMENT_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image too large",
        )
    _validate_magic_bytes(raw, suffix)
    mime_type = _IMAGE_MIME_BY_SUFFIX.get(suffix, "image/png")
    return raw, mime_type


async def _prepare_diagram_copy_images_async(
    *,
    request: Request,
    files: list[UploadFile],
    current_user: User,
) -> str:
    """Rate-limit, validate gallery images, OCR via Qwen vision."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "showcase_ai_diagram_copy",
        identifier,
        max_requests=12,
        window_seconds=60,
    )

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one gallery image required",
        )
    if len(files) > _MAX_DIAGRAM_OCR_IMAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At most {_MAX_DIAGRAM_OCR_IMAGES} images for AI copy",
        )

    images: list[tuple[bytes, str]] = []
    total_bytes = 0
    for upload in files:
        raw, mime_type = await _read_validated_gallery_image(upload)
        total_bytes += len(raw)
        if total_bytes > _MAX_DIAGRAM_OCR_TOTAL_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Total image size for AI copy exceeds limit",
            )
        images.append((raw, mime_type))

    try:
        return await asyncio.to_thread(extract_diagram_text_from_images, images)
    except ValueError as exc:
        if str(exc) == "no_text_extracted":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No text extracted from images",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to extract text from images",
        ) from exc


async def _stream_diagram_copy_events(
    *,
    http_request: Request,
    diagram_text: str,
    title: str,
    subject: str,
    grade: str,
    diagram_type: str,
    user_id: int | None,
    organization_id: int | None,
) -> AsyncIterator[str]:
    """Yield SSE chunks for diagram AI copy; cancel on client disconnect."""
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    cancel_event = asyncio.Event()

    async def run_stream() -> None:
        try:
            await queue.put({"event": "phase", "phase": "generating"})
            async for event in stream_diagram_case_copy(
                diagram_text=diagram_text,
                title=title,
                subject=subject,
                grade=grade,
                diagram_type=diagram_type,
                user_id=user_id,
                organization_id=organization_id,
                endpoint_path=_DIAGRAM_STREAM_ENDPOINT_PATH,
            ):
                if cancel_event.is_set():
                    break
                await queue.put(event)
        except asyncio.CancelledError:
            logger.debug("[ShowcaseAI] diagram stream cancelled")
        except LLMContentFilterError as exc:
            msg = getattr(exc, "user_message", None) or "AI content filtered"
            await queue.put({"event": "error", "message": msg, "error_type": "content_filter"})
        except LLMRateLimitError as exc:
            msg = getattr(exc, "user_message", None) or "AI rate limited, please retry shortly"
            await queue.put({"event": "error", "message": msg, "error_type": "rate_limit"})
        except LLMTimeoutError as exc:
            msg = getattr(exc, "user_message", None) or "AI generation timed out"
            await queue.put({"event": "error", "message": msg, "error_type": "timeout"})
        except LLMAccessDeniedError as exc:
            msg = getattr(exc, "user_message", None) or "AI access denied"
            await queue.put({"event": "error", "message": msg, "error_type": "access_denied"})
        except (LLMProviderError, LLMServiceError, *LLM_PIPELINE_ERRORS) as exc:
            logger.warning("[ShowcaseAI] diagram stream failed: %s", exc)
            await queue.put(
                {
                    "event": "error",
                    "message": "AI generation failed",
                    "error_type": "service_error",
                }
            )
        finally:
            await queue.put(None)

    task = asyncio.create_task(run_stream())

    async def monitor_disconnect() -> None:
        while not task.done():
            if await http_request.is_disconnected():
                cancel_event.set()
                task.cancel()
                return
            await asyncio.sleep(0.25)

    monitor_task = asyncio.create_task(monitor_disconnect())
    try:
        yield _sse_line({"event": "phase", "phase": "extracting"})
        while True:
            item = await queue.get()
            if item is None:
                break
            yield _sse_line(item)
    finally:
        monitor_task.cancel()
        if not task.done():
            cancel_event.set()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass


@router.post("/ai/diagram-copy")
async def generate_diagram_ai_copy(
    request: Request,
    body: DiagramCopyBody,
    current_user: User = Depends(get_current_user),
):
    """Extract diagram node text then draft intro / classroom application."""
    diagram_text = await _prepare_diagram_copy_text_async(
        request=request,
        body=body,
        current_user=current_user,
    )
    try:
        fields = await generate_diagram_case_copy(
            diagram_text=diagram_text,
            title=body.title,
            subject=body.subject,
            grade=body.grade,
            diagram_type=body.diagram_type,
            user_id=getattr(current_user, "id", None),
            organization_id=getattr(current_user, "organization_id", None),
            endpoint_path=_DIAGRAM_ENDPOINT_PATH,
        )
    except (
        LLMRateLimitError,
        LLMTimeoutError,
        LLMAccessDeniedError,
        LLMContentFilterError,
        LLMProviderError,
        *LLM_PIPELINE_ERRORS,
    ) as exc:
        raise _map_llm_http(exc) from exc

    return {
        "description": fields["description"],
        "classroom_application": fields["classroom_application"],
        "model": "qwen3.7-flash",
    }


@router.post("/ai/diagram-copy/stream")
async def generate_diagram_ai_copy_stream(
    request: Request,
    body: DiagramCopyBody,
    current_user: User = Depends(get_current_user),
):
    """SSE stream: phase + incremental fields + done for diagram AI copy."""
    diagram_text = await _prepare_diagram_copy_text_async(
        request=request,
        body=body,
        current_user=current_user,
    )
    return StreamingResponse(
        _stream_diagram_copy_events(
            http_request=request,
            diagram_text=diagram_text,
            title=body.title,
            subject=body.subject,
            grade=body.grade,
            diagram_type=body.diagram_type,
            user_id=getattr(current_user, "id", None),
            organization_id=getattr(current_user, "organization_id", None),
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/ai/diagram-copy/images")
async def generate_diagram_ai_copy_from_images(
    request: Request,
    title: str = Form(""),
    subject: str = Form(""),
    grade: str = Form(""),
    diagram_type: str = Form(""),
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    """OCR gallery images (Qwen vision) then draft intro / classroom application."""
    diagram_text = await _prepare_diagram_copy_images_async(
        request=request,
        files=files,
        current_user=current_user,
    )
    try:
        fields = await generate_diagram_case_copy(
            diagram_text=diagram_text,
            title=title,
            subject=subject,
            grade=grade,
            diagram_type=diagram_type,
            user_id=getattr(current_user, "id", None),
            organization_id=getattr(current_user, "organization_id", None),
            endpoint_path=_DIAGRAM_IMAGES_ENDPOINT_PATH,
        )
    except (
        LLMRateLimitError,
        LLMTimeoutError,
        LLMAccessDeniedError,
        LLMContentFilterError,
        LLMProviderError,
        *LLM_PIPELINE_ERRORS,
    ) as exc:
        raise _map_llm_http(exc) from exc

    return {
        "description": fields["description"],
        "classroom_application": fields["classroom_application"],
        "model": "qwen3.7-flash",
    }


@router.post("/ai/diagram-copy/images/stream")
async def generate_diagram_ai_copy_from_images_stream(
    request: Request,
    title: str = Form(""),
    subject: str = Form(""),
    grade: str = Form(""),
    diagram_type: str = Form(""),
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    """SSE stream for gallery-image OCR → diagram AI copy."""
    diagram_text = await _prepare_diagram_copy_images_async(
        request=request,
        files=files,
        current_user=current_user,
    )
    return StreamingResponse(
        _stream_diagram_copy_events(
            http_request=request,
            diagram_text=diagram_text,
            title=title,
            subject=subject,
            grade=grade,
            diagram_type=diagram_type,
            user_id=getattr(current_user, "id", None),
            organization_id=getattr(current_user, "organization_id", None),
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
