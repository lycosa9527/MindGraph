"""Resolve lesson-frame focus to mind-map node ids for canvas sync."""

from __future__ import annotations

from typing import Any

from services.mind_classroom.outline import MindMapOutline


def resolve_frame_focus_node_ids(
    outline: MindMapOutline,
    *,
    slide_index: int,
    batch_role: str = "",
    focus_branch: Any = None,
) -> list[str]:
    """
    Map a planner frame to canvas focus node ids.

    - Slide 0 (topic overview) always returns ``[]`` → fit whole diagram.
    - Empty / open-overview frames also return ``[]``.
    - Branch frames return the matched first-level branch id (FE expands children).
    """
    if slide_index <= 0:
        return []

    hint = str(focus_branch or "").strip()
    role = (batch_role or "").strip().lower()
    if not hint:
        # No branch cue — keep whole-map framing (open/close or ambiguous).
        return []

    hint_lower = hint.lower()
    for branch in outline.branches:
        branch_id = (branch.id or "").strip()
        text = (branch.text or "").strip()
        if branch_id and (branch_id == hint or branch_id.lower() == hint_lower):
            return [branch_id]
        if text and (text == hint or text.lower() == hint_lower):
            return [branch_id] if branch_id else []

    for branch in outline.branches:
        branch_id = (branch.id or "").strip()
        text = (branch.text or "").strip()
        if not text:
            continue
        text_lower = text.lower()
        if hint_lower in text_lower or text_lower in hint_lower:
            return [branch_id] if branch_id else []

    # Leave raw hint for frontend text→node resolution.
    if role == "open":
        return []
    return [hint]
