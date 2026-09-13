"""
Channel unread aggregation for 研习社.

Channel list badge = main-stream messages (``topic_id IS NULL``) above the
member waterline, plus topic messages that are still unread:

- Topic with ``UserTopicPreference``: ``created_at > last_updated``
- Topic without a preference: ``id >`` the same waterline
- Muted topics are excluded

Topic read must not advance the channel waterline; that waterline is only
for the main stream and for topics the user has never opened.
"""

from typing import Dict, List, Set

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count as sql_count

from models.domain.workshop_chat import ChannelMember, ChatMessage, UserTopicPreference


def merge_unread_parts(
    channel_ids: List[int],
    main_stream: Dict[int, int],
    pref_topics: Dict[int, int],
    no_pref_topics: Dict[int, int],
) -> Dict[int, int]:
    """Sum the three unread slices into one channel-id map."""
    merged = {cid: 0 for cid in channel_ids}
    for part in (main_stream, pref_topics, no_pref_topics):
        for cid, cnt in part.items():
            if cid in merged:
                merged[cid] += int(cnt)
    return merged


def _count_pairs(rows: List) -> List[tuple[int, int]]:
    """Normalize SQLAlchemy ``(channel_id, count)`` rows."""
    pairs: List[tuple[int, int]] = []
    for row in rows:
        pairs.append((int(row[0]), int(row[1])))
    return pairs


def _add_count_rows(target: Dict[int, int], rows: List[tuple[int, int]]) -> None:
    """Add ``(channel_id, count)`` rows into *target*."""
    for row_cid, cnt in rows:
        target[row_cid] = target.get(row_cid, 0) + cnt


def _waterline_clauses(
    mids: List[int],
    member_map: Dict[int, ChannelMember],
) -> List:
    """Per-channel ``id > waterline`` predicates."""
    return [
        and_(
            ChatMessage.channel_id == cid,
            ChatMessage.id > (member_map[cid].last_read_message_id or 0),
        )
        for cid in mids
    ]


async def batch_channel_unread_counts(
    db: AsyncSession,
    channel_ids: List[int],
    member_map: Dict[int, ChannelMember],
) -> Dict[int, int]:
    """Unread counts keyed by channel id for the member map's user."""
    if not channel_ids:
        return {}
    unread = {cid: 0 for cid in channel_ids}
    if not member_map:
        return unread

    mids = [cid for cid in member_map if cid in channel_ids]
    if not mids:
        return unread

    uid = member_map[mids[0]].user_id
    or_clauses = _waterline_clauses(mids, member_map)
    if not or_clauses:
        return unread

    main_stream: Dict[int, int] = {}
    main_stmt = (
        select(ChatMessage.channel_id, sql_count(ChatMessage.id))
        .where(
            ChatMessage.channel_id.in_(mids),
            ChatMessage.is_deleted.is_(False),
            ChatMessage.topic_id.is_(None),
            or_(*or_clauses),
        )
        .group_by(ChatMessage.channel_id)
    )
    main_result = await db.execute(main_stmt)
    _add_count_rows(main_stream, _count_pairs(list(main_result.all())))

    pref_result = await db.execute(select(UserTopicPreference).where(UserTopicPreference.user_id == uid))
    prefs = list(pref_result.scalars().all())
    muted_ids: Set[int] = {int(pref.topic_id) for pref in prefs if pref.visibility_policy == "muted"}
    pref_topic_ids: Set[int] = {int(pref.topic_id) for pref in prefs}

    pref_topics: Dict[int, int] = {}
    if pref_topic_ids:
        pref_stmt = (
            select(ChatMessage.channel_id, sql_count(ChatMessage.id))
            .join(
                UserTopicPreference,
                and_(
                    UserTopicPreference.topic_id == ChatMessage.topic_id,
                    UserTopicPreference.user_id == uid,
                ),
            )
            .where(
                ChatMessage.channel_id.in_(mids),
                ChatMessage.is_deleted.is_(False),
                ChatMessage.topic_id.is_not(None),
                ChatMessage.created_at > UserTopicPreference.last_updated,
            )
            .group_by(ChatMessage.channel_id)
        )
        if muted_ids:
            pref_stmt = pref_stmt.where(ChatMessage.topic_id.notin_(muted_ids))
        pref_unread = await db.execute(pref_stmt)
        _add_count_rows(pref_topics, _count_pairs(list(pref_unread.all())))

    no_pref_topics: Dict[int, int] = {}
    no_pref_stmt = select(ChatMessage.channel_id, sql_count(ChatMessage.id)).where(
        ChatMessage.channel_id.in_(mids),
        ChatMessage.is_deleted.is_(False),
        ChatMessage.topic_id.is_not(None),
        or_(*or_clauses),
    )
    if pref_topic_ids:
        no_pref_stmt = no_pref_stmt.where(ChatMessage.topic_id.notin_(pref_topic_ids))
    no_pref_stmt = no_pref_stmt.group_by(ChatMessage.channel_id)
    no_pref_result = await db.execute(no_pref_stmt)
    _add_count_rows(no_pref_topics, _count_pairs(list(no_pref_result.all())))

    return merge_unread_parts(channel_ids, main_stream, pref_topics, no_pref_topics)
