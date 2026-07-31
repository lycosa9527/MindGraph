"""
Strip server-only fields from Maite task payloads returned to clients.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Optional

_SECRET_KEYS = (
    "reference_answer",
    "reference_strategy",
    "success_criteria",
    "expected_strategy",
)


def model_to_dict(obj: Any) -> Optional[dict[str, Any]]:
    """Convert an ORM row to a plain dict using table columns."""
    if obj is None:
        return None
    table = getattr(obj, "__table__", None)
    if table is None:
        return None
    return {col.name: getattr(obj, col.name) for col in table.columns}


def strip_secret_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Remove pedagogy/answer keys that must never reach the client."""
    cleaned = dict(data)
    for key in _SECRET_KEYS:
        cleaned.pop(key, None)
    return cleaned


def public_variant_task(task: Any) -> dict[str, Any]:
    """Serialize a variant task without server-only scoring fields."""
    data = model_to_dict(task) or {}
    data.pop("expected_strategy", None)
    feedback = data.get("ai_feedback")
    if isinstance(feedback, dict):
        data["ai_feedback"] = strip_secret_fields(feedback)
    return data


def public_remedy_task(task: Any) -> dict[str, Any]:
    """Serialize a remedy task without reference answers."""
    data = model_to_dict(task) or {}
    payload = data.get("task_payload")
    if isinstance(payload, dict):
        data["task_payload"] = strip_secret_fields(payload)
    feedback = data.get("ai_feedback")
    if isinstance(feedback, dict):
        data["ai_feedback"] = strip_secret_fields(feedback)
    return data
