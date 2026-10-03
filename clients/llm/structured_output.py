"""Shared JSON Schema response_format handling for chat completions.

Qwen and Volcengine Ark chat completions both take
``response_format.type = json_schema``. Ark's Responses API puts the same
schema under ``text.format``; auto-complete uses chat completions
(``/api/v3``), so the schema travels in ``response_format``.

A token cap truncates the JSON mid-string. Schema calls omit ``max_tokens``
and use the model output limit.
"""

from __future__ import annotations

from typing import Any


def is_json_schema_format(response_format: Any) -> bool:
    """True when the caller asked for native JSON Schema output."""
    return isinstance(response_format, dict) and response_format.get("type") == "json_schema"


def apply_structured_output(payload: dict[str, Any], response_format: Any) -> None:
    """Attach ``response_format`` and drop ``max_tokens`` for a schema call."""
    if response_format is None:
        return
    payload["response_format"] = response_format
    if is_json_schema_format(response_format):
        payload.pop("max_tokens", None)
