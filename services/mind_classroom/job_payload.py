"""Public JSON payloads for Mind Classroom jobs."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Request

from services.mind_classroom.job_match import spec_snapshot_node_ids
from services.mind_classroom.storage_keys import classroom_public_asset_url


def classroom_asset_url(request: Request, logical_key: str) -> str:
    """Same-origin classroom asset URL (JWT on GET)."""
    del request
    return classroom_public_asset_url(logical_key.lstrip("/"))


def slide_payload(row: Any, request: Request) -> dict[str, Any]:
    """Serialize one slide row."""
    image_url = None
    key = getattr(row, "cos_logical_key", None)
    if key:
        try:
            image_url = classroom_asset_url(request, str(key))
        except ValueError:
            image_url = None
    return {
        "id": row.id,
        "slide_index": row.slide_index,
        "title": row.title,
        "teacher_script": row.teacher_script,
        "focus_node_ids": row.focus_node_ids,
        "image_url": image_url,
        "size": row.size,
    }


def job_event_dict(row: Any) -> dict[str, Any]:
    """Serialize a job for SSE / Redis without a request object."""
    settings = row.settings if isinstance(row.settings, dict) else {}
    result = row.result_json if isinstance(row.result_json, dict) else None
    payload: dict[str, Any] = {
        "id": row.id,
        "status": row.status,
        "current_stage": row.current_stage,
        "progress": row.progress,
        "error_message": row.error_message,
        "diagram_id": row.diagram_id,
        "settings": settings,
        "spec_hash": getattr(row, "spec_hash", None),
        "spec_node_ids": spec_snapshot_node_ids(getattr(row, "spec_snapshot", None)),
        "result_json": result,
        "celery_task_id": row.celery_task_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    transcript_key = ""
    if isinstance(result, dict):
        transcript_key = str(result.get("transcript_key") or "").strip()
    if transcript_key:
        try:
            payload["transcript_url"] = classroom_public_asset_url(transcript_key.lstrip("/"))
        except ValueError:
            payload["transcript_url"] = None
    return payload


def job_payload(
    row: Any,
    request: Request,
    *,
    slides: Optional[list[Any]] = None,
) -> dict[str, Any]:
    """Serialize a job for detail GET."""
    payload = job_event_dict(row)
    if slides is not None:
        payload["slides"] = [slide_payload(slide, request) for slide in slides]
    return payload
