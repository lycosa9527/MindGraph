"""
AdminScope — row-level security context for management panel API requests.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from dataclasses import dataclass
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import false, true
from sqlalchemy.sql.elements import ColumnElement

from models.domain.auth import Organization
from models.domain.messages import Language, Messages
from utils.auth.admin_panel_permissions import (
    CAP_PANEL_ACCESS,
    CAP_SCOPE_GLOBAL,
    CAP_SCOPE_INVITED_ORGS,
    CAP_SCOPE_ORG,
    user_panel_capabilities,
)
from utils.auth.expert_invited_org_ids import load_expert_invited_org_ids
from utils.auth.role_constants import normalize_role
from utils.auth.roles import is_superadmin
from utils.db.rls_context import to_rls_session_vars as _admin_scope_to_rls_session_vars


@dataclass(frozen=True)
class AdminScope:
    """
    Resolved access scope for a management-panel API request.

    Prefer capability checks (``assert_capability``) over raw role tests.
    Obtained via ``get_admin_scope`` / ``require_panel_capability`` in
    ``routers.auth.dependencies``.
    """

    actor: Any
    role: str
    capabilities: frozenset[str]
    org_ids: frozenset[int] | None
    effective_org_id: int | None
    read_only: bool
    invited_org_ids: frozenset[int] | None = None

    def has_capability(self, capability: str) -> bool:
        """Has capability."""
        return capability in self.capabilities

    def can_access_panel(self) -> bool:
        """Can access panel."""
        return self.has_capability(CAP_PANEL_ACCESS)

    def assert_capability(self, capability: str, lang: Language) -> None:
        """Assert capability."""
        if not self.has_capability(capability):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=Messages.error("admin_access_required", lang),
            )

    def assert_not_read_only(self, lang: Language) -> None:
        """Assert not read only."""
        if self.read_only:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=Messages.error("admin_access_required", lang),
            )

    def assert_mutation_allowed(self, lang: Language) -> None:
        """Deprecated — prefer assert_capability(edit_cap) on mutation routes."""
        self.assert_not_read_only(lang)

    def assert_any_capability(self, capabilities: frozenset[str], lang: Language) -> None:
        """Assert any capability."""
        if any(cap in self.capabilities for cap in capabilities):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=Messages.error("admin_access_required", lang),
        )

    def to_rls_session_vars(self) -> dict[str, str]:
        """To rls session vars."""
        return _admin_scope_to_rls_session_vars(self)


def _read_only_for_role(role: str, capabilities: frozenset[str]) -> bool:
    """Read only for role."""
    if is_superadmin_role_only(role):
        return False
    if CAP_SCOPE_GLOBAL in capabilities and CAP_SCOPE_ORG not in capabilities:
        return True
    return False


def is_superadmin_role_only(role: str) -> bool:
    """Is superadmin role only."""
    return normalize_role(role) == "superadmin"


def panel_read_only_for_user(current_user) -> bool:
    """Whether the user has read-only panel access (teaching researcher, etc.)."""
    if is_superadmin(current_user):
        return False
    role = normalize_role(getattr(current_user, "role", None))
    capabilities = user_panel_capabilities(current_user)
    return _read_only_for_role(role, capabilities)


def _resolve_org_scope(
    current_user: Any,
    capabilities: frozenset[str],
    organization_id: Optional[int],
    invited_org_ids: frozenset[int] | None,
    lang: Language,
) -> tuple[frozenset[int] | None, int | None]:
    """Return (org_ids, effective_org_id) for the authenticated panel user."""
    if is_superadmin(current_user):
        return None, organization_id

    if CAP_SCOPE_ORG in capabilities:
        user_org = getattr(current_user, "organization_id", None)
        if user_org is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=Messages.error("school_dashboard_manager_no_org", lang=lang),
            )
        if organization_id is not None and int(organization_id) != int(user_org):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=Messages.error(
                    "school_dashboard_manager_cross_org_forbidden",
                    lang=lang,
                ),
            )
        return frozenset({int(user_org)}), int(user_org)

    if CAP_SCOPE_INVITED_ORGS in capabilities and CAP_SCOPE_GLOBAL not in capabilities:
        org_ids = invited_org_ids if invited_org_ids is not None else frozenset()
        return org_ids, organization_id

    return None, organization_id


def build_admin_scope(
    current_user: Any,
    organization_id: Optional[int] = None,
    lang: Language = "en",
    invited_org_ids: frozenset[int] | None = None,
) -> AdminScope:
    """
    Build AdminScope for the authenticated user.

    Raises 403 when the user has no panel access (roles 5–7).
    For expert roles, pass ``invited_org_ids`` from the DB (or omit for empty scope).
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

    org_ids, effective_org_id = _resolve_org_scope(
        current_user,
        capabilities,
        organization_id,
        invited_org_ids,
        lang,
    )

    return AdminScope(
        actor=current_user,
        role=role,
        capabilities=capabilities,
        org_ids=org_ids,
        effective_org_id=effective_org_id,
        read_only=read_only,
        invited_org_ids=invited_org_ids,
    )


