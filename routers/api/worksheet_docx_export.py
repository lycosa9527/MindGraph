"""Export printable learning sheet as editable DOCX (diagram embedded as image)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response

from models.domain.auth import User
from services.diagram.worksheet_docx import (
    WorksheetDocxLabels,
    WorksheetDocxSpec,
    WorksheetLayout,
    build_worksheet_docx,
)
from services.utils.error_types import FILE_IO_ERRORS
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["export"])

_MAX_DIAGRAM_BYTES = 20 * 1024 * 1024
_SAFE_NAME = re.compile(r"[^\w\-.\u4e00-\u9fff]+", re.UNICODE)


def _as_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _sanitize_filename(name: str) -> str:
    cleaned = _SAFE_NAME.sub("-", name.strip())[:80].strip("-.")
    return cleaned or "worksheet"


def _content_disposition(filename: str) -> str:
    """HTTP headers are latin-1; use RFC 5987 for non-ASCII titles (e.g. 中文课题)."""
    ascii_raw = filename.encode("ascii", "ignore").decode("ascii")
    if ascii_raw.lower().endswith(".docx"):
        ascii_raw = ascii_raw[:-5]
    ascii_stem = _SAFE_NAME.sub("-", ascii_raw).strip("._- ")
    if ascii_stem.lower() in {"doc", "docx"}:
        ascii_stem = ""
    ascii_stem = ascii_stem or "worksheet"
    ascii_name = f"{ascii_stem}.docx"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def _parse_meta(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid worksheet metadata JSON",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Worksheet metadata must be an object",
        )
    return parsed


def _build_spec(meta: dict[str, Any]) -> WorksheetDocxSpec:
    layout_raw = str(meta.get("layout", "landscape")).strip().lower()
    layout: WorksheetLayout = "portrait" if layout_raw == "portrait" else "landscape"
    labels_raw = meta.get("labels")
    if not isinstance(labels_raw, dict):
        labels_raw = {}
    labels = WorksheetDocxLabels(
        name=str(labels_raw.get("name", "Name:")),
        class_name=str(labels_raw.get("className", labels_raw.get("class_name", "Class:"))),
        date=str(labels_raw.get("date", "Date:")),
        instruction_prefix=str(labels_raw.get("instructionPrefix", labels_raw.get("instruction_prefix", "Task:"))),
        default_instruction=str(
            labels_raw.get(
                "defaultInstruction",
                labels_raw.get("default_instruction", ""),
            )
        ),
    )
    return WorksheetDocxSpec(
        title=str(meta.get("title", "diagram")),
        layout=layout,
        show_topic=_as_bool(meta.get("showTopic", meta.get("show_topic")), True),
        show_name=_as_bool(meta.get("showName", meta.get("show_name")), True),
        show_class=_as_bool(meta.get("showClass", meta.get("show_class")), True),
        show_date=_as_bool(meta.get("showDate", meta.get("show_date")), True),
        show_instruction=_as_bool(meta.get("showInstruction", meta.get("show_instruction")), True),
        topic_text=str(meta.get("topicText", meta.get("topic_text", ""))),
        instruction_text=str(meta.get("instructionText", meta.get("instruction_text", ""))),
        diagram_offset_x=_as_float(meta.get("diagramOffsetX", meta.get("diagram_offset_x")), 0.0),
        diagram_offset_y=_as_float(meta.get("diagramOffsetY", meta.get("diagram_offset_y")), 0.0),
        diagram_scale=_as_float(meta.get("diagramScale", meta.get("diagram_scale")), 1.0),
        labels=labels,
    )


@router.post("/export_worksheet_docx")
async def export_worksheet_docx(
    meta: str = Form(...),
    diagram: UploadFile = File(...),
    _user: User = Depends(get_current_user),
) -> Response:
    """Build an editable DOCX learning sheet with the uploaded diagram image."""
    payload = _parse_meta(meta)
    spec = _build_spec(payload)

    content_type = (diagram.content_type or "").lower()
    if content_type and content_type not in {
        "image/png",
        "image/jpeg",
        "image/jpg",
        "application/octet-stream",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Diagram must be a PNG or JPEG image",
        )

    try:
        diagram_bytes = await diagram.read(_MAX_DIAGRAM_BYTES + 1)
    except FILE_IO_ERRORS as exc:
        logger.warning("Failed reading worksheet diagram upload: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read diagram image",
        ) from exc

    if not diagram_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Diagram image is empty",
        )
    if len(diagram_bytes) > _MAX_DIAGRAM_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Diagram image is too large",
        )

    try:
        docx_bytes = build_worksheet_docx(spec, diagram_bytes)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except FILE_IO_ERRORS as exc:
        logger.exception("Worksheet DOCX build failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to build DOCX",
        ) from exc

    filename = f"{_sanitize_filename(spec.title)}.docx"
    return Response(
        content=docx_bytes,
        media_type=("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        headers={
            "Content-Disposition": _content_disposition(filename),
        },
    )
