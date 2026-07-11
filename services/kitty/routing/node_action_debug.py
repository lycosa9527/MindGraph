"""Structured debug logging for NodeActionAgent tuning.

Enable verbose ``kitty.node_action`` DEBUG lines with ``KITTY_NODE_ACTION_DEBUG=1``
(default on). Set ``KITTY_NODE_ACTION_DEBUG=0`` to silence module debug output;
workflow one-liners still emit via ``kitty_wf_log`` when ``KITTY_WORKFLOW_TRACE``
is enabled.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.routing.diagram_agent_context import (
    build_diagram_agent_payload,
    diagram_agent_payload_stats,
)
from services.kitty.routing.node_action_library import (
    extract_branch_labels,
    extract_mindmap_topic,
)

_LOGGER = logging.getLogger("kitty.node_action")
_TEXT_CLIP = 120
_LABEL_CLIP = 48


def node_action_debug_enabled() -> bool:
    """On by default; set ``KITTY_NODE_ACTION_DEBUG=0`` to disable verbose debug."""
    raw = os.environ.get("KITTY_NODE_ACTION_DEBUG", "")
    if not raw.strip():
        return True
    return raw.strip().lower() not in ("0", "false", "no", "off")


def clip_node_action_text(text: str, limit: int = _TEXT_CLIP) -> str:
    """Single-line clip for log fields."""
    cleaned = " ".join(str(text or "").split()).strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 1]}…"


def build_diagram_snapshot_meta(
    session_context: Optional[Dict[str, Any]],
    *,
    diagram_type: str,
) -> Dict[str, Any]:
    """Compact diagram snapshot dict for debug / workflow extra fields."""
    ctx = session_context if isinstance(session_context, dict) else {}
    payload = build_diagram_agent_payload(ctx, diagram_type=diagram_type)
    stats = diagram_agent_payload_stats(payload)
    branches = extract_branch_labels(ctx.get("diagram_data") or {})
    selected_nodes = ctx.get("selected_nodes")
    selected_count = len(selected_nodes) if isinstance(selected_nodes, list) else 0
    topic = stats.get("topic") or extract_mindmap_topic(ctx.get("diagram_data") or {})
    return {
        "diagram_type": diagram_type,
        "topic": clip_node_action_text(str(topic), _LABEL_CLIP) if topic else "",
        "node_count": stats.get("node_count", 0),
        "branch_count": len(branches),
        "branches": [clip_node_action_text(b, _LABEL_CLIP) for b in branches[:8]],
        "selected_count": selected_count,
    }


def summarize_legacy_command(command: Optional[Dict[str, Any]]) -> str:
    """One-line legacy command summary for logs."""
    if not isinstance(command, dict):
        return "—"
    action = str(command.get("action") or "").strip() or "?"
    parts = [f"action={action}"]
    confidence = command.get("confidence")
    if isinstance(confidence, (int, float)):
        parts.append(f"conf={confidence:.2f}")
    for key in ("target", "node_identifier", "node_id", "new_text", "question"):
        raw = command.get(key)
        if isinstance(raw, str) and raw.strip():
            parts.append(f"{key}={clip_node_action_text(raw.strip(), _LABEL_CLIP)}")
    options = command.get("options")
    if isinstance(options, list) and options:
        parts.append(f"options={len(options)}")
    follow_ups = command.get("follow_up_actions")
    if isinstance(follow_ups, list) and follow_ups:
        follow_names = [str(item.get("action") or "?") for item in follow_ups if isinstance(item, dict)]
        parts.append(f"follow_ups={'+'.join(follow_names) or len(follow_ups)}")
    return " ".join(parts)


def log_node_action_debug(
    event: str,
    *,
    voice_session_id: Optional[str] = None,
    detail: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Verbose module debug (``kitty.node_action`` logger)."""
    if not node_action_debug_enabled():
        return
    clipped = clip_node_action_text(detail) if detail else ""
    if extra:
        if clipped:
            _LOGGER.debug("NODE_ACTION %s | %s | extra=%s", event, clipped, extra)
        else:
            _LOGGER.debug("NODE_ACTION %s | extra=%s", event, extra)
    elif clipped:
        _LOGGER.debug(
            "NODE_ACTION %s | sid=%s | %s",
            event,
            voice_session_id or "—",
            clipped,
        )
    else:
        _LOGGER.debug("NODE_ACTION %s | sid=%s", event, voice_session_id or "—")


def log_node_action_wf(
    event: str,
    *,
    voice_session_id: Optional[str] = None,
    detail: str = "",
    action: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Pipeline-visible one-liner via ``kitty_wf_log`` (stage=node_action)."""
    clipped = clip_node_action_text(detail) if detail else event
    kitty_wf_log(
        "node_action",
        f"{event} {clipped}".strip(),
        voice_session_id=voice_session_id,
        action=action,
        extra=extra,
    )


def log_node_action(
    event: str,
    *,
    voice_session_id: Optional[str] = None,
    detail: str = "",
    action: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    workflow: bool = True,
) -> None:
    """Emit debug log and optional workflow trace for a node-action step."""
    log_node_action_debug(
        event,
        voice_session_id=voice_session_id,
        detail=detail,
        extra=extra,
    )
    if workflow:
        log_node_action_wf(
            event,
            voice_session_id=voice_session_id,
            detail=detail,
            action=action,
            extra=extra,
        )
