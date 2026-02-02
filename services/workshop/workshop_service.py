"""
Workshop Service for Collaborative Diagram Editing
===================================================

Service for managing workshop sessions where multiple users can collaborate
on editing diagrams in real-time.

Features:
- Generate shareable workshop codes (xxx-xxx format)
- Track active workshop sessions
- Manage participant connections
- Real-time collaboration via WebSocket

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import random
import string
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from services.redis.redis_client import get_redis
from config.database import SessionLocal
from models.domain.diagrams import Diagram

logger = logging.getLogger(__name__)

# Workshop code format: xxx-xxx (3 digits - 3 digits)
WORKSHOP_CODE_PATTERN = "{}-{}"
WORKSHOP_CODE_LENGTH = 3
WORKSHOP_SESSION_TTL = 86400  # 24 hours (max session duration)
WORKSHOP_PARTICIPANTS_TTL = 3600  # 1 hour (refreshed on activity)
WORKSHOP_INACTIVITY_TIMEOUT = 1800  # 30 minutes (inactivity timeout - tracked per participant)

# Redis key patterns
WORKSHOP_SESSION_KEY = "workshop:session:{code}"
WORKSHOP_DIAGRAM_KEY = "workshop:diagram:{code}"
WORKSHOP_PARTICIPANTS_KEY = "workshop:participants:{code}"
WORKSHOP_CODE_TO_DIAGRAM_KEY = "workshop:code_to_diagram:{code}"


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
        # Redis is REQUIRED - application exits if Redis unavailable
        # No need for fallback logic
        pass

    def _get_session_key(self, code: str) -> str:
        """Get Redis key for workshop session."""
        return WORKSHOP_SESSION_KEY.format(code=code)

    def _get_diagram_key(self, code: str) -> str:
        """Get Redis key for workshop diagram mapping."""
        return WORKSHOP_DIAGRAM_KEY.format(code=code)

    def _get_participants_key(self, code: str) -> str:
        """Get Redis key for workshop participants."""
        return WORKSHOP_PARTICIPANTS_KEY.format(code=code)

    def _get_code_to_diagram_key(self, code: str) -> str:
        """Get Redis key for code to diagram ID mapping."""
        return WORKSHOP_CODE_TO_DIAGRAM_KEY.format(code=code)

    async def start_workshop(
        self, diagram_id: str, user_id: int
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Start a workshop session for a diagram.

        Args:
            diagram_id: Diagram ID
            user_id: User ID of the owner

        Returns:
            Tuple of (workshop code if successful, error message if failed)
        """
        # Verify diagram exists and user owns it
        db = SessionLocal()
        try:
            diagram = db.query(Diagram).filter(
                Diagram.id == diagram_id,
                Diagram.user_id == user_id,
                ~Diagram.is_deleted,
            ).first()

            if not diagram:
                error_msg = f"Diagram {diagram_id} not found or not owned by user {user_id}"
                logger.warning("[WorkshopService] %s", error_msg)
                return None, error_msg

            # Generate unique workshop code
            max_attempts = 10
            code = None
            redis = get_redis()
            if not redis:
                error_msg = "Redis client not available. Workshop feature requires Redis."
                logger.error("[WorkshopService] %s", error_msg)
                return None, error_msg

            for _ in range(max_attempts):
                candidate = generate_workshop_code()
                # Use synchronous Redis operations (no await)
                existing = redis.get(
                    self._get_code_to_diagram_key(candidate)
                )
                if not existing:
                    code = candidate
                    break

            if not code:
                error_msg = "Failed to generate unique workshop code after multiple attempts"
                logger.error("[WorkshopService] %s", error_msg)
                return None, error_msg

            # Update diagram with workshop code
            diagram.workshop_code = code
            db.commit()

            # Store workshop session in Redis (Redis is required)
            redis = get_redis()
            if not redis:
                error_msg = "Redis client not available. Workshop feature requires Redis."
                logger.error("[WorkshopService] %s", error_msg)
                db.rollback()
                return None, error_msg

            session_data = {
                "diagram_id": diagram_id,
                "owner_id": str(user_id),
                "created_at": datetime.utcnow().isoformat(),
            }
            # Use synchronous Redis operations (no await)
            redis.setex(
                self._get_session_key(code),
                WORKSHOP_SESSION_TTL,
                str(session_data),
            )
            redis.setex(
                self._get_code_to_diagram_key(code),
                WORKSHOP_SESSION_TTL,
                diagram_id,
            )

            logger.info(
                "[WorkshopService] Started workshop %s for diagram %s (user %s)",
                code,
                diagram_id,
                user_id,
            )
            return code, None

        except Exception as e:
            error_msg = f"Error starting workshop: {str(e)}"
            logger.error(
                "[WorkshopService] %s",
                error_msg,
                exc_info=True,
            )
            db.rollback()
            return None, error_msg
        finally:
            db.close()

    async def stop_workshop(self, diagram_id: str, user_id: int) -> bool:
        """
        Stop a workshop session.

        Args:
            diagram_id: Diagram ID
            user_id: User ID of the owner

        Returns:
            True if successful, False otherwise
        """
        db = SessionLocal()
        try:
            diagram = db.query(Diagram).filter(
                Diagram.id == diagram_id,
                Diagram.user_id == user_id,
                ~Diagram.is_deleted,
            ).first()

            if not diagram or not diagram.workshop_code:
                return False

            code = diagram.workshop_code

            # Clear workshop code from diagram
            diagram.workshop_code = None
            db.commit()

            # Remove from Redis (Redis is required)
            redis = get_redis()
            if redis:
                await redis.delete(self._get_session_key(code))
                await redis.delete(self._get_diagram_key(code))
                await redis.delete(self._get_participants_key(code))
                await redis.delete(self._get_code_to_diagram_key(code))

            logger.info(
                "[WorkshopService] Stopped workshop %s for diagram %s",
                code,
                diagram_id,
            )
            return True

        except Exception as e:
            logger.error(
                "[WorkshopService] Error stopping workshop: %s",
                e,
                exc_info=True,
            )
            db.rollback()
            return False
        finally:
            db.close()

    async def join_workshop(
        self, code: str, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Join a workshop session.

        Args:
            code: Workshop code
            user_id: User ID joining

        Returns:
            Workshop info dict with diagram_id if successful, None otherwise
        """
        db = SessionLocal()
        try:
            # Normalize code (digits only, no case conversion needed)
            code = code.strip()

            # Check Redis first (fast path)
            redis = get_redis()
            diagram_id = None
            if redis:
                # Use synchronous Redis operations (no await)
                diagram_id_raw = redis.get(
                    self._get_code_to_diagram_key(code)
                )
                if diagram_id_raw:
                    # Redis client returns strings (decode_responses=True), no need to decode
                    diagram_id = diagram_id_raw if isinstance(diagram_id_raw, str) else diagram_id_raw.decode("utf-8")

            # Fallback to database (edge case: Redis TTL expired but code still in DB)
            # This allows joining even if Redis key expired but workshop is still active
            if not diagram_id:
                diagram = db.query(Diagram).filter(
                    Diagram.workshop_code == code,
                    ~Diagram.is_deleted,
                ).first()
                if diagram:
                    diagram_id = diagram.id
                    # Restore Redis key if found in database
                    if redis:
                        # Use synchronous Redis operations (no await)
                        redis.setex(
                            self._get_code_to_diagram_key(code),
                            WORKSHOP_SESSION_TTL,
                            diagram_id,
                        )

            if not diagram_id:
                logger.warning(
                    "[WorkshopService] Invalid workshop code: %s",
                    code,
                )
                return None

            # Verify diagram exists
            diagram = db.query(Diagram).filter(
                Diagram.id == diagram_id,
                ~Diagram.is_deleted,
            ).first()

            if not diagram:
                return None

            # Add participant to Redis (Redis is required)
            redis = get_redis()
            if not redis:
                logger.error("[WorkshopService] Redis client not available")
                return None

            participant_key = self._get_participants_key(code)
            # Use synchronous Redis operations (no await)
            redis.sadd(
                participant_key,
                str(user_id),
            )
            redis.expire(
                participant_key,
                WORKSHOP_PARTICIPANTS_TTL,
            )
            # Track last activity timestamp for inactivity timeout
            activity_key = f"workshop:activity:{code}:{user_id}"
            redis.setex(
                activity_key,
                WORKSHOP_INACTIVITY_TIMEOUT,
                datetime.utcnow().isoformat(),
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
            }

        except Exception as e:
            logger.error(
                "[WorkshopService] Error joining workshop: %s",
                e,
                exc_info=True,
            )
            return None
        finally:
            db.close()

    async def get_workshop_status(
        self, diagram_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get workshop status for a diagram.

        Args:
            diagram_id: Diagram ID

        Returns:
            Workshop status dict or None
        """
        db = SessionLocal()
        try:
            diagram = db.query(Diagram).filter(
                Diagram.id == diagram_id,
                ~Diagram.is_deleted,
            ).first()

            if not diagram:
                return None

            code = diagram.workshop_code
            if not code:
                return {"active": False}

            # Get participants count from Redis (Redis is required)
            participant_count = 0
            redis = get_redis()
            if redis:
                participants = await redis.smembers(
                    self._get_participants_key(code)
                )
                participant_count = len(participants) if participants else 0

            return {
                "active": True,
                "code": code,
                "participant_count": participant_count,
            }

        except Exception as e:
            logger.error(
                "[WorkshopService] Error getting workshop status: %s",
                e,
                exc_info=True,
            )
            return None
        finally:
            db.close()

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
            # Use synchronous Redis operations (no await)
            participants = redis.smembers(
                self._get_participants_key(code)
            )
            if not participants:
                return []

            # Redis client returns strings (decode_responses=True), no need to decode
            return [int(pid) if isinstance(pid, str) else int(pid.decode("utf-8")) for pid in participants]
        except Exception as e:
            logger.error(
                "[WorkshopService] Error getting participants: %s",
                e,
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
            participant_key = self._get_participants_key(code)
            # Check if user is in the set before refreshing
            # Use synchronous Redis operations (no await)
            is_member = redis.sismember(participant_key, str(user_id))
            if is_member:
                redis.expire(participant_key, WORKSHOP_PARTICIPANTS_TTL)
                # Update activity timestamp for inactivity timeout
                activity_key = f"workshop:activity:{code}:{user_id}"
                redis.setex(
                    activity_key,
                    WORKSHOP_INACTIVITY_TIMEOUT,
                    datetime.utcnow().isoformat(),
                )
                logger.debug(
                    "[WorkshopService] Refreshed TTL for participant %s in workshop %s",
                    user_id,
                    code,
                )
        except Exception as e:
            logger.error(
                "[WorkshopService] Error refreshing participant TTL: %s",
                e,
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
            # Use synchronous Redis operations (no await)
            redis.srem(
                self._get_participants_key(code),
                str(user_id),
            )
            # Remove activity tracking key
            activity_key = f"workshop:activity:{code}:{user_id}"
            redis.delete(activity_key)
            logger.debug(
                "[WorkshopService] Removed participant %s from workshop %s",
                user_id,
                code,
            )
        except Exception as e:
            logger.error(
                "[WorkshopService] Error removing participant: %s",
                e,
                exc_info=True,
            )

    async def check_inactivity_timeout(self, code: str, user_id: int) -> bool:
        """
        Check if participant has exceeded inactivity timeout.

        Args:
            code: Workshop code
            user_id: User ID to check

        Returns:
            True if inactive (should be removed), False if active
        """
        redis = get_redis()
        if not redis:
            logger.error("[WorkshopService] Redis client not available")
            return False

        try:
            activity_key = f"workshop:activity:{code}:{user_id}"
            # Use synchronous Redis operations (no await)
            exists = redis.exists(activity_key)
            return not exists  # If key expired, user is inactive
        except Exception as e:
            logger.error(
                "[WorkshopService] Error checking inactivity timeout: %s",
                e,
                exc_info=True,
            )
            return False

    async def cleanup_expired_workshops(self) -> int:
        """
        Clean up expired workshop codes from database.

        Checks Redis for expired codes and clears them from database.
        This should be called periodically (e.g., daily).

        Returns:
            Number of workshops cleaned up
        """
        redis = get_redis()
        if not redis:
            logger.error("[WorkshopService] Redis client not available")
            return 0

        db = SessionLocal()
        cleaned_count = 0
        try:
            # Get all workshop codes from database
            diagrams_with_workshop = db.query(Diagram).filter(
                Diagram.workshop_code.isnot(None),
                ~Diagram.is_deleted,
            ).all()

            for diagram in diagrams_with_workshop:
                code = diagram.workshop_code
                # Check if code exists in Redis
                exists = await redis.exists(
                    self._get_code_to_diagram_key(code)
                )
                if not exists:
                    # Redis key expired, clear from database
                    diagram.workshop_code = None
                    cleaned_count += 1
                    logger.info(
                        "[WorkshopService] Cleaned up expired workshop %s for diagram %s",
                        code,
                        diagram.id,
                    )

            if cleaned_count > 0:
                db.commit()
                logger.info(
                    "[WorkshopService] Cleaned up %d expired workshop(s)",
                    cleaned_count,
                )

        except Exception as e:
            logger.error(
                "[WorkshopService] Error cleaning up expired workshops: %s",
                e,
                exc_info=True,
            )
            db.rollback()
        finally:
            db.close()

        return cleaned_count


# Singleton instance
workshop_service = WorkshopService()
