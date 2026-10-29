"""
MindMate collab session manager — start, stop, join, list.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any, Dict, List, Mapping, Optional, Tuple
from uuid import uuid4

from redis.exceptions import RedisError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from models.domain.auth import User
from models.domain.mindmate_seminar import MindmateSeminarMember, MindmateSeminarSession
from services.auth.expert_live_scope import bound_org_label
from services.auth.expert_school_binding import bound_org_ids_for_user
from services.features.mindmate_seminar.config import (
    MINDMATE_COLLAB_CLOSING_TTL_SEC,
    MINDMATE_COLLAB_DEFAULT_DURATION,
    MINDMATE_COLLAB_MAX_LIVE_SECONDS,
    MINDMATE_COLLAB_MAX_ORG_CONCURRENT_SESSIONS,
    MINDMATE_COLLAB_MAX_PARTICIPANTS,
    MINDMATE_COLLAB_PARTICIPANTS_TTL,
)
from services.features.mindmate_seminar.dify_identity import (
    read_seminar_dify_conversation,
    seminar_dify_conversation_ref,
)
from services.features.mindmate_seminar.dify_stream_control import abort_dify_stream
from services.features.mindmate_seminar.group_members import (
    accepted_member_ids,
    actor_is_seminar_leader,
    list_invited_member_ids,
    seed_closed_group,
    seminar_room_is_closed,
)
from services.features.mindmate_seminar.member_record import record_collab_member
from services.features.mindmate_seminar.message_cursor import remember_latest_collab_message_id
from services.features.mindmate_seminar.message_history import (
    CollabHistoryPage,
    PersistedCollabMessage,
    fetch_session_message_page,
    insert_collab_message,
    normalize_seed_messages,
    persist_seed_messages,
)
from services.features.mindmate_seminar.org_listing import list_visible_org_sessions
from services.features.mindmate_seminar.participant_ops import refresh_participant_ttl_for_code
from services.features.mindmate_seminar.redis_keys import (
    async_purge_session_redis_keys,
    closing_key,
    code_to_session_key,
    idle_scores_key,
    normalize_collab_code,
    participants_key,
    registry_keys_for_visibility,
    session_meta_key,
    start_lock_key,
)
from services.features.mindmate_seminar.visibility import user_may_join_mindmate_seminar
from services.features.mindmate_seminar.ws_broadcast import broadcast_to_all
from services.online_collab.core.online_collab_code import (
    _allocate_unique_online_collab_code,
    generate_online_collab_code,
)
from services.online_collab.lifecycle.online_collab_expiry import (
    compute_online_collab_expires_at,
    duration_allowed_for_visibility,
    expires_at_to_unix,
)
from services.online_collab.lifecycle.online_collab_visibility_helpers import (
    ONLINE_COLLAB_VISIBILITY_NETWORK,
    ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
)
from services.online_collab.redis.online_collab_redis_locks import (
    acquire_nx_lock,
    new_lock_token,
    release_nx_lock,
)
from services.online_collab.redis.online_collab_redis_scripts import (
    JOIN_CAP_SCRIPT_NAME,
    evalsha_with_reload,
)
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS
from services.utils.typing_helpers import redis_hset_mapping
from utils.db.session_open import system_rls_session, user_rls_session

logger = logging.getLogger(__name__)


class MindmateSeminarManager:
    """Orchestrates MindMate shared chatroom sessions."""

    async def _count_live_org_sessions(self, org_id: int) -> int:
        """Count live organization-visible rooms for one org (host End sets ended_at)."""
        async with system_rls_session() as db:
            result = await db.execute(
                select(func.count())
                .select_from(MindmateSeminarSession)
                .where(
                    MindmateSeminarSession.organization_id == org_id,
                    MindmateSeminarSession.visibility == ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
                    MindmateSeminarSession.ended_at.is_(None),
                ),
            )
            return int(result.scalar_one() or 0)

    async def stop_hosted_sessions_for_user(self, user_id: int) -> int:
        """Stop every live session hosted by user_id; return count stopped."""
        stopped = 0
        async with user_rls_session(user_id) as db:
            result = await db.execute(
                select(MindmateSeminarSession).where(
                    MindmateSeminarSession.owner_user_id == user_id,
                    MindmateSeminarSession.ended_at.is_(None),
                ),
            )
            rows = result.scalars().all()
        for row in rows:
            if await self.stop_session(row.id, user_id, reason="single_host"):
                stopped += 1
        return stopped

    async def start_session(
        self,
        user_id: int,
        *,
        visibility: str = ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
        title: Optional[str] = None,
        duration: str = MINDMATE_COLLAB_DEFAULT_DURATION,
        seed_messages: Optional[List[Dict[str, Any]]] = None,
        member_user_ids: Optional[List[int]] = None,
        member_roles: Optional[Mapping[int, str]] = None,
        brief_topic: Optional[str] = None,
        brief_goals: Optional[List[str]] = None,
        close_group: bool = False,
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Create a MindMate collab room; return (payload, error message)."""
        if not duration_allowed_for_visibility(visibility, duration):
            return None, "Invalid duration for this visibility mode"

        redis = get_async_redis()
        if not redis:
            return None, "Collaboration service unavailable"

        lock_token = new_lock_token()
        lock_key = start_lock_key(user_id)
        acquired = await acquire_nx_lock(redis, lock_key, 30, lock_token)
        if not acquired:
            return None, "Please retry starting the room"

        try:
            async with user_rls_session(user_id) as db:
                user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
                if not user:
                    return None, "User not found"

                org_id = user.organization_id
                bound_org_ids = await bound_org_ids_for_user(db, user)
                if visibility == ONLINE_COLLAB_VISIBILITY_ORGANIZATION and org_id is not None:
                    live_count = await self._count_live_org_sessions(org_id)
                    if live_count >= MINDMATE_COLLAB_MAX_ORG_CONCURRENT_SESSIONS:
                        return None, (
                            "Organization has reached the maximum of "
                            f"{MINDMATE_COLLAB_MAX_ORG_CONCURRENT_SESSIONS} "
                            "concurrent seminar rooms"
                        )

                started_at = datetime.now(tz=UTC)
                expires_at = compute_online_collab_expires_at(started_at, duration)
                session_id = str(uuid4())
                code: Optional[str] = None

                for _ in range(5):
                    candidate = await _allocate_unique_online_collab_code(redis)
                    if not candidate:
                        candidate = generate_online_collab_code()
                    topic = (brief_topic or title or "").strip()[:200] or None
                    goals_raw = [str(item).strip() for item in (brief_goals or []) if str(item).strip()][:20]
                    goals_json = json.dumps(goals_raw, ensure_ascii=False) if goals_raw else None
                    row = MindmateSeminarSession(
                        id=session_id,
                        code=candidate,
                        organization_id=org_id,
                        owner_user_id=user_id,
                        title=(title or topic or "MindMate Collab").strip()[:200] or "MindMate Collab",
                        brief_topic=topic,
                        brief_goals=goals_json,
                        visibility=visibility,
                        duration_preset=duration,
                        started_at=started_at,
                        expires_at=expires_at,
                    )
                    db.add(row)
                    try:
                        await db.commit()
                        code = candidate
                        break
                    except IntegrityError:
                        await db.rollback()
                        session_id = str(uuid4())

                if not code:
                    return None, "Could not allocate room code"

                normalized_seed, seed_error = normalize_seed_messages(seed_messages or [], user_id)
                if seed_error:
                    return None, seed_error
                if normalized_seed:
                    await persist_seed_messages(db, session_id, normalized_seed)

            # Public rooms are always a closed group. School colleagues are
            # accepted immediately; teachers outside the host school stay pending.
            if code and (close_group or member_user_ids or visibility == ONLINE_COLLAB_VISIBILITY_NETWORK):
                await seed_closed_group(
                    session_id,
                    user_id,
                    member_user_ids or [],
                    roles_by_user=member_roles,
                    organization_id=org_id,
                )

            redis_ok = await self._write_redis_session(
                code=code,
                session_id=session_id,
                owner_id=user_id,
                owner_name=user.name or user.phone or user.email or str(user_id),
                org_id=org_id,
                bound_org_ids=bound_org_ids,
                title=(title or "").strip() or "MindMate Collab",
                visibility=visibility,
                expires_at=expires_at,
            )
            if not redis_ok:
                async with system_rls_session() as db:
                    await db.execute(
                        update(MindmateSeminarSession)
                        .where(MindmateSeminarSession.id == session_id)
                        .values(ended_at=datetime.now(tz=UTC)),
                    )
                    await db.commit()
                return None, "Collaboration service unavailable"
            await record_collab_member(session_id, user_id)
            return {
                "session_id": session_id,
                "code": code,
                "visibility": visibility,
                "title": (title or "").strip() or "MindMate Collab",
                "owner_user_id": user_id,
                "expires_at": expires_at.isoformat() + "Z",
            }, None
        finally:
            await release_nx_lock(redis, lock_key, lock_token)

    async def _write_redis_session(
        self,
        *,
        code: str,
        session_id: str,
        owner_id: int,
        owner_name: str,
        org_id: Optional[int],
        title: str,
        visibility: str,
        expires_at: datetime,
        bound_org_ids: Optional[List[int]] = None,
        dify_conversation_id: Optional[str] = None,
        started_at: Optional[datetime] = None,
    ) -> bool:
        redis = get_async_redis()
        if not redis:
            return False
        norm = normalize_collab_code(code)
        now = int(time.time())
        exp_unix = expires_at_to_unix(expires_at)
        ttl = MINDMATE_COLLAB_MAX_LIVE_SECONDS
        if started_at is None:
            started_label = str(now)
        else:
            stamp = started_at if started_at.tzinfo is not None else started_at.replace(tzinfo=UTC)
            started_label = str(int(stamp.timestamp()))
        meta = {
            "session_id": session_id,
            "owner_id": str(owner_id),
            "owner_name": owner_name,
            "org_id": str(org_id) if org_id is not None else "",
            "bound_org_ids": bound_org_label(org_id, bound_org_ids or []),
            "title": title,
            "visibility": visibility,
            "expires_at": str(exp_unix),
            "last_activity": str(now),
            "started_at": started_label,
            "dify_conversation_id": (dify_conversation_id or "").strip(),
        }
        try:
            pipe = redis.pipeline()
            pipe.hset(session_meta_key(norm), mapping=redis_hset_mapping(meta))
            pipe.expire(session_meta_key(norm), ttl)
            pipe.set(code_to_session_key(norm), session_id, ex=ttl)
            pipe.zadd(idle_scores_key(), {norm: now})
            for reg in registry_keys_for_visibility(org_id, visibility, bound_org_ids):
                pipe.sadd(reg, norm)
            await pipe.execute()
        except REDIS_ERRORS as exc:
            logger.warning("[MindmateSeminar] Redis session write failed code=%s: %s", norm, exc)
            return False
        return True

    async def count_live_org_sessions(self, org_id: int) -> int:
        """Count non-expired organization-visible rooms for one org."""
        return await self._count_live_org_sessions(org_id)

    async def publish_live_room(
        self,
        *,
        code: str,
        session_id: str,
        owner_id: int,
        owner_name: str,
        org_id: Optional[int],
        title: str,
        visibility: str,
        expires_at: datetime,
        bound_org_ids: Optional[List[int]] = None,
        dify_conversation_id: Optional[str] = None,
        started_at: Optional[datetime] = None,
    ) -> bool:
        """Write Redis keys so an existing seminar row is joinable again."""
        redis = get_async_redis()
        if not redis:
            return False
        try:
            await redis.delete(closing_key(normalize_collab_code(code)))
        except REDIS_ERRORS:
            return False
        return await self._write_redis_session(
            code=code,
            session_id=session_id,
            owner_id=owner_id,
            owner_name=owner_name,
            org_id=org_id,
            bound_org_ids=bound_org_ids,
            title=title,
            visibility=visibility,
            expires_at=expires_at,
            dify_conversation_id=dify_conversation_id,
            started_at=started_at,
        )

    async def load_session_by_code(self, code: str) -> Optional[MindmateSeminarSession]:
        """Load an active session row by invite code."""
        norm = normalize_collab_code(code)
        async with system_rls_session() as db:
            result = await db.execute(
                select(MindmateSeminarSession).where(
                    MindmateSeminarSession.code == norm,
                    MindmateSeminarSession.ended_at.is_(None),
                ),
            )
            return result.scalar_one_or_none()

    async def load_session_by_id(self, session_id: str) -> Optional[MindmateSeminarSession]:
        """Load an active session row by session id."""
        async with system_rls_session() as db:
            result = await db.execute(
                select(MindmateSeminarSession).where(
                    MindmateSeminarSession.id == session_id,
                    MindmateSeminarSession.ended_at.is_(None),
                ),
            )
            return result.scalar_one_or_none()

    async def load_session_by_id_any(self, session_id: str) -> Optional[MindmateSeminarSession]:
        """Load a session row by id, including ended rooms (history API)."""
        async with system_rls_session() as db:
            result = await db.execute(
                select(MindmateSeminarSession).where(MindmateSeminarSession.id == session_id),
            )
            return result.scalar_one_or_none()

    async def session_accepts_chat(self, code: str) -> bool:
        """Return False when the room is closing or no longer live."""
        if await self.session_is_closing(code):
            return False
        return await self.load_session_by_code(code) is not None

    async def join_by_code(
        self,
        user_id: int,
        code: str,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Validate join permissions and return (payload, error).

        ``not_found`` means the invite code is not a live room. ``still_live``
        means the row is still open but a stop is in progress, so the caller
        must not archive it. ``forbidden`` means the room is live and this
        person may not enter.
        """
        session = await self.load_session_by_code(code)
        if not session:
            return None, "not_found"
        # Duration presets are advisory. A live row ends when the host stops it or it passes 30 days.
        if await self.session_is_closing(session.code):
            return None, "still_live"
        if not await self._validate_join_permissions(session, user_id):
            return None, "forbidden"
        return await self._session_payload(session), None

    async def _closed_group_allows(self, session: MindmateSeminarSession, user_id: int) -> bool:
        """Open school rooms stay open. Invited rooms and public rooms use the roster."""
        if not await seminar_room_is_closed(session.id, session.visibility):
            return True
        if int(user_id) == int(session.owner_user_id):
            return True
        invited = {int(item) for item in await list_invited_member_ids(session.id)}
        accepted = {int(item) for item in await accepted_member_ids(session.id)}
        return int(user_id) in invited and int(user_id) in accepted

    async def _validate_join_permissions(
        self,
        session: MindmateSeminarSession,
        user_id: int,
    ) -> bool:
        """Return True when the user may join; participant registration happens on WS connect."""
        if await self.session_is_closing(session.code):
            return False
        if not await self._closed_group_allows(session, user_id):
            return False
        async with user_rls_session(user_id, organization_id=session.organization_id) as db:
            allowed = await user_may_join_mindmate_seminar(
                db,
                visibility=session.visibility,
                owner_user_id=session.owner_user_id,
                owner_org_id=session.organization_id,
                joiner_id=user_id,
            )
        if not allowed and session.visibility != ONLINE_COLLAB_VISIBILITY_NETWORK:
            return False
        return True

    async def join_by_session_id(self, user_id: int, session_id: str) -> Optional[Dict[str, Any]]:
        """Validate org-room join permissions and return session payload."""
        session = await self.load_session_by_id(session_id)
        if not session:
            return None
        if session.visibility != ONLINE_COLLAB_VISIBILITY_ORGANIZATION:
            return None
        if not await self._validate_join_permissions(session, user_id):
            return None
        return await self._session_payload(session)

    async def user_may_connect(self, user_id: int, session: MindmateSeminarSession) -> bool:
        """Return True when user may open a WebSocket to this room."""
        # Duration presets are advisory; a seminar ends only when its leader stops it.
        if not await self._closed_group_allows(session, user_id):
            return False
        if await seminar_room_is_closed(session.id, session.visibility):
            return True
        async with user_rls_session(user_id, organization_id=session.organization_id) as db:
            return await user_may_join_mindmate_seminar(
                db,
                visibility=session.visibility,
                owner_user_id=session.owner_user_id,
                owner_org_id=session.organization_id,
                joiner_id=user_id,
            )

    async def _session_payload(self, session: MindmateSeminarSession) -> Dict[str, Any]:
        count = await self.participant_count(session.code)
        goals: list[str] = []
        if session.brief_goals:
            try:
                parsed = json.loads(session.brief_goals)
            except (TypeError, ValueError, json.JSONDecodeError):
                parsed = []
            if isinstance(parsed, list):
                goals = [str(item).strip() for item in parsed if str(item).strip()]
        return {
            "session_id": session.id,
            "code": session.code,
            "title": session.title,
            "brief_topic": (session.brief_topic or "").strip() or None,
            "brief_goals": goals,
            "visibility": session.visibility,
            "owner_user_id": session.owner_user_id,
            "organization_id": session.organization_id,
            "participant_count": count,
            "expires_at": session.expires_at.isoformat() + "Z" if session.expires_at else None,
        }

    async def update_session_title(
        self,
        session_id: str,
        actor_user_id: int,
        title: str,
    ) -> Optional[Dict[str, Any]]:
        """Rename a live seminar. Only the host may change the title."""
        cleaned = (title or "").strip()[:200]
        if not cleaned:
            return None
        async with system_rls_session() as db:
            session = (
                await db.execute(
                    select(MindmateSeminarSession).where(MindmateSeminarSession.id == session_id),
                )
            ).scalar_one_or_none()
            if session is None or session.ended_at is not None:
                return None
            if int(session.owner_user_id) != int(actor_user_id):
                return None
            session.title = cleaned
            await db.commit()
            await db.refresh(session)
        return await self._session_payload(session)

    async def _host_stop_already_settled(
        self,
        session_id: str,
        actor_user_id: int,
        reason: str,
    ) -> bool:
        """True when the host retries stop after the room is already ended."""
        if reason not in {"owner", "single_host"}:
            return False
        async with system_rls_session() as db:
            session = (
                await db.execute(
                    select(MindmateSeminarSession).where(MindmateSeminarSession.id == session_id),
                )
            ).scalar_one_or_none()
        if session is None or session.ended_at is None:
            return False
        return session.owner_user_id == actor_user_id

    async def stop_session(
        self,
        session_id: str,
        actor_user_id: int,
        *,
        reason: str = "owner",
    ) -> bool:
        """End a session, notify clients, and purge Redis keys."""
        system_reasons = frozenset({"expired"})
        if reason in system_reasons:
            async with system_rls_session() as db:
                session = (
                    await db.execute(
                        select(MindmateSeminarSession).where(MindmateSeminarSession.id == session_id),
                    )
                ).scalar_one_or_none()
                if not session or session.ended_at is not None:
                    return False
                code = session.code
                org_id = session.organization_id
                visibility = session.visibility
        else:
            async with system_rls_session() as db:
                session = (
                    await db.execute(
                        select(MindmateSeminarSession).where(MindmateSeminarSession.id == session_id),
                    )
                ).scalar_one_or_none()
                if not session:
                    return await self._host_stop_already_settled(
                        session_id,
                        actor_user_id,
                        reason,
                    )
                if session.ended_at is not None:
                    if reason not in {"owner", "single_host"}:
                        return False
                    if session.owner_user_id == actor_user_id:
                        return True
                    return await actor_is_seminar_leader(
                        session_id,
                        session.owner_user_id,
                        actor_user_id,
                    )
                if reason == "owner":
                    is_leader = await actor_is_seminar_leader(
                        session_id,
                        session.owner_user_id,
                        actor_user_id,
                    )
                    if not is_leader:
                        return False
                code = session.code
                org_id = session.organization_id
                visibility = session.visibility

        await abort_dify_stream(code)
        redis = get_async_redis()
        if redis:
            await redis.set(closing_key(code), "1", ex=MINDMATE_COLLAB_CLOSING_TTL_SEC)

        ended_at = datetime.now(tz=UTC)
        async with system_rls_session() as db:
            await db.execute(
                update(MindmateSeminarSession)
                .where(MindmateSeminarSession.id == session_id)
                .values(
                    ended_at=ended_at,
                    library_saved_at=func.coalesce(
                        MindmateSeminarSession.library_saved_at,
                        ended_at,
                    ),
                ),
            )
            await db.commit()

        await broadcast_to_all(code, {"type": "session_closing"})

        if reason in ("owner", "single_host"):
            await broadcast_to_all(code, {"type": "session_ended_shutdown"})
        else:
            await broadcast_to_all(code, {"type": "room_idle_shutdown"})
        if redis:
            await async_purge_session_redis_keys(redis, code, org_id, visibility)
        return True

    async def list_org_sessions(
        self,
        user_id: int,
        organization_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """List live organization-visible rooms for the viewer's org."""
        return await list_visible_org_sessions(
            user_id,
            organization_id=organization_id,
            participant_counts_fn=self.participant_counts_for_codes,
        )

    async def get_status(self, code: str) -> Optional[Dict[str, Any]]:
        """Return live session metadata for a code, or live=False when absent."""
        session = await self.load_session_by_code(code)
        if not session:
            return {"live": False, "code": normalize_collab_code(code)}
        return {
            "live": True,
            "code": session.code,
            "session_id": session.id,
            "title": session.title,
            "visibility": session.visibility,
            "participant_count": await self.participant_count(session.code),
            "expires_at": session.expires_at.isoformat() + "Z" if session.expires_at else None,
            "owner_user_id": session.owner_user_id,
        }

    async def get_hosted_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Return payload for the user's newest live hosted session, if any."""
        async with user_rls_session(user_id) as db:
            session = (
                await db.execute(
                    select(MindmateSeminarSession)
                    .where(
                        MindmateSeminarSession.owner_user_id == user_id,
                        MindmateSeminarSession.ended_at.is_(None),
                    )
                    .order_by(MindmateSeminarSession.started_at.desc())
                    .limit(1),
                )
            ).scalar_one_or_none()
        if not session:
            return None
        return await self._session_payload(session)

    async def list_accessible_live_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """Live rooms this user hosts, plus rooms they have already agreed to join."""
        async with user_rls_session(user_id) as db:
            owned = (
                (
                    await db.execute(
                        select(MindmateSeminarSession)
                        .where(
                            MindmateSeminarSession.owner_user_id == user_id,
                            MindmateSeminarSession.ended_at.is_(None),
                        )
                        .order_by(MindmateSeminarSession.started_at.desc()),
                    )
                )
                .scalars()
                .all()
            )
        async with system_rls_session() as db:
            joined = (
                (
                    await db.execute(
                        select(MindmateSeminarSession)
                        .join(
                            MindmateSeminarMember,
                            MindmateSeminarMember.session_id == MindmateSeminarSession.id,
                        )
                        .where(
                            MindmateSeminarMember.user_id == user_id,
                            MindmateSeminarMember.accepted.is_(True),
                            MindmateSeminarMember.left_at.is_(None),
                            MindmateSeminarSession.ended_at.is_(None),
                            MindmateSeminarSession.owner_user_id != user_id,
                        )
                        .order_by(MindmateSeminarSession.started_at.desc()),
                    )
                )
                .scalars()
                .all()
            )
        payloads: List[Dict[str, Any]] = []
        for session in list(owned) + list(joined):
            payloads.append(await self._session_payload(session))
        return payloads

    async def session_is_closing(self, code: str) -> bool:
        """True when the room is in a stop/teardown window and must reject new joins."""
        redis = get_async_redis()
        if not redis:
            return True
        norm = normalize_collab_code(code)
        try:
            raw = await redis.get(closing_key(norm))
        except REDIS_ERRORS:
            return True
        return raw is not None and raw not in (b"", "", b"0", "0")

    async def refresh_participant_ttl(self, code: str, user_id: int) -> None:
        """Slide participant HASH field TTL on ping/chat activity."""
        await refresh_participant_ttl_for_code(code, user_id)

    async def participant_count(self, code: str) -> int:
        """Return the number of registered Redis participants for a room."""
        counts = await self.participant_counts_for_codes([code])
        return counts.get(normalize_collab_code(code), 0)

    async def participant_counts_for_codes(self, codes: List[str]) -> Dict[str, int]:
        """Return participant counts for many room codes in one Redis pipeline."""
        redis = get_async_redis()
        if not redis or not codes:
            return {}
        norm_codes = [normalize_collab_code(code) for code in codes]
        try:
            pipe = redis.pipeline(transaction=False)
            for norm in norm_codes:
                pipe.hlen(participants_key(norm))
            raw_counts = await pipe.execute()
        except (RedisError, OSError, RuntimeError, TypeError, ValueError):
            return {}
        out: Dict[str, int] = {}
        for norm, raw in zip(norm_codes, raw_counts):
            try:
                out[norm] = int(raw or 0)
            except (TypeError, ValueError):
                out[norm] = 0
        return out

    async def resolve_dify_conversation_id(
        self,
        code: str,
        fallback: Optional[str] = None,
    ) -> Optional[str]:
        """Return the Dify conversation id, without the server prefix."""
        meta = await self.get_session_meta(code)
        stored = (meta.get("dify_conversation_id") or "").strip() or (fallback or "")
        raw, _server = read_seminar_dify_conversation(stored)
        return raw or None

    async def add_participant(self, code: str, user_id: int) -> bool:
        """Register participant in Redis; return False when room is at capacity."""
        redis = get_async_redis()
        if not redis:
            return False
        norm = normalize_collab_code(code)
        key = participants_key(norm)
        member = str(user_id)
        join_ts = str(int(time.time()))
        try:
            result = await evalsha_with_reload(
                redis,
                JOIN_CAP_SCRIPT_NAME,
                1,
                key,
                member,
                str(MINDMATE_COLLAB_MAX_PARTICIPANTS),
                str(MINDMATE_COLLAB_PARTICIPANTS_TTL),
                join_ts,
            )
        except (RedisError, TypeError, AttributeError, RuntimeError, OSError) as exc:
            logger.warning("[MindmateSeminar] Participant cap check failed: %s", exc)
            return False
        if result == -1:
            logger.warning(
                "[MindmateSeminar] Room full code=%s max=%s",
                norm,
                MINDMATE_COLLAB_MAX_PARTICIPANTS,
            )
            return False
        await self.touch_activity(code)
        return True

    async def remove_participant(self, code: str, user_id: int) -> None:
        """Remove a user from the room participant set."""
        redis = get_async_redis()
        if not redis:
            return
        norm = normalize_collab_code(code)
        try:
            await redis.hdel(participants_key(norm), str(user_id))
            await self.touch_activity(code)
        except REDIS_ERRORS:
            pass

    async def is_participant(self, code: str, user_id: int) -> bool:
        """Return True when user_id is in the room participant set."""
        redis = get_async_redis()
        if not redis:
            return False
        norm = normalize_collab_code(code)
        try:
            return bool(await redis.hexists(participants_key(norm), str(user_id)))
        except REDIS_ERRORS:
            return False

    async def list_participant_user_ids(self, code: str) -> List[int]:
        """Return user ids currently registered in the room participant hash."""
        redis = get_async_redis()
        if not redis:
            return []
        norm = normalize_collab_code(code)
        try:
            raw_ids = await redis.hkeys(participants_key(norm))
        except REDIS_ERRORS:
            return []
        out: List[int] = []
        for raw in raw_ids or []:
            text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
            try:
                out.append(int(text))
            except (TypeError, ValueError):
                continue
        return out

    async def touch_activity(self, code: str) -> None:
        """Update last-activity timestamps and idle-monitor scores for a room."""
        redis = get_async_redis()
        if not redis:
            return
        norm = normalize_collab_code(code)
        meta_key = session_meta_key(norm)
        try:
            room_alive = await redis.hexists(meta_key, "session_id")
        except REDIS_ERRORS:
            return
        if not room_alive:
            try:
                await redis.zrem(idle_scores_key(), norm)
            except REDIS_ERRORS:
                pass
            return
        now = int(time.time())
        # Slide the live keys out to the 30-day cap. The duration preset does not set this.
        safety_ttl_sec = MINDMATE_COLLAB_MAX_LIVE_SECONDS
        try:
            pipe = redis.pipeline(transaction=False)
            pipe.hset(meta_key, "last_activity", str(now))
            pipe.zadd(idle_scores_key(), {norm: now})
            pipe.expire(meta_key, safety_ttl_sec)
            pipe.expire(code_to_session_key(norm), safety_ttl_sec)
            await pipe.execute()
        except REDIS_ERRORS:
            pass

    async def fetch_message_page(
        self,
        session_id: str,
        limit: int | None = None,
        after_id: int | None = None,
        before_id: int | None = None,
    ) -> CollabHistoryPage:
        """Return one history page and whether another page exists in that direction."""
        async with system_rls_session() as db:
            return await fetch_session_message_page(
                db,
                session_id,
                limit=limit,
                after_id=after_id,
                before_id=before_id,
            )

    async def fetch_message_history(
        self,
        session_id: str,
        limit: int | None = None,
        after_id: int | None = None,
        before_id: int | None = None,
    ) -> List[Dict[str, Any]]:
        """Return persisted chat messages for a session, optionally after an id."""
        page = await self.fetch_message_page(
            session_id,
            limit=limit,
            after_id=after_id,
            before_id=before_id,
        )
        return page.messages

    async def persist_message(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        sender_user_id: Optional[int],
        room_code: Optional[str] = None,
    ) -> PersistedCollabMessage:
        """Insert a chat message row and return its id plus the previous room id."""
        async with system_rls_session() as db:
            saved = await insert_collab_message(
                db,
                session_id,
                role=role,
                content=content,
                sender_user_id=sender_user_id,
            )
        if room_code:
            await remember_latest_collab_message_id(room_code, saved.id)
        return saved

    async def resolve_dify_conversation_server(
        self,
        code: str,
        fallback: Optional[str] = None,
    ) -> Optional[int]:
        """Return the Dify server stored on the conversation id, then the Redis field."""
        meta = await self.get_session_meta(code)
        _raw, server = read_seminar_dify_conversation(meta.get("dify_conversation_id"))
        if server is not None:
            return server
        field = (meta.get("dify_conversation_server") or "").strip()
        if field.isdigit():
            value = int(field)
            if value >= 1:
                return value
        _raw, server = read_seminar_dify_conversation(fallback)
        return server

    async def set_dify_conversation_id(
        self,
        session_id: str,
        conversation_id: str,
        *,
        server: Optional[int] = None,
    ) -> None:
        """Persist ``s{server}:{id}`` in PostgreSQL and Redis session meta."""
        stored = seminar_dify_conversation_ref(conversation_id, server)
        async with system_rls_session() as db:
            await db.execute(
                update(MindmateSeminarSession)
                .where(MindmateSeminarSession.id == session_id)
                .values(dify_conversation_id=stored),
            )
            await db.commit()
        session = await self.load_session_by_id(session_id)
        if not session:
            return
        redis = get_async_redis()
        if not redis:
            return
        mapping = {"dify_conversation_id": stored}
        _raw, packed_server = read_seminar_dify_conversation(stored)
        if packed_server is not None:
            mapping["dify_conversation_server"] = str(packed_server)
        try:
            await redis.hset(session_meta_key(session.code), mapping=redis_hset_mapping(mapping))
        except REDIS_ERRORS:
            pass

    async def get_session_meta(self, code: str) -> Dict[str, str]:
        """Return Redis HASH session metadata for a room code."""
        redis = get_async_redis()
        if not redis:
            return {}
        try:
            raw = await redis.hgetall(session_meta_key(normalize_collab_code(code)))
        except REDIS_ERRORS:
            return {}
        if not raw:
            return {}
        out: Dict[str, str] = {}
        for key, val in raw.items():
            k = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            v = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            out[k] = v
        return out
