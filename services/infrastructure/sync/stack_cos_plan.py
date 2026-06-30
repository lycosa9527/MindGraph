"""
Pure helpers for stack COS CLI (Qdrant + Celery update planning).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import List, Optional, TypedDict


class ComponentUpdate(TypedDict):
    """Whether to run an update and whether to force reinstall."""

    run: bool
    force: bool


class StackUpdatePlan(TypedDict):
    """Per-component update decisions for the stack CLI."""

    qdrant: ComponentUpdate
    celery: ComponentUpdate


def artifact_on_cos(plan: dict) -> bool:
    """True when COS meta exists for this artifact."""
    return plan.get("reason") != "cos_meta_missing"


def stack_check_exit_code(qdrant_plan: dict, celery_plan: dict) -> int:
    """
    Exit code for check action.

    0 = up to date, 1 = update available, 2 = config/meta error.
    """
    if qdrant_plan.get("reason") == "cos_not_configured" or celery_plan.get("reason") == "cos_not_configured":
        return 2
    if not artifact_on_cos(qdrant_plan) and not artifact_on_cos(celery_plan):
        return 2
    if qdrant_plan.get("update_needed") or celery_plan.get("update_needed"):
        return 1
    return 0


def stack_has_pending_updates(qdrant_plan: dict, celery_plan: dict) -> bool:
    """True when at least one on-COS artifact is newer than installed."""
    if artifact_on_cos(qdrant_plan) and qdrant_plan.get("update_needed"):
        return True
    return bool(artifact_on_cos(celery_plan) and celery_plan.get("update_needed"))


def stack_update_prompt(qdrant_plan: dict, celery_plan: dict) -> Optional[str]:
    """Human-readable install prompt, or None when no COS artifacts exist."""
    parts: List[str] = []
    if artifact_on_cos(qdrant_plan) and qdrant_plan.get("update_needed"):
        parts.append(f"Qdrant {qdrant_plan.get('cos_version')}")
    if artifact_on_cos(celery_plan) and celery_plan.get("update_needed"):
        parts.append(f"Celery {celery_plan.get('cos_version')}")
    if not parts:
        return None
    return f"Install {' and '.join(parts)} from COS now"


def resolve_stack_update(
    qdrant_plan: dict,
    celery_plan: dict,
    *,
    reinstall: bool,
) -> StackUpdatePlan:
    """Decide which components to update and whether to force reinstall."""
    if reinstall:
        return {
            "qdrant": {
                "run": artifact_on_cos(qdrant_plan),
                "force": artifact_on_cos(qdrant_plan),
            },
            "celery": {
                "run": artifact_on_cos(celery_plan),
                "force": artifact_on_cos(celery_plan),
            },
        }
    return {
        "qdrant": {
            "run": bool(artifact_on_cos(qdrant_plan) and qdrant_plan.get("update_needed")),
            "force": False,
        },
        "celery": {
            "run": bool(artifact_on_cos(celery_plan) and celery_plan.get("update_needed")),
            "force": False,
        },
    }


def verify_component_outcome(result: dict) -> str:
    """
    Classify verify pull result.

    Returns one of: verified, skipped, failed.
    """
    if result.get("error") == "cos_meta_missing":
        return "skipped"
    if result.get("ok") and result.get("verified"):
        return "verified"
    return "failed"


def summarize_update_result(label: str, result: dict) -> tuple[bool, int]:
    """
    Return (success, exit_code_increment).

    success True when ok/skipped appropriately; exit_code 1 on hard failure.
    """
    if result.get("needs_root"):
        return False, 1
    if result.get("ok") and result.get("skipped"):
        return True, 0
    if label == "Qdrant":
        if result.get("ok") and result.get("api_ok"):
            return True, 0
        return False, 0 if not result.get("ok") else 1
    if label == "Celery":
        if result.get("ok") and result.get("import_ok"):
            return True, 0
        return False, 0 if not result.get("ok") else 1
    if result.get("ok"):
        return True, 0
    return False, 1
