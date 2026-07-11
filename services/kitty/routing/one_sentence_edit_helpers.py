"""Helpers for one-sentence edit routing (detection + follow-up peeling).

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
    """Mindmap + one-sentence edit + typed text → verified DiagramCommandBus."""
    return (
        is_text_message
        and is_one_sentence_edit_mode(session_context, live_session)
        and is_mindmap_diagram_type(diagram_type)
    )


def normalize_follow_up_actions(command: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Return validated follow-up command dicts from a primary command."""
    raw = command.get("follow_up_actions")
    if not isinstance(raw, list):
        return []
    out: list[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action") or "").strip()
        if not action or action == "none":
            continue
        out.append(dict(item))
    return out


def split_parallel_auto_complete_follow_ups(
    primary_action: str,
    follow_ups: list[Dict[str, Any]],
    *,
    primary_command: Dict[str, Any] | None = None,
) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    """
    Peel auto-complete follow-ups that can start without waiting for verify.

    - update_center → whole-diagram auto_complete must wait until the topic
      mutation is verified (otherwise Hub revision races → stale_revision).
    - add_node → whole-diagram auto_complete (topic from canvas later)

    Branch auto-complete must wait for the verified ``created_node_id`` (see
    ``maybe_start_background_branch_autocomplete``). Explicit
    ``auto_complete_branch`` follow-ups on ``add_node`` are dropped (handled
    post-verify); on ``update_node`` they stay in remaining.

    Returns (parallel_follow_ups, remaining_follow_ups).
    """
    primary = str(primary_action or "")
    parallel: list[Dict[str, Any]] = []
    remaining: list[Dict[str, Any]] = []
    primary_target = ""
    primary_node_id = ""
    if isinstance(primary_command, dict):
        raw_target = primary_command.get("target")
        if isinstance(raw_target, str) and raw_target.strip():
            primary_target = raw_target.strip()
        raw_nid = primary_command.get("node_id")
        if isinstance(raw_nid, str) and raw_nid.strip():
            primary_node_id = raw_nid.strip()
        if not primary_target:
            ident = primary_command.get("node_identifier")
            if isinstance(ident, str) and ident.strip():
                primary_target = ident.strip()

    for follow in follow_ups:
        follow_action = str(follow.get("action") or "").strip()
        if primary == "update_center" and follow_action == "auto_complete":
            # Topic must land on canvas + Hub before whole-map fill starts.
            remaining.append(dict(follow))
            continue
        if primary == "add_node" and follow_action == "auto_complete_branch":
            # Post-verify maybe_start_background_branch_autocomplete owns this.
            continue
        if primary == "update_node" and follow_action == "auto_complete_branch":
            item = dict(follow)
            if primary_target and not (isinstance(item.get("target"), str) and str(item.get("target")).strip()):
                item["target"] = primary_target
            if primary_node_id and not (isinstance(item.get("node_id"), str) and str(item.get("node_id")).strip()):
                item["node_id"] = primary_node_id
            remaining.append(item)
            continue
        if primary == "add_node" and follow_action == "auto_complete":
            # Whole-diagram fill after adding a branch — still safe with topic from canvas later
            parallel.append(dict(follow))
            continue
        remaining.append(dict(follow))
    return parallel, remaining
