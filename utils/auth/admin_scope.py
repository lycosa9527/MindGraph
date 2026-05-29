"""
AdminScope — row-level security context for management panel API requests.
"""

from dataclasses import dataclass
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.sql import true
from sqlalchemy.sql.elements import ColumnElement

from models.domain.messages import Language, Messages
from utils.auth.admin_panel_permissions import (
    CAP_PANEL_ACCESS,
    CAP_SCOPE_GLOBAL,
    CAP_SCOPE_ORG,
    user_panel_capabilities,
)
from utils.auth.role_constants import normalize_role
from utils.auth.roles import is_superadmin


@dataclass(frozen=True)
class AdminScope:
    """Resolved access scope for a management-panel API request."""

    actor: Any
    role: str
    capabilities: frozenset[str]
    org_ids: frozenset[int] | None
    effective_org_id: int | None
    read_only: bool

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities

    def can_access_panel(self) -> bool:
        return self.has_capability(CAP_PANEL_ACCESS)

    def assert_capability(self, capability: str, lang: Language) -> None:
        if not self.has_capability(capability):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=Messages.error("admin_access_required", lang),
            )

    def assert_not_read_only(self, lang: Language) -> None:
        if self.read_only:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=Messages.error("admin_access_required", lang),
            )

    def assert_mutation_allowed(self, lang: Language) -> None:
        self.assert_not_read_only(lang)


def _read_only_for_role(role: str, capabilities: frozenset[str]) -> bool:
    if is_superadmin_role_only(role):
        return False
    if CAP_SCOPE_GLOBAL in capabilities and CAP_SCOPE_ORG not in capabilities:
        return True
    return False


def is_superadmin_role_only(role: str) -> bool:
    return normalize_role(role) == "superadmin"


def panel_read_only_for_user(current_user) -> bool:
    """Whether the user has read-only panel access (platform BD, etc.)."""
    if is_superadmin(current_user):
        return False
    role = normalize_role(getattr(current_user, "role", None))
    capabilities = user_panel_capabilities(current_user)
    return _read_only_for_role(role, capabilities)


def build_admin_scope(
    current_user: Any,
    organization_id: Optional[int] = None,
    lang: Language = "en",
) -> AdminScope:
    """
    Build AdminScope for the authenticated user.

    Raises 403 when the user has no panel access (roles 5–7).
    """
    role = normalize_role(getattr(current_user, "role", None))
    capabilities = user_panel_capabilities(current_user)

    if CAP_PANEL_ACCESS not in capabilities:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=Messages.error("admin_access_required", lang),
        )

    read_only = _read_only_for_role(role, capabilities)
    if is_superadmin(current_user):
        read_only = False

    if is_superadmin(current_user):
        org_ids = None
        effective_org_id = organization_id
    elif CAP_SCOPE_ORG in capabilities:
        user_org = getattr(current_user, "organization_id", None)
        if user_org is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=Messages.error("school_dashboard_manager_no_org", lang=lang),
            )
        org_ids = frozenset({int(user_org)})
        if organization_id is not None and int(organization_id) != int(user_org):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=Messages.error(
                    "school_dashboard_manager_cross_org_forbidden",
                    lang=lang,
                ),
            )
        effective_org_id = int(user_org)
    else:
        org_ids = None
        effective_org_id = organization_id

    return AdminScope(
        actor=current_user,
        role=role,
        capabilities=capabilities,
        org_ids=org_ids,
        effective_org_id=effective_org_id,
        read_only=read_only,
    )


def resolve_effective_org_id(
    scope: AdminScope,
    organization_id: Optional[int],
    lang: Language,
    require_org_for_superadmin: bool = True,
) -> int:
    """
    Resolve organization_id for org-scoped admin endpoints.

    Superadmin must pass organization_id when require_org_for_superadmin is True.
    School admin is locked to their org.
    """
    if scope.org_ids is not None:
        if len(scope.org_ids) != 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=Messages.error("admin_access_required", lang),
            )
        locked = next(iter(scope.org_ids))
        if organization_id is not None and int(organization_id) != locked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=Messages.error(
                    "school_dashboard_manager_cross_org_forbidden",
                    lang=lang,
                ),
            )
        return locked

    if organization_id is None and require_org_for_superadmin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("school_dashboard_admin_org_required", lang=lang),
        )
    if organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("school_dashboard_admin_org_required", lang=lang),
        )
    return int(organization_id)


def org_filter(scope: AdminScope, column: Any) -> ColumnElement:
    """SQLAlchemy filter restricting rows to scope.org_ids when set."""
    if scope.org_ids is None:
        return true()
    return column.in_(scope.org_ids)


def assert_resource_org_in_scope(
    scope: AdminScope,
    resource_org_id: int | None,
    lang: Language,
) -> None:
    """IDOR guard: resource must belong to an org in scope."""
    if scope.org_ids is None:
        return
    if resource_org_id is None or int(resource_org_id) not in scope.org_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("user_not_found", lang),
        )
