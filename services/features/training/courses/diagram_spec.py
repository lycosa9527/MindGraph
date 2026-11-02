"""Persist the slide diagram on the course step (not the editor Pinia store)."""

from __future__ import annotations

import json
from typing import Any

_DROP_KEYS = frozenset({"llm_results", "_llm_results"})
_MAX_CHARS = 750_000


def clean_diagram_spec(raw: object) -> dict[str, Any] | None:
    """Keep a JSON object the canvas can loadFromSpec. None means use the type template."""
    if not isinstance(raw, dict) or not raw:
        return None
    cleaned = {key: value for key, value in raw.items() if key not in _DROP_KEYS}
    if not cleaned:
        return None
    try:
        encoded = json.dumps(cleaned, ensure_ascii=False, default=str)
    except (TypeError, ValueError) as error:
        raise ValueError("diagram_spec is not JSON") from error
    if len(encoded) > _MAX_CHARS:
        raise ValueError("diagram_spec too large")
    parsed = json.loads(encoded)
    if not isinstance(parsed, dict):
        return None
    return parsed
