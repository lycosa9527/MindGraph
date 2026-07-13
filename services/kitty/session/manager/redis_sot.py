"""Session Manager Redis SoT wrappers (pairing keys).

Delegates to existing desktop/infra helpers so writers can migrate to one facade.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from services.kitty.infra.desktop.kitty_canvas_owner_presence import (
    clear_kitty_canvas_owner_present,
    has_kitty_canvas_owner_present,
    mark_kitty_canvas_owner_present,
)
from services.kitty.infra.desktop.kitty_desktop_focus import (
    get_kitty_desktop_focus_diagram,
    set_kitty_desktop_focus_diagram,
)
from services.kitty.infra.desktop.kitty_mobile_active import (
    clear_kitty_mobile_scope,
    mark_kitty_mobile_active,
    read_kitty_mobile_active,
)


async def sot_get_desktop_focus(user_id: int) -> Tuple[Optional[str], Optional[int]]:
    """Return ``(library_id, updated_at)`` from Redis desktop_focus."""
    return await get_kitty_desktop_focus_diagram(user_id)


async def sot_set_desktop_focus(user_id: int, diagram_library_id: Optional[str]) -> None:
    """Set or clear desktop_focus pairing hint."""
    await set_kitty_desktop_focus_diagram(user_id, diagram_library_id)


async def sot_read_mobile_active(user_id: int) -> Dict[str, Any]:
    """Return ``{ active, scopes, primary_scope }``."""
    return await read_kitty_mobile_active(user_id)


async def sot_mark_mobile_active(user_id: int, scope: str) -> None:
    """Mark mobile-lane Kitty active for scope."""
    await mark_kitty_mobile_active(user_id, scope)


async def sot_clear_mobile_scope(user_id: int, scope: str) -> None:
    """Clear one mobile-active scope."""
    await clear_kitty_mobile_scope(user_id, scope)


async def sot_mark_canvas_owner_present(user_id: int, scope: str) -> None:
    """Lease: desktop canvas owner live for user+scope."""
    await mark_kitty_canvas_owner_present(user_id, scope)


async def sot_clear_canvas_owner_present(user_id: int, scope: str) -> None:
    """Clear canvas-owner presence lease."""
    await clear_kitty_canvas_owner_present(user_id, scope)


async def sot_has_canvas_owner_present(user_id: int, scope: str) -> bool:
    """True when Redis reports a live desktop canvas owner."""
    return await has_kitty_canvas_owner_present(user_id, scope)
