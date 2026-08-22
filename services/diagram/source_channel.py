"""Allowlisted diagram provenance channels for library create/list."""

from __future__ import annotations

from typing import Any, Optional

ALLOWED_DIAGRAM_SOURCE_CHANNELS = frozenset({"mindgraph", "voice_notes"})
DEFAULT_DIAGRAM_SOURCE_CHANNEL = "mindgraph"


def _require_allowed_source_channel(raw: str) -> str:
    value = raw.strip()[:32]
    if value not in ALLOWED_DIAGRAM_SOURCE_CHANNELS:
        raise ValueError("invalid source_channel")
    return value


def resolve_diagram_source_channel(raw: Optional[str]) -> str:
    """Return the stored channel. Blank is mindgraph; unknown values raise."""
    if raw is None or not raw.strip():
        return DEFAULT_DIAGRAM_SOURCE_CHANNEL
    return _require_allowed_source_channel(raw)


def parse_list_source_channel(raw: Optional[str]) -> Optional[str]:
    """Parse a list query channel. Empty is None; unknown values raise."""
    if raw is None or not raw.strip():
        return None
    return _require_allowed_source_channel(raw)


def filter_diagram_list_by_source_channel(
    items: list[dict[str, Any]],
    requested: Optional[str],
) -> list[dict[str, Any]]:
    """Keep rows whose stored source_channel equals ``requested``."""
    if not requested:
        return items
    return [item for item in items if item.get("source_channel") == requested]


def list_items_missing_source_channel_field(items: list[dict[str, Any]]) -> bool:
    """True when a Redis list blob predates source_channel on list rows."""
    return any(not isinstance(item, dict) or "source_channel" not in item for item in items)
