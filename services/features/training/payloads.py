"""
Training follow DTO helpers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from services.features.training.courses.constants import PAGE_KEYS

ACTIVITY_PAGE_KEYS = PAGE_KEYS | frozenset({"slide", "video"})


def sanitize_activity_page_key(raw: Optional[str]) -> Optional[str]:
    """Keep known app pages plus live slide/video overlays."""
    if raw is None:
        return None
    text = str(raw).strip()
    if text in ACTIVITY_PAGE_KEYS:
        return text
    return None


class TopicOption(BaseModel):
    """Instructor-authored topic chip."""

    id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=80)
    item_a: Optional[str] = Field(default=None, max_length=80)
    item_b: Optional[str] = Field(default=None, max_length=80)
    prompt: Optional[str] = Field(default=None, max_length=200)


class StartSessionBody(BaseModel):
    """Start a training session."""

    org_id: int
    confirm_teacher_total: int = Field(ge=0)


class NavigateBody(BaseModel):
    """Steer the org to a diagram type."""

    diagram_type: str = Field(min_length=1, max_length=40)


class OptionsBody(BaseModel):
    """Replace topic chips."""

    options: list[TopicOption] = Field(default_factory=list)


class ActivityBody(BaseModel):
    """Teacher activity heartbeat."""

    diagram_type: Optional[str] = Field(default=None, max_length=40)
    page_key: Optional[str] = Field(default=None, max_length=40)
    option_id: Optional[str] = Field(default=None, max_length=64)
    option_label: Optional[str] = Field(default=None, max_length=80)
    generate_state: str = Field(default="idle", max_length=20)


class PlayBody(BaseModel):
    """Bind a course and jump to the first step."""

    course_id: str = Field(min_length=36, max_length=36)


class StepBody(BaseModel):
    """Advance or jump to a course step."""

    index: Optional[int] = Field(default=None, ge=0)
    delta: Optional[int] = None


class FreeBody(BaseModel):
    """Release teachers on the current page, or pull them back."""

    free: bool = True


def _step_for_viewer(step: Any, *, include_notes: bool) -> Any:
    """Speaker notes stay on the instructor snapshot only."""
    if not isinstance(step, dict):
        return step
    if include_notes:
        return step
    redacted = dict(step)
    redacted.pop("notes", None)
    return redacted


def command_etag(session_id: Any, seq: Any, state: Any = None) -> str:
    """ETag is per session and viewed state so a virtual pause is not a 304."""
    token = str(session_id or "none")
    status = str(state or "none")
    return f'"{token}:{int(seq or 0)}:{status}"'


def snapshot_from_session(
    session: Optional[dict[str, Any]],
    *,
    viewer_user_id: Optional[int] = None,
) -> dict[str, Any]:
    """Public command snapshot. Notes are omitted unless the viewer is the instructor."""
    if session is None:
        return {
            "state": "none",
            "session_id": None,
            "org_id": None,
            "seq": 0,
            "diagram_type": None,
            "topic_options": [],
            "instructor_id": None,
            "instructor_name": None,
            "course_id": None,
            "step_index": 0,
            "step_count": 0,
            "step": None,
            "pull_users": True,
        }
    instructor_id = session.get("instructor_id")
    include_notes = (
        viewer_user_id is not None and instructor_id is not None and int(instructor_id) == int(viewer_user_id)
    )
    step = _step_for_viewer(session.get("step"), include_notes=include_notes)
    if include_notes and isinstance(step, dict) and session.get("instructor_notes"):
        step = dict(step)
        step["notes"] = str(session.get("instructor_notes") or "")
    return {
        "state": session.get("state"),
        "session_id": session.get("session_id"),
        "org_id": session.get("org_id"),
        "seq": int(session.get("seq") or 0),
        "diagram_type": session.get("diagram_type"),
        "topic_options": session.get("topic_options") or [],
        "instructor_id": instructor_id,
        "instructor_name": session.get("instructor_name"),
        "started_at": session.get("started_at"),
        "expires_at": session.get("expires_at"),
        "course_id": session.get("course_id"),
        "step_index": int(session.get("step_index") or 0),
        "step_count": int(session.get("step_count") or 0),
        "step": step,
        "pull_users": session.get("pull_users") is not False,
    }
