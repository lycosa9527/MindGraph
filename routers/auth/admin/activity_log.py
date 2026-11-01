"""List privileged admin activity for system settings."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from routers.auth.dependencies import require_settings_admin_activities
from services.admin.activity_record import list_admin_activities
from utils.auth.admin_scope import AdminScope
from utils.db.session_open import system_rls_session

router = APIRouter()


class AdminActivityItem(BaseModel):
    """One privileged admin write."""

    id: int
    created_at: datetime
    actor_user_id: Optional[int] = None
    actor_role: str
    actor_label: str
    organization_id: Optional[int] = None
    action: str
    http_method: str
    path: str
    status_code: int
    detail: Optional[dict[str, Any]] = None
    client_ip: Optional[str] = None


class AdminActivityListResponse(BaseModel):
    """Paginated admin activity log."""

    items: list[AdminActivityItem]
    total: int
    page: int
    page_size: int
    total_pages: int = Field(ge=1)


@router.get("/admin/activity-log", response_model=AdminActivityListResponse)
async def get_admin_activity_log(
    _scope: AdminScope = Depends(require_settings_admin_activities),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    hours: int = Query(168, ge=1, le=24 * 366),
    action: Optional[str] = Query(None, max_length=80),
    role: Optional[str] = Query(None, max_length=32),
    q: Optional[str] = Query(None, max_length=80),
) -> AdminActivityListResponse:
    """Recent writes by superadmins, researchers, experts, and school managers."""
    async with system_rls_session() as db:
        payload = await list_admin_activities(
            db,
            page=page,
            page_size=page_size,
            hours=hours,
            action=action.strip() if action else None,
            role=role.strip() if role else None,
            query=q.strip() if q else None,
        )
    return AdminActivityListResponse.model_validate(payload)
