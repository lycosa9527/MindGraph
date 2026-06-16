"""
Map AdminScope to Postgres RLS session variables (app.* GUCs).
"""

from __future__ import annotations

from typing import Any, Optional

from utils.auth.admin_panel_permissions import (
    CAP_SCOPE_GLOBAL,
    CAP_SCOPE_ORG,
)
from utils.auth.admin_scope import AdminScope, uses_invited_org_panel_scope
from utils.auth.roles import is_superadmin
from utils.db.rls_context import (
    MODE_PANEL,
    RlsContext,
)


def _comma_join_org_ids(org_ids: frozenset[int] | None) -> Optional[str]:
    if org_ids is None or len(org_ids) == 0:
        return None
    return ",".join(str(int(x)) for x in sorted(org_ids))


def admin_scope_to_session_vars(scope: AdminScope) -> dict[str, Any]:
    """
    Build kwargs for RlsContext from AdminScope.

    Mirrors org_filter / invite_org_filter / panel_readable_org_condition.
    """
    actor = scope.actor
    actor_id = getattr(actor, "id", None)
    actor_org = getattr(actor, "organization_id", None)
    role = scope.role

    if is_superadmin(actor):
        return {
            "mode": MODE_PANEL,
            "user_id": int(actor_id) if actor_id is not None else None,
            "organization_id": (
                int(scope.effective_org_id)
                if scope.effective_org_id is not None
                else (int(actor_org) if actor_org is not None else None)
            ),
            "role": role,
            "actor_user_id": int(actor_id) if actor_id is not None else None,
            "panel_global_read": True,
        }

    if CAP_SCOPE_ORG in scope.capabilities and scope.org_ids is not None:
        org_id = next(iter(scope.org_ids)) if len(scope.org_ids) == 1 else scope.effective_org_id
        return {
            "mode": MODE_PANEL,
            "user_id": int(actor_id) if actor_id is not None else None,
            "organization_id": int(org_id) if org_id is not None else None,
            "role": role,
            "readable_org_ids": _comma_join_org_ids(scope.org_ids),
            "actor_user_id": int(actor_id) if actor_id is not None else None,
        }

    if CAP_SCOPE_GLOBAL in scope.capabilities:
        return {
            "mode": MODE_PANEL,
            "user_id": int(actor_id) if actor_id is not None else None,
            "role": role,
            "actor_user_id": int(actor_id) if actor_id is not None else None,
            "panel_global_read": True,
        }

    if uses_invited_org_panel_scope(scope):
        invited = scope.invited_org_ids if scope.invited_org_ids is not None else frozenset()
        return {
            "mode": MODE_PANEL,
            "user_id": int(actor_id) if actor_id is not None else None,
            "organization_id": (int(scope.effective_org_id) if scope.effective_org_id is not None else None),
            "role": role,
            "readable_org_ids": _comma_join_org_ids(invited),
            "actor_user_id": int(actor_id) if actor_id is not None else None,
        }

    return {
        "mode": MODE_PANEL,
        "user_id": int(actor_id) if actor_id is not None else None,
        "role": role,
        "readable_org_ids": _comma_join_org_ids(scope.org_ids),
        "actor_user_id": int(actor_id) if actor_id is not None else None,
    }


def to_rls_session_vars(scope: AdminScope) -> dict[str, str]:
    """Flat app.* key → value map for SET LOCAL (panel routes)."""
    ctx = RlsContext.from_admin_scope(scope)
    return ctx.session_vars()


def rls_context_from_admin_scope(scope: AdminScope) -> RlsContext:
    return RlsContext.from_admin_scope(scope)


def rls_context_panel_superadmin(user: Any) -> RlsContext:
    return RlsContext.panel_superadmin(user)
