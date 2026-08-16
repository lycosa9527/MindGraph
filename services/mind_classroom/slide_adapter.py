"""Adapt ZhiHui-style lesson frames to the shared lecture step schema."""

from __future__ import annotations

from typing import Any

from services.mind_classroom.focus import resolve_frame_focus_node_ids
from services.mind_classroom.outline import MindMapOutline
from services.mind_classroom.steps import normalize_steps
from services.mind_classroom.storage_keys import classroom_public_asset_url


def _frame_kind(batch_role: str, frame_role: str, index: int, total: int) -> str:
    role = (frame_role or "").strip().lower()
    batch = (batch_role or "").strip().lower()
    if role == "topic_overview" or (batch == "open" and index == 0):
        return "overview"
    if role == "close" or batch == "close" or index == total - 1:
        return "closing"
    return "branch"


def frames_to_steps(
    plan: dict[str, Any],
    *,
    outline: MindMapOutline,
    spec: dict[str, Any],
    slides: list[Any],
    max_steps: int,
) -> list[dict[str, Any]]:
    """Build shared steps from a lesson plan plus persisted slides."""
    raw_frames: list[dict[str, Any]] = []
    for batch in plan.get("batches") or []:
        if not isinstance(batch, dict):
            continue
        batch_role = str(batch.get("batch_role") or "")
        frames = batch.get("frames") or []
        if not isinstance(frames, list):
            continue
        for frame in frames:
            if isinstance(frame, dict):
                raw_frames.append({**frame, "_batch_role": batch_role})

    slide_by_index = {}
    for slide in slides:
        index = getattr(slide, "slide_index", None)
        if index is not None:
            slide_by_index[int(index)] = slide

    total = max(len(raw_frames), len(slide_by_index))
    raw_steps: list[dict[str, Any]] = []
    for index in range(total):
        frame = raw_frames[index] if index < len(raw_frames) else {}
        slide = slide_by_index.get(index)
        batch_role = str(frame.get("_batch_role") or "")
        frame_role = str(frame.get("frame_role") or "").strip().lower()
        title = str(frame.get("title") or getattr(slide, "title", "") or "").strip()
        caption = str(
            frame.get("teacher_script") or getattr(slide, "teacher_script", "") or frame.get("learning_point") or ""
        ).strip()
        focus_child = str(frame.get("focus_child") or "").strip()
        if focus_child and frame_role != "branch_intro":
            focus_ids = [focus_child]
        else:
            focus_ids = resolve_frame_focus_node_ids(
                outline,
                slide_index=index,
                batch_role=batch_role,
                focus_branch=frame.get("focus_branch"),
            )
        if slide is not None and getattr(slide, "focus_node_ids", None):
            stored = slide.focus_node_ids
            if isinstance(stored, list) and stored:
                focus_ids = [str(item) for item in stored if str(item).strip()]
        image_url = None
        if slide is not None and getattr(slide, "cos_logical_key", None):
            try:
                image_url = classroom_public_asset_url(slide.cos_logical_key)
            except ValueError:
                image_url = None
        bullets = []
        subjects = frame.get("visual_subjects")
        if isinstance(subjects, list):
            bullets = [str(item).strip() for item in subjects if str(item).strip()][:6]
        branch_id = ""
        if focus_ids:
            branch_id = focus_ids[0]
        raw_steps.append(
            {
                "id": f"slide-{index}",
                "kind": _frame_kind(batch_role, frame_role, index, total),
                "title": title,
                "caption": caption,
                "bullets": bullets,
                "focus_node_ids": focus_ids,
                "branch_node_id": branch_id,
                "image_url": image_url,
            }
        )
    return normalize_steps(raw_steps, spec=spec, max_steps=max_steps)
