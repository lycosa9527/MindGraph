"""
Validate a history-move plan before any SQL runs.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from uuid import UUID

from scripts.dify.db_merge.models import MergePlan, PlanError, SourceMove

_PERSONA_MAX = 200


def parse_uuid(value: object, label: str) -> str:
    """Return the canonical UUID text or raise PlanError."""
    if not isinstance(value, str):
        raise PlanError(f"{label} must be a UUID string")
    try:
        return str(UUID(value.strip()))
    except ValueError as exc:
        raise PlanError(f"{label} is not a UUID") from exc


def persona_from_fields(name: str, alias: str, school: str) -> dict[str, str]:
    """Build the three Start-variable keys. Empty fields mean no patch."""
    cleaned = (name.strip(), alias.strip(), school.strip())
    if cleaned == ("", "", ""):
        return {}
    agent_name, agent_alias, school_name = cleaned
    if not agent_name or not school_name:
        raise PlanError("mg_agent_name and mg_school_name are both required when setting a persona")
    if not agent_alias:
        agent_alias = agent_name
    values = {
        "mg_agent_name": agent_name,
        "mg_agent_alias": agent_alias,
        "mg_school_name": school_name,
    }
    for key, text in values.items():
        _check_persona_value(key, text)
    return values


def plan_from_sources(target_app_id: str, sources: list[SourceMove], *, execute: bool) -> MergePlan:
    """Reject duplicate apps and a target that is also a source."""
    target = parse_uuid(target_app_id, "target_app_id")
    if not sources:
        raise PlanError("select at least one input workflow")
    seen: set[str] = set()
    for source in sources:
        if source.app_id in seen:
            raise PlanError(f"source app repeated: {source.app_id}")
        seen.add(source.app_id)
        if source.app_id == target:
            raise PlanError("a source app cannot also be the target app")
    return MergePlan(target_app_id=target, sources=tuple(sources), execute=execute)


def _check_persona_value(key: str, text: str) -> None:
    if len(text) > _PERSONA_MAX:
        raise PlanError(f"{key} is longer than {_PERSONA_MAX} characters")
    if any(ord(char) < 32 for char in text):
        raise PlanError(f"{key} contains a control character")
