"""
Remove or nullify all database rows that reference a user before deleting the user row.

Call within an open AsyncSession in the same transaction as ``db.delete(user)``.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import UpdateNotificationDismissed
from models.domain.community import CommunityPost, CommunityPostComment, CommunityPostLike
from models.domain.device import Device
from models.domain.diagrams import Diagram
from models.domain.feature_access_control import FeatureAccessUserGrant
from models.domain.knowledge_space import KnowledgeSpace
from models.domain.library import (
    LibraryBookmark,
    LibraryDanmaku,
    LibraryDanmakuLike,
    LibraryDanmakuReply,
    LibraryDocument,
)
from models.domain.pinned_conversations import PinnedConversation
from models.domain.school_zone import (
    SharedDiagram,
    SharedDiagramComment,
    SharedDiagramLike,
)
from models.domain.user_activity_log import UserActivityLog
from models.domain.user_api_token import UserAPIToken
from models.domain.user_usage_stats import UserUsageStats
from models.domain.workshop_chat import ChatTopic

try:
    from models.domain.token_usage import TokenUsage
except ImportError:  # pragma: no cover
    TokenUsage = None  # type: ignore[misc, assignment]

try:
    from models.domain.mindbot_usage import MindbotUsageEvent
except ImportError:  # pragma: no cover
    MindbotUsageEvent = None  # type: ignore[misc, assignment]

logger = logging.getLogger(__name__)


async def _null_token_usage_user_id(db: AsyncSession, user_id: int) -> None:
    if TokenUsage is None:
        return
    await db.execute(update(TokenUsage).where(TokenUsage.user_id == user_id).values(user_id=None))


async def _null_mindbot_linked_user(db: AsyncSession, user_id: int) -> None:
    if MindbotUsageEvent is None:
        return
    await db.execute(
        update(MindbotUsageEvent)
        .where(MindbotUsageEvent.linked_user_id == user_id)  # type: ignore[attr-defined]
        .values(linked_user_id=None)
    )


async def _delete_community_for_user(db: AsyncSession, user_id: int) -> None:
    ap = select(CommunityPost.id).where(CommunityPost.author_id == user_id).scalar_subquery()
    await db.execute(delete(CommunityPostComment).where(CommunityPostComment.post_id.in_(ap)))
    await db.execute(delete(CommunityPostLike).where(CommunityPostLike.post_id.in_(ap)))
    await db.execute(delete(CommunityPostLike).where(CommunityPostLike.user_id == user_id))
    await db.execute(delete(CommunityPostComment).where(CommunityPostComment.user_id == user_id))
    await db.execute(delete(CommunityPost).where(CommunityPost.author_id == user_id))


async def _delete_school_zone_for_user(db: AsyncSession, user_id: int) -> None:
    dsub = select(SharedDiagram.id).where(SharedDiagram.author_id == user_id).scalar_subquery()
    await db.execute(delete(SharedDiagramComment).where(SharedDiagramComment.diagram_id.in_(dsub)))
    await db.execute(delete(SharedDiagramLike).where(SharedDiagramLike.diagram_id.in_(dsub)))
    await db.execute(delete(SharedDiagramLike).where(SharedDiagramLike.user_id == user_id))
    await db.execute(delete(SharedDiagramComment).where(SharedDiagramComment.user_id == user_id))
    await db.execute(delete(SharedDiagram).where(SharedDiagram.author_id == user_id))


async def _delete_library_for_user(db: AsyncSession, user_id: int) -> None:
    await db.execute(delete(LibraryDanmakuLike).where(LibraryDanmakuLike.user_id == user_id))
    await db.execute(delete(LibraryDanmakuReply).where(LibraryDanmakuReply.user_id == user_id))
    await db.execute(delete(LibraryDanmaku).where(LibraryDanmaku.user_id == user_id))
    await db.execute(delete(LibraryBookmark).where(LibraryBookmark.user_id == user_id))
    await db.execute(delete(LibraryDocument).where(LibraryDocument.uploader_id == user_id))


async def _delete_debate_for_user(db: AsyncSession, user_id: int) -> None:
    """Remove debate rows where user owns a session or participates as a person."""
    uid = {"uid": user_id}
    await db.execute(
        text(
            "UPDATE debate_messages SET parent_message_id = NULL "
            "WHERE session_id IN (SELECT id FROM debate_sessions WHERE user_id = :uid)"
        ),
        uid,
    )
    await db.execute(
        text("DELETE FROM debate_judgments WHERE session_id IN (SELECT id FROM debate_sessions WHERE user_id = :uid)"),
        uid,
    )
    await db.execute(
        text("DELETE FROM debate_messages WHERE session_id IN (SELECT id FROM debate_sessions WHERE user_id = :uid)"),
        uid,
    )
    await db.execute(
        text(
            "DELETE FROM debate_participants WHERE session_id IN (SELECT id FROM debate_sessions WHERE user_id = :uid)"
        ),
        uid,
    )
    await db.execute(text("DELETE FROM debate_sessions WHERE user_id = :uid"), uid)
    await db.execute(
        text(
            "DELETE FROM debate_judgments WHERE judge_participant_id IN "
            "(SELECT id FROM debate_participants WHERE user_id = :uid) "
            "OR (best_debater_id IN "
            "(SELECT id FROM debate_participants WHERE user_id = :uid))"
        ),
        uid,
    )
    await db.execute(
        text(
            "UPDATE debate_messages SET parent_message_id = NULL "
            "WHERE participant_id IN "
            "(SELECT id FROM debate_participants WHERE user_id = :uid)"
        ),
        uid,
    )
    await db.execute(
        text(
            "DELETE FROM debate_messages WHERE participant_id IN "
            "(SELECT id FROM debate_participants WHERE user_id = :uid)"
        ),
        uid,
    )
    await db.execute(text("DELETE FROM debate_participants WHERE user_id = :uid"), uid)


async def _delete_workshop_for_user(db: AsyncSession, user_id: int) -> None:
    """Clear workshop / chat rows so users.id can be deleted."""
    uid = {"uid": user_id}
    await db.execute(
        text("DELETE FROM direct_messages WHERE sender_id = :uid OR recipient_id = :uid"),
        uid,
    )
    await db.execute(text("DELETE FROM message_reactions WHERE user_id = :uid"), uid)
    await db.execute(text("DELETE FROM starred_messages WHERE user_id = :uid"), uid)
    await db.execute(text("DELETE FROM file_attachments WHERE uploader_id = :uid"), uid)
    await db.execute(text("DELETE FROM user_topic_preferences WHERE user_id = :uid"), uid)
    await db.execute(text("DELETE FROM channel_members WHERE user_id = :uid"), uid)

    for _ in range(12):
        await db.execute(
            text(
                "UPDATE chat_messages SET parent_id = NULL WHERE parent_id IN "
                "(SELECT id FROM chat_messages WHERE sender_id = :uid)"
            ),
            uid,
        )
    await db.execute(text("DELETE FROM chat_messages WHERE sender_id = :uid"), uid)
    await db.execute(delete(ChatTopic).where(ChatTopic.created_by == user_id))

    for _ in range(64):
        res = await db.execute(
            text(
                """
                DELETE FROM chat_channels c
                WHERE c.created_by = :uid
                AND NOT EXISTS (SELECT 1 FROM chat_channels ch WHERE ch.parent_id = c.id)
                """
            ),
            uid,
        )
        if getattr(res, "rowcount", 0) == 0:
            break
    else:
        logger.warning("[UserFkCleanup] channel leaf loop did not finish for user %s", user_id)
    rem = await db.execute(text("SELECT 1 FROM chat_channels WHERE created_by = :uid LIMIT 1"), uid)
    if rem.first():
        await db.execute(text("DELETE FROM chat_channels WHERE created_by = :uid"), uid)


async def delete_user_fk_dependent_rows(db: AsyncSession, user_id: int) -> None:
    """
    Delete child rows and null FKs that would block ``DELETE FROM users`` for this id.
    """
    try:
        from services.online_collab.core.purge_user_collab import (  # pylint: disable=import-outside-toplevel
            purge_user_from_active_collab,
        )

        purge_user_from_active_collab(user_id)
    except Exception:
        pass

    await _null_token_usage_user_id(db, user_id)
    await _null_mindbot_linked_user(db, user_id)

    await db.execute(update(Device).where(Device.student_id == user_id).values(student_id=None))
    await db.execute(delete(UserAPIToken).where(UserAPIToken.user_id == user_id))
    await db.execute(delete(UpdateNotificationDismissed).where(UpdateNotificationDismissed.user_id == user_id))
    await db.execute(delete(FeatureAccessUserGrant).where(FeatureAccessUserGrant.user_id == user_id))
    await db.execute(delete(PinnedConversation).where(PinnedConversation.user_id == user_id))
    await db.execute(delete(UserUsageStats).where(UserUsageStats.user_id == user_id))
    await db.execute(delete(UserActivityLog).where(UserActivityLog.user_id == user_id))
    await db.execute(delete(Diagram).where(Diagram.user_id == user_id))

    await _delete_community_for_user(db, user_id)
    await _delete_school_zone_for_user(db, user_id)
    await _delete_library_for_user(db, user_id)
    await _delete_debate_for_user(db, user_id)

    ks = (await db.execute(select(KnowledgeSpace).where(KnowledgeSpace.user_id == user_id))).scalar_one_or_none()
    if ks is not None:
        await db.delete(ks)

    await _delete_workshop_for_user(db, user_id)
