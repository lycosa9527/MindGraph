"""
Copy a MindMate seminar diagram preview into the viewer's library.

Collab generations use a shared Dify user, so the preview is not saved under
any participant. Each person who opens the canvas gets their own library copy.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy import select

from agents.core.prompt_to_diagram_result import coerce_prompt_to_diagram_spec
from models.domain.auth import User
from models.domain.diagrams import Diagram
from models.domain.mindmate_collab import MindmateCollabMessage, MindmateCollabSession
from services.diagram.generation_library_save import SAVE_LIMIT_REACHED, try_save_diagram_to_library
from services.diagram.generation_skip_registry import get_generation_preview_outcome
from services.features.mindmate_collab.manager_access import get_mindmate_collab_manager
from services.utils.error_types import DATABASE_ERRORS
from utils.db.session_open import system_rls_session, user_rls_session

logger = logging.getLogger(__name__)

COPY_NOT_FOUND = "not_found"
COPY_FORBIDDEN = "forbidden"
COPY_NO_SPEC = "no_spec"
COPY_LIMIT = "limit_reached"
COPY_FAILED = "save_error"

_PREVIEW_ID_RE = re.compile(r"^[a-f0-9]{8}$")


def normalize_collab_preview_id(raw: str) -> Optional[str]:
    """Return the 8-hex temp PNG id, or None when the value is not a preview id."""
    text = (raw or "").strip().lower()
    if _PREVIEW_ID_RE.fullmatch(text):
        return text
    return None


def collab_preview_conversation_id(preview_id: str) -> str:
    """Stable library marker so a second click reopens the same personal copy."""
    return f"mmcollab:{preview_id}"


def actor_may_copy_collab_diagram(
    *,
    owner_user_id: int,
    actor_user_id: int,
    session_ended: bool,
    is_live_participant: bool,
) -> bool:
    """Host can always copy. Guests can copy only while they are in the live room."""
    if actor_user_id == owner_user_id:
        return True
    if session_ended:
        return False
    return is_live_participant


async def _load_session_access(session_id: str) -> Optional[tuple[str, int, bool]]:
    """Return ``(code, owner_user_id, ended)`` for a seminar, or None."""
    sid = (session_id or "").strip()
    if not sid:
        return None
    try:
        async with system_rls_session() as db:
            row = (
                await db.execute(
                    select(
                        MindmateCollabSession.code,
                        MindmateCollabSession.owner_user_id,
                        MindmateCollabSession.ended_at,
                    ).where(MindmateCollabSession.id == sid),
                )
            ).one_or_none()
    except DATABASE_ERRORS as exc:
        logger.warning("[MindmateCollabDiagram] session lookup failed id=%s: %s", sid, exc)
        return None
    if row is None:
        return None
    code, owner_id, ended_at = row
    return str(code), int(owner_id), ended_at is not None


def _preview_like_pattern(preview_id: str) -> str:
    """LIKE pattern for a temp PNG id, with ``_`` and ``%`` escaped."""
    needle = f"/temp_images/dingtalk_{preview_id}_"
    escaped = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def _session_has_preview(session_id: str, preview_id: str) -> bool:
    """True when a persisted seminar message contains this generate_dingtalk PNG id."""
    pattern = _preview_like_pattern(preview_id)
    try:
        async with system_rls_session() as db:
            found = (
                await db.execute(
                    select(MindmateCollabMessage.id)
                    .where(
                        MindmateCollabMessage.session_id == session_id,
                        MindmateCollabMessage.content.like(pattern, escape="\\"),
                    )
                    .limit(1),
                )
            ).scalar_one_or_none()
    except DATABASE_ERRORS as exc:
        logger.warning(
            "[MindmateCollabDiagram] preview message lookup failed session=%s: %s",
            session_id,
            exc,
        )
        return False
    return found is not None


async def _find_user_copy(
    user_id: int,
    organization_id: Optional[int],
    conversation_id: str,
) -> tuple[Optional[str], bool]:
    """Return ``(diagram_id, lookup_ok)`` for this user's earlier copy of the preview."""
    try:
        async with user_rls_session(user_id, organization_id) as db:
            found = (
                await db.execute(
                    select(Diagram.id)
                    .where(
                        Diagram.user_id == user_id,
                        Diagram.conversation_id == conversation_id,
                        Diagram.is_deleted.is_(False),
                    )
                    .order_by(Diagram.updated_at.desc())
                    .limit(1),
                )
            ).scalar_one_or_none()
    except DATABASE_ERRORS as exc:
        logger.warning("[MindmateCollabDiagram] copy lookup failed user=%s: %s", user_id, exc)
        return None, False
    if isinstance(found, str) and found.strip():
        return found.strip(), True
    return None, True


