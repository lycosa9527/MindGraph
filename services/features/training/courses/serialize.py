"""Serialize training courses for API and Redis snapshots."""

from __future__ import annotations

from typing import Any, Optional

from models.domain.training import TrainingCourse, TrainingCourseAsset, TrainingCourseStep
from services.features.training.storage.keys import training_public_asset_url


def localized_text(value: Any, locale: str) -> str:
    """Read a bilingual JSON field."""
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    preferred = "zh" if locale.startswith("zh") else "en"
    fallback = "en" if preferred == "zh" else "zh"
    text = value.get(preferred) or value.get(fallback) or ""
    return str(text)


def asset_url(asset: Optional[TrainingCourseAsset]) -> Optional[str]:
    """App-relative URL for a stored asset."""
    if asset is None or not asset.logical_key:
        return None
    try:
        return training_public_asset_url(asset.logical_key)
    except ValueError:
        return None


def step_navigation_fields(step_type: str, payload: dict[str, Any]) -> tuple[str | None, bool]:
    """Default page_key / pull_users for legacy canvas steps."""
    raw_key = payload.get("page_key")
    page_key = str(raw_key).strip() if raw_key else None
    if not page_key and step_type == "canvas":
        page_key = "canvas"
    pull_users = payload.get("pull_users")
    if pull_users is None:
        pull_users = step_type == "canvas"
    return page_key, bool(pull_users)


def step_preview_url(
    step_type: str,
    asset: Optional[TrainingCourseAsset],
    thumb: Optional[TrainingCourseAsset],
) -> Optional[str]:
    """Filmstrip preview: dedicated thumb, else the slide/video file."""
    preview = asset_url(thumb)
    if preview is None and step_type in {"slide", "video"}:
        return asset_url(asset)
    return preview


def serialize_step(
    step: TrainingCourseStep,
    assets_by_id: dict[str, TrainingCourseAsset],
) -> dict[str, Any]:
    """One step for builder GET or play snapshot."""
    payload = dict(step.payload or {})
    asset_id = payload.get("asset_id")
    asset = assets_by_id.get(str(asset_id)) if asset_id else None
    thumb_id = payload.get("thumb_id")
    thumb = assets_by_id.get(str(thumb_id)) if thumb_id else None
    page_key, pull_users = step_navigation_fields(step.step_type, payload)
    return {
        "id": step.id,
        "position": step.position,
        "type": step.step_type,
        "diagram_type": payload.get("diagram_type"),
        "topic_options": payload.get("topic_options") or [],
        "asset_id": asset_id,
        "asset_url": asset_url(asset),
        "thumb_id": thumb_id,
        "thumb_url": step_preview_url(step.step_type, asset, thumb),
        "overlays": payload.get("overlays") or [],
        "page_key": page_key,
        "pull_users": bool(pull_users),
        "mindmap_canvas_mode": payload.get("mindmap_canvas_mode"),
        "modal_key": payload.get("modal_key"),
        "focus_key": payload.get("focus_key"),
        "notes": str(payload.get("notes") or ""),
        "mark_step": payload.get("mark_step") or 1,
        "mark_steps": payload.get("mark_steps") or 1,
    }


def serialize_course(
    course: TrainingCourse,
    *,
    locale: str = "zh",
    include_steps: bool = True,
) -> dict[str, Any]:
    """Course card or editor payload."""
    assets_by_id = {asset.id: asset for asset in course.assets}
    cover = None
    if course.cover_asset_id:
        cover = assets_by_id.get(course.cover_asset_id)
    body: dict[str, Any] = {
        "id": course.id,
        "title": localized_text(course.title, locale),
        "title_i18n": course.title or {},
        "description": localized_text(course.description, locale),
        "description_i18n": course.description or {},
        "status": course.status,
        "is_system": bool(course.is_system),
        "cover_url": asset_url(cover),
        "updated_at": course.updated_at.isoformat() if course.updated_at else None,
    }
    if include_steps:
        body["steps"] = [serialize_step(step, assets_by_id) for step in course.steps]
    else:
        first = course.steps[0] if course.steps else None
        body["first_step"] = serialize_step(first, assets_by_id) if first else None
    return body


def snapshot_step_payload(step_body: dict[str, Any]) -> dict[str, Any]:
    """Compact step stored on the Redis session."""
    return {
        "type": step_body.get("type"),
        "diagram_type": step_body.get("diagram_type"),
        "topic_options": step_body.get("topic_options") or [],
        "asset_url": step_body.get("asset_url"),
        "overlays": step_body.get("overlays") or [],
        "page_key": step_body.get("page_key"),
        "pull_users": bool(step_body.get("pull_users")),
        "mindmap_canvas_mode": step_body.get("mindmap_canvas_mode"),
        "modal_key": step_body.get("modal_key"),
        "focus_key": step_body.get("focus_key"),
        "mark_step": step_body.get("mark_step") or 1,
        "mark_steps": step_body.get("mark_steps") or 1,
    }
