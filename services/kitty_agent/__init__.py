"""Kitty Agent product module — LangGraph runtime and session manager.

The LangGraph implementation lives in ``services.features.voice_agent`` (module name is
historical). Multi-worker Kitty scope lifecycle (refcount, control pub/sub, snapshots) is
owned by ``services.agent_hub`` and ``services.kitty``; set
``KITTY_CONTROL_SHARED_SECRET`` when ``DEBUG=False`` in production.
"""

from services.features.voice_agent import (
    AgentState,
    DiagramNode,
    DiagramState,
    KittyAgent,
    KittyAgentManager,
    kitty_agent_manager,
)

__all__ = [
    "AgentState",
    "DiagramNode",
    "DiagramState",
    "KittyAgent",
    "KittyAgentManager",
    "kitty_agent_manager",
]
