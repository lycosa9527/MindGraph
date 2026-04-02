"""Workshop sessions: codes, Redis, WebSocket collab, Phase 2 live spec flush hooks."""

# Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)

import logging
import random
import string
from typing import Any, Dict, List, Optional, Tuple
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import AsyncSessionLocal
from models.domain.auth import User
from models.domain.diagrams import Diagram
from services.redis.redis_client import get_redis
from services.workshop.workshop_cleanup_impl import cleanup_expired_workshops_impl
from services.workshop.workshop_expiry import (
    DURATION_TODAY,
    compute_workshop_expires_at,
    duration_allowed_for_visibility,
    is_workshop_expired,
    redis_ttl_seconds_for_expires_at,
    remaining_seconds,
)
from services.workshop.workshop_join_helpers import restore_workshop_redis_from_db_row
from services.workshop.workshop_redis_keys import (
    code_to_diagram_key,
    mutation_idle_key,
    participants_key,
    purge_workshop_redis_keys,
    session_key,
)
from services.workshop.workshop_live_spec_ops import (
    flush_live_spec_to_db,
    maybe_flush_live_spec_when_room_empty,
)
from services.workshop.workshop_session_fields import (
    backfill_workshop_expiry_if_needed,
    clear_workshop_session_fields,
)

logger = logging.getLogger(__name__)

# Workshop code format: xxx-xxx (3 digits - 3 digits)
WORKSHOP_CODE_PATTERN = "{}-{}"
WORKSHOP_CODE_LENGTH = 3
WORKSHOP_SESSION_TTL = 86400  # legacy fallback cap when expiry unknown
WORKSHOP_PARTICIPANTS_TTL = 3600  # 1 hour (refreshed on activity)
MUTATION_IDLE_KICK_SECONDS = 1800  # 30 minutes without diagram update

WORKSHOP_VISIBILITY_ORGANIZATION = "organization"
WORKSHOP_VISIBILITY_NETWORK = "network"


async def _user_may_join_diagram_workshop(
    db: AsyncSession,
    diagram: Diagram,
    joiner_id: int,
) -> bool:
    """
    Owner always joins. Admins may join. Same-organization as diagram owner may join.
    """
    if diagram.user_id == joiner_id:
        return True
    result = await db.execute(select(User).filter(User.id == joiner_id))
    joiner = result.scalars().first()
    result = await db.execute(select(User).filter(User.id == diagram.user_id))
    owner = result.scalars().first()
    if not joiner or not owner:
        return False
    if joiner.role in ("admin", "superadmin", "manager"):
        return True
    org_joiner = joiner.organization_id
    org_owner = owner.organization_id
    if org_joiner is not None and org_owner is not None and org_joiner == org_owner:
        return True
    return False


def _diagram_workshop_visibility(diagram: Diagram) -> str:
    """Effective visibility: None/unknown defaults to organization."""
    vis = getattr(diagram, "workshop_visibility", None)
    if vis in (None, "", WORKSHOP_VISIBILITY_ORGANIZATION):
        return WORKSHOP_VISIBILITY_ORGANIZATION
    if vis == WORKSHOP_VISIBILITY_NETWORK:
        return WORKSHOP_VISIBILITY_NETWORK
    return WORKSHOP_VISIBILITY_ORGANIZATION


async def _viewer_may_see_workshop_code(
    db: AsyncSession,
    diagram: Diagram,
    viewer_id: int,
) -> bool:
    """
    Who may receive the join code via GET workshop/status.
    Owner always; organization sessions: same rules as join; network: owner only.
    """
    if diagram.user_id == viewer_id:
        return True
    vis = _diagram_workshop_visibility(diagram)
    if vis == WORKSHOP_VISIBILITY_NETWORK:
        return False
    return await _user_may_join_diagram_workshop(db, diagram, viewer_id)


def _workshop_start_validation_error(
    diagram: Optional[Diagram],
    diagram_id: str,
    user_id: int,
    visibility: str,
    duration: str,
) -> Optional[str]:
    """Return an error message if start inputs are invalid, else None."""
    if not diagram:
        error_msg = f"Diagram {diagram_id} not found or not owned by user {user_id}"
        logger.warning("[WorkshopService] %s", error_msg)
        return error_msg
    if visibility not in (
        WORKSHOP_VISIBILITY_ORGANIZATION,
        WORKSHOP_VISIBILITY_NETWORK,
    ):
        return "Invalid workshop visibility"
    if not duration_allowed_for_visibility(visibility, duration):
        return "Invalid duration for this visibility mode"
    return None


