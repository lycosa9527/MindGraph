"""
MindMate collab session manager — start, stop, join, list.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from redis.exceptions import RedisError
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from models.domain.auth import User
from models.domain.mindmate_collab import MindmateCollabMessage, MindmateCollabSession
from services.features.mindmate_collab.config import (
    MINDMATE_COLLAB_CLOSING_TTL_SEC,
    MINDMATE_COLLAB_DEFAULT_DURATION,
    MINDMATE_COLLAB_MAX_ORG_CONCURRENT_SESSIONS,
    MINDMATE_COLLAB_MAX_PARTICIPANTS,
    MINDMATE_COLLAB_PARTICIPANTS_TTL,
    MINDMATE_COLLAB_SESSION_TTL,
)
from services.features.mindmate_collab.dify_stream_control import abort_dify_stream
from services.features.mindmate_collab.message_history import (
    fetch_session_message_history,
    normalize_seed_messages,
    persist_seed_messages,
)
from services.features.mindmate_collab.participant_ops import refresh_participant_ttl_for_code
from services.features.mindmate_collab.redis_keys import (
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
from services.features.mindmate_collab.visibility import user_may_join_mindmate_collab
from services.features.mindmate_collab.ws_broadcast import broadcast_to_all
from services.online_collab.core.online_collab_code import (
    _allocate_unique_online_collab_code,
    generate_online_collab_code,
)
from services.online_collab.lifecycle.online_collab_expiry import (
    compute_online_collab_expires_at,
    duration_allowed_for_visibility,
    expires_at_to_unix,
    is_online_collab_expired,
    redis_ttl_seconds_for_expires_at,
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


class MindmateCollabManager:
    """Orchestrates MindMate shared chatroom sessions."""

    async def _count_live_org_sessions(self, org_id: int) -> int:
        """Count non-expired organization-visible rooms for one org."""
        now_naive = datetime.now(tz=UTC).replace(tzinfo=None)
        async with system_rls_session() as db:
            result = await db.execute(
                select(func.count())
                .select_from(MindmateCollabSession)
                .where(
                    MindmateCollabSession.organization_id == org_id,
                    MindmateCollabSession.visibility == ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
                    MindmateCollabSession.ended_at.is_(None),
                    or_(
                        MindmateCollabSession.expires_at.is_(None),
                        MindmateCollabSession.expires_at > now_naive,
                    ),
                ),
            )
            return int(result.scalar_one() or 0)

    async def stop_hosted_sessions_for_user(self, user_id: int) -> int:
        """Stop every live session hosted by user_id; return count stopped."""
        stopped = 0
        async with user_rls_session(user_id) as db:
            result = await db.execute(
                select(MindmateCollabSession).where(
                    MindmateCollabSession.owner_user_id == user_id,
                    MindmateCollabSession.ended_at.is_(None),
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
            await self.stop_hosted_sessions_for_user(user_id)

            async with user_rls_session(user_id) as db:
                user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
                if not user:
                    return None, "User not found"

                org_id = user.organization_id
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
                    row = MindmateCollabSession(
                        id=session_id,
                        code=candidate,
                        organization_id=org_id,
                        owner_user_id=user_id,
                        title=(title or "").strip() or "MindMate Collab",
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

            redis_ok = await self._write_redis_session(
                code=code,
                session_id=session_id,
                owner_id=user_id,
                owner_name=user.name or user.phone or user.email or str(user_id),
                org_id=org_id,
                title=(title or "").strip() or "MindMate Collab",
                visibility=visibility,
                expires_at=expires_at,
            )
            if not redis_ok:
                async with system_rls_session() as db:
                    await db.execute(
                        update(MindmateCollabSession)
                        .where(MindmateCollabSession.id == session_id)
                        .values(ended_at=datetime.now(tz=UTC)),
                    )
                    await db.commit()
                return None, "Collaboration service unavailable"
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
    ) -> bool:
        redis = get_async_redis()
        if not redis:
            return False
        norm = normalize_collab_code(code)
        now = int(time.time())
        exp_unix = expires_at_to_unix(expires_at)
        ttl = min(
            max(1, redis_ttl_seconds_for_expires_at(expires_at)),
            MINDMATE_COLLAB_SESSION_TTL * 14,
        )
        meta = {
            "session_id": session_id,
            "owner_id": str(owner_id),
            "owner_name": owner_name,
            "org_id": str(org_id) if org_id is not None else "",
            "title": title,
            "visibility": visibility,
            "expires_at": str(exp_unix),
            "last_activity": str(now),
            "started_at": str(now),
            "dify_conversation_id": "",
        }
        try:
            pipe = redis.pipeline()
            pipe.hset(session_meta_key(norm), mapping=redis_hset_mapping(meta))
            pipe.expire(session_meta_key(norm), ttl)
            pipe.set(code_to_session_key(norm), session_id, ex=ttl)
            pipe.zadd(idle_scores_key(), {norm: now})
            for reg in registry_keys_for_visibility(org_id, visibility):
                pipe.sadd(reg, norm)
            await pipe.execute()
        except REDIS_ERRORS as exc:
            logger.warning("[MindmateCollab] Redis session write failed code=%s: %s", norm, exc)
            return False
        return True

    async def load_session_by_code(self, code: str) -> Optional[MindmateCollabSession]:
        """Load an active session row by invite code."""
        norm = normalize_collab_code(code)
        async with system_rls_session() as db:
            result = await db.execute(
                select(MindmateCollabSession).where(
                    MindmateCollabSession.code == norm,
                    MindmateCollabSession.ended_at.is_(None),
                ),
            )
            return result.scalar_one_or_none()

    async def load_session_by_id(self, session_id: str) -> Optional[MindmateCollabSession]:
        """Load an active session row by session id."""
        async with system_rls_session() as db:
            result = await db.execute(
                select(MindmateCollabSession).where(
                    MindmateCollabSession.id == session_id,
                    MindmateCollabSession.ended_at.is_(None),
                ),
            )
            return result.scalar_one_or_none()

    async def load_session_by_id_any(self, session_id: str) -> Optional[MindmateCollabSession]:
        """Load a session row by id, including ended rooms (history API)."""
        async with system_rls_session() as db:
            result = await db.execute(
                select(MindmateCollabSession).where(MindmateCollabSession.id == session_id),
            )
            return result.scalar_one_or_none()

    async def session_accepts_chat(self, code: str) -> bool:
        """Return False when the room is closing or no longer live."""
        if await self.session_is_closing(code):
            return False
        return await self.load_session_by_code(code) is not None

    async def join_by_code(self, user_id: int, code: str) -> Optional[Dict[str, Any]]:
        """Validate join permissions and return session payload for an invite code."""
        session = await self.load_session_by_code(code)
        if not session:
            return None
        if session.expires_at and is_online_collab_expired(session.expires_at):
            return None
        if await self.session_is_closing(session.code):
            return None
        async with user_rls_session(user_id) as db:
            allowed = await user_may_join_mindmate_collab(
                db,
                visibility=session.visibility,
                owner_user_id=session.owner_user_id,
                owner_org_id=session.organization_id,
                joiner_id=user_id,
            )
        if not allowed and session.visibility != ONLINE_COLLAB_VISIBILITY_NETWORK:
            return None
        if not await self._register_join_participant(session.code, user_id):
            return None
        return await self._session_payload(session)

    async def join_by_session_id(self, user_id: int, session_id: str) -> Optional[Dict[str, Any]]:
        """Validate org-room join permissions and return session payload."""
        session = await self.load_session_by_id(session_id)
        if not session:
            return None
        if session.visibility != ONLINE_COLLAB_VISIBILITY_ORGANIZATION:
            return None
        if await self.session_is_closing(session.code):
            return None
        async with user_rls_session(user_id) as db:
            allowed = await user_may_join_mindmate_collab(
                db,
                visibility=session.visibility,
                owner_user_id=session.owner_user_id,
                owner_org_id=session.organization_id,
                joiner_id=user_id,
            )
        if not allowed:
            return None
        if not await self._register_join_participant(session.code, user_id):
            return None
        return await self._session_payload(session)

    async def _register_join_participant(self, code: str, user_id: int) -> bool:
        """Register joiner in Redis roster on REST join (idempotent with WS connect).

        Returns False only when Redis is available and the room is at capacity.
        When Redis is down, join is allowed and the WebSocket path surfaces the outage.
        """
        if await self.is_participant(code, user_id):
            await self.touch_activity(code)
            return True
        if await self.add_participant(code, user_id):
            return True
        if not get_async_redis():
            return True
        count = await self.participant_count(code)
        return count < MINDMATE_COLLAB_MAX_PARTICIPANTS

    async def user_may_connect(self, user_id: int, session: MindmateCollabSession) -> bool:
        """Return True when user may open a WebSocket to this room."""
        if session.expires_at and is_online_collab_expired(session.expires_at):
            return False
        if session.visibility == ONLINE_COLLAB_VISIBILITY_NETWORK:
            return True
        async with user_rls_session(user_id) as db:
            return await user_may_join_mindmate_collab(
                db,
                visibility=session.visibility,
                owner_user_id=session.owner_user_id,
                owner_org_id=session.organization_id,
                joiner_id=user_id,
            )

    async def _session_payload(self, session: MindmateCollabSession) -> Dict[str, Any]:
        count = await self.participant_count(session.code)
        return {
            "session_id": session.id,
            "code": session.code,
            "title": session.title,
            "visibility": session.visibility,
            "owner_user_id": session.owner_user_id,
            "organization_id": session.organization_id,
            "participant_count": count,
            "expires_at": session.expires_at.isoformat() + "Z" if session.expires_at else None,
        }

    async def stop_session(
        self,
        session_id: str,
        actor_user_id: int,
        *,
        reason: str = "owner",
    ) -> bool:
        """End a session, notify clients, and purge Redis keys."""
        system_reasons = frozenset({"idle", "zombie", "expired"})
        if reason in system_reasons:
            async with system_rls_session() as db:
                session = (
                    await db.execute(
                        select(MindmateCollabSession).where(MindmateCollabSession.id == session_id),
                    )
                ).scalar_one_or_none()
                if not session or session.ended_at is not None:
                    return False
                code = session.code
                org_id = session.organization_id
                visibility = session.visibility
        else:
            async with user_rls_session(actor_user_id) as db:
                session = (
                    await db.execute(
                        select(MindmateCollabSession).where(MindmateCollabSession.id == session_id),
                    )
                ).scalar_one_or_none()
                if not session or session.ended_at is not None:
                    return False
                if reason == "owner" and session.owner_user_id != actor_user_id:
                    return False
                code = session.code
                org_id = session.organization_id
                visibility = session.visibility

        await abort_dify_stream(code)
        redis = get_async_redis()
        if redis:
            await redis.set(closing_key(code), "1", ex=MINDMATE_COLLAB_CLOSING_TTL_SEC)

        async with system_rls_session() as db:
            await db.execute(
                update(MindmateCollabSession)
                .where(MindmateCollabSession.id == session_id)
                .values(ended_at=datetime.now(tz=UTC)),
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

    async def list_org_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """List live organization-visible rooms for the viewer's org."""
        async with user_rls_session(user_id) as db:
            viewer = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if not viewer or viewer.organization_id is None:
                return []
            org_id = viewer.organization_id
            result = await db.execute(
                select(MindmateCollabSession, User.name, User.phone, User.email)
                .join(User, User.id == MindmateCollabSession.owner_user_id)
                .where(
                    MindmateCollabSession.organization_id == org_id,
                    MindmateCollabSession.visibility == ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
                    MindmateCollabSession.ended_at.is_(None),
                )
                .order_by(MindmateCollabSession.started_at.desc()),
            )
            rows = result.all()

        codes = [
            session.code
            for session, _, _, _ in rows
            if not (session.expires_at and is_online_collab_expired(session.expires_at))
        ]
        counts = await self.participant_counts_for_codes(codes)

        sessions: List[Dict[str, Any]] = []
        for session, owner_name, owner_phone, owner_email in rows:
            if session.expires_at and is_online_collab_expired(session.expires_at):
                continue
            display = owner_name or owner_phone or owner_email or str(session.owner_user_id)
            sessions.append(
                {
                    "session_id": session.id,
                    "code": session.code,
                    "title": session.title,
                    "owner_name": display,
                    "owner_user_id": session.owner_user_id,
                    "participant_count": counts.get(normalize_collab_code(session.code), 0),
                    "visibility": session.visibility,
                },
            )
        return sessions

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
        """Return payload for the user's active hosted session, if any."""
        async with user_rls_session(user_id) as db:
            session = (
                await db.execute(
                    select(MindmateCollabSession).where(
                        MindmateCollabSession.owner_user_id == user_id,
                        MindmateCollabSession.ended_at.is_(None),
                    ),
                )
            ).scalar_one_or_none()
        if not session:
            return None
        return await self._session_payload(session)

    async def session_is_closing(self, code: str) -> bool:
        """True when the room is in a stop/teardown window and must reject new joins."""
        redis = get_async_redis()
        if not redis:
            return False
        norm = normalize_collab_code(code)
        try:
            raw = await redis.get(closing_key(norm))
        except REDIS_ERRORS:
            return False
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
        """Return the latest Dify conversation id for a room from Redis meta."""
        meta = await self.get_session_meta(code)
        raw = (meta.get("dify_conversation_id") or "").strip()
        if raw:
            return raw
        return fallback

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
            logger.warning("[MindmateCollab] Participant cap check failed: %s", exc)
            return False
        if result == -1:
            logger.warning(
                "[MindmateCollab] Room full code=%s max=%s",
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
        now = int(time.time())
        safety_ttl_sec = MINDMATE_COLLAB_PARTICIPANTS_TTL
        try:
            pipe = redis.pipeline(transaction=False)
            pipe.hset(session_meta_key(norm), "last_activity", str(now))
            pipe.zadd(idle_scores_key(), {norm: now})
            await pipe.execute()
            try:
                await redis.execute_command(
                    "EXPIRE",
                    session_meta_key(norm),
                    safety_ttl_sec,
                    "GT",
                )
            except RedisError as exp_exc:
                logger.debug(
                    "[MindmateCollab] touch_activity EXPIRE GT skipped code=%s: %s",
                    norm,
                    exp_exc,
                )
        except REDIS_ERRORS:
            pass

    async def fetch_message_history(self, session_id: str, limit: int | None = None) -> List[Dict[str, Any]]:
        """Return recent persisted chat messages for a session."""
        async with system_rls_session() as db:
            return await fetch_session_message_history(db, session_id, limit=limit)

    async def persist_message(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        sender_user_id: Optional[int],
    ) -> MindmateCollabMessage:
        """Insert a chat message row and return the saved record."""
        async with system_rls_session() as db:
            msg = MindmateCollabMessage(
                session_id=session_id,
                role=role,
                content=content,
                sender_user_id=sender_user_id,
                created_at=datetime.now(tz=UTC),
            )
            db.add(msg)
            await db.commit()
            await db.refresh(msg)
            return msg

    async def set_dify_conversation_id(self, session_id: str, conversation_id: str) -> None:
        """Persist Dify conversation id in PostgreSQL and Redis session meta."""
        async with system_rls_session() as db:
            await db.execute(
                update(MindmateCollabSession)
                .where(MindmateCollabSession.id == session_id)
                .values(dify_conversation_id=conversation_id),
            )
            await db.commit()
        session = await self.load_session_by_id(session_id)
        if not session:
            return
        redis = get_async_redis()
        if not redis:
            return
        try:
            await redis.hset(
                session_meta_key(session.code),
                "dify_conversation_id",
                conversation_id,
            )
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
