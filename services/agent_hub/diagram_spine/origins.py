"""Diagram command provenance and channel adapter registration."""

from __future__ import annotations

import logging
from enum import Enum
from typing import List

logger = logging.getLogger(__name__)


class DiagramCommandOrigin(str, Enum):
    """Provenance for diagram mutations routed through the hub."""

    KITTY_MOBILE = "kitty_mobile"
    MINDMATE = "mindmate"
    CANVAS = "canvas"
    WORKSHOP = "workshop"
    DINGTALK = "dingtalk"
    API = "api"


_registered_adapters: List[str] = []


def register_channel_adapter(name: str) -> None:
    """
    Register a channel adapter name for future multi-agent ingress.

    P0 Kitty uses the Kitty WS adapter directly; MindMate registers here as a no-op stub.
    """
    normalized = name.strip().lower()
    if not normalized:
        return
    if normalized not in _registered_adapters:
        _registered_adapters.append(normalized)
        logger.debug("[DiagramSpine] register_channel_adapter %s", normalized)


def list_registered_channel_adapters() -> List[str]:
    """Return registered adapter names (tests / diagnostics)."""
    return list(_registered_adapters)


def reset_channel_adapters_for_tests() -> None:
    """Clear adapter registry (tests only)."""
    _registered_adapters.clear()
