"""
Persist and list admin activity rows.

Writes use a system RLS session so a school manager's own panel context
can insert a row the superadmin later reads. Failures are logged and never
raised to the request that was being audited.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.admin_activity_log import AdminActivityLog
from services.admin.activity_catalog import resolve_admin_action
from services.utils.error_types import DATABASE_ERRORS
from utils.auth.admin_panel_permissions import is_management_panel_user
from utils.auth.env_superadmin import is_env_configured_superadmin
from utils.auth.request_helpers import get_client_ip
from utils.auth.role_constants import ROLE_SUPERADMIN, normalize_role
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

ADMIN_ACTIVITY_DETAIL_ATTR = "admin_activity_detail"
_DETAIL_CHAR_CAP = 4000
_RECORD_ERRORS = (
    *DATABASE_ERRORS,
    TypeError,
    AttributeError,
    KeyError,
)


def note_admin_activity(request: Any, detail: dict[str, Any]) -> None:
    """Attach structured detail for the middleware to store after a 2xx write."""
    state = getattr(request, "state", None)
    if state is None:
        return
    current = getattr(state, ADMIN_ACTIVITY_DETAIL_ATTR, None)
    if isinstance(current, dict):
        merged = dict(current)
        merged.update(detail)
        setattr(state, ADMIN_ACTIVITY_DETAIL_ATTR, merged)
        return
    setattr(state, ADMIN_ACTIVITY_DETAIL_ATTR, dict(detail))


def _actor_role(user: Any) -> str:
    """Panel role to store. Env-configured superadmins keep superadmin, not the DB role."""
    if is_env_configured_superadmin(user):
        return ROLE_SUPERADMIN
    return normalize_role(getattr(user, "role", None))[:32]


def _actor_label(user: Any) -> str:
    name = getattr(user, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()[:128]
    phone = getattr(user, "phone", None)
    if isinstance(phone, str) and phone.strip():
        return phone.strip()[:128]
    email = getattr(user, "email", None)
    if isinstance(email, str) and email.strip():
        return email.strip()[:128]
    return f"user:{getattr(user, 'id', '')}"[:128]


def _optional_int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _organization_id(user: Any, request: Any) -> Optional[int]:
    params = getattr(request, "query_params", None)
    if params is not None:
        from_query = _optional_int(params.get("organization_id"))
        if from_query is not None:
            return from_query
    return _optional_int(getattr(user, "organization_id", None))


def _request_detail(request: Any) -> Optional[dict[str, Any]]:
    state = getattr(request, "state", None)
    if state is None:
        return None
    detail = getattr(state, ADMIN_ACTIVITY_DETAIL_ATTR, None)
    if isinstance(detail, dict):
        return detail
    return None


def _cap_detail(detail: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not detail:
        return None
    encoded = str(detail)
    if len(encoded) <= _DETAIL_CHAR_CAP:
        return detail
    return {"truncated": True, "keys": [str(key) for key in list(detail.keys())[:40]]}


def _client_ip(request: Any) -> Optional[str]:
    ip = get_client_ip(request)
    if not ip:
        return None
    return ip[:64]


async def record_admin_activity(request: Any, response: Any, user: Any) -> None:
    """Store one row when a panel user completes an admin write. Never raises."""
    try:
        await _record_admin_activity(request, response, user)
    except _RECORD_ERRORS:
        logger.warning("Admin activity log write failed", exc_info=True)


async def _record_admin_activity(request: Any, response: Any, user: Any) -> None:
    if user is None or not is_management_panel_user(user):
        return
    status_code = getattr(response, "status_code", None)
    if not isinstance(status_code, int) or status_code < 200 or status_code >= 300:
        return
    method = str(getattr(request, "method", "") or "")
    path = str(getattr(getattr(request, "url", None), "path", "") or "")
    detail = _cap_detail(_request_detail(request))
    action = resolve_admin_action(method, path, detail)
    if action is None:
        return
    user_id = _optional_int(getattr(user, "id", None))
    row = AdminActivityLog(
        actor_user_id=user_id,
        actor_role=_actor_role(user),
        actor_label=_actor_label(user),
        organization_id=_organization_id(user, request),
        action=action[:80],
        http_method=method[:8],
        path=path[:512],
        status_code=status_code,
        detail=detail,
        client_ip=_client_ip(request),
    )
    async with system_rls_session() as db:
        db.add(row)
        await db.commit()


def _like_pattern(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def list_admin_activities(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    hours: int,
    action: Optional[str],
    role: Optional[str],
    query: Optional[str],
) -> dict[str, Any]:
    """Page recent admin activity rows. Caller supplies a system RLS session."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    filters = [AdminActivityLog.created_at >= since]
    if action:
        filters.append(AdminActivityLog.action == action[:80])
    if role:
        filters.append(AdminActivityLog.actor_role == normalize_role(role)[:32])
    if query:
        pattern = _like_pattern(query.strip()[:80])
        filters.append(
            or_(
                AdminActivityLog.actor_label.ilike(pattern, escape="\\"),
                AdminActivityLog.path.ilike(pattern, escape="\\"),
                AdminActivityLog.action.ilike(pattern, escape="\\"),
            )
        )
    total = int((await db.execute(select(func.count()).select_from(AdminActivityLog).where(*filters))).scalar_one())
    stmt = (
        select(AdminActivityLog)
        .where(*filters)
        .order_by(AdminActivityLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "items": [_row_dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def _row_dict(row: AdminActivityLog) -> dict[str, Any]:
    created = row.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return {
        "id": row.id,
        "created_at": created,
        "actor_user_id": row.actor_user_id,
        "actor_role": row.actor_role,
        "actor_label": row.actor_label,
        "organization_id": row.organization_id,
        "action": row.action,
        "http_method": row.http_method,
        "path": row.path,
        "status_code": row.status_code,
        "detail": row.detail,
        "client_ip": row.client_ip,
    }
