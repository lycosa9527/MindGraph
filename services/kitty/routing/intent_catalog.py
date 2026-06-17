"""
Kitty voice intent → transport / hub routing catalog.

Used for LLMOps manifesting and contract tests. ``channel`` values:
- ``hub_patch`` — prefer ``apply_diagram_spec_mutation`` / ``live_spec`` (may also WS notify phone).
- ``ws_action`` — ``safe_websocket_send`` action / diagram_update to active client only.
- ``omni`` primary path (plus optional WS).
- ``desktop_queue`` — Redis FIFO for desktop SPA navigation (not diagram mutation).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, TypedDict

Channel = Literal["hub_patch", "ws_action", "omni", "desktop_queue", "mixed"]


class IntentRow(TypedDict):
    """One classifiable ``command[\"action\"]`` or special flow."""

    name: str
    kind: Literal["diagram", "ui", "flow"]
    channel: Channel
    hub_op: str | None
    notes: str


KITTY_INTENT_ROWS: List[IntentRow] = [
    {
        "name": "update_center",
        "kind": "diagram",
        "channel": "hub_patch",
        "hub_op": "patch_context",
        "notes": "Center/title/topic fields vary by ``diagram_type`` (e.g. double_bubble left/right).",
    },
    {
        "name": "update_node",
        "kind": "diagram",
        "channel": "hub_patch",
        "hub_op": "patch_context",
        "notes": "``node_index``, ``node_id``, ``node_identifier``; diagram-specific keys on command.",
    },
    {
        "name": "add_node",
        "kind": "diagram",
        "channel": "hub_patch",
        "hub_op": "patch_context",
        "notes": "Palette-open (no target) is WS-only UX; no hub sync.",
    },
    {
        "name": "delete_node",
        "kind": "diagram",
        "channel": "hub_patch",
        "hub_op": "patch_context",
        "notes": "Structured deletes for tree/brace/flow etc. share same intent name.",
    },
    {
        "name": "open_thinkguide",
        "kind": "ui",
        "channel": "ws_action",
        "hub_op": None,
        "notes": "Mapped to open MindMate panel.",
    },
    {
        "name": "close_thinkguide",
        "kind": "ui",
        "channel": "ws_action",
        "hub_op": None,
        "notes": "Mapped to close MindMate.",
    },
    {
        "name": "open_node_palette",
        "kind": "ui",
        "channel": "ws_action",
        "hub_op": None,
        "notes": "",
    },
    {
        "name": "close_node_palette",
        "kind": "ui",
        "channel": "ws_action",
        "hub_op": None,
        "notes": "",
    },
    {
        "name": "open_mindmate",
        "kind": "ui",
        "channel": "ws_action",
        "hub_op": None,
        "notes": "",
    },
    {
        "name": "close_mindmate",
        "kind": "ui",
        "channel": "ws_action",
        "hub_op": None,
        "notes": "",
    },
    {
        "name": "close_all_panels",
        "kind": "ui",
        "channel": "ws_action",
        "hub_op": None,
        "notes": "",
    },
    {
        "name": "select_node",
        "kind": "ui",
        "channel": "mixed",
        "hub_op": "patch_context",
        "notes": "WS today; ``selected_nodes`` good fit for hub ``patch_context``.",
    },
    {
        "name": "explain_node",
        "kind": "ui",
        "channel": "ws_action",
        "hub_op": None,
        "notes": "Omni explanation via WS action params.",
    },
    {
        "name": "ask_thinkguide",
        "kind": "ui",
        "channel": "ws_action",
        "hub_op": None,
        "notes": "Forwarded as ask_mindmate.",
    },
    {
        "name": "ask_mindmate",
        "kind": "ui",
        "channel": "ws_action",
        "hub_op": None,
        "notes": "",
    },
    {
        "name": "auto_complete",
        "kind": "ui",
        "channel": "ws_action",
        "hub_op": None,
        "notes": "Optional Omni ack.",
    },
    {
        "name": "start_inline_recommendations",
        "kind": "ui",
        "channel": "ws_action",
        "hub_op": None,
        "notes": "",
    },
    {
        "name": "help",
        "kind": "ui",
        "channel": "ws_action",
        "hub_op": None,
        "notes": "",
    },
    {
        "name": "open_desktop_canvas",
        "kind": "ui",
        "channel": "desktop_queue",
        "hub_op": None,
        "notes": "``enqueue_kitty_desktop_action`` — navigation / open_canvas only.",
    },
    {
        "name": "none",
        "kind": "flow",
        "channel": "omni",
        "hub_op": None,
        "notes": "Conversational; no structured action.",
    },
]

KITTY_SPECIAL_FLOWS: List[Dict[str, Any]] = [
    {
        "name": "paragraph_path",
        "channel": "mixed",
        "hub_op": "replace_context or patch_context",
        "notes": "Qwen Plus extraction; large specs may use replace or batched patch (bridge policy).",
    },
    {
        "name": "pedagogical_review",
        "channel": "ws_action",
        "hub_op": None,
        "notes": "``diagram_review_annotation`` WS; diagram may be unchanged.",
    },
    {
        "name": "append_image_vision",
        "channel": "omni",
        "hub_op": "optional patch_context",
        "notes": "WS ``append_image`` → Omni; transcript may route paragraph/Qwen; hub if canvas updates.",
    },
]


def voice_intent_rows_as_json() -> List[Dict[str, Any]]:
    """Return plain dicts for HTTP manifest / admin JSON."""
    return [dict(r) for r in KITTY_INTENT_ROWS]


def special_flows_as_json() -> List[Dict[str, Any]]:
    """Special flows as json."""
    return [dict(s) for s in KITTY_SPECIAL_FLOWS]
