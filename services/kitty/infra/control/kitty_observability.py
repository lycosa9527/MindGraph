"""Structured :func:`logging` ``extra`` keys for Kitty control plane and agent hub.

Use with ``logger.info(..., extra=kitty_extra(...))``. Keys are prefixed with
``kitty_`` to avoid clashing with standard :class:`logging.LogRecord` attributes.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def kitty_extra(
    event: str,
    *,
    scope: Optional[str] = None,
    user_id: Optional[int] = None,
    reason: Optional[str] = None,
    origin: Optional[str] = None,
    error_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a dict suitable for ``logging`` ``extra=`` (JSON/log-shipper friendly).

    Args:
        event: Short machine-readable event name (e.g. ``voice_cleanup_failed``).
        scope: Normalized Kitty diagram session scope when known.
        user_id: Authenticated subject when known.
        reason: Control ``reason`` string or high-level cause.
        origin: Publisher ``origin`` when relevant.
        error_type: ``type(exc).__name__`` for failures.
    """
    out: Dict[str, Any] = {"kitty_event": event}
    if scope is not None:
        out["kitty_scope"] = scope
    if user_id is not None:
        out["kitty_user_id"] = user_id
    if reason is not None:
        out["kitty_reason"] = reason
    if origin is not None:
        out["kitty_origin"] = origin
    if error_type is not None:
        out["kitty_error_type"] = error_type
    return out
