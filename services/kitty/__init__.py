"""Kitty product package — realtime agent, diagram commands, session infrastructure.

Subpackages:
    ws, omni, session, routing, diagram, context, content, http — realtime agent
    infra — redis, desktop, control, scope, bootstrap, guards
"""

from services.kitty.infra.scope.kitty_ws_scope import normalize_kitty_diagram_session_id

__all__ = ["normalize_kitty_diagram_session_id"]
