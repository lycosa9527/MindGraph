"""
Resolve MindMate export targets (web MindMate + DingTalk MindBot Dify identities).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Dict, List, Optional, Set

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from repositories.dingtalk_staff_link_repo import DingtalkStaffLinkRepository
from repositories.mindbot_usage_repo import MindbotUsageRepository
from services.dify.export.export_config import USER_BATCH_SIZE
from services.dify.export.types import ExportScope, UserTarget
from services.mindbot.core.dify_user_id import mindbot_dify_user_id_for_chat
from utils.dify_mindmate_user_id import mindmate_dify_user_id

UNBOUND_STAFF_CAP = 500


@dataclass
class ExportTargetResult:
    """Resolved Dify identities plus export metadata."""

    targets: List[UserTarget] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    users_loaded: int = 0


def user_label(user: User) -> str:
    """Human-readable label for a user (name, else phone/email, else id)."""
    name = (getattr(user, "name", None) or "").strip()
    if name:
        return name
    phone = (getattr(user, "phone", None) or "").strip()
    if phone:
        return phone
    email = (getattr(user, "email", None) or "").strip()
    if email:
        return email
    return f"User {user.id}"


def _epoch_to_datetime(epoch: Optional[int]) -> datetime | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(int(epoch), UTC)


def _export_users_stmt(
    scope: ExportScope,
    org_id: Optional[int],
    user_ids: Optional[List[int]],
):
    stmt = select(User)
    if scope != "all":
        if org_id is None:
            return None
        stmt = stmt.where(User.organization_id == int(org_id))
    if scope == "users" and user_ids:
        stmt = stmt.where(User.id.in_(user_ids))
    return stmt.order_by(User.id.asc())


async def count_export_users(
    db: AsyncSession,
    scope: ExportScope,
    org_id: Optional[int],
    user_ids: Optional[List[int]],
) -> int:
    """Count MindGraph users matching export scope."""
    base = _export_users_stmt(scope, org_id, user_ids)
    if base is None:
        return 0
    stmt = select(func.count()).select_from(base.subquery())
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


async def load_export_users(
    db: AsyncSession,
    scope: ExportScope,
    org_id: Optional[int],
    user_ids: Optional[List[int]],
) -> List[User]:
    """Load all users in scope (stable ascending id order)."""
    base = _export_users_stmt(scope, org_id, user_ids)
    if base is None:
        return []
    rows = list((await db.execute(base)).scalars().all())
    return rows


async def load_export_users_page(
    db: AsyncSession,
    scope: ExportScope,
    org_id: Optional[int],
    user_ids: Optional[List[int]],
    *,
    after_user_id: Optional[int] = None,
    limit: int = USER_BATCH_SIZE,
) -> List[User]:
    """Load one page of users for batched export (ascending id, cursor after_user_id)."""
    base = _export_users_stmt(scope, org_id, user_ids)
    if base is None:
        return []
    stmt = base
    if after_user_id is not None:
        stmt = stmt.where(User.id > int(after_user_id))
    stmt = stmt.limit(max(1, limit))
    return list((await db.execute(stmt)).scalars().all())


def _mindbot_label(base: str, *, unbound: bool = False) -> str:
    if unbound:
        return f"{base} · DingTalk (unbound)"
    return f"{base} · DingTalk"


def _append_mindbot_target(
    targets: List[UserTarget],
    seen_dify: Set[str],
    *,
    organization_id: int,
    staff_id: str,
    user_id: Optional[int],
    label: str,
) -> None:
    staff = (staff_id or "").strip()
    if not staff:
        return
    dify_user = mindbot_dify_user_id_for_chat(organization_id, staff)
    if dify_user in seen_dify:
        return
    seen_dify.add(dify_user)
    targets.append(
        UserTarget(
            organization_id=organization_id,
            user_id=user_id,
            dify_user=dify_user,
            label=label,
            channel="mindbot",
        )
    )


async def _historical_staff_by_org(
    usage_repo: MindbotUsageRepository,
    users_by_org: Dict[int, List[User]],
) -> Dict[int, Dict[int, List[tuple[str, str | None]]]]:
    """Batch historical staff lookup per org (avoids N+1)."""
    out: Dict[int, Dict[int, List[tuple[str, str | None]]]] = {}
    for org_key, org_users in users_by_org.items():
        uid_list = [int(user.id) for user in org_users]
        out[org_key] = await usage_repo.distinct_staff_map_for_users(org_key, uid_list)
    return out


async def build_export_targets(
    db: AsyncSession,
    users: List[User],
    *,
    scope: ExportScope,
    org_id: Optional[int],
    start: Optional[int] = None,
    end: Optional[int] = None,
    include_unbound: bool = True,
) -> ExportTargetResult:
    """Expand users + org MindBot staff into web/mindbot Dify identities."""
    if not users and scope == "users":
        return ExportTargetResult(
            warnings=["no users matched the requested user_ids"],
            users_loaded=0,
        )

    link_repo = DingtalkStaffLinkRepository(db)
    usage_repo = MindbotUsageRepository(db)
    targets: List[UserTarget] = []
    warnings: List[str] = []
    seen_dify: Set[str] = set()
    covered_staff_by_org: Dict[int, Set[str]] = {}

    users_by_org: Dict[int, List[User]] = {}
    for user in users:
        org_raw = getattr(user, "organization_id", None)
        if org_raw is None:
            continue
        org_key = int(org_raw)
        users_by_org.setdefault(org_key, []).append(user)

    if scope == "all":
        link_map = await link_repo.map_for_users_all_orgs([int(user.id) for user in users])
    else:
        link_map = {}
        if org_id is not None:
            link_map = {
                (int(org_id), int(uid)): row
                for uid, row in (
                    await link_repo.map_for_users(int(org_id), [int(user.id) for user in users])
                ).items()
            }

    historical_by_org = await _historical_staff_by_org(usage_repo, users_by_org)

    for user in users:
        org_raw = getattr(user, "organization_id", None)
        if org_raw is None:
            continue
        org_key = int(org_raw)
        uid = int(user.id)
        label = user_label(user)
        web_dify = mindmate_dify_user_id(user)
        if web_dify not in seen_dify:
            seen_dify.add(web_dify)
            targets.append(
                UserTarget(
                    organization_id=org_key,
                    user_id=uid,
                    dify_user=web_dify,
                    label=label,
                    channel="web",
                )
            )

        if scope == "all":
            link = link_map.get((org_key, uid))
        else:
            link = link_map.get((org_key, uid)) if org_id is not None else None

        staff_ids: Set[str] = set()
        staff_labels: Dict[str, str] = {}

        if link is not None:
            staff = (link.dingtalk_staff_id or "").strip()
            if staff:
                staff_ids.add(staff)
                staff_labels[staff] = label

        for staff_id, nick in historical_by_org.get(org_key, {}).get(uid, []):
            staff_ids.add(staff_id)
            if staff_id not in staff_labels:
                staff_labels[staff_id] = (nick or label).strip() or staff_id

        for staff_id in staff_ids:
            display = staff_labels.get(staff_id, staff_id)
            _append_mindbot_target(
                targets,
                seen_dify,
                organization_id=org_key,
                staff_id=staff_id,
                user_id=uid,
                label=_mindbot_label(display),
            )
            covered_staff_by_org.setdefault(org_key, set()).add(staff_id)

    if not include_unbound:
        return ExportTargetResult(targets=targets, warnings=warnings, users_loaded=len(users))

    start_dt = _epoch_to_datetime(start)
    end_dt = _epoch_to_datetime(end)

    if scope == "whole" and org_id is not None:
        unbound = await usage_repo.distinct_unbound_staff_for_org(
            int(org_id),
            exclude_staff_ids=covered_staff_by_org.get(int(org_id), set()),
            start=start_dt,
            end=end_dt,
            limit=UNBOUND_STAFF_CAP,
        )
        if len(unbound) >= UNBOUND_STAFF_CAP:
            warnings.append(
                f"unbound_staff_capped: org={org_id} limit={UNBOUND_STAFF_CAP}"
            )
        for staff_id, nick in unbound:
            nick_label = (nick or staff_id).strip()
            _append_mindbot_target(
                targets,
                seen_dify,
                organization_id=int(org_id),
                staff_id=staff_id,
                user_id=None,
                label=_mindbot_label(nick_label, unbound=True),
            )
    elif scope == "all":
        unbound_rows = await usage_repo.distinct_unbound_staff_all_orgs(
            exclude_staff_by_org=covered_staff_by_org,
            start=start_dt,
            end=end_dt,
            limit=UNBOUND_STAFF_CAP,
        )
        if len(unbound_rows) >= UNBOUND_STAFF_CAP:
            warnings.append(f"unbound_staff_capped: platform limit={UNBOUND_STAFF_CAP}")
        for org_key, staff_id, nick in unbound_rows:
            nick_label = (nick or staff_id).strip()
            _append_mindbot_target(
                targets,
                seen_dify,
                organization_id=org_key,
                staff_id=staff_id,
                user_id=None,
                label=_mindbot_label(nick_label, unbound=True),
            )

    return ExportTargetResult(
        targets=targets,
        warnings=warnings,
        users_loaded=len(users),
    )


def export_scope_label(scope: ExportScope, org_id: Optional[int], user_count: int) -> str:
    """Short scope description for audit logs and export headers."""
    if scope == "all":
        return f"platform-all ({user_count} users, web+mindbot)"
    if scope == "users":
        if user_count == 1:
            return f"org-{org_id}-single-user (web+mindbot)"
        return f"org-{org_id}-multi-user ({user_count} users, web+mindbot)"
    return f"org-{org_id}-whole ({user_count} users, web+mindbot)"