async def build_admin_scope_async(
    current_user: Any,
    organization_id: Optional[int] = None,
    lang: Language = "en",
) -> AdminScope:
    """Build AdminScope with DB-backed expert org resolution."""
    capabilities = user_panel_capabilities(current_user)
    invited_org_ids: frozenset[int] | None = None
    if CAP_SCOPE_INVITED_ORGS in capabilities:
        actor_id = getattr(current_user, "id", None)
        if actor_id is not None:
            invited_org_ids = await load_expert_invited_org_ids(int(actor_id))
        else:
            invited_org_ids = frozenset()
    return build_admin_scope(
        current_user,
        organization_id=organization_id,
        lang=lang,
        invited_org_ids=invited_org_ids,
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
        if CAP_SCOPE_ORG in scope.capabilities and len(scope.org_ids) == 1:
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
        if organization_id is not None and int(organization_id) in scope.org_ids:
            return int(organization_id)
        if len(scope.org_ids) == 1:
            return next(iter(scope.org_ids))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=Messages.error("admin_access_required", lang),
        )

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
    if CAP_SCOPE_ORG in scope.capabilities and scope.org_ids is not None:
        if len(scope.org_ids) == 0:
            return false()
        return column.in_(scope.org_ids)
    if CAP_SCOPE_GLOBAL in scope.capabilities:
        return true()
    if uses_invited_org_panel_scope(scope):
        return column.in_(panel_readable_org_id_subquery(scope))
    if scope.org_ids is not None:
        if len(scope.org_ids) == 0:
            return false()
        return column.in_(scope.org_ids)
    return true()


def uses_invited_org_panel_scope(scope: AdminScope) -> bool:
    """True when the actor reads orgs via invited-org scope (BD / expert)."""
    if is_superadmin(scope.actor):
        return False
    return CAP_SCOPE_INVITED_ORGS in scope.capabilities


def expert_invite_scope_only(scope: AdminScope) -> bool:
    """Expert invite tab: own created orgs only (no global or legacy org access)."""
    return CAP_SCOPE_INVITED_ORGS in scope.capabilities and CAP_SCOPE_GLOBAL not in scope.capabilities


def panel_readable_org_where_clause() -> ColumnElement:
    """WHERE clause on Organization: legacy shared (NULL invited_by_user_id)."""
    return Organization.invited_by_user_id.is_(None)


def panel_readable_org_condition(scope: AdminScope) -> ColumnElement:
    """Organization-row predicate for invited-org panel roles."""
    invited_ids = scope.invited_org_ids if scope.invited_org_ids is not None else frozenset()
    if expert_invite_scope_only(scope):
        if len(invited_ids) == 0:
            return false()
        return Organization.id.in_(invited_ids)
    legacy_clause = panel_readable_org_where_clause()
    if len(invited_ids) == 0:
        return legacy_clause
    return or_(Organization.id.in_(invited_ids), legacy_clause)


def panel_readable_org_id_subquery(scope: AdminScope):
    """Subquery of organization IDs readable under invited-org panel scope."""
    return select(Organization.id).where(panel_readable_org_condition(scope))


def panel_org_table_filter(scope: AdminScope) -> ColumnElement:
    """Filter Organization rows for list endpoints (superadmin = all rows)."""
    if CAP_SCOPE_GLOBAL in scope.capabilities:
        return true()
    if not uses_invited_org_panel_scope(scope):
        return true()
    return panel_readable_org_condition(scope)


def invite_org_filter(scope: AdminScope, column: Any) -> ColumnElement:
    """SQLAlchemy filter for invite-tab org lists (includes teaching researcher invited scope)."""
    if CAP_SCOPE_INVITED_ORGS not in scope.capabilities:
        return org_filter(scope, column)
    if column is Organization.id:
        if CAP_SCOPE_GLOBAL in scope.capabilities:
            return panel_readable_org_condition(scope)
        return panel_org_table_filter(scope)
    return column.in_(panel_readable_org_id_subquery(scope))


def org_id_readable_in_panel_scope(
    scope: AdminScope,
    org_id: int,
    invited_by_user_id: int | None,
) -> bool:
    """Return True when org_id is readable for invited-org panel roles."""
    if not uses_invited_org_panel_scope(scope):
        return True
    invited_ids = scope.invited_org_ids if scope.invited_org_ids is not None else frozenset()
    if expert_invite_scope_only(scope):
        return int(org_id) in invited_ids
    if invited_by_user_id is None:
        return True
    return int(org_id) in invited_ids


def assert_resource_org_in_scope(
    scope: AdminScope,
    resource_org_id: int | None,
    lang: Language,
    resource_invited_by_user_id: int | None = None,
) -> None:
    """IDOR guard: resource must belong to an org in scope."""
    if CAP_SCOPE_ORG in scope.capabilities and scope.org_ids is not None:
        if resource_org_id is None or int(resource_org_id) not in scope.org_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=Messages.error("user_not_found", lang),
            )
        return
    if uses_invited_org_panel_scope(scope):
        if resource_org_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=Messages.error("user_not_found", lang),
            )
        if org_id_readable_in_panel_scope(
            scope,
            int(resource_org_id),
            resource_invited_by_user_id,
        ):
            return
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("user_not_found", lang),
        )
    if scope.org_ids is not None:
        if resource_org_id is None or int(resource_org_id) not in scope.org_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=Messages.error("user_not_found", lang),
            )


async def assert_panel_org_readable(
    scope: AdminScope,
    org_id: int,
    db: AsyncSession,
    lang: Language,
) -> None:
    """Load org invited_by and enforce panel read scope for BD / expert."""
    if not uses_invited_org_panel_scope(scope):
        return
    row = (await db.execute(select(Organization.invited_by_user_id).where(Organization.id == org_id))).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("organization_not_found", lang, org_id),
        )
    assert_resource_org_in_scope(
        scope,
        org_id,
        lang,
        resource_invited_by_user_id=row[0],
    )


async def assert_panel_user_readable(
    scope: AdminScope,
    user_organization_id: int | None,
    db: AsyncSession,
    lang: Language,
) -> None:
    """Ensure a user's org is readable under invited-org panel scope."""
    if not uses_invited_org_panel_scope(scope):
        return
    if user_organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("user_not_found", lang),
        )
    await assert_panel_org_readable(scope, int(user_organization_id), db, lang)
