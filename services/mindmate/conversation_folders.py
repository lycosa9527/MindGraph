"""Persist MindMate conversation folder membership."""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.mindmate_folders import MindmateConversationFolder


async def delete_conversation_folder_assignment(
    db: AsyncSession,
    user_id: int,
    conversation_id: str,
) -> None:
    """Drop a conversation's folder membership. Caller commits."""
    await db.execute(
        delete(MindmateConversationFolder).where(
            MindmateConversationFolder.user_id == user_id,
            MindmateConversationFolder.conversation_id == conversation_id,
        )
    )
