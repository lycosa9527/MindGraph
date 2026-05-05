"""Agent matrix bus (skeleton): single write spine + channel adapters — extend for DingTalk/workshop."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DiagramCommandOrigin(str, Enum):
    """Provenance for diagram mutations routed through the hub."""

    KITTY_MOBILE = "kitty_mobile"
    MINDMATE = "mindmate"
    CANVAS = "canvas"
    WORKSHOP = "workshop"
    DINGTALK = "dingtalk"
    API = "api"


class DiagramCommandBus:
    """
    Placeholder integration bus: register adapters and publish diagram-domain events.

    P0 Kitty path uses Kitty control pub/sub directly; this class is the extension point for P3.
    """

    def __init__(self) -> None:
        self._adapters: List[str] = []

    def register_adapter(self, name: str) -> None:
        """Record a registered channel adapter (no-op until bus is wired to Redis Streams)."""
        if name not in self._adapters:
            self._adapters.append(name)
            logger.debug("[DiagramCommandBus] register_adapter %s", name)

    async def apply_diagram_command(
        self,
        _draft: Dict[str, Any],
        *,
        _origin: DiagramCommandOrigin,
        _user_id: int,
        _correlation_id: Optional[str] = None,
    ) -> bool:
        """Spine hook: fan in diagram edits from any channel (not yet implemented)."""
        logger.debug("[DiagramCommandBus] apply_diagram_command (stub)")
        return False


_BUS: Optional[DiagramCommandBus] = None


def get_diagram_command_bus() -> DiagramCommandBus:
    global _BUS
    if _BUS is None:
        _BUS = DiagramCommandBus()
    return _BUS
