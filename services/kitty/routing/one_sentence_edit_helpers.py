"""Helpers for one-sentence edit routing (mode + mindmap detection).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# Client already toasted + chat-acked these; BE must not emit a second failure ack.
CLIENT_REPORTED_FAILURE_CODES = frozenset(
    {
        "verify_failed",
        "hub_persist_failed",
        "apply_noop",
        "hub_persist_timeout",
        "context_mutation_rejected",
    }
)


def is_mindmap_diagram_type(diagram_type: Any) -> bool:
    """True for mindmap / mind_map diagram types."""
    if not isinstance(diagram_type, str):
        return False
    norm = diagram_type.strip().lower()
    return norm in ("mindmap", "mind_map")


def is_one_sentence_edit_mode(
    session_context: Dict[str, Any],
    live_session: Optional[Dict[str, Any]],
) -> bool:
    """
    True when the one-sentence panel is in edit phase.

    Missing ``one_sentence_phase`` with ``active_panel == "one_sentence"``
    is treated as edit. Explicit ``create`` is never edit.
    """
    phase = session_context.get("one_sentence_phase")
    if phase == "edit":
        return True
    if phase == "create":
        return False
    panel = None
    if isinstance(live_session, dict):
        panel = live_session.get("active_panel")
    if panel is None:
        panel = session_context.get("active_panel")
    return panel == "one_sentence"


def should_use_verified_diagram_edit(
    session_context: Dict[str, Any],
    live_session: Optional[Dict[str, Any]],
    diagram_type: Any,
    *,
    is_text_message: bool,
) -> bool:
    """Typed mindmap structural ops use verified DiagramCommandBus."""
    del session_context
    del live_session
    return is_text_message and is_mindmap_diagram_type(diagram_type)
