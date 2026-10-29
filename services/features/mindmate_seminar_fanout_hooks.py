"""
Leaf callbacks so the Redis fan-out listener can reach MindMate seminars.

The listener must not import the MindMate package: that package's startup
imports the listener before the listener has finished loading.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional


class _CollabFanoutHooks:
    """Holds seminar deliver and resync callbacks registered after import."""

    __slots__ = ("deliver", "resync")

    def __init__(self) -> None:
        self.deliver: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
        self.resync: Optional[Callable[[], None]] = None


_hooks = _CollabFanoutHooks()


def register_collab_fanout_hooks(
    deliver: Callable[[Dict[str, Any]], Awaitable[None]],
    resync: Callable[[], None],
) -> None:
    """Connect seminar delivery once both sides have finished importing."""
    _hooks.deliver = deliver
    _hooks.resync = resync


async def deliver_registered_collab_fanout(envelope: Dict[str, Any]) -> bool:
    """Hand one envelope to MindMate. Returns False when the feature is not wired."""
    deliver = _hooks.deliver
    if deliver is None:
        return False
    await deliver(envelope)
    return True


def notify_collab_fanout_subscribed() -> None:
    """Ask open seminars to pull lines missed while pub/sub was down."""
    resync = _hooks.resync
    if resync is not None:
        resync()
