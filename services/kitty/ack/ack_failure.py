"""Action- and error-code-aware failure acknowledgments for Kitty node edits.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.kitty.ack.ack_action_resolve import (
    classify_add_node_variant,
    classify_delete_node_variant,
)
from services.kitty.ack.ack_library import render_ack
from services.kitty.ack.ack_slots import slots_from_command

# Infrastructure / transport failures — prefer these over action-variant copy.
_CODE_FAILURE_KEYS: Dict[str, str] = {
    "busy_llm_generating": "diagram.failed.busy_llm",
    "access_denied": "diagram.failed.access_denied",
    "stale_revision": "diagram.failed.stale_revision",
    "ack_timeout": "diagram.failed.timeout",
    "hub_persist_failed": "diagram.failed.persist",
    "hub_persist_timeout": "diagram.failed.persist",
    "context_mutation_rejected": "diagram.failed.persist",
    "no_owner": "diagram.failed.no_owner",
    "compensate_failed": "diagram.failed.compensate",
}


def resolve_failure_ack_key(
    action: str,
    command: Dict[str, Any],
    session_context: Optional[Dict[str, Any]],
    slots: Dict[str, str],
    *,
    error_code: Optional[str] = None,
) -> str:
    """Pick failure template key from error code, then action variant."""
    code = str(error_code or "").strip()
    if code in _CODE_FAILURE_KEYS:
        return _CODE_FAILURE_KEYS[code]

    act = str(action or "").strip()
    if act == "add_node":
        variant = classify_add_node_variant(command, session_context)
        if variant == "branch":
            return "diagram.add_branch.failed"
        if variant == "child":
            if slots.get("branch_label"):
                return "diagram.add_child.branch.failed"
            return "diagram.add_child.failed"
        return "diagram.add_node.failed"
    if act == "delete_node":
        variant = classify_delete_node_variant(command, session_context)
        if variant == "branch":
            return "diagram.delete_branch.failed"
        if variant == "child":
            if slots.get("branch_label"):
                return "diagram.delete_child.branch.failed"
            return "diagram.delete_child.failed"
        return "diagram.delete_node.failed"
    if act == "update_node":
        if slots.get("old_text") and slots.get("new_text"):
            return "diagram.update_node.failed"
        return "diagram.update_node.failed_no_old"
    if act == "update_center":
        if slots.get("left") and slots.get("right"):
            return "diagram.update_center.double_bubble.failed"
        return "diagram.update_center.failed"
    return "diagram.execute_failed"


def render_failure_ack_for_command(
    action: str,
    command: Dict[str, Any],
    session_context: Optional[Dict[str, Any]] = None,
    *,
    error_code: Optional[str] = None,
    lang: str = "zh",
) -> str:
    """Render a user-facing failure ack for a routed diagram command."""
    act = str(action or "").strip()
    slots = slots_from_command(act, command, session_context)
    key = resolve_failure_ack_key(
        act,
        command,
        session_context,
        slots,
        error_code=error_code,
    )
    return render_ack(key, slots, lang=lang)
