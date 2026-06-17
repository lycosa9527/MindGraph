"""In-memory per-diagram state mirror for Kitty voice sessions."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

logger = logging.getLogger("KITTY_AGENT")


class DiagramNode(TypedDict):
    """DiagramNode helper."""

    id: str
    index: int
    text: str


class DiagramState(TypedDict):
    """DiagramState helper."""

    diagram_type: str
    center_text: str
    nodes: List[DiagramNode]
    selected_nodes: List[str]


class AgentState(TypedDict):
    """AgentState helper."""

    messages: List[Any]
    diagram: DiagramState
    active_panel: str
    mindmate_open: bool
    node_palette_open: bool
    action: Optional[Dict[str, Any]]
    session_id: str
    last_updated: str


class KittyAgent:
    """Lightweight per-diagram canvas mirror while a voice session is active."""

    def __init__(self, session_id: str) -> None:
        """init  ."""
        self.session_id = session_id
        self._state = self._create_initial_state()
        logger.info("KittyAgent initialized for session %s", session_id)

    def _create_initial_state(self) -> AgentState:
        """Create initial state."""
        return {
            "messages": [],
            "diagram": {
                "diagram_type": "unknown",
                "center_text": "",
                "nodes": [],
                "selected_nodes": [],
            },
            "active_panel": "none",
            "mindmate_open": False,
            "node_palette_open": False,
            "action": None,
            "session_id": self.session_id,
            "last_updated": datetime.now().isoformat(),
        }

    def update_diagram_state(self, diagram_data: Dict[str, Any]) -> None:
        """Sync diagram state from frontend ``diagram_data``."""
        nodes: List[DiagramNode] = []
        children = diagram_data.get("children", [])

        for child in children:
            if isinstance(child, dict):
                nodes.append(
                    {
                        "id": child.get("id", f"node_{len(nodes)}"),
                        "index": child.get("index", len(nodes)),
                        "text": child.get("text", ""),
                    }
                )
            elif isinstance(child, str):
                nodes.append({"id": f"node_{len(nodes)}", "index": len(nodes), "text": child})

        center = diagram_data.get("center")
        center_text = ""
        if isinstance(center, dict):
            center_text = str(center.get("text") or "")
        elif isinstance(diagram_data.get("topic"), str):
            center_text = diagram_data["topic"]

        self._state["diagram"] = {
            "diagram_type": diagram_data.get("diagram_type", self._state["diagram"]["diagram_type"]),
            "center_text": center_text,
            "nodes": nodes,
            "selected_nodes": list(diagram_data.get("selected_nodes") or []),
        }
        self._state["last_updated"] = datetime.now().isoformat()
        logger.debug("Diagram state updated: %d nodes", len(nodes))

    def update_panel_state(self, active_panel: str, panels: Optional[Dict[str, bool]] = None) -> None:
        """Update panel state."""
        self._state["active_panel"] = active_panel
        if panels:
            self._state["mindmate_open"] = panels.get("mindmate", False)
            self._state["node_palette_open"] = panels.get("node_palette", False)

    def get_state(self) -> AgentState:
        """Get state."""
        return self._state

    def clear_history(self) -> None:
        """Clear history."""
        self._state["messages"] = []
        logger.debug("Conversation history cleared")


class KittyAgentManager:
    """Manages :class:`KittyAgent` instances per diagram session."""

    def __init__(self) -> None:
        """init  ."""
        self._agents: Dict[str, KittyAgent] = {}

    def get_or_create(self, session_id: str) -> KittyAgent:
        """Get or create."""
        if session_id not in self._agents:
            self._agents[session_id] = KittyAgent(session_id)
            logger.info("Created new KittyAgent for session %s", session_id)
        return self._agents[session_id]

    def remove(self, session_id: str) -> None:
        """Remove."""
        if session_id in self._agents:
            del self._agents[session_id]
            logger.info("Removed KittyAgent for session %s", session_id)

    def get(self, session_id: str) -> Optional[KittyAgent]:
        """Get."""
        return self._agents.get(session_id)

    def clear_all(self) -> None:
        """Clear all."""
        self._agents.clear()
        logger.info("Cleared all KittyAgent instances")


kitty_agent_manager = KittyAgentManager()