def _workshop_start_session_redis_value(
    diagram_id: str,
    user_id: int,
    started_at: datetime,
) -> str:
    """Serialized session metadata for Redis ``workshop:session``."""
    return str(
        {
            "diagram_id": diagram_id,
            "owner_id": str(user_id),
            "created_at": started_at.isoformat(),
        }
    )


def _allocate_unique_workshop_code(redis: Any) -> Optional[str]:
    """Pick a code with no existing code_to_diagram mapping, or None."""
    for _ in range(10):
        candidate = generate_workshop_code()
        if not redis.get(code_to_diagram_key(candidate)):
            return candidate
    return None


def generate_workshop_code() -> str:
    """
    Generate a workshop code in xxx-xxx format (digits only).

    Returns:
        Workshop code (e.g., "123-456")
    """
    digits = string.digits
    part1 = "".join(random.choices(digits, k=WORKSHOP_CODE_LENGTH))
    part2 = "".join(random.choices(digits, k=WORKSHOP_CODE_LENGTH))
    return WORKSHOP_CODE_PATTERN.format(part1, part2)


class WorkshopService:
    """
    Service for managing workshop sessions.
    """

    def __init__(self):
        pass

    async def _clear_expired_workshop_session(self, diagram: Diagram, db: AsyncSession, redis: Any) -> bool:
        """
        If session is expired, clear DB + Redis. Returns True if cleared.
        """
        await backfill_workshop_expiry_if_needed(diagram, db)
        if not diagram.workshop_code:
            return False
        if not diagram.workshop_expires_at:
            return False
        if not is_workshop_expired(diagram.workshop_expires_at):
            return False
        code = diagram.workshop_code
        purge_workshop_redis_keys(redis, code)
        clear_workshop_session_fields(diagram)
        await db.commit()
        logger.info(
            "[WorkshopService] Cleared expired workshop for diagram %s",
            diagram.id,
        )
        return True

    def _redis_ttl_seconds_for_diagram(self, diagram: Diagram) -> int:
        if diagram.workshop_expires_at:
            return redis_ttl_seconds_for_expires_at(diagram.workshop_expires_at)
        return WORKSHOP_SESSION_TTL

    async def _finalize_join_after_diagram_loaded(
        self,
        db: AsyncSession,
        redis: Any,
        diagram: Diagram,
        diagram_id: str,
        code: str,
        user_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Authorize join, add participant keys, return workshop info or None."""
        await backfill_workshop_expiry_if_needed(diagram, db)
        if diagram.workshop_expires_at and is_workshop_expired(diagram.workshop_expires_at):
            if redis:
                await self._clear_expired_workshop_session(diagram, db, redis)
            return None

        vis = _diagram_workshop_visibility(diagram)
        may_join = vis == WORKSHOP_VISIBILITY_NETWORK or await _user_may_join_diagram_workshop(db, diagram, user_id)
        if not may_join:
            logger.warning(
                "[WorkshopService] Join denied user=%s diagram=%s",
                user_id,
                diagram_id,
            )
            return None

        if not redis:
            logger.error("[WorkshopService] Redis client not available")
            return None

        p_key = participants_key(code)
        redis.sadd(
            p_key,
            str(user_id),
        )
        redis.expire(
            p_key,
            WORKSHOP_PARTICIPANTS_TTL,
        )
        redis.setex(
            mutation_idle_key(code, user_id),
            MUTATION_IDLE_KICK_SECONDS,
            "1",
        )

        logger.info(
            "[WorkshopService] User %s joined workshop %s (diagram %s)",
            user_id,
            code,
            diagram_id,
        )

        return {
            "code": code,
            "diagram_id": diagram_id,
            "diagram_type": diagram.diagram_type,
            "title": diagram.title,
            "owner_id": diagram.user_id,
        }

    async def start_workshop(
        self,
        diagram_id: str,
        user_id: int,
        visibility: str = WORKSHOP_VISIBILITY_ORGANIZATION,
        duration: str = DURATION_TODAY,
    ) -> Tuple[Optional[str], Optional[str], Optional[datetime]]:
        """
        Start a workshop session for a diagram.

        Args:
            diagram_id: Diagram ID
            user_id: User ID of the owner
            visibility: organization (校内) or network (共同)
            duration: 1h | today | 2d (validated per visibility)

        Returns:
            Tuple of (workshop code, error message, expires_at naive UTC or None)
        """
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    select(Diagram).filter(
                        Diagram.id == diagram_id,
                        Diagram.user_id == user_id,
                        ~Diagram.is_deleted,
                    )
                )
                diagram = result.scalars().first()

                verr = _workshop_start_validation_error(
                    diagram,
                    diagram_id,
                    user_id,
                    visibility,
                    duration,
                )
                if verr:
                    return None, verr, None

                redis = get_redis()
                if not redis:
                    error_msg = "Redis client not available. Presentation mode requires Redis."
                    logger.error("[WorkshopService] %s", error_msg)
                    return None, error_msg, None

                code = _allocate_unique_workshop_code(redis)

                if not code:
                    error_msg = "Failed to generate unique presentation code after multiple attempts"
                    logger.error("[WorkshopService] %s", error_msg)
                    return None, error_msg, None

                started_at = datetime.now(UTC)
                expires_at = compute_workshop_expires_at(started_at, duration)
                ttl_sec = redis_ttl_seconds_for_expires_at(expires_at)
                ttl_sec = min(max(ttl_sec, 1), WORKSHOP_SESSION_TTL * 14)

                diagram.workshop_code = code
                diagram.workshop_visibility = visibility
                diagram.workshop_started_at = started_at
                diagram.workshop_expires_at = expires_at
                diagram.workshop_duration_preset = duration
                await db.commit()

                redis.setex(
                    session_key(code),
                    ttl_sec,
                    _workshop_start_session_redis_value(
                        diagram_id,
                        user_id,
                        started_at,
                    ),
                )
                redis.setex(
                    code_to_diagram_key(code),
                    ttl_sec,
                    diagram_id,
                )

                logger.info(
                    "[WorkshopService] Started workshop %s for diagram %s (user %s)",
                    code,
                    diagram_id,
                    user_id,
                )
                return code, None, expires_at

            except Exception as exc:
                error_msg = f"Error starting presentation mode: {str(exc)}"
                logger.error(
                    "[WorkshopService] %s",
                    error_msg,
                    exc_info=True,
                )
                await db.rollback()
                return None, error_msg, None

    async def stop_workshop(self, diagram_id: str, user_id: int) -> bool:
        """
        Stop a workshop session.

        Args:
            diagram_id: Diagram ID
            user_id: User ID of the owner

        Returns:
            True if successful, False otherwise
        """
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    select(Diagram).filter(
                        Diagram.id == diagram_id,
                        Diagram.user_id == user_id,
                        ~Diagram.is_deleted,
                    )
                )
                diagram = result.scalars().first()

                if not diagram or not diagram.workshop_code:
                    return False

                code = diagram.workshop_code

                await flush_live_spec_to_db(code, diagram_id)

                clear_workshop_session_fields(diagram)
                await db.commit()

                redis = get_redis()
                if redis:
                    purge_workshop_redis_keys(redis, code)

                logger.info(
                    "[WorkshopService] Stopped workshop %s for diagram %s",
                    code,
                    diagram_id,
                )
                return True

            except Exception as exc:
                logger.error(
                    "[WorkshopService] Error stopping workshop: %s",
                    exc,
                    exc_info=True,
                )
                await db.rollback()
                return False

    async def join_workshop(self, code: str, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Join a workshop session.

        Args:
            code: Workshop code
            user_id: User ID joining

        Returns:
            Workshop info dict with diagram_id if successful, None otherwise
        """
        async with AsyncSessionLocal() as db:
            try:
                code = code.strip()

                redis = get_redis()
                diagram_id = None
                if redis:
                    diagram_id_raw = redis.get(code_to_diagram_key(code))
                    if diagram_id_raw:
                        diagram_id = (
                            diagram_id_raw if isinstance(diagram_id_raw, str) else diagram_id_raw.decode("utf-8")
                        )

                if not diagram_id:
                    result = await db.execute(
                        select(Diagram).filter(
                            Diagram.workshop_code == code,
                            ~Diagram.is_deleted,
                        )
                    )
                    diagram = result.scalars().first()
                    if diagram:
                        diagram_id = diagram.id
                        if redis:
                            await backfill_workshop_expiry_if_needed(diagram, db)
                            ttl = self._redis_ttl_seconds_for_diagram(diagram)
                            restore_workshop_redis_from_db_row(
                                redis,
                                code,
                                diagram_id,
                                diagram,
                                ttl,
                            )

                if not diagram_id:
                    logger.warning(
                        "[WorkshopService] Invalid workshop code: %s",
                        code,
                    )
                    return None

                result = await db.execute(
                    select(Diagram).filter(
                        Diagram.id == diagram_id,
                        ~Diagram.is_deleted,
                    )
                )
                diagram = result.scalars().first()

                if not diagram:
                    return None

                return await self._finalize_join_after_diagram_loaded(
                    db,
                    redis,
                    diagram,
                    diagram_id,
                    code,
                    user_id,
                )

            except Exception as exc:
                logger.error(
                    "[WorkshopService] Error joining workshop: %s",
                    exc,
                    exc_info=True,
                )
                return None

    def _participant_count_for_code(self, code: str) -> int:
        redis = get_redis()
        if not redis:
            return 0
        try:
            participants = redis.smembers(participants_key(code))
            return len(participants) if participants else 0
        except (TypeError, ValueError, RuntimeError):
            return 0

    async def join_workshop_by_diagram(self, diagram_id: str, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Join an organization-scoped workshop by diagram id (校内 — no typed code in UI).
        """
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Diagram).filter(
                    Diagram.id == diagram_id,
                    ~Diagram.is_deleted,
                )
            )
            diagram = result.scalars().first()
            if not diagram or not diagram.workshop_code:
                return None
            if _diagram_workshop_visibility(diagram) != WORKSHOP_VISIBILITY_ORGANIZATION:
                return None
            if not await _user_may_join_diagram_workshop(db, diagram, user_id):
                logger.warning(
                    "[WorkshopService] Org join denied user=%s diagram=%s",
                    user_id,
                    diagram_id,
                )
                return None
            code = diagram.workshop_code
        return await self.join_workshop(code, user_id)

    async def list_organization_workshop_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Active workshops visible within the same organization (校内 list).
        """
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(select(User).filter(User.id == user_id))
                viewer = result.scalars().first()
                if not viewer or viewer.organization_id is None:
                    return []

                result = await db.execute(
                    select(Diagram, User)
                    .join(User, User.id == Diagram.user_id)
                    .filter(
                        ~Diagram.is_deleted,
                        Diagram.workshop_code.isnot(None),
                        User.organization_id == viewer.organization_id,
                        or_(
                            Diagram.workshop_visibility.is_(None),
                            Diagram.workshop_visibility == WORKSHOP_VISIBILITY_ORGANIZATION,
                        ),
                        or_(
                            Diagram.workshop_expires_at.is_(None),
                            Diagram.workshop_expires_at > datetime.now(UTC),
                        ),
                    )
                )
                rows = result.all()
                out: List[Dict[str, Any]] = []
                for diagram, owner in rows:
                    code = diagram.workshop_code
                    if not code:
                        continue
                    rem = remaining_seconds(diagram.workshop_expires_at)
                    out.append(
                        {
                            "diagram_id": diagram.id,
                            "title": diagram.title,
                            "owner_username": getattr(owner, "username", None) or f"User {owner.id}",
                            "participant_count": self._participant_count_for_code(code),
                            "expires_at": (
                                diagram.workshop_expires_at.isoformat() + "Z" if diagram.workshop_expires_at else None
                            ),
                            "remaining_seconds": rem,
                        }
                    )
                return out
            except Exception as exc:
                logger.error(
                    "[WorkshopService] list_organization_workshop_sessions: %s",
                    exc,
                    exc_info=True,
                )
                return []

    async def _workshop_status_payload_for_viewer(
        self,
        db: AsyncSession,
        diagram: Diagram,
        viewer_user_id: int,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """Compute status payload; error is '' or 'not_found' or 'forbidden'."""
        await backfill_workshop_expiry_if_needed(diagram, db)
        redis = get_redis()
        if diagram.workshop_expires_at and is_workshop_expired(diagram.workshop_expires_at):
            if redis:
                await self._clear_expired_workshop_session(diagram, db, redis)
            await db.refresh(diagram)
            if diagram.user_id != viewer_user_id:
                return None, "forbidden"
            return {"active": False}, ""

        code = diagram.workshop_code
        if not code:
            if diagram.user_id != viewer_user_id:
                return None, "forbidden"
            return {"active": False}, ""

        participant_count = self._participant_count_for_code(code)
        vis = _diagram_workshop_visibility(diagram)

        if await _viewer_may_see_workshop_code(db, diagram, viewer_user_id):
            rem = remaining_seconds(diagram.workshop_expires_at)
            payload = {
                "active": True,
                "code": code,
                "participant_count": participant_count,
                "workshop_visibility": vis,
                "expires_at": (diagram.workshop_expires_at.isoformat() + "Z" if diagram.workshop_expires_at else None),
                "remaining_seconds": rem,
                "duration_preset": diagram.workshop_duration_preset,
            }
            return payload, ""
        return None, "forbidden"

    async def get_workshop_status(self, diagram_id: str, viewer_user_id: int) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Get workshop status for a diagram for a specific viewer.

        Returns:
            (payload, error) where error is '' or 'not_found' or 'forbidden'
        """
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    select(Diagram).filter(
                        Diagram.id == diagram_id,
                        ~Diagram.is_deleted,
                    )
                )
                diagram = result.scalars().first()

                if not diagram:
                    return None, "not_found"

                return await self._workshop_status_payload_for_viewer(
                    db,
                    diagram,
                    viewer_user_id,
                )

            except Exception as exc:
                logger.error(
                    "[WorkshopService] Error getting workshop status: %s",
                    exc,
                    exc_info=True,
                )
                return None, "not_found"

    async def get_participants(self, code: str) -> List[int]:
        """
        Get list of participant user IDs for a workshop.

        Args:
            code: Workshop code

        Returns:
            List of user IDs
        """
        redis = get_redis()
        if not redis:
            logger.error("[WorkshopService] Redis client not available")
            return []

        try:
            participants = redis.smembers(participants_key(code))
            if not participants:
                return []

            return [int(pid) if isinstance(pid, str) else int(pid.decode("utf-8")) for pid in participants]
        except Exception as exc:
            logger.error(
                "[WorkshopService] Error getting participants: %s",
                exc,
                exc_info=True,
            )
            return []

    async def refresh_participant_ttl(self, code: str, user_id: int) -> None:
        """
        Refresh participant TTL on activity (e.g., when sending updates).
        Also updates activity timestamp for inactivity timeout tracking.

        Args:
            code: Workshop code
            user_id: User ID
        """
        redis = get_redis()
        if not redis:
            logger.error("[WorkshopService] Redis client not available")
            return

        try:
            p_key = participants_key(code)
            is_member = redis.sismember(p_key, str(user_id))
            if is_member:
                redis.expire(p_key, WORKSHOP_PARTICIPANTS_TTL)
                logger.debug(
                    "[WorkshopService] Refreshed TTL for participant %s in workshop %s",
                    user_id,
                    code,
                )
        except Exception as exc:
            logger.error(
                "[WorkshopService] Error refreshing participant TTL: %s",
                exc,
                exc_info=True,
            )

    async def remove_participant(self, code: str, user_id: int) -> None:
        """
        Remove a participant from workshop.

        Args:
            code: Workshop code
            user_id: User ID to remove
        """
        redis = get_redis()
        if not redis:
            logger.error("[WorkshopService] Redis client not available")
            return

        try:
            redis.srem(
                participants_key(code),
                str(user_id),
            )
            redis.delete(mutation_idle_key(code, user_id))
            await maybe_flush_live_spec_when_room_empty(redis, code)
            logger.debug(
                "[WorkshopService] Removed participant %s from workshop %s",
                user_id,
                code,
            )
        except Exception as exc:
            logger.error(
                "[WorkshopService] Error removing participant: %s",
                exc,
                exc_info=True,
            )

    async def refresh_mutation_idle_for_update(self, code: str, user_id: int) -> None:
        """Reset mutation-idle TTL after a diagram ``update`` message."""
        redis = get_redis()
        if not redis:
            return
        try:
            redis.setex(
                mutation_idle_key(code, user_id),
                MUTATION_IDLE_KICK_SECONDS,
                "1",
            )
        except (TypeError, ValueError, RuntimeError):
            pass

    async def cleanup_expired_workshops(self) -> int:
        """Delegate to :func:`cleanup_expired_workshops_impl`."""
        return await cleanup_expired_workshops_impl()


workshop_service = WorkshopService()
