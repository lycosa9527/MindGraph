"""LangChain tools for Kitty voice diagram intents (used by :class:`KittyAgent`)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from langchain_core.tools import tool


@tool
def select_node(node_identifier: str) -> Dict[str, Any]:
    """
    Select a node in the diagram by its text content or index.

    Args:
        node_identifier: Node text (e.g., "ABC") or index (e.g., "1", "first")

    Returns:
        Action to select the node
    """
    return {"action": "select_node", "target": node_identifier, "confidence": 0.95}


@tool
def update_center(new_text: str) -> Dict[str, Any]:
    """
    Update the center/topic of the diagram.

    Args:
        new_text: New text for the center

    Returns:
        Action to update center
    """
    return {"action": "update_center", "target": new_text, "confidence": 0.95}


@tool
def add_node(text: str, position: Optional[int] = None) -> Dict[str, Any]:
    """
    Add a new node to the diagram.

    Args:
        text: Text content for the new node
        position: Optional position/index where to add the node (0-based).
                  If None, adds to the end. If specified, inserts at that position.
                  For mindmaps: "branch 1" = position 0, "branch 2" = position 1, etc.

    Returns:
        Action to add node
    """
    result = {"action": "add_node", "target": text, "confidence": 0.95}
    if position is not None:
        result["node_index"] = position
    return result


@tool
def delete_node(node_identifier: str) -> Dict[str, Any]:
    """
    Delete a node from the diagram.

    Args:
        node_identifier: Node text or index to delete

    Returns:
        Action to delete node
    """
    return {"action": "delete_node", "target": node_identifier, "confidence": 0.95}


@tool
def update_node(node_identifier: str, new_text: str) -> Dict[str, Any]:
    """
    Update a node's text content.

    Args:
        node_identifier: Node text or index to update
        new_text: New text for the node

    Returns:
        Action to update node
    """
    return {
        "action": "update_node",
        "target": new_text,
        "node_identifier": node_identifier,
        "confidence": 0.95,
    }


@tool
def auto_complete() -> Dict[str, Any]:
    """
    Trigger AI auto-complete to fill in the diagram.

    Returns:
        Action to trigger auto-complete
    """
    return {"action": "auto_complete", "confidence": 0.95}


@tool
def open_panel(panel_name: str) -> Dict[str, Any]:
    """
    Open a panel (mindmate, node_palette).

    Args:
        panel_name: Name of panel to open

    Returns:
        Action to open panel
    """
    panel_map = {
        "thinkguide": "open_mindmate",
        "mindmate": "open_mindmate",
        "node_palette": "open_node_palette",
        "palette": "open_node_palette",
    }
    action = panel_map.get(panel_name.lower(), f"open_{panel_name}")
    return {"action": action, "confidence": 0.95}


@tool
def close_panel(panel_name: str) -> Dict[str, Any]:
    """
    Close a panel or close all panels.

    Args:
        panel_name: Name of panel to close, or "all" for all panels

    Returns:
        Action to close panel
    """
    if panel_name.lower() == "all":
        return {"action": "close_all_panels", "confidence": 0.95}

    panel_map = {
        "thinkguide": "close_mindmate",
        "mindmate": "close_mindmate",
        "node_palette": "close_node_palette",
    }
    action = panel_map.get(panel_name.lower(), f"close_{panel_name}")
    return {"action": action, "confidence": 0.95}


KITTY_AGENT_TOOLS = [
    select_node,
    update_center,
    add_node,
    delete_node,
    update_node,
    auto_complete,
    open_panel,
    close_panel,
]
