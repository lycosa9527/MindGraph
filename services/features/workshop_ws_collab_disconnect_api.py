"""
Registration hook for canvas collab disconnect (breaks import cycles).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional

_FinalizeFn = Callable[..., Awaitable[None]]


class _FinalizeCanvasCollabDisconnectState:
    """Holds the registered disconnect implementation."""

    impl: Optional[_FinalizeFn] = None


_state = _FinalizeCanvasCollabDisconnectState()


def register_finalize_canvas_collab_disconnect(fn: _FinalizeFn) -> None:
    """Register the real disconnect handler (called from disconnect_cleanup init)."""
    _state.impl = fn


async def finalize_canvas_collab_disconnect(*args: Any, **kwargs: Any) -> None:
    """Forward to the registered disconnect implementation."""
    if _state.impl is None:
        raise RuntimeError("finalize_canvas_collab_disconnect is not registered yet")
    await _state.impl(*args, **kwargs)
