"""
Edit the pinned seminar brief after the room has started.

Goals and materials are optional at start. The host can fill them in later.
The pinned card is the seed message, so the same text is rewritten in place.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.mindmate_seminar import (
    MindmateSeminarMember,
    MindmateSeminarMessage,
    MindmateSeminarSession,
)
from services.features.mindmate_seminar.config import MINDMATE_COLLAB_MAX_CHAT_CONTENT_CHARS
from services.features.mindmate_seminar.redis_mirror import mirror_live_session_fields
from services.features.mindmate_seminar.seminar_roles import (
    SEMINAR_ROLE_LEADER,
    SEMINAR_ROLE_UNASSIGNED,
    normalize_seminar_role,
    resolve_seminar_leader_id,
)
from services.features.mindmate_seminar.ws_broadcast import broadcast_to_all
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_MARKER = "[[seminar-brief]]"
_GOAL_LIMIT = 12
_GOAL_LEN = 200
_RESOURCE_LIMIT = 30
_RESOURCE_LEN = 180

_LABELS_ZH = {
    "topic": "教研主题",
    "goals": "教研目标",
    "people": "参与人员",
    "files": "资源准备",
}
_LABELS_EN = {
    "topic": "Seminar topic",
    "goals": "Seminar goals",
    "people": "Participants",
    "files": "Materials",
}
_HEADER_TO_SECTION = {label: key for labels in (_LABELS_ZH, _LABELS_EN) for key, label in labels.items()}
_NUMBERED_LINE = re.compile(r"^\d+\.\s*")
_ROLE_ZH = {
    "leader": "组长",
    "leadPrep": "主备人",
    "coPrep": "辅备人",
    "expert": "专家",
    "researcher": "教研员",
    "observer": "观摩学习",
    "none": "",
}
_ROLE_EN = {
    "leader": "Lead",
    "leadPrep": "Lead planner",
    "coPrep": "Co-planner",
    "expert": "Expert",
    "researcher": "Teaching researcher",
    "observer": "Observer",
    "none": "",
}
_PENDING_ZH = "待对方同意"
_PENDING_EN = "Awaiting consent"


def normalize_brief_lines(raw: List[str], *, limit: int, max_len: int) -> Optional[List[str]]:
    """Drop blank lines. Reject a line that is too long or a list past the cap."""
    cleaned: List[str] = []
    for item in raw:
        text = " ".join(str(item).split())
        if not text:
            continue
        if len(text) > max_len or len(cleaned) >= limit:
            return None
        cleaned.append(text)
    return cleaned


@dataclass(frozen=True)
class SeminarBriefParts:
    """Lines kept when the host edits the pinned brief."""

    marked: bool
    labels: Dict[str, str]
    topic: List[str]
    goals: List[str]
    people: List[str]
    files: List[str]


def seminar_brief_sections(content: str) -> Optional[SeminarBriefParts]:
    """Split a brief seed into topic and participant lines. None when it is chat."""
    raw = (content or "").strip()
    if not raw:
        return None
    marked = raw.startswith(_MARKER)
    body = raw[len(_MARKER) :].strip() if marked else raw
    lines = body.split("\n")
    first = lines[0].strip() if lines else ""
    if first not in {_LABELS_ZH["topic"], _LABELS_EN["topic"]}:
        return None
    labels = _LABELS_EN if first == _LABELS_EN["topic"] else _LABELS_ZH
    buckets: Dict[str, List[str]] = {"topic": [], "goals": [], "people": [], "files": []}
    section: Optional[str] = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        mapped = _HEADER_TO_SECTION.get(stripped)
        if mapped:
            section = mapped
            continue
        if section:
            buckets[section].append(stripped)
    if not buckets["topic"]:
        return None
    return SeminarBriefParts(
        marked=marked,
        labels=labels,
        topic=buckets["topic"],
        goals=buckets["goals"],
        people=buckets["people"],
        files=buckets["files"],
    )


def _plain_goal_lines(lines: List[str]) -> List[str]:
    """Drop numbering so a rewrite can re-number goals."""
    cleaned: List[str] = []
    for line in lines:
        text = _NUMBERED_LINE.sub("", line).strip()
        if text:
            cleaned.append(text)
    return cleaned


def brief_visibility_lines(people: List[str]) -> List[str]:
    """Keep the school / network tag above the numbered roster."""
    return [line for line in people if not _NUMBERED_LINE.match(line)]


def format_brief_roster_line(
    index: int,
    name: str,
    role: str,
    pending: bool,
    language: str,
) -> str:
    """One numbered participant line in the brief card language."""
    labels = _ROLE_EN if language == "en" else _ROLE_ZH
    pending_label = _PENDING_EN if language == "en" else _PENDING_ZH
    cleaned_name = " ".join((name or "").split()) or f"User {index}"
    cleaned_role = normalize_seminar_role(role, default=SEMINAR_ROLE_UNASSIGNED)
    role_text = labels.get(cleaned_role, cleaned_role)
    if cleaned_role == SEMINAR_ROLE_UNASSIGNED:
        role_text = ""
    role_part = f"（{role_text}）" if role_text else ""
    pending_part = f"（{pending_label}）" if pending else ""
    return f"{index}. {cleaned_name}{role_part}{pending_part}"


def rewrite_seminar_brief_text(
    content: str,
    goals: Optional[List[str]] = None,
    resources: Optional[List[str]] = None,
    topic: Optional[str] = None,
    people: Optional[List[str]] = None,
) -> Optional[str]:
    """Replace topic, goals, or people. Materials stay unless replaced."""
    parsed = seminar_brief_sections(content)
    if parsed is None:
        return None
    topic_text = " ".join(topic.split()) if topic is not None else "\n".join(parsed.topic)
    if not topic_text:
        return None
    goal_lines = goals if goals is not None else _plain_goal_lines(parsed.goals)
    people_lines = people if people is not None else parsed.people
    parts = [f"{parsed.labels['topic']}\n{topic_text}"]
    if goal_lines:
        numbered = "\n".join(f"{index}. {goal}" for index, goal in enumerate(goal_lines, start=1))
        parts.append(f"{parsed.labels['goals']}\n{numbered}")
    if people_lines:
        parts.append(f"{parsed.labels['people']}\n" + "\n".join(people_lines))
    if resources is None:
        if parsed.files:
            parts.append(f"{parsed.labels['files']}\n" + "\n".join(parsed.files))
    elif resources:
        numbered = "\n".join(f"{index}. {name}" for index, name in enumerate(resources, start=1))
        parts.append(f"{parsed.labels['files']}\n{numbered}")
    text = "\n\n".join(parts)
    if parsed.marked:
        return f"{_MARKER}\n{text}"
    return text


async def _brief_message(db: AsyncSession, session_id: str) -> Optional[MindmateSeminarMessage]:
    """Earliest message in the room that renders as the pinned brief card."""
    result = await db.execute(
        select(MindmateSeminarMessage)
        .where(
            MindmateSeminarMessage.session_id == session_id,
            or_(
                MindmateSeminarMessage.content.like(f"{_MARKER}%"),
                MindmateSeminarMessage.content.like(f"{_LABELS_ZH['topic']}%"),
                MindmateSeminarMessage.content.like(f"{_LABELS_EN['topic']}%"),
            ),
        )
        .order_by(MindmateSeminarMessage.id.asc())
        .limit(5),
    )
    for row in result.scalars().all():
        if seminar_brief_sections(row.content) is not None:
            return row
    return None


async def update_seminar_brief(
    session_id: str,
    actor_user_id: int,
    goals_raw: List[str],
    resources_raw: Optional[List[str]],
    topic: Optional[str],
) -> Tuple[Optional[Dict[str, object]], Optional[str]]:
    """Host-only rewrite of the pinned brief. Returns payload, or an error code."""
    goals = normalize_brief_lines(goals_raw, limit=_GOAL_LIMIT, max_len=_GOAL_LEN)
    if goals is None:
        return None, "invalid"
    resources: Optional[List[str]] = None
    if resources_raw is not None:
        resources = normalize_brief_lines(resources_raw, limit=_RESOURCE_LIMIT, max_len=_RESOURCE_LEN)
        if resources is None:
            return None, "invalid"
    topic_text: Optional[str] = None
    if topic is not None:
        topic_text = " ".join(str(topic).split())
        if not topic_text or len(topic_text) > _GOAL_LEN:
            return None, "invalid"
    rewritten = ""
    message_id = 0
    code = ""
    saved_topic = ""
    saved_title = ""
    async with system_rls_session() as db:
        session = (
            await db.execute(
                select(MindmateSeminarSession).where(MindmateSeminarSession.id == session_id),
            )
        ).scalar_one_or_none()
        if session is None or session.ended_at is not None:
            return None, "not_found"
        if int(session.owner_user_id) != int(actor_user_id):
            return None, "not_found"
        message = await _brief_message(db, session_id)
        if message is None:
            return None, "not_found"
        parsed = seminar_brief_sections(message.content)
        old_topic = " ".join(parsed.topic) if parsed is not None else ""
        next_text = rewrite_seminar_brief_text(message.content, goals, resources, topic_text)
        if next_text is None:
            return None, "not_found"
        if len(next_text) > MINDMATE_COLLAB_MAX_CHAT_CONTENT_CHARS:
            return None, "too_long"
        message.content = next_text
        session.brief_goals = json.dumps(goals, ensure_ascii=False) if goals else None
        if topic_text:
            previous_brief = (session.brief_topic or "").strip()
            session.brief_topic = topic_text
            if session.title.strip() in {old_topic, previous_brief}:
                session.title = topic_text
        rewritten = next_text
        message_id = int(message.id)
        code = session.code
        saved_topic = (session.brief_topic or "").strip()
        saved_title = session.title
        await db.commit()
    await mirror_live_session_fields(code, {"title": saved_title})
    await broadcast_to_all(
        code,
        {
            "type": "brief_updated",
            "message_id": message_id,
            "content": rewritten,
            "brief_goals": goals,
            "brief_topic": saved_topic,
            "title": saved_title,
        },
    )
    logger.info("[MindmateSeminar] brief updated session=%s message=%s", session_id, message_id)
    return {
        "brief_goals": goals,
        "brief_topic": saved_topic,
        "title": saved_title,
        "message_id": message_id,
        "content": rewritten,
    }, None


async def _roster_people_lines(
    db: AsyncSession,
    session: MindmateSeminarSession,
    language: str,
    visibility: List[str],
) -> List[str]:
    """Numbered roster for the pinned brief, leader first."""
    rows = (
        await db.execute(
            select(
                MindmateSeminarMember.user_id,
                MindmateSeminarMember.seminar_role,
                MindmateSeminarMember.accepted,
                MindmateSeminarMember.joined_at,
                User.name,
            )
            .join(User, User.id == MindmateSeminarMember.user_id)
            .where(MindmateSeminarMember.session_id == session.id)
        )
    ).all()
    roles = {int(user_id): normalize_seminar_role(role) for user_id, role, _accepted, _joined, _name in rows}
    leader_id = resolve_seminar_leader_id(roles, int(session.owner_user_id))
    ordered = sorted(
        rows,
        key=lambda row: (0 if int(row[0]) == leader_id else 1, row[3] is None, row[3]),
    )
    lines = list(visibility)
    for index, (user_id, role, accepted, _joined, name) in enumerate(ordered, start=1):
        display_role = SEMINAR_ROLE_LEADER if int(user_id) == leader_id else normalize_seminar_role(role)
        display_name = str(name or "").strip() or f"User {user_id}"
        lines.append(format_brief_roster_line(index, display_name, display_role, accepted is False, language))
    return lines


async def sync_seminar_brief_people(session_id: str) -> None:
    """Rewrite the pinned brief roster after members are added, removed, or reassigned."""
    try:
        await _sync_seminar_brief_people(session_id)
    except SQLAlchemyError as exc:
        logger.warning("[MindmateSeminar] brief people sync failed session=%s err=%s", session_id, exc)


async def _sync_seminar_brief_people(session_id: str) -> None:
    rewritten = ""
    message_id = 0
    code = ""
    saved_topic = ""
    saved_title = ""
    goals: List[str] = []
    async with system_rls_session() as db:
        session = (
            await db.execute(select(MindmateSeminarSession).where(MindmateSeminarSession.id == session_id))
        ).scalar_one_or_none()
        if session is None or session.ended_at is not None:
            return
        message = await _brief_message(db, session_id)
        if message is None:
            return
        parsed = seminar_brief_sections(message.content)
        if parsed is None:
            return
        language = "en" if parsed.labels["people"] == _LABELS_EN["people"] else "zh"
        people_lines = await _roster_people_lines(db, session, language, brief_visibility_lines(parsed.people))
        next_text = rewrite_seminar_brief_text(message.content, people=people_lines)
        if next_text is None or next_text == message.content:
            return
        if len(next_text) > MINDMATE_COLLAB_MAX_CHAT_CONTENT_CHARS:
            logger.warning("[MindmateSeminar] brief people sync too long session=%s", session_id)
            return
        message.content = next_text
        rewritten = next_text
        message_id = int(message.id)
        code = session.code
        saved_topic = (session.brief_topic or "").strip()
        saved_title = session.title
        goals = _plain_goal_lines(parsed.goals)
        await db.commit()
    if not rewritten or not code:
        return
    await broadcast_to_all(
        code,
        {
            "type": "brief_updated",
            "message_id": message_id,
            "content": rewritten,
            "brief_goals": goals,
            "brief_topic": saved_topic,
            "title": saved_title,
        },
    )
    logger.info("[MindmateSeminar] brief people synced session=%s message=%s", session_id, message_id)
