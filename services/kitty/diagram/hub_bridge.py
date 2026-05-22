"""Kitty voice diagram intents: hub patch envelope, preview helper, post-edit hub sync."""

from __future__ import annotations

import copy
from typing import Any, Dict, Optional

from services.agent_hub import get_mind_graph_agent_hub

from services.kitty.diagram.diagram_utils import get_diagram_prefix_map
from services.kitty.diagram.diagram_spec_sync import sync_diagram_data_to_spec_shape
from services.kitty.context.hub_context import apply_kitty_ws_context_patch
from services.kitty.session.runtime_state import logger
from services.kitty.session.ops import get_voice_session

DIAGRAM_VOICE_INTENTS = frozenset({"update_center", "update_node", "add_node", "delete_node"})


def build_patch_context_mutation_cmd(
    *,
    merged_context: Dict[str, Any],
    diagram_type: str,
    active_panel: str,
) -> Dict[str, Any]:
    """Build ``mutation_cmd`` for :meth:`MindGraphAgentHub.apply_diagram_spec_mutation`."""
    return {
        "op": "patch_context",
        "context": merged_context,
        "diagram_type": diagram_type,
        "active_panel": active_panel,
    }


def _preview_double_bubble_update_center(
    command: Dict[str, Any],
    diagram_data: Dict[str, Any],
) -> bool:
    left = command.get("left")
    right = command.get("right")
    if not (
        isinstance(left, str)
        and left.strip()
        and isinstance(right, str)
        and right.strip()
    ):
        return False
    diagram_data["left"] = left.strip()
    diagram_data["right"] = right.strip()
    return True


def _preview_update_center(command: Dict[str, Any], diagram_data: Dict[str, Any]) -> bool:
    new_text = command.get("target") or command.get("new_text")
    if not isinstance(new_text, str) or not new_text.strip():
        return False
    center = diagram_data.setdefault("center", {})
    if not isinstance(center, dict):
        diagram_data["center"] = {"text": new_text.strip()}
    else:
        center["text"] = new_text.strip()
    return True


def _preview_update_node(
    command: Dict[str, Any],
    diagram_data: Dict[str, Any],
    diagram_type: str,
) -> bool:
    target = command.get("target")
    if not isinstance(target, str) or not target.strip():
        return False
    node_index = command.get("node_index")
    node_identifier = command.get("node_identifier")
    resolved_node_id = command.get("node_id")
    resolved_node_index: Optional[int] = node_index if isinstance(node_index, int) else None

    nodes = diagram_data.get("children", [])
    if not isinstance(nodes, list):
        return False

    prefix_map = get_diagram_prefix_map()
    prefix = prefix_map.get(diagram_type, "node")

    if resolved_node_index is not None:
        if not 0 <= resolved_node_index < len(nodes):
            return False
        node = nodes[resolved_node_index]
        if not resolved_node_id:
            resolved_node_id = node.get("id") if isinstance(node, dict) else f"{prefix}_{resolved_node_index}"
    elif node_identifier and not resolved_node_id:
        for idx, node in enumerate(nodes):
            node_text = node.get("text") if isinstance(node, dict) else str(node)
            if node_text and (node_identifier in node_text or node_text in node_identifier):
                resolved_node_index = idx
                resolved_node_id = node.get("id") if isinstance(node, dict) else f"context_{idx}"
                break

    if (
        resolved_node_id is None
        or resolved_node_index is None
        or not 0 <= resolved_node_index < len(nodes)
    ):
        return False

    node = nodes[resolved_node_index]
    if isinstance(node, dict):
        node["text"] = target.strip()
        if "label" in node:
            node["label"] = target.strip()
    else:
        nodes[resolved_node_index] = target.strip()
    return True


def _preview_add_node(command: Dict[str, Any], diagram_data: Dict[str, Any], diagram_type: str) -> bool:
    target = command.get("target")
    if not isinstance(target, str) or not target.strip():
        return False
    nodes = diagram_data.setdefault("children", [])
    if not isinstance(nodes, list):
        return False

    prefix_map = get_diagram_prefix_map()
    prefix = prefix_map.get(diagram_type, "node")
    add_node_index = command.get("node_index")
    if isinstance(add_node_index, int):
        if 0 <= add_node_index < len(nodes):
            existing_node = nodes[add_node_index]
            if isinstance(existing_node, dict):
                existing_node["text"] = target.strip()
            else:
                nodes[add_node_index] = target.strip()
        else:
            new_node = {
                "id": f"{prefix}_{add_node_index}",
                "index": add_node_index,
                "text": target.strip(),
            }
            while len(nodes) < add_node_index:
                nodes.append(None)
            nodes.insert(add_node_index, new_node)
    else:
        new_node = {
            "id": f"{prefix}_{len(nodes)}",
            "index": len(nodes),
            "text": target.strip(),
        }
        nodes.append(new_node)
    return True


