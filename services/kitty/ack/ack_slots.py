"""Slot extraction for Kitty acknowledgment templates."""

from __future__ import annotations

from typing import Any, Dict, Optional


def enrich_ack_session_context(
    session_context: Optional[Dict[str, Any]],
    voice_session: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge voice-session fields needed for acknowledgment templates."""
    merged: Dict[str, Any] = dict(session_context) if isinstance(session_context, dict) else {}
    if not isinstance(voice_session, dict):
        return merged
    history = voice_session.get("conversation_history")
    if isinstance(history, list):
        merged["conversation_history"] = history
    diagram_type = voice_session.get("diagram_type")
    if diagram_type and not merged.get("diagram_type"):
        merged["diagram_type"] = str(diagram_type)
    return merged


def _clip_label(value: Any, *, limit: int = 48) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def _branch_label_from_session(
    session_context: Optional[Dict[str, Any]],
    branch_index: int,
) -> str:
    if not isinstance(session_context, dict):
        return ""
    diagram_data = session_context.get("diagram_data")
    if not isinstance(diagram_data, dict):
        return ""
    children = diagram_data.get("children")
    if not isinstance(children, list) or branch_index < 0 or branch_index >= len(children):
        return ""
    branch = children[branch_index]
    if not isinstance(branch, dict):
        return ""
    for key in ("text", "label", "name"):
        raw = branch.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


def slots_from_command(
    action: str,
    command: Dict[str, Any],
    session_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Build template slots from a routed tool command."""
    slots: Dict[str, str] = {}

    target = command.get("target")
    if isinstance(target, str) and target.strip():
        slots["target"] = _clip_label(target)

    new_text = command.get("new_text")
    if isinstance(new_text, str) and new_text.strip():
        slots["new_text"] = _clip_label(new_text)
    elif "target" in slots and action in ("update_node", "update_center"):
        slots["new_text"] = slots["target"]

    ident = command.get("node_identifier")
    if isinstance(ident, str) and ident.strip():
        slots["old_text"] = _clip_label(ident)
    elif ident is not None and str(ident).strip():
        slots["old_text"] = _clip_label(ident)

    branch_index_raw = command.get("branch_index")
    if branch_index_raw is not None:
        try:
            branch_index = int(branch_index_raw)
            branch_label = _branch_label_from_session(session_context, branch_index)
            if branch_label:
                slots["branch_label"] = _clip_label(branch_label)
        except (TypeError, ValueError):
            pass

    for key in ("left", "right", "title", "event", "whole", "dimension"):
        raw = command.get(key)
        if isinstance(raw, str) and raw.strip():
            slots[key] = _clip_label(raw)

    return slots


def slots_from_diagram_update(action: str, updates: Any) -> Dict[str, str]:
    """Build template slots from a diagram_update WS payload."""
    slots: Dict[str, str] = {}
    act = str(action or "").strip()

    if act == "update_center" and isinstance(updates, dict):
        for key in ("new_text", "title", "event", "whole", "dimension", "left", "right"):
            raw = updates.get(key)
            if isinstance(raw, str) and raw.strip():
                slots["new_text"] = _clip_label(raw)
                if key in ("left", "right"):
                    slots[key] = _clip_label(raw)
                break
        return slots

    if act in ("update_nodes", "add_nodes", "remove_nodes") and isinstance(updates, list):
        first = updates[0] if updates else None
        if isinstance(first, dict):
            new_text = first.get("new_text") or first.get("text")
            if isinstance(new_text, str) and new_text.strip():
                slots["new_text"] = _clip_label(new_text)
                slots["target"] = slots["new_text"]
            node_id = first.get("node_id")
            if isinstance(node_id, str) and node_id.strip():
                slots["node_id"] = _clip_label(node_id)
        return slots

    if isinstance(updates, dict):
        for key in ("text", "new_text", "target", "label", "topic"):
            raw = updates.get(key)
            if isinstance(raw, str) and raw.strip():
                slots["target"] = _clip_label(raw)
                slots["new_text"] = slots["target"]
                break

    return slots


def echo_hint_from_slots(slots: Dict[str, str], *, lang: str) -> str:
    """Short phrase for low-confidence clarify templates."""
    if slots.get("old_text") and slots.get("new_text"):
        if lang == "en":
            return f'change "{slots["old_text"]}" to "{slots["new_text"]}"'
        return f"把「{slots['old_text']}」改为「{slots['new_text']}」"
    if slots.get("target"):
        if lang == "en":
            return f'work on "{slots["target"]}"'
        return f"处理「{slots['target']}」"
    if slots.get("new_text"):
        if lang == "en":
            return f'update to "{slots["new_text"]}"'
        return f"改成「{slots['new_text']}」"
    return ""
