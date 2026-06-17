"""Kitty product package — realtime agent, diagram commands, session infrastructure.

Subpackages:
    ws, omni, session, routing, diagram, context, content, http — realtime agent
    infra — redis, desktop, control, scope, bootstrap, guards

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from services.kitty.infra.scope.kitty_ws_scope import normalize_kitty_diagram_session_id

__all__ = ["normalize_kitty_diagram_session_id"]
