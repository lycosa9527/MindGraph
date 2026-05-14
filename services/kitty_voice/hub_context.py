"""Centralize Kitty WebSocket ``context_update`` → Agent Hub ``patch_context`` calls."""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.agent_hub import MindGraphAgentHub


async def apply_kitty_ws_context_patch(
    hub: MindGraphAgentHub,
    *,
    hub_session_id: str,
    diagram_scope: str,
    merged_context: Dict[str, Any],
    diagram_type: str,
    active_panel: str,
    expected_revision: Optional[int],
    idempotency_key: Optional[str],
    source_module: str = "kitty_ws_context_update",
) -> Dict[str, Any]:
    """
    Apply ``patch_context`` for merged voice/editor context from the Kitty WS loop.

    Callers own updating in-memory session revision and WebSocket error responses.
    """
    return await hub.apply_diagram_spec_mutation(
        hub_session_id=hub_session_id,
        diagram_scope=diagram_scope,
        mutation_cmd={
            "op": "patch_context",
            "context": merged_context,
            "diagram_type": diagram_type,
            "active_panel": active_panel,
        },
        source_module=source_module,
        expected_revision=expected_revision,
        idempotency_key=idempotency_key,
    )
