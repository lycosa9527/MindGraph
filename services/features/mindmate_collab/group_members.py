"""
Closed membership for a school seminar.

A room with rows here is a WeChat-style group: only those teachers can enter,
and anyone already inside can invite more colleagues. An empty table means the
room is still open to the school.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Mapping, Sequence

from sqlalchemy import delete, select

from models.domain.auth import Organization, User
from models.domain.mindmate_collab import MindmateCollabMember, MindmateCollabSession
from services.features.mindmate_collab.config import MINDMATE_COLLAB_MAX_PARTICIPANTS
from services.features.mindmate_collab.seminar_roles import (
    SEMINAR_ROLE_LEADER,
    SEMINAR_ROLE_OBSERVER,
    normalize_seminar_role,
    resolve_seminar_leader_id,
)
from services.utils.typing_helpers import result_rowcount
from utils.db.session_open import system_rls_session


def normalize_group_member_ids(owner_id: int, raw_ids: Sequence[int], limit: int) -> list[int]:
    """Owner first, then unique positive ids, capped at the room size."""
    ordered = [int(owner_id)]
    seen = {int(owner_id)}
    cap = max(int(limit), 1)
    for raw in raw_ids:
        try:
            user_id = int(raw)
        except (TypeError, ValueError):
            continue
        if user_id <= 0 or user_id in seen:
            continue
        if len(ordered) >= cap:
            break
        seen.add(user_id)
        ordered.append(user_id)
    return ordered


async def list_member_acceptance(session_id: str) -> dict[int, bool]:
    """Return accepted flag keyed by user id. Missing rows are not pending."""
    async with system_rls_session() as db:
        rows = await db.execute(
            select(MindmateCollabMember.user_id, MindmateCollabMember.accepted).where(
                MindmateCollabMember.session_id == session_id
            )
        )
        return {int(user_id): bool(accepted) for user_id, accepted in rows.all()}


async def accepted_member_ids(session_id: str) -> list[int]:
    """Members who may enter. Pending cross-school invites are excluded."""
    acceptance = await list_member_acceptance(session_id)
    return [user_id for user_id, accepted in acceptance.items() if accepted]


async def member_is_pending(session_id: str, user_id: int) -> bool:
    """True when this teacher was invited and has not agreed yet."""
    acceptance = await list_member_acceptance(session_id)
    return acceptance.get(int(user_id)) is False


async def external_invite_ids(
    organization_id: int | None,
    user_ids: Sequence[int],
    owner_id: int,
) -> set[int]:
    """Teachers outside the host school must agree before they can enter."""
    wanted = []
    seen: set[int] = set()
    for raw in user_ids:
        try:
            user_id = int(raw)
        except (TypeError, ValueError):
            continue
        if user_id <= 0 or user_id == int(owner_id) or user_id in seen:
            continue
        seen.add(user_id)
        wanted.append(user_id)
    if not wanted:
        return set()
    async with system_rls_session() as db:
        rows = await db.execute(select(User.id, User.organization_id).where(User.id.in_(wanted)))
    pending: set[int] = set()
    for user_id, org_id in rows.all():
        same_school = organization_id is not None and org_id is not None and int(org_id) == int(organization_id)
        if not same_school:
            pending.add(int(user_id))
    return pending


async def seminar_host_org_label(organization_id: int | None) -> str:
    """Display name of the school that owns the seminar."""
    if organization_id is None:
        return ""
    async with system_rls_session() as db:
        row = (
            await db.execute(
                select(Organization.display_name, Organization.name).where(Organization.id == int(organization_id))
            )
        ).one_or_none()
    if row is None:
        return ""
    display_name, name = row
    return str(display_name or name or "").strip()


async def list_group_member_ids(session_id: str) -> list[int]:
    """Return invited user ids. Empty means the seminar is not a closed group."""
    async with system_rls_session() as db:
        rows = await db.execute(
            select(MindmateCollabMember.user_id).where(MindmateCollabMember.session_id == session_id)
        )
        return [int(row[0]) for row in rows.all()]


async def user_is_accepted_member(session_id: str, user_id: int) -> bool:
    """True when this teacher has agreed to a seat in the seminar."""
    async with system_rls_session() as db:
        accepted = (
            await db.execute(
                select(MindmateCollabMember.accepted).where(
                    MindmateCollabMember.session_id == session_id,
                    MindmateCollabMember.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
    return accepted is True


async def member_seminar_role(session_id: str, user_id: int) -> str | None:
    """Return the stored seminar role, or None when this user has no seat."""
    async with system_rls_session() as db:
        role = (
            await db.execute(
                select(MindmateCollabMember.seminar_role).where(
                    MindmateCollabMember.session_id == session_id,
                    MindmateCollabMember.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
    if role is None:
        return None
    return str(role).strip()


async def user_observes_seminar(session_id: str, user_id: int) -> bool:
    """True when this seat is 观摩学习 and must stay read-only."""
    return await member_seminar_role(session_id, user_id) == SEMINAR_ROLE_OBSERVER


async def list_group_member_roles(session_id: str) -> dict[int, str]:
    """Return seminar_role keyed by user id for invited members."""
    async with system_rls_session() as db:
        rows = await db.execute(
            select(MindmateCollabMember.user_id, MindmateCollabMember.seminar_role).where(
                MindmateCollabMember.session_id == session_id
            )
        )
        return {int(user_id): normalize_seminar_role(role) for user_id, role in rows.all()}


async def seed_closed_group(
    session_id: str,
    owner_id: int,
    raw_ids: Sequence[int],
    roles_by_user: Mapping[int, str] | None = None,
    organization_id: int | None = None,
) -> list[int]:
    """Insert the owner and invited colleagues. Returns ids that were not already members."""
    wanted = normalize_group_member_ids(owner_id, raw_ids, MINDMATE_COLLAB_MAX_PARTICIPANTS)
    pending = await external_invite_ids(organization_id, wanted, owner_id)
    role_map = {int(key): normalize_seminar_role(value) for key, value in (roles_by_user or {}).items()}
    async with system_rls_session() as db:
        existing_rows = await db.execute(
            select(MindmateCollabMember.user_id).where(MindmateCollabMember.session_id == session_id)
        )
        existing = {int(row[0]) for row in existing_rows.all()}
        now = datetime.now(tz=UTC)
        inserted: list[int] = []
        for user_id in wanted:
            if user_id in existing:
                continue
            role = SEMINAR_ROLE_LEADER if user_id == int(owner_id) else role_map.get(user_id, SEMINAR_ROLE_OBSERVER)
            if user_id != int(owner_id) and role == SEMINAR_ROLE_LEADER:
                role = SEMINAR_ROLE_OBSERVER
            db.add(
                MindmateCollabMember(
                    session_id=session_id,
                    user_id=user_id,
                    joined_at=now,
                    seminar_role=role,
                    accepted=user_id not in pending,
                )
            )
            inserted.append(user_id)
        await db.commit()
    return inserted


async def repair_seminar_leader_roles(session_id: str, owner_user_id: int) -> int:
    """Among existing members, ensure exactly one leader; return that user id.

    Does not insert rows into an empty (open) group.
    """
    async with system_rls_session() as db:
        rows = (
            (await db.execute(select(MindmateCollabMember).where(MindmateCollabMember.session_id == session_id)))
            .scalars()
            .all()
        )
        if not rows:
            return int(owner_user_id)
        roles = {int(row.user_id): normalize_seminar_role(row.seminar_role) for row in rows}
        leader_id = resolve_seminar_leader_id(roles, owner_user_id)
        changed = False
        for row in rows:
            user_id = int(row.user_id)
            if user_id == leader_id:
                if normalize_seminar_role(row.seminar_role) != SEMINAR_ROLE_LEADER:
                    row.seminar_role = SEMINAR_ROLE_LEADER
                    changed = True
            elif normalize_seminar_role(row.seminar_role) == SEMINAR_ROLE_LEADER:
                row.seminar_role = SEMINAR_ROLE_OBSERVER
                changed = True
        if leader_id not in roles:
            # Owner missing from closed group — add them as leader.
            db.add(
                MindmateCollabMember(
                    session_id=session_id,
                    user_id=int(leader_id),
                    joined_at=datetime.now(tz=UTC),
                    seminar_role=SEMINAR_ROLE_LEADER,
                )
            )
            changed = True
        if changed:
            await db.commit()
        return int(leader_id)


async def set_group_member_role(session_id: str, user_id: int, role: str) -> bool:
    """Update one member's seminar role, creating the membership row when needed."""
    normalized = normalize_seminar_role(role)
    if normalized == SEMINAR_ROLE_LEADER:
        return await transfer_seminar_leadership(session_id, user_id)
    target = int(user_id)
    async with system_rls_session() as db:
        row = (
            await db.execute(
                select(MindmateCollabMember).where(
                    MindmateCollabMember.session_id == session_id,
                    MindmateCollabMember.user_id == target,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            db.add(
                MindmateCollabMember(
                    session_id=session_id,
                    user_id=target,
                    joined_at=datetime.now(tz=UTC),
                    seminar_role=normalized,
                )
            )
            await db.commit()
            return True
        if normalize_seminar_role(row.seminar_role) == SEMINAR_ROLE_LEADER:
            # Demote the current leader only via an explicit leadership transfer.
            return False
        row.seminar_role = normalized
        await db.commit()
    return True


async def transfer_seminar_leadership(session_id: str, new_leader_id: int) -> bool:
    """Make new_leader_id the sole leader; demote any previous leaders to observer."""
    target = int(new_leader_id)
    async with system_rls_session() as db:
        rows = (
            (await db.execute(select(MindmateCollabMember).where(MindmateCollabMember.session_id == session_id)))
            .scalars()
            .all()
        )
        if not rows:
            return False
        by_user = {int(row.user_id): row for row in rows}
        if target not in by_user:
            db.add(
                MindmateCollabMember(
                    session_id=session_id,
                    user_id=target,
                    joined_at=datetime.now(tz=UTC),
                    seminar_role=SEMINAR_ROLE_LEADER,
                )
            )
        else:
            by_user[target].seminar_role = SEMINAR_ROLE_LEADER
        for user_id, row in by_user.items():
            if user_id == target:
                continue
            if normalize_seminar_role(row.seminar_role) == SEMINAR_ROLE_LEADER:
                row.seminar_role = SEMINAR_ROLE_OBSERVER
        await db.commit()
    return True


async def actor_is_seminar_leader(
    session_id: str,
    owner_user_id: int,
    actor_user_id: int,
) -> bool:
    """True when the actor currently holds the seminar leader role."""
    roles = await list_group_member_roles(session_id)
    if not roles:
        return int(actor_user_id) == int(owner_user_id)
    leader_id = await repair_seminar_leader_roles(session_id, owner_user_id)
    return int(leader_id) == int(actor_user_id)


async def remove_group_member(session_id: str, user_id: int) -> bool:
    """Remove one invited member. Returns False when nothing was deleted."""
    async with system_rls_session() as db:
        result = await db.execute(
            delete(MindmateCollabMember).where(
                MindmateCollabMember.session_id == session_id,
                MindmateCollabMember.user_id == int(user_id),
            )
        )
        await db.commit()
        return result_rowcount(result) > 0


async def list_pending_seminar_invites(user_id: int) -> list[dict[str, str | int]]:
    """Basic seminar info for invites this teacher has not answered."""
    async with system_rls_session() as db:
        rows = (
            await db.execute(
                select(
                    MindmateCollabSession.id,
                    MindmateCollabSession.title,
                    MindmateCollabSession.visibility,
                    MindmateCollabSession.brief_topic,
                    MindmateCollabSession.owner_user_id,
                    User.name,
                    Organization.display_name,
                    Organization.name,
                )
                .join(
                    MindmateCollabSession,
                    MindmateCollabSession.id == MindmateCollabMember.session_id,
                )
                .join(User, User.id == MindmateCollabSession.owner_user_id)
                .outerjoin(Organization, Organization.id == MindmateCollabSession.organization_id)
                .where(
                    MindmateCollabMember.user_id == int(user_id),
                    MindmateCollabMember.accepted.is_(False),
                    MindmateCollabSession.ended_at.is_(None),
                )
            )
        ).all()
    invites: list[dict[str, str | int]] = []
    for session_id, title, visibility, topic, owner_id, owner_name, org_display, org_name in rows:
        invites.append(
            {
                "session_id": str(session_id),
                "title": (title or "").strip() or "MindMate Collab",
                "visibility": str(visibility or "organization"),
                "brief_topic": (topic or "").strip(),
                "from_name": (owner_name or "").strip() or "Teacher",
                "host_org": (org_display or org_name or "").strip(),
                "owner_user_id": int(owner_id),
            }
        )
    return invites


async def respond_seminar_invite(
    user_id: int,
    session_id: str,
    accept: bool,
) -> dict[str, str | int | bool] | None:
    """Agree or decline a pending invite. None when this user has no row."""
    async with system_rls_session() as db:
        row = (
            await db.execute(
                select(MindmateCollabMember).where(
                    MindmateCollabMember.session_id == session_id,
                    MindmateCollabMember.user_id == int(user_id),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        if not accept:
            await db.execute(
                delete(MindmateCollabMember).where(
                    MindmateCollabMember.session_id == session_id,
                    MindmateCollabMember.user_id == int(user_id),
                )
            )
            await db.commit()
            return {"accepted": False}
        session = (
            await db.execute(select(MindmateCollabSession).where(MindmateCollabSession.id == session_id))
        ).scalar_one_or_none()
        ended = session is None or session.ended_at is not None
        payload: dict[str, str | int | bool] = {"accepted": False, "ended": True}
        if session is not None and not ended:
            payload = {
                "accepted": True,
                "session_id": session.id,
                "code": session.code,
                "title": session.title,
                "visibility": session.visibility,
                "owner_user_id": int(session.owner_user_id),
            }
        row.accepted = True
        await db.commit()
        return payload
