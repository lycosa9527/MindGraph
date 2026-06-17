"""Build ``RlsContext`` field dicts from users and admin scopes (auth leaf module)."""

from __future__ import annotations

from typing import Any, Optional

from utils.db.rls_types import MODE_PANEL

MODE_AUTHENTICATED = "authenticated"
MODE_PANEL_SUPERADMIN = "panel_superadmin"

_ROLE_TEACHER = "teacher"
_SUPERADMIN_ROLES = frozenset({"superadmin", "admin"})
_ALL_USER_ROLES = frozenset(
    {
        "superadmin",
        "platform_bd",
        "expert",
        "school_admin",
        "teacher",
        "personal_trial",
        "personal_paid",
    }
)
_LEGACY_TO_CANONICAL = {
    "admin": "superadmin",
    "manager": "school_admin",
    "user": "teacher",
}
_CAP_SCOPE_GLOBAL = "scope.global"
_CAP_SCOPE_ORG = "scope.org"
_CAP_SCOPE_INVITED_ORGS = "scope.invited_orgs"


def _normalize_role(role: str | None) -> str:
    """Map legacy DB role strings to canonical slugs (local copy to avoid auth import cycle)."""
    if not role:
        return _ROLE_TEACHER
    if role in _ALL_USER_ROLES:
        return role
    return _LEGACY_TO_CANONICAL.get(role, role)


def _role_in(actor: Any, roles: frozenset[str]) -> bool:
    """True when the actor role is in the given set (with legacy fallbacks)."""
    raw = getattr(actor, "role", None) or "user"
    if raw in roles:
        return True
    return _LEGACY_TO_CANONICAL.get(raw, raw) in roles


def _comma_join_org_ids(org_ids: frozenset[int] | None) -> Optional[str]:
    """Comma join org ids."""
    if org_ids is None or len(org_ids) == 0:
        return None
    return ",".join(str(int(x)) for x in sorted(org_ids))


def _admin_scope_to_session_vars(scope: Any) -> dict[str, Any]:
    """Build kwargs for RlsContext from AdminScope (local copy; avoids auth import cycle)."""
    actor = scope.actor
    actor_id = getattr(actor, "id", None)
    actor_org = getattr(actor, "organization_id", None)
    role = scope.role

    if _role_in(actor, _SUPERADMIN_ROLES):
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

    if _CAP_SCOPE_ORG in scope.capabilities and scope.org_ids is not None:
        org_id = next(iter(scope.org_ids)) if len(scope.org_ids) == 1 else scope.effective_org_id
        return {
            "mode": MODE_PANEL,
            "user_id": int(actor_id) if actor_id is not None else None,
            "organization_id": int(org_id) if org_id is not None else None,
            "role": role,
            "readable_org_ids": _comma_join_org_ids(scope.org_ids),
            "actor_user_id": int(actor_id) if actor_id is not None else None,
        }

    if _CAP_SCOPE_GLOBAL in scope.capabilities:
        return {
            "mode": MODE_PANEL,
            "user_id": int(actor_id) if actor_id is not None else None,
            "role": role,
            "actor_user_id": int(actor_id) if actor_id is not None else None,
            "panel_global_read": True,
        }

    if not _role_in(actor, _SUPERADMIN_ROLES) and _CAP_SCOPE_INVITED_ORGS in scope.capabilities:
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


def build_from_user_kwargs(
    user: Any,
    *,
    allow_global_channels: bool = False,
) -> dict[str, Any]:
    """Build from user kwargs."""
    uid = getattr(user, "id", None)
    org_id = getattr(user, "organization_id", None)
    role = _normalize_role(getattr(user, "role", None))
    return {
        "mode": MODE_AUTHENTICATED,
        "user_id": int(uid) if uid is not None else None,
        "organization_id": int(org_id) if org_id is not None else None,
        "role": role,
        "actor_user_id": int(uid) if uid is not None else None,
        "allow_global_channels": allow_global_channels,
    }


def build_from_admin_scope_kwargs(scope: Any) -> dict[str, Any]:
    """Build from admin scope kwargs."""
    return dict(_admin_scope_to_session_vars(scope))


def build_panel_superadmin_kwargs(user: Any) -> dict[str, Any]:
    """Build panel superadmin kwargs."""
    uid = getattr(user, "id", None)
    return {
        "mode": MODE_PANEL_SUPERADMIN,
        "user_id": int(uid) if uid is not None else None,
        "role": _normalize_role(getattr(user, "role", None)),
        "actor_user_id": int(uid) if uid is not None else None,
        "panel_global_read": True,
    }