def _organization_id(current_user: User) -> Optional[int]:
    org_raw = getattr(current_user, "organization_id", None)
    if isinstance(org_raw, int) and org_raw > 0:
        return org_raw
    return None


async def _insert_preview_copy(
    *,
    preview_id: str,
    user_id: int,
    organization_id: Optional[int],
    conversation_id: str,
) -> tuple[Optional[str], str]:
    """Save the preview spec as a new library diagram for this user."""
    outcome = await get_generation_preview_outcome(preview_id)
    if outcome is None:
        return None, COPY_NOT_FOUND
    spec = outcome.get("spec")
    if not isinstance(spec, dict) or not spec:
        return None, COPY_NO_SPEC
    diagram_type = str(outcome.get("diagram_type") or "mind_map").strip() or "mind_map"
    coerced = coerce_prompt_to_diagram_spec(spec, diagram_type)
    if not coerced:
        return None, COPY_NO_SPEC
    title = str(outcome.get("title") or "Diagram").strip()[:200] or "Diagram"
    language = str(outcome.get("language") or "zh").strip() or "zh"
    saved_id = await try_save_diagram_to_library(
        user_id,
        title=title,
        diagram_type=diagram_type,
        spec=coerced,
        language=language,
        organization_id=organization_id,
        log_prefix="mindmate_collab_diagram",
        source_channel="mindmate",
        conversation_id=conversation_id,
    )
    if saved_id == SAVE_LIMIT_REACHED:
        return None, COPY_LIMIT
    if not saved_id:
        return None, COPY_FAILED
    logger.info(
        "[MindmateCollabDiagram] library_copy_ok preview=%s user=%s diagram=%s",
        preview_id,
        user_id,
        saved_id,
    )
    return saved_id, ""


async def save_collab_diagram_for_user(
    session_id: str,
    preview_id: str,
    current_user: User,
) -> tuple[Optional[str], str]:
    """
    Save the seminar preview into ``current_user``'s library.

    Returns ``(diagram_id, error_code)``. ``error_code`` is empty on success.
    Repeated calls return the same diagram id.
    """
    preview = normalize_collab_preview_id(preview_id)
    if preview is None:
        return None, COPY_NOT_FOUND
    access = await _load_session_access(session_id)
    if access is None:
        return None, COPY_NOT_FOUND
    code, owner_id, ended = access
    if not await _session_has_preview(session_id, preview):
        return None, COPY_NOT_FOUND

    user_id = int(current_user.id)
    participant = False
    if not ended and owner_id != user_id:
        participant = await get_mindmate_collab_manager().is_participant(code, user_id)
    if not actor_may_copy_collab_diagram(
        owner_user_id=owner_id,
        actor_user_id=user_id,
        session_ended=ended,
        is_live_participant=participant,
    ):
        return None, COPY_FORBIDDEN

    org_id = _organization_id(current_user)
    conversation_id = collab_preview_conversation_id(preview)
    existing, lookup_ok = await _find_user_copy(user_id, org_id, conversation_id)
    if not lookup_ok:
        return None, COPY_FAILED
    if existing:
        return existing, ""
    return await _insert_preview_copy(
        preview_id=preview,
        user_id=user_id,
        organization_id=org_id,
        conversation_id=conversation_id,
    )