def _preview_delete_node(command: Dict[str, Any], diagram_data: Dict[str, Any], diagram_type: str) -> bool:
    target = command.get("target")
    node_index_raw = command.get("node_index")
    nodes = diagram_data.get("children", [])
    if not isinstance(nodes, list):
        return False

    prefix_map = get_diagram_prefix_map()
    prefix = prefix_map.get(diagram_type, "node")
    resolved_node_id = command.get("node_id")
    resolved_node_index: Optional[int] = node_index_raw if isinstance(node_index_raw, int) else None

    if not resolved_node_id and resolved_node_index is not None:
        if 0 <= resolved_node_index < len(nodes):
            node = nodes[resolved_node_index]
            resolved_node_id = node.get("id") if isinstance(node, dict) else f"{prefix}_{resolved_node_index}"

    if not resolved_node_id and isinstance(target, str) and target.strip():
        for idx, node in enumerate(nodes):
            node_text = node.get("text") if isinstance(node, dict) else str(node)
            if node_text and (target in node_text or node_text in target):
                resolved_node_index = idx
                resolved_node_id = node.get("id") if isinstance(node, dict) else f"{prefix}_{idx}"
                break

    if resolved_node_index is None or not 0 <= resolved_node_index < len(nodes):
        return False

    nodes.pop(resolved_node_index)
    return True


def preview_voice_context_after_diagram_intent(
    *,
    action: str,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
    diagram_type: str,
) -> Optional[Dict[str, Any]]:
    """
    Pure copy of ``session_context`` after applying a diagram voice intent.

    Applies children/center mutations for all diagram types that use ``children[]``,
    ``double_bubble_map`` center updates, then ``sync_diagram_data_to_spec_shape``.
    """

    if action not in DIAGRAM_VOICE_INTENTS:
        return None

    out = copy.deepcopy(session_context)
    diagram_data = out.get("diagram_data")
    if not isinstance(diagram_data, dict):
        diagram_data = {}
        out["diagram_data"] = diagram_data

    if diagram_type == "double_bubble_map" and action == "update_center":
        if _preview_double_bubble_update_center(command, diagram_data):
            sync_diagram_data_to_spec_shape(diagram_type, diagram_data)
            return out
        return None

    applied = False
    if action == "update_center":
        applied = _preview_update_center(command, diagram_data)
    elif action == "update_node":
        applied = _preview_update_node(command, diagram_data, diagram_type)
    elif action == "add_node":
        applied = _preview_add_node(command, diagram_data, diagram_type)
    elif action == "delete_node":
        applied = _preview_delete_node(command, diagram_data, diagram_type)

    if applied:
        sync_diagram_data_to_spec_shape(diagram_type, diagram_data)
        return out
    return None


async def try_sync_voice_diagram_to_hub(voice_session_id: str) -> None:
    """
    Push the current voice session ``context`` through ``patch_context`` when a hub session exists.

    Best-effort: logs and returns on missing session, scope, or hub rejection.
    """
    session = get_voice_session(voice_session_id)
    if not session:
        return

    hub_session_id = session.get("_hub_session_id")
    if not hub_session_id or not isinstance(hub_session_id, str):
        return

    diagram_scope = session.get("diagram_session_id")
    if not diagram_scope or not isinstance(diagram_scope, str) or not diagram_scope.strip():
        return

    ctx = session.get("context")
    if not isinstance(ctx, dict):
        return

    merged = copy.deepcopy(ctx)
    diagram_type = session.get("diagram_type") or merged.get("diagram_type") or "circle_map"
    panel = session.get("active_panel") or merged.get("active_panel") or "none"
    hub_rev_raw = session.get("_hub_scope_revision")
    expected_revision = hub_rev_raw if isinstance(hub_rev_raw, int) else None

    hub = get_mind_graph_agent_hub()
    try:
        mutation_out = await apply_kitty_ws_context_patch(
            hub,
            hub_session_id=hub_session_id,
            diagram_scope=diagram_scope.strip(),
            merged_context=merged,
            diagram_type=str(diagram_type),
            active_panel=str(panel),
            expected_revision=expected_revision,
            idempotency_key=None,
            source_module="kitty_diagram_intent",
        )
    except ValueError as exc:
        logger.warning(
            "Hub sync after Kitty diagram voice intent rejected for %s: %s",
            voice_session_id,
            exc,
        )
        return

    new_rev = mutation_out.get("revision")
    if isinstance(new_rev, int):
        session["_hub_scope_revision"] = new_rev
