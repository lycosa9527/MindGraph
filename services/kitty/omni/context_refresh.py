"""Debounced Omni context refresh (delta updates, not full instruction rebuild)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from services.kitty.context.messaging import build_voice_instructions
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.session.ops import get_session_omni_client

logger = logging.getLogger(__name__)

_DEBOUNCE_SEC = 0.3
_pending: Dict[str, asyncio.Task] = {}
_delta_notes: Dict[str, str] = {}
_full_refresh_reasons = frozenset(
    {"session_start", "diagram_type_change", "pedagogical_review", "context_update", "library_refresh"}
)


async def schedule_omni_context_refresh(
    voice_session_id: str,
    *,
    reason: str = "diagram_mutation",
    delta: Optional[str] = None,
) -> None:
    """Debounce Omni instruction/context updates (~300ms)."""
    if reason in _full_refresh_reasons:
        await _apply_omni_refresh(voice_session_id, reason=reason, delta=None)
        return

    if delta:
        prev = _delta_notes.get(voice_session_id, "")
        _delta_notes[voice_session_id] = f"{prev}\n{delta}".strip() if prev else delta

    existing = _pending.get(voice_session_id)
    if existing is not None and not existing.done():
        return

    async def _debounced() -> None:
        try:
            await asyncio.sleep(_DEBOUNCE_SEC)
            note = _delta_notes.pop(voice_session_id, None)
            await _apply_omni_refresh(voice_session_id, reason=reason, delta=note)
        finally:
            _pending.pop(voice_session_id, None)

    _pending[voice_session_id] = asyncio.create_task(_debounced())


async def _apply_omni_refresh(
    voice_session_id: str,
    *,
    reason: str,
    delta: Optional[str],
) -> None:
    session = voice_sessions.get(voice_session_id)
    if not session:
        return

    omni_client = get_session_omni_client(voice_session_id)
    if not omni_client:
        return

    ctx = session.get("context") or {}
    diagram_type = session.get("diagram_type") or ctx.get("diagram_type") or "circle_map"
    active_panel = session.get("active_panel") or ctx.get("active_panel") or "none"
    diagram_data = dict(ctx.get("diagram_data") or {})
    diagram_data["diagram_type"] = diagram_type

    updated_context: Dict[str, Any] = {
        "diagram_type": diagram_type,
        "active_panel": active_panel,
        "conversation_history": session.get("conversation_history", []),
        "selected_nodes": ctx.get("selected_nodes", []),
        "diagram_data": diagram_data,
        "diagram_library_id": ctx.get("diagram_library_id"),
        "diagram_display_title": ctx.get("diagram_display_title"),
    }

    diagram_review_deep = reason == "pedagogical_review"

    if delta and reason == "diagram_mutation":
        children = diagram_data.get("children", [])
        child_count = len(children) if isinstance(children, list) else 0
        center_text = ""
        center = diagram_data.get("center")
        if isinstance(center, dict):
            center_text = str(center.get("text") or "")
        elif isinstance(diagram_data.get("topic"), str):
            center_text = diagram_data["topic"]
        append_note = f"\n\n[Diagram update] {delta}. Current topic: {center_text or '(empty)'}. Nodes: {child_count}."
        base_instructions = build_voice_instructions(updated_context)
        new_instructions = f"{base_instructions}{append_note}"
    else:
        new_instructions = build_voice_instructions(
            updated_context,
            diagram_review_deep=diagram_review_deep,
        )

    try:
        await omni_client.update_instructions(new_instructions)
        child_count = len(diagram_data.get("children", [])) if isinstance(diagram_data.get("children"), list) else 0
        kitty_wf_log(
            "omni_refresh",
            f"reason={reason} nodes={child_count} delta={bool(delta)}",
            voice_session_id=voice_session_id,
        )
    except (RuntimeError, ConnectionError, AttributeError) as exc:
        logger.debug("Omni context refresh skipped for %s: %s", voice_session_id, exc)
        kitty_wf_log(
            "omni_refresh_fail",
            str(exc)[:120],
            voice_session_id=voice_session_id,
        )


def cancel_pending_omni_refresh(voice_session_id: str) -> None:
    task = _pending.pop(voice_session_id, None)
    if task is not None and not task.done():
        task.cancel()
    _delta_notes.pop(voice_session_id, None)
