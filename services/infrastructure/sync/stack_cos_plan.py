"""
Pure helpers for stack COS CLI (Celery, Playwright, GeoLite).

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
    playwright: ComponentUpdate
    geolite: ComponentUpdate


def artifact_on_cos(plan: dict) -> bool:
    """True when COS meta exists for this artifact."""
    return plan.get("reason") != "cos_meta_missing"


def _optional_plans(*plans: dict | None) -> List[dict]:
    """Drop components the caller did not ask about."""
    return [plan for plan in plans if plan is not None]


def _live_stack_plans(
    qdrant_plan: dict,
    celery_plan: dict,
    playwright_plan: dict | None,
    geolite_plan: dict | None,
) -> List[dict]:
    """Celery, Playwright, and GeoLite. The retired vector plan is not installed."""
    del qdrant_plan
    return [celery_plan, *_optional_plans(playwright_plan, geolite_plan)]


def stack_check_exit_code(
    qdrant_plan: dict,
    celery_plan: dict,
    playwright_plan: dict | None = None,
    geolite_plan: dict | None = None,
) -> int:
    """
    Exit code for check action.

    0 = up to date, 1 = update available, 2 = config/meta error.
    A missing local vector server does not count.
    """
    plans = _live_stack_plans(qdrant_plan, celery_plan, playwright_plan, geolite_plan)
    if any(plan.get("reason") == "cos_not_configured" for plan in plans):
        return 2
    if not any(artifact_on_cos(plan) for plan in plans):
        return 2
    mismatch_reasons = {"package_newer_than_cos", "cos_newer_than_package"}
    if any(plan.get("reason") in mismatch_reasons for plan in plans):
        return 2
    if any(plan.get("update_needed") for plan in plans):
        return 1
    return 0


def stack_has_pending_updates(
    qdrant_plan: dict,
    celery_plan: dict,
    playwright_plan: dict | None = None,
    geolite_plan: dict | None = None,
) -> bool:
    """True when at least one on-COS artifact is newer than installed."""
    plans = _live_stack_plans(qdrant_plan, celery_plan, playwright_plan, geolite_plan)
    return any(artifact_on_cos(plan) and plan.get("update_needed") for plan in plans)


def stack_update_prompt(
    qdrant_plan: dict,
    celery_plan: dict,
    playwright_plan: dict | None = None,
    geolite_plan: dict | None = None,
) -> Optional[str]:
    """Human-readable install prompt, or None when no COS artifacts exist."""
    parts: List[str] = []
    del qdrant_plan
    if artifact_on_cos(celery_plan) and celery_plan.get("update_needed"):
        parts.append(f"Celery {celery_plan.get('cos_version')}")
    if playwright_plan is not None and artifact_on_cos(playwright_plan) and playwright_plan.get("update_needed"):
        if playwright_plan.get("reason") == "apt_deps_missing":
            parts.append("Playwright apt deps")
        else:
            parts.append(f"Playwright {playwright_plan.get('cos_version')}")
    if geolite_plan is not None and artifact_on_cos(geolite_plan) and geolite_plan.get("update_needed"):
        parts.append("GeoLite2-Country")
    if not parts:
        return None
    return f"Install {' and '.join(parts)} from COS now"


def _component_update(plan: dict | None, *, reinstall: bool) -> ComponentUpdate:
    """Run when COS has the artifact and it is newer, or on an explicit reinstall."""
    if plan is None or not artifact_on_cos(plan):
        return {"run": False, "force": False}
    if reinstall:
        return {"run": True, "force": True}
    return {"run": bool(plan.get("update_needed")), "force": False}


def resolve_stack_update(
    qdrant_plan: dict,
    celery_plan: dict,
    playwright_plan: dict | None = None,
    geolite_plan: dict | None = None,
    *,
    reinstall: bool,
) -> StackUpdatePlan:
    """Decide which components to update and whether to force reinstall."""
    pw_plan = playwright_plan or {"reason": "cos_meta_missing", "update_needed": False}
    del qdrant_plan
    return {
        "qdrant": {"run": False, "force": False},
        "celery": _component_update(celery_plan, reinstall=reinstall),
        "playwright": _component_update(pw_plan, reinstall=reinstall),
        "geolite": _component_update(geolite_plan, reinstall=reinstall),
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
        return False, 1
    if label == "Celery":
        if result.get("ok") and result.get("import_ok"):
            return True, 0
        return False, 1
    if label == "Playwright":
        if result.get("ok") and result.get("browser_ok"):
            # Browser from COS is enough for success; apt deps are best-effort.
            return True, 0
        return False, 1
    if result.get("ok"):
        return True, 0
    return False, 1
